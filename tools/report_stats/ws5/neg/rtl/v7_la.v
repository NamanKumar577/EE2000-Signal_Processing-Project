// FECG v7-DL - look-ahead unit: chooses the final beats with a fixed delay (about 13.5 s,
// at most 17.5 s) on the FPGA.  Bit-exact with model/v7_post.c (-DV7; WP=6, WF=3, M=375,
// LV=0, one clean-up pass, deadline 3750).
//
// It only listens to the other units: every uplink word they write is tapped (BEAT -> beat
// rings, FEAT -> normalised beat shape summed per 2.5-s slot, MPK -> maternal ring, COV ->
// covariance), RSP_V / RSP_MK come from the link.  When the sequencer starts it (T == want
// time, or FLUSH) it scores the 16 tracks over [-15 s, +10 s] around the segment, runs one
// Viterbi step, takes the chosen track's beats, cleans them up and sends OUT7 frames.
//   OUT7 0x8D: u32 t, u16 fhr_x10, u8 src      END7 0x8E: u32 number of OUT7 (after FLUSH)
// Area: everything is sequential (one shared log2 / divider / shifter per use, single-port
// small memories); the unit runs only once per 625 samples, so cycles are cheap.
`timescale 1ns / 1ps

module v7_la (
    input  wire         clk,
    input  wire         clear,
    // taps
    input  wire         t_ms,          // a unit starts an uplink message (cmd t_mc)
    input  wire [7:0]   t_mc,
    input  wire         t_wv,          // payload word accepted by the link
    input  wire [63:0]  t_wd,
    input  wire         v_seen,        // RSP_V received
    input  wire [255:0] v_q,
    input  wire [1:0]   mk,            // latest RSP_MK
    output wire         busy,          // shape engine busy: the core holds new messages back
    // sequencer
    input  wire         start,
    input  wire         fl,            // 1 = FLUSH run
    input  wire [31:0]  T,
    output wire         want,          // a segment is due at this sample
    output reg          done,
    // uplink writer
    output reg          msg_start,
    output reg  [7:0]   msg_cmd,
    output reg  [15:0]  msg_len,
    input  wire         msg_idle,
    output reg          w_valid,
    output reg  [63:0]  w_data,
    output reg  [3:0]   w_nb,
    input  wire         w_ready
);
    localparam signed [31:0] FLOOR = -2551;      // 256*log2(1e-3)
    localparam signed [31:0] LGW = 3226;         // lg2q8(10*625)
    localparam signed [31:0] DL = 3750;
    localparam signed [31:0] BIG = 32'sh7FFFFFFF, SMALL = -32'sh7FFFFFFF - 1;

    // ------------------------------------------------------------------ small tables
    function [7:0] lgt(input [5:0] f);           // 256*log2(1 + f/64)
        case (f)
        0: lgt = 0;     1: lgt = 6;     2: lgt = 11;    3: lgt = 17;    4: lgt = 22;    5: lgt = 28;    6: lgt = 33;    7: lgt = 38;
        8: lgt = 44;    9: lgt = 49;    10: lgt = 54;   11: lgt = 59;   12: lgt = 63;   13: lgt = 68;   14: lgt = 73;   15: lgt = 78;
        16: lgt = 82;   17: lgt = 87;   18: lgt = 92;   19: lgt = 96;   20: lgt = 100;  21: lgt = 105;  22: lgt = 109;  23: lgt = 113;
        24: lgt = 118;  25: lgt = 122;  26: lgt = 126;  27: lgt = 130;  28: lgt = 134;  29: lgt = 138;  30: lgt = 142;  31: lgt = 146;
        32: lgt = 150;  33: lgt = 154;  34: lgt = 157;  35: lgt = 161;  36: lgt = 165;  37: lgt = 169;  38: lgt = 172;  39: lgt = 176;
        40: lgt = 179;  41: lgt = 183;  42: lgt = 186;  43: lgt = 190;  44: lgt = 193;  45: lgt = 197;  46: lgt = 200;  47: lgt = 203;
        48: lgt = 207;  49: lgt = 210;  50: lgt = 213;  51: lgt = 216;  52: lgt = 220;  53: lgt = 223;  54: lgt = 226;  55: lgt = 229;
        56: lgt = 232;  57: lgt = 235;  58: lgt = 238;  59: lgt = 241;  60: lgt = 244;  61: lgt = 247;  62: lgt = 250;  default: lgt = 253;
        endcase
    endfunction

    function signed [11:0] prior(input [8:0] R);  // 256*log2(max(0.2, (15000/R - 80)/40)), R <= 187
        case (R)
        126: prior = -9;   127: prior = -18;  128: prior = -27;  129: prior = -36;  130: prior = -45;  131: prior = -55;
        132: prior = -64;  133: prior = -73;  134: prior = -83;  135: prior = -93;  136: prior = -103; 137: prior = -113;
        138: prior = -123; 139: prior = -133; 140: prior = -143; 141: prior = -154; 142: prior = -164; 143: prior = -175;
        144: prior = -186; 145: prior = -197; 146: prior = -209; 147: prior = -220; 148: prior = -232; 149: prior = -244;
        150: prior = -256; 151: prior = -268; 152: prior = -281; 153: prior = -294; 154: prior = -307; 155: prior = -321;
        156: prior = -335; 157: prior = -349; 158: prior = -364; 159: prior = -379; 160: prior = -394; 161: prior = -410;
        162: prior = -427; 163: prior = -444; 164: prior = -462; 165: prior = -480; 166: prior = -499; 167: prior = -519;
        168: prior = -539; 169: prior = -561; 170: prior = -584;
        default: prior = (R <= 125) ? 12'sd0 : -12'sd594;
        endcase
    endfunction

    function [3:0] cix(input [1:0] a, input [1:0] b);   // upper-triangle index of C[a][b]
        reg [1:0] lo, hi;
        begin
            lo = (a < b) ? a : b; hi = (a < b) ? b : a;
            case ({lo, hi})
            4'b0000: cix = 0; 4'b0001: cix = 1; 4'b0010: cix = 2; 4'b0011: cix = 3;
            4'b0101: cix = 4; 4'b0110: cix = 5; 4'b0111: cix = 6;
            4'b1010: cix = 7; 4'b1011: cix = 8; default: cix = 9;
            endcase
        end
    endfunction

    // ------------------------------------------------------------------ block memories
    (* ram_style = "block" *) reg [31:0] bqm [0:4095];     // beat rings: {track, index}
    reg [11:0] bq_wa, bq_ra; reg [31:0] bq_wd, bq_rd; reg bq_we;
    always @(posedge clk) begin if (bq_we) bqm[bq_wa] <= bq_wd; bq_rd <= bqm[bq_ra]; end

    (* ram_style = "block" *) reg [33:0] mpm [0:255];      // maternal peaks {train, p}
    reg [7:0] mp_wa, mp_ra; reg [33:0] mp_wd, mp_rd; reg mp_we;
    always @(posedge clk) begin if (mp_we) mpm[mp_wa] <= mp_wd; mp_rd <= mpm[mp_ra]; end

    (* ram_style = "block" *) reg [17:0] ssm [0:8191];     // shape sums {track, slot, entry}
    reg [12:0] ss_wa, h_ssra, e_ssra; reg [17:0] ss_wd, ss_rd; reg ss_we;
    wire [12:0] ss_ra = busy ? h_ssra : e_ssra;
    always @(posedge clk) begin if (ss_we) ssm[ss_wa] <= ss_wd; ss_rd <= ssm[ss_ra]; end

    // slot tags {valid, segment number} and counts (distributed RAM, written by the shape engine)
    reg [23:0] tgm [0:255];
    reg [7:0]  tcm [0:255];

    // ------------------------------------------------------------------ taps
    reg [7:0]  tcmd;
    reg [5:0]  twi;
    reg [23:0] bn [0:15];
    reg [23:0] mn;
    reg [63:0] cov [0:9];
    reg        have_cov;
    reg [31:0] snap [0:30];
    reg [3:0]  fk;
    reg [31:0] fq, fmx;
    reg        sh_go;
    wire [31:0] tabs = t_wd[31] ? (~t_wd[31:0] + 32'd1) : t_wd[31:0];
    integer ii;
    always @(posedge clk) begin
        bq_we <= 1'b0; mp_we <= 1'b0; sh_go <= 1'b0;
        if (clear) begin
            for (ii = 0; ii < 16; ii = ii + 1) bn[ii] <= 0;
            mn <= 0; have_cov <= 1'b0; tcmd <= 0; twi <= 0;
        end else if (t_ms) begin tcmd <= t_mc; twi <= 0; end
        else if (t_wv) begin
            twi <= twi + 1'b1;
            case (tcmd)
            8'h87: begin                                               // BEAT k, q
                bq_wa <= {t_wd[3:0], bn[t_wd[3:0]][7:0]}; bq_wd <= t_wd[39:8]; bq_we <= 1'b1;
                bn[t_wd[3:0]] <= bn[t_wd[3:0]] + 1'b1;
            end
            8'h88: begin                                               // FEAT k, q, 31 x s32, pem
                if (twi == 0) begin fk <= t_wd[3:0]; fq <= t_wd[39:8]; fmx <= 0; end
                else if (twi <= 31) begin snap[twi - 1] <= t_wd[31:0]; if (tabs > fmx) fmx <= tabs; end
                else sh_go <= 1'b1;
            end
            8'h83: begin mp_wa <= mn[7:0]; mp_wd <= {mk, t_wd[31:0]}; mp_we <= 1'b1; mn <= mn + 1'b1; end   // MPK
            8'h80: begin if (twi < 10) cov[twi] <= t_wd; if (twi == 9) have_cov <= 1'b1; end           // COV
            default: ;
            endcase
        end
    end

    // ------------------------------------------------------------------ shape engine (one FEAT)
    // s >>= sh (max |s| < 2^15); d = 31 s - sum; nr = isqrt(sum d^2); slot += (|d| << 10) / nr
    reg [3:0]  h;
    reg [4:0]  hi;
    reg [7:0]  hc;
    reg signed [31:0] hx;
    reg [31:0] mxs;
    reg [4:0]  hsh, hcnt;
    reg signed [31:0] sbf [0:30];
    reg signed [21:0] dbf [0:30];
    reg signed [31:0] hsum;
    reg [47:0] hE, qrem, qroot, qbit;
    reg [23:0] nr;
    reg [31:0] grem, gdv;
    reg [22:0] gq;
    reg [4:0]  gb;
    reg        fresh;
    reg [7:0]  hslot;
    reg [35:0] er, edv;
    reg [10:0] ev;
    reg [3:0]  eb;
    wire signed [21:0] d_now = 31 * sbf[hi] - hsum;
    wire signed [43:0] d_sq = d_now * d_now;
    wire signed [21:0] dcur = dbf[hi];
    wire [21:0] dabs = dcur[21] ? -dcur : dcur;
    wire [23:0] tg_h = tgm[hslot];
    assign busy = sh_go | (h != 0);
    always @(posedge clk) begin
        ss_we <= 1'b0;
        if (clear) begin h <= 13; hc <= 0; end
        else case (h)
        0: if (sh_go) begin mxs <= fmx; hsh <= 0; h <= 1; end
        1: if (mxs >= 32'd32768) begin mxs <= mxs >> 1; hsh <= hsh + 1'b1; end      // C: while ((mx >> sh) >= 32768) sh++
           else begin hi <= 0; hsum <= 0; hx <= snap[0]; hcnt <= hsh; h <= 2; end
        2: if (hcnt != 0) begin hx <= hx >>> 1; hcnt <= hcnt - 1'b1; end             // s >>= sh, one bit per cycle
           else begin
               sbf[hi] <= hx; hsum <= hsum + hx;
               if (hi == 30) begin hi <= 0; hE <= 0; h <= 3; end
               else begin hi <= hi + 1'b1; hx <= snap[hi + 1'b1]; hcnt <= hsh; end
           end
        3: begin
            dbf[hi] <= d_now; hE <= hE + d_sq[42:0];
            if (hi == 30) h <= 4; else hi <= hi + 1'b1;
        end
        4: begin qrem <= hE; qroot <= 0; qbit <= 48'd1 << 46; h <= 5; end
        5: if (qbit != 0) begin
               if (qrem >= qroot + qbit) begin qrem <= qrem - (qroot + qbit); qroot <= (qroot >> 1) + qbit; end
               else qroot <= qroot >> 1;
               qbit <= qbit >> 2;
           end else begin nr <= qroot[23:0]; grem <= fq; gdv <= 32'd625 << 22; gq <= 0; gb <= 22; h <= 6; end
        6: begin                                                       // g = q / 625
            if (grem >= gdv) begin grem <= grem - gdv; gq[gb] <= 1'b1; end
            gdv <= gdv >> 1;
            if (gb == 0) h <= 7; else gb <= gb - 1'b1;
        end
        7: begin hslot <= {fk, gq[3:0]}; h <= 8; end
        8: begin
            fresh <= !tg_h[23] || tg_h[22:0] != gq;
            tgm[hslot] <= {1'b1, gq};
            tcm[hslot] <= (!tg_h[23] || tg_h[22:0] != gq) ? 8'd1 : tcm[hslot] + 1'b1;
            hi <= 0; h <= 9;
        end
        9: begin h_ssra <= {hslot, hi}; er <= {4'd0, dabs, 10'd0}; edv <= {2'd0, nr, 10'd0}; ev <= 0; eb <= 10; h <= 10; end
        10: begin                                                      // 11-bit quotient (|d| <= nr)
            if (nr != 0 && er >= edv) begin er <= er - edv; ev[eb] <= 1'b1; end
            edv <= edv >> 1;
            if (eb == 0) h <= 11; else eb <= eb - 1'b1;
        end
        11: begin
            ss_wa <= {hslot, hi};
            ss_wd <= (fresh ? 18'sd0 : $signed(ss_rd)) + (dcur[21] ? -$signed({7'd0, ev}) : $signed({7'd0, ev}));
            ss_we <= 1'b1;
            if (hi == 30) h <= 0; else begin hi <= hi + 1'b1; h <= 9; end
        end
        13: begin tgm[hc] <= 24'd0; hc <= hc + 1'b1; if (hc == 8'd255) h <= 0; end   // clear: all slots invalid
        default: h <= 0;
        endcase
    end

    // ------------------------------------------------------------------ engine state
    reg [8:0]  s, ret, sret, rret;
    reg        flm, fin, vinit, gate_ok;
    reg [3:0]  gate;
    reg [31:0] Tn, segT, nextT, decT, jT, iseg, decn, jseg, lastseg;
    reg signed [17:0] Vt [0:15], nv [0:15];
    reg signed [15:0] LQ [0:15];
    reg [63:0] bpm [0:15];
    reg [63:0] bprow;
    reg [3:0]  pathm [0:15];
    reg        dzm [0:255];
    reg [3:0]  k, x, y, best, bk, j4, tk;
    reg signed [17:0] bv18, mx;
    assign want = (T == nextT);

    // one read port into the beat counters
    reg [3:0]  bix;
    wire [23:0] bnr = bn[bix];
    reg [23:0] bnv;
    wire [8:0] bnm = (bnv > 24'd256) ? 9'd256 : bnv[8:0];

    // gather: beats of track gk in [glo, ghi) -> qbuf (descending), rbuf = differences
    reg [3:0]  gk;
    reg signed [31:0] glo, ghi, gprev;
    reg [8:0]  gj, gm, gn;
    reg [31:0] qbuf [0:255];
    reg [31:0] rbuf [0:255];
    // lower median of rbuf[0 .. mc-1]
    reg [8:0]  mc, ma, mb, mlt, mle, mwant;
    reg signed [31:0] mva, mres;
    // near: number of qbuf[0 .. na-1] with a B entry (track nk ring, or gated maternal ring) within ntol
    reg        nsel, bskip;
    reg [3:0]  nk;
    reg signed [31:0] nlo, nhi, bv;
    reg [4:0]  ntol;
    reg [8:0]  na, ai, bj, mB, nh;
    reg  [7:0] qa;                                                    // single read port of qbuf
    wire signed [31:0] qai = qbuf[qa];
    wire signed [31:0] ntols = {27'd0, ntol};
    wire signed [31:0] qhi = qai + ntols, qlo = qai - ntols;
    // quality
    reg signed [31:0] w0, w1, L, la, lr, acc;
    reg [8:0]  n, ok, R, jj, nm;
    reg [11:0] ns;
    reg [47:0] E;
    reg [4:0]  dd;
    reg [3:0]  gg;
    reg [4:0]  act;
    reg [12:0] shh;
    wire signed [63:0] acc_sq = acc * acc;
    reg  [7:0] rba;                                                   // single read port of rbuf
    wire signed [31:0] rbr = rbuf[rba];
    wire signed [31:0] Rs = {23'd0, R};
    wire signed [31:0] rdev = (rbr < Rs) ? Rs - rbr : rbr - Rs;
    // log2 (sequential): lgx -> lgy = 256*log2(lgx), lgx >= 1
    reg [47:0] lgx;
    reg [5:0]  lge;
    reg [13:0] lgy;
    wire signed [31:0] lgs = {18'd0, lgy};
    wire [31:0] sgi = iseg - 32'd6 + gg;                               // slot segment number
    wire [7:0]  sgs = {k, sgi[3:0]};
    wire [23:0] tg_e = tgm[sgs];
    wire        sg_ok = tg_e[23] && tg_e[22:0] == sgi[22:0];
    // gates
    reg [3:0]  gi;
    reg [5:0]  gsh, gcnt;
    reg signed [63:0] gx, gtr, lam;
    reg signed [24:0] covs [0:9];
    reg signed [31:0] vv;
    reg signed [24:0] cc;
    reg [3:0]  ab;
    wire signed [15:0] Va = v_q[16 * (4 * k[1:0] + ab[3:2]) +: 16];
    wire signed [15:0] Vb = v_q[16 * (4 * k[1:0] + ab[1:0]) +: 16];
    // pool
    reg [4:0]  pk;
    reg signed [31:0] pe, pR, pbest;
    wire signed [31:0] pq = bq_rd;
    wire signed [31:0] pd = (pq > pe) ? pq - pe : pe - pq;
    wire signed [31:0] pbd = (pbest > pe) ? pbest - pe : pe - pbest;
    // stages (single read port each)
    reg [31:0] s0b [0:63]; reg [4:0] s0s [0:63];
    reg [31:0] s1b [0:63]; reg [4:0] s1s [0:63];
    reg [5:0]  s0ra, s1ra;
    wire signed [31:0] s0rd = s0b[s0ra], s1rd = s1b[s1ra];
    wire [4:0] s0rs = s0s[s0ra], s1rs = s1s[s1ra];
    reg [23:0] s0n, s0i, s1n, s1i, lo, hi2, jx;
    reg        s0st;
    reg signed [31:0] s0last, R0, gap, bi, bi1, bprev, pv;
    reg [4:0]  srci;
    reg [8:0]  rc;
    reg [8:0]  x9;
    wire signed [31:0] dA = bi1 - s0last - R0, dB = bi1 - bi - R0;
    wire signed [31:0] gadj = gap + $signed({31'd0, gap[31]});
    wire signed [31:0] gfill = s0last + (gadj >>> 1);                 // C: last + gap / 2
    // division (FHR)
    reg [17:0] drem, dvd;
    reg [19:0] ddv;
    reg [11:0] dq;
    reg [3:0]  dbit;
    // output
    reg [31:0] ot, nout;
    reg [15:0] of10;
    reg [4:0]  osrc;

    always @(posedge clk) begin
        done <= 1'b0; msg_start <= 1'b0;
        if (w_valid && w_ready) w_valid <= 1'b0;
        if (clear) begin
            s <= 0; vinit <= 1'b0; gate_ok <= 1'b0; gate <= 0; w_valid <= 1'b0;
            iseg <= 7; segT <= 4375; nextT <= 7250; decn <= 7; decT <= 4375;
            s0n <= 0; s0i <= 0; s0st <= 1'b0; s1n <= 0; s1i <= 0; nout <= 0;
        end else case (s)
        // ---------------------------------------------------------- top
        0: if (start) begin flm <= fl; if (!fl) Tn <= T; s <= 1; end
        1: if (!busy) s <= (!gate_ok && have_cov && v_seen) ? 9'd200 : 9'd2;
        2: if (flm) begin
               if ($signed(segT) < $signed(T)) begin sret <= 4; s <= 100; end
               else s <= 150;
           end else begin sret <= 3; s <= 100; end
        3: begin bk <= 0; k <= 1; s <= 5; end                           // decide: argmax V
        4: begin iseg <= iseg + 1; segT <= segT + 625; s <= 2; end      // flush: next segment
        5: begin
            if (Vt[k] > Vt[bk]) bk <= k;
            if (k == 15) s <= 6; else k <= k + 1;
        end
        6: begin tk <= bk; jT <= segT; ret <= 7; s <= 120; end           // take(iseg, argmax)
        7: begin decn <= iseg + 1; decT <= segT + 625; fin <= 1'b0; rret <= 8; s <= 130; end
        8: begin iseg <= iseg + 1; segT <= segT + 625; nextT <= nextT + 625; done <= 1'b1; s <= 0; end

        // ---------------------------------------------------------- gather
        20: begin bix <= gk; s <= 24; end
        24: begin bnv <= bnr; s <= 25; end
        25: begin gj <= 0; gn <= 0; gm <= bnm; s <= 21; end
        21: if (gj == gm) s <= ret; else begin bq_ra <= {gk, bnv[7:0] - 8'd1 - gj[7:0]}; s <= 22; end
        22: s <= 23;
        23: if ($signed(bq_rd) < glo) s <= ret;
            else begin
                if ($signed(bq_rd) < ghi) begin
                    qbuf[gn[7:0]] <= bq_rd;
                    if (gn != 0) rbuf[gn[7:0] - 8'd1] <= gprev - bq_rd;
                    gprev <= bq_rd; gn <= gn + 1;
                end
                gj <= gj + 1; s <= 21;
            end
        // ---------------------------------------------------------- lower median of rbuf[0..mc-1]
        30: begin mwant <= (mc - 1) >> 1; ma <= 0; rba <= 0; s <= 31; end
        31: begin mva <= rbr; mb <= 0; mlt <= 0; mle <= 0; rba <= 0; s <= 32; end
        32: begin
            if (rbr < mva) mlt <= mlt + 1;
            if (rbr <= mva) mle <= mle + 1;
            if (mb + 1 == mc) s <= 33;
            mb <= mb + 1; rba <= mb[7:0] + 8'd1;
        end
        33: if (mlt <= mwant && mwant < mle) begin mres <= mva; s <= ret; end
            else begin ma <= ma + 1; rba <= ma[7:0] + 8'd1; s <= 31; end
        // ---------------------------------------------------------- near
        40: begin bix <= nk; s <= 46; end
        46: begin bnv <= bnr; s <= 47; end
        47: begin
            ai <= 0; qa <= 0; bj <= 0; nh <= 0;
            mB <= nsel ? ((mn > 24'd256) ? 9'd256 : mn[8:0]) : bnm;
            s <= 41;
        end
        41: if (ai == na || bj == mB) s <= ret;
            else begin
                if (nsel) mp_ra <= mn[7:0] - 8'd1 - bj[7:0];
                else bq_ra <= {nk, bnv[7:0] - 8'd1 - bj[7:0]};
                s <= 42;
            end
        42: s <= 43;
        43: begin bv <= nsel ? $signed(mp_rd[31:0]) : $signed(bq_rd); bskip <= nsel && !gate[mp_rd[33:32]]; s <= 44; end
        44: if (bskip || bv >= nhi || bv > qhi) begin bj <= bj + 1; s <= 41; end
            else if (bv < nlo) s <= ret;
            else begin if (bv >= qlo) nh <= nh + 1; ai <= ai + 1; qa <= ai[7:0] + 8'd1; s <= 45; end
        45: if (ai == na) s <= ret; else s <= 44;
        // ---------------------------------------------------------- nearest beat of any track within R/5 of pe
        50: begin pk <= 0; pbest <= -1; s <= 51; end
        51: if (pk == 16) s <= ret; else begin bix <= pk[3:0]; s <= 55; end
        55: begin bnv <= bnr; s <= 56; end
        56: begin gj <= 0; gm <= bnm; s <= 52; end
        52: if (gj == gm) begin pk <= pk + 1; s <= 51; end
            else begin bq_ra <= {pk[3:0], bnv[7:0] - 8'd1 - gj[7:0]}; s <= 53; end
        53: s <= 54;
        54: if (pq < pe - pR) begin pk <= pk + 1; s <= 51; end
            else begin
                if (pq < pe + pR + 1 && 5 * pd <= pR && (pbest < 0 || pd < pbd || (pd == pbd && pq < pbest))) pbest <= pq;
                gj <= gj + 1; s <= 52;
            end
        // ---------------------------------------------------------- dq = dvd / dvs (12-bit quotient)
        60: begin drem <= dvd; ddv <= {pv[8:0], 11'd0}; dq <= 0; dbit <= 11; s <= 61; end
        61: begin
            if ({2'd0, drem} >= ddv) begin drem <= drem - ddv[17:0]; dq[dbit] <= 1'b1; end
            ddv <= ddv >> 1;
            if (dbit == 0) s <= ret; else dbit <= dbit - 1'b1;
        end
        // ---------------------------------------------------------- lgy = lg2q8(lgx): normalise, then table
        80: begin lge <= 47; s <= 81; end
        81: if (lgx[47]) begin lgy <= {lge, 8'd0} + lgt(lgx[46:41]); s <= ret; end
            else begin lgx <= lgx << 1; lge <= lge - 1'b1; end
        // ---------------------------------------------------------- OUT7 / END7
        70: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h8D; msg_len <= 7; s <= 71; end
        71: if (!w_valid && w_ready) begin w_valid <= 1'b1; w_data <= {8'd0, 3'd0, osrc, of10, ot}; w_nb <= 7; s <= 72; end
        72: if (!w_valid) begin nout <= nout + 1; s <= ret; end
        75: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h8E; msg_len <= 4; s <= 76; end
        76: if (!w_valid && w_ready) begin w_valid <= 1'b1; w_data <= {32'd0, nout}; w_nb <= 4; s <= 77; end
        77: if (!w_valid) begin done <= 1'b1; s <= 0; end

        // ---------------------------------------------------------- seg_step(iseg)
        100: begin k <= 0; s <= 160; end
        102: begin
            LQ[k] <= L[15:0];
            if (k == 15) begin x <= 0; s <= 104; end else begin k <= k + 1; s <= 160; end
        end
        // switching matrix: dzm[x][y] = 1 when > 80% of x's segment beats have a y beat within 8
        104: begin gk <= x; glo <= segT; ghi <= segT + 625; ret <= 105; s <= 20; end
        105: begin na <= gn; y <= 0; s <= 106; end
        106: if (y == x) s <= 108;
             else begin nsel <= 1'b0; nk <= y; nlo <= segT; nhi <= segT + 625; ntol <= 8; ret <= 107; s <= 40; end
        107: begin dzm[{x, y}] <= (5 * nh > 4 * na); s <= 108; end
        108: if (y == 15) s <= 109; else begin y <= y + 1; s <= 106; end
        109: if (x == 15) begin y <= 0; s <= 110; end else begin x <= x + 1; s <= 104; end
        // Viterbi step
        110: if (!vinit) begin                                         // first segment: V = LQ
                 Vt[y] <= LQ[y];
                 if (y == 15) begin bpm[iseg[3:0]] <= 64'hFEDCBA9876543210; vinit <= 1'b1; s <= sret; end
                 else y <= y + 1;
             end else begin y <= 0; s <= 111; end
        111: begin x <= 0; s <= 112; end
        112: begin
            if (x == 0 || Vt[x] - ((x == y || dzm[{x, y}]) ? 18'sd0 : 18'sd369) > bv18) begin
                bv18 <= Vt[x] - ((x == y || dzm[{x, y}]) ? 18'sd0 : 18'sd369); best <= x;
            end
            if (x == 15) s <= 113; else x <= x + 1;
        end
        113: begin
            nv[y] <= bv18 + LQ[y]; bprow[4 * y +: 4] <= best;
            if (y == 0 || bv18 + LQ[y] > mx) mx <= bv18 + LQ[y];
            if (y == 15) begin y <= 0; s <= 114; end else begin y <= y + 1; s <= 111; end
        end
        114: begin
            Vt[y] <= nv[y] - mx;
            if (y == 15) begin bpm[iseg[3:0]] <= bprow; s <= sret; end else y <= y + 1;
        end

        // ---------------------------------------------------------- take(jT/625, tk) -> stage 0
        120: begin gk <= tk; glo <= jT; ghi <= jT + 625; sret <= ret; ret <= 121; s <= 20; end
        121: begin x9 <= gn; qa <= gn[7:0] - 8'd1; s <= 122; end
        122: if (x9 == 0) s <= sret;
             else begin s0b[s0n[5:0]] <= qai; s0s[s0n[5:0]] <= {1'b0, tk}; s0n <= s0n + 1; x9 <= x9 - 1; qa <= qa - 8'd1; end

        // ---------------------------------------------------------- run_stages(fin) -> rret
        130: begin s0ra <= 0; s <= 230; end
        230: begin
            if (!s0st && s0n != 0) begin
                s0st <= 1'b1; s0last <= s0rd; s0i <= 1;
                s1b[s1n[5:0]] <= s0rd; s1s[s1n[5:0]] <= s0rs; s1n <= s1n + 1;
            end
            s <= 231;
        end
        231: begin s0ra <= s0i[5:0]; s <= 131; end
        131: if (s0i < s0n && (fin || s0i + 4 < s0n || $signed(Tn) - s0rd >= DL)) begin
                 bi <= s0rd; srci <= s0rs;
                 lo <= (s0i > 5) ? s0i - 5 : 0;
                 hi2 <= (s0i + 4 < s0n - 1) ? s0i + 4 : s0n - 1;
                 rc <= 0; s <= 132;
             end else begin s1ra <= s1i[5:0]; s <= 140; end
        132: begin jx <= lo; s0ra <= lo[5:0]; s <= 232; end
        232: begin bprev <= s0rd; s0ra <= jx[5:0] + 6'd1; s <= 133; end
        133: begin
            rbuf[rc[7:0]] <= s0rd - bprev; bprev <= s0rd; rc <= rc + 1; jx <= jx + 1; s0ra <= jx[5:0] + 6'd2;
            if (jx + 1 == hi2) begin mc <= rc + 1; ret <= 134; s <= 30; end
        end
        134: begin R0 <= mres; gap <= bi - s0last; s0ra <= s0i[5:0] + 6'd1; s <= 135; end
        135: begin bi1 <= s0rd; s <= 235; end
        235: if (8 * R0 < 5 * gap && 2 * gap < 5 * R0) begin pe <= gfill; pR <= R0; ret <= 136; s <= 50; end
             else s <= 137;
        136: begin
            s0last <= (pbest >= 0) ? pbest : pe;
            s1b[s1n[5:0]] <= (pbest >= 0) ? pbest : pe; s1s[s1n[5:0]] <= 5'd16; s1n <= s1n + 1;
            s <= 137;
        end
        137: begin
            if (20 * gap < 11 * R0 && s0i + 1 < s0n && (dA < 0 ? -dA : dA) < (dB < 0 ? -dB : dB)) s0i <= s0i + 1;
            else begin
                s0last <= bi; s1b[s1n[5:0]] <= bi; s1s[s1n[5:0]] <= srci; s1n <= s1n + 1; s0i <= s0i + 1;
            end
            s <= 231;
        end
        // centred FHR: interval e uses the intervals e-2 .. e+2
        140: if (s1i < s1n && (fin || s1i + 3 < s1n || $signed(Tn) - s1rd >= DL)) begin
                 ot <= s1rd - 13; osrc <= s1rs;
                 if (s1i + 1 < s1n) begin
                     lo <= (s1i > 2) ? s1i - 2 : 0;
                     hi2 <= (s1i + 3 < s1n - 1) ? s1i + 3 : s1n - 1;
                     rc <= 0; s <= 141;
                 end else begin of10 <= 0; s <= 145; end
             end else s <= rret;
        141: begin jx <= lo; s1ra <= lo[5:0]; s <= 241; end
        241: begin bprev <= s1rd; s1ra <= jx[5:0] + 6'd1; s <= 142; end
        142: begin
            rbuf[rc[7:0]] <= s1rd - bprev; bprev <= s1rd; rc <= rc + 1; jx <= jx + 1; s1ra <= jx[5:0] + 6'd2;
            if (jx + 1 == hi2) begin mc <= rc + 1; ret <= 143; s <= 30; end
        end
        143: if (mres >= 50 && mres <= 300) begin dvd <= 18'd150000 + mres[8:1]; pv <= mres; ret <= 144; s <= 60; end
             else begin of10 <= 0; s <= 145; end
        144: begin of10 <= {4'd0, dq}; s <= 145; end
        145: begin ret <= 146; s <= 70; end
        146: begin s1i <= s1i + 1; s1ra <= s1i[5:0] + 6'd1; s <= 140; end

        // ---------------------------------------------------------- FLUSH: backtrack the undecided segments
        150: if (!vinit || iseg - 1 < decn) s <= 158;
             else begin bk <= 0; k <= 1; s <= 151; end
        151: begin
            if (Vt[k] > Vt[bk]) bk <= k;
            if (k == 15) begin jseg <= iseg - 1; lastseg <= iseg - 1; s <= 152; end else k <= k + 1;
        end
        152: begin
            pathm[jseg[3:0]] <= bk; bk <= bpm[jseg[3:0]][4 * bk +: 4];
            if (jseg == decn) begin jseg <= decn; jT <= decT; s <= 153; end else jseg <= jseg - 1;
        end
        153: if (jseg > lastseg) begin decn <= lastseg + 1; s <= 158; end
             else begin tk <= pathm[jseg[3:0]]; ret <= 154; s <= 120; end
        154: begin fin <= 1'b0; rret <= 155; s <= 130; end
        155: begin jseg <= jseg + 1; jT <= jT + 625; s <= 153; end
        158: begin fin <= 1'b1; rret <= 159; s <= 130; end
        159: s <= 75;

        // ---------------------------------------------------------- quality(k) -> L, then 102
        160: begin
            w0 <= segT - 3750; w1 <= segT + 2500;
            gk <= k; glo <= segT - 3750; ghi <= segT + 2500; ret <= 161; s <= 20;
        end
        161: begin
            n <= gn;
            if (gn < 4) begin L <= FLOOR; s <= 102; end
            else begin mc <= gn - 1; ret <= 162; s <= 30; end
        end
        162: begin
            R <= mres[8:0];
            if (mres < 69 || mres > 187) begin L <= FLOOR; s <= 102; end
            else begin ok <= 0; jj <= 0; rba <= 0; s <= 163; end
        end
        163: begin
            if (20 * rdev <= 3 * Rs) ok <= ok + 1;
            if (jj + 2 == n) s <= 164; else begin jj <= jj + 1; rba <= jj[7:0] + 8'd1; end
        end
        164: if (ok == 0) begin L <= FLOOR; s <= 102; end
             else begin ns <= 0; gg <= 0; s <= 165; end
        165: begin
            if (sg_ok) ns <= ns + tcm[sgs];
            if (gg == 9) begin dd <= 0; E <= 0; s <= 167; end else gg <= gg + 1;
        end
        167: begin acc <= 0; gg <= 0; s <= 168; end
        168: if (sg_ok) begin e_ssra <= {sgs, dd}; s <= 169; end else s <= 171;
        169: s <= 170;
        170: begin acc <= acc + $signed(ss_rd); s <= 171; end
        171: if (gg == 9) s <= 172; else begin gg <= gg + 1; s <= 168; end
        172: begin
            E <= E + acc_sq[47:0];
            if (dd == 30) s <= 173; else begin dd <= dd + 1; s <= 167; end
        end
        173: if (ns < 3 || E == 0) begin L <= FLOOR; s <= 102; end
             else begin lgx <= E; ret <= 175; s <= 80; end
        175: begin L <= (lgs >>> 1) - 2560; lgx <= ns; ret <= 177; s <= 80; end
        177: begin L <= L - lgs; lgx <= n; ret <= 179; s <= 80; end
        179: begin la <= lgs; lgx <= R; ret <= 181; s <= 80; end
        181: begin
            if (la + lgs - LGW < 0) L <= L + la + lgs - LGW;
            lgx <= ok; ret <= 183; s <= 80;
        end
        183: begin lr <= lgs; lgx <= n - 1; ret <= 185; s <= 80; end
        185: begin L <= L + 2 * (lr - lgs) + prior(R); nm <= 0; jj <= 0; mB <= (mn > 24'd256) ? 9'd256 : mn[8:0]; s <= 186; end
        // maternal peaks (trusted trains) in [w0-20, w1+20)
        186: if (jj == mB) s <= 189;
             else begin mp_ra <= mn[7:0] - 8'd1 - jj[7:0]; s <= 187; end
        187: s <= 188;
        188: if ($signed(mp_rd[31:0]) < w0 - 20) s <= 189;
             else begin
                 if (gate[mp_rd[33:32]] && $signed(mp_rd[31:0]) < w1 + 20) nm <= nm + 1;
                 jj <= jj + 1; s <= 186;
             end
        189: if (nm > 3) begin na <= n; nsel <= 1'b1; nlo <= SMALL; nhi <= BIG; ntol <= 12; ret <= 190; s <= 40; end
             else s <= 194;
        190: if (6 * n <= 10 * nh) begin L <= FLOOR; s <= 102; end
             else begin lgx <= 6 * n - 10 * nh; ret <= 192; s <= 80; end
        192: begin la <= lgs; lgx <= 3 * n; ret <= 199; s <= 80; end
        199: begin if (la - lgs < 0) L <= L + la - lgs; s <= 194; end
        // agreement with the other active tracks
        194: begin act <= 0; shh <= 0; j4 <= 0; s <= 195; end
        195: begin bix <= j4; s <= 196; end
        196: if (j4 != k && bnr != 0) begin
                 act <= act + 1; na <= n; nsel <= 1'b0; nk <= j4; nlo <= SMALL; nhi <= BIG; ntol <= 8; ret <= 191; s <= 40;
             end else s <= 197;
        191: begin shh <= shh + nh; s <= 197; end
        197: if (j4 == 15) s <= 198; else begin j4 <= j4 + 1; s <= 195; end
        198: if (act == 0) begin L <= L - 256; s <= 220; end
             else begin lgx <= n * act + 2 * shh; ret <= 222; s <= 80; end
        222: begin la <= lgs; lgx <= 2 * n * act; ret <= 224; s <= 80; end
        224: begin L <= L + la - lgs; s <= 220; end
        220: begin if (L < FLOOR) L <= FLOOR; s <= 102; end

        // ---------------------------------------------------------- maternal-train gates (once)
        // sh: while ((dmax >> sh) >= 2^24) sh++;  covs = cov >> sh;  gate[k] = 10 v'Cv >= trace << 28
        200: begin gx <= $signed(cov[0]); gi <= 1; s <= 201; end
        201: begin
            if ($signed(cov[gi == 1 ? 4 : gi == 2 ? 7 : 9]) > gx) gx <= $signed(cov[gi == 1 ? 4 : gi == 2 ? 7 : 9]);
            if (gi == 3) begin gsh <= 0; s <= 202; end else gi <= gi + 1;
        end
        202: if (gx >= 64'sd16777216) begin gx <= gx >>> 1; gsh <= gsh + 1'b1; end
             else begin gi <= 0; s <= 203; end
        203: begin gx <= $signed(cov[gi]); gcnt <= gsh; s <= 204; end
        204: if (gcnt != 0) begin gx <= gx >>> 1; gcnt <= gcnt - 1'b1; end
             else begin
                 covs[gi] <= gx[24:0];
                 if (gi == 9) s <= 205; else begin gi <= gi + 1; s <= 203; end
             end
        205: begin gtr <= covs[0] + covs[4] + covs[7] + covs[9]; k <= 0; s <= 206; end
        206: begin lam <= 0; ab <= 0; s <= 207; end
        207: begin vv <= Va * Vb; cc <= covs[cix(ab[3:2], ab[1:0])]; s <= 208; end
        208: begin
            lam <= lam + vv * cc;
            if (ab == 15) s <= 209; else begin ab <= ab + 1; s <= 207; end
        end
        209: s <= 210;
        210: begin
            gate[k[1:0]] <= (10 * lam >= (gtr <<< 28));
            if (k == 3) begin gate_ok <= 1'b1; s <= 2; end else begin k <= k + 1; s <= 206; end
        end
        default: s <= 0;
        endcase
    end
endmodule

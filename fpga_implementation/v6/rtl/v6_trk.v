// FECG v6 - candidate tracks (Z-time processing of the C model, s = T - 176).
//  before calibration: band-pass + MWI of lead 0 of Z and Xf (start state of the tracks)
//  s = 3750: REQ_CAL -> 16 tracks (kind, source, blanking, 4 weights Q14 from the PC)
//  per track and sample: projection (64-sample crossfade from lead 0), BP SOS, MWI(30) of
//  bp^2 -> 16-bit envelope code, maternal blanking (45 samples), rings; RR-predictive
//  tracker (kind 0) or adaptive detector (kind 1); BEAT / FEAT / BMED messages;
//  every 625 samples REQ_SEL; beats of the selected track -> OUT (with FHR).
`timescale 1ns / 1ps

module v6_trk (
    input  wire               clk,
    input  wire               clear,
    input  wire               start,
    input  wire signed [31:0] s_in,         // Z-time sample (>= 0)
    output reg                done,
    // calibration and selection responses
    input  wire               cal_valid,
    input  wire [4:0]         cal_ntr,
    input  wire [15:0]        cal_kind, cal_src, cal_blank,
    input  wire [1023:0]      cal_w,
    output reg                cal_clr,
    input  wire               sel_valid,
    input  wire [3:0]         sel_in,
    output reg                sel_clr,
    // maternal peaks
    input  wire [31:0]        nmpk,
    output reg  [8:0]         mpk_ra,
    input  wire signed [31:0] mpk_rd,
    // rings (read at s)
    output reg  [11:0]        xr_ra,
    input  wire [63:0]        xr_rd,
    output reg  [11:0]        zr_ra,
    input  wire [63:0]        zr_rd,
    // envelope rings, 16 tracks x 2048 codes (memory in v6_core, shared with v6_mat)
    output reg  [14:0]        ea,
    input  wire [15:0]        erd,
    output reg                ewe,
    output reg  [14:0]        ewa,
    output reg  [15:0]        ewd,
    // message writer
    output reg                msg_start,
    output reg  [7:0]         msg_cmd,
    output reg  [15:0]        msg_len,
    input  wire               msg_idle,
    output reg                w_valid,
    output reg  [63:0]        w_data,
    output reg  [3:0]         w_nb,
    input  wire               w_ready
);
    localparam signed [31:0] CAL_END = 3750, T0_TRACK = 3877, SEL_START = 4877;

    // ---------------- envelope code (enc_e / dec_e of proto.h)
    function [15:0] enc_e(input [63:0] x);
        integer b, n, sh;
        reg [63:0] m, r, half;
        begin
            if (x < 256) enc_e = x[15:0];
            else begin
                n = 0;
                for (b = 0; b < 64; b = b + 1) if (x[b]) n = b;
                sh = n - 7;
                m = x >> sh;
                r = x & ((64'd1 << sh) - 1);
                half = 64'd1 << (sh - 1);
                if (r > half || (r == half && m[0])) m = m + 1;
                if (m == 256) begin m = 128; sh = sh + 1; end
                enc_e = ((sh + 1) << 7) + (m - 128);
            end
        end
    endfunction
    function [63:0] dec_e(input [15:0] c);
        begin
            if (c[15:7] <= 1) dec_e = {48'd0, c};
            else dec_e = {56'd0, 1'b1, c[6:0]} << (c[15:7] - 1);
        end
    endfunction
    function [31:0] div100(input [31:0] x); div100 = (x * 32'd5243) >> 19; endfunction

    // ---------------- memories
    reg signed [31:0] bmem [0:4095]; reg [11:0] ba, bwa; reg bwe; reg signed [31:0] bwd, brd;
    always @(posedge clk) begin if (bwe) bmem[bwa] <= bwd; brd <= bmem[ba]; end
    reg signed [31:0] pmem [0:511]; reg [8:0] pa_, pwa; reg pwe; reg signed [31:0] pwd, prd;
    always @(posedge clk) begin if (pwe) pmem[pwa] <= pwd; prd <= pmem[pa_]; end
    reg [63:0] amem [0:127];     reg [6:0] aa_, awa; reg awe; reg [63:0] awd, ard;
    always @(posedge clk) begin if (awe) amem[awa] <= awd; ard <= amem[aa_]; end
    // autocorrelation scratch, two read ports
    reg signed [31:0] xmem [0:1023]; reg [9:0] xa0, xa1, xwa; reg xwe; reg signed [31:0] xwd, xrd0, xrd1;
    always @(posedge clk) begin if (xwe) xmem[xwa] <= xwd; xrd0 <= xmem[xa0]; xrd1 <= xmem[xa1]; end

    // ---------------- engines
    reg so_start, so_clear, so_copy; reg [4:0] so_inst, so_from; reg signed [31:0] so_x; wire so_busy, so_done; wire signed [31:0] so_y;
    v6_sos #(.NINST(18)) sos(.clk(clk), .clear(so_clear), .start(so_start), .inst(so_inst), .fset(2'd2), .x(so_x),
                             .copy(so_copy), .copy_from(so_from), .busy(so_busy), .done(so_done), .y(so_y));
    reg mw_start, mw_clear, mw_copy; reg [4:0] mw_inst, mw_from; reg signed [63:0] mw_sq; wire mw_done; wire signed [63:0] mw_sum;
    v6_mwi #(.NINST(18)) mwi(.clk(clk), .clear(mw_clear), .start(mw_start), .inst(mw_inst), .w(6'd30), .sq(mw_sq),
                             .copy(mw_copy), .copy_from(mw_from), .done(mw_done), .sum(mw_sum));
    reg d_init, d_start; reg [2:0] d_inst; reg signed [31:0] d_t; reg signed [63:0] d_e, d_ab; wire d_done; wire signed [31:0] d_out;
    v6_det #(.NINST(4)) det(.clk(clk), .init(d_init), .i_start(T0_TRACK), .i_refr(8'd50), .i_loc(8'd26), .i_rrmin(8'd50),
                            .start(d_start), .inst(d_inst), .t(d_t), .e(d_e), .ab(d_ab), .done(d_done), .out(d_out));
    reg signed [31:0] ma, mb; reg signed [63:0] mp;
    always @(posedge clk) mp <= ma * mb;

    // ---------------- per-track state
    reg        calibrated;
    reg [4:0]  ntr;
    reg [15:0] ehold [0:15];
    reg signed [31:0] blank_until [0:15], tt [0:15], RR [0:15], ts [0:15], aa [0:15], dec [0:15];
    reg [2:0]  st [0:15], misses [0:15];
    reg [31:0] nrr [0:15], namp [0:15], npk [0:15], nfeat [0:15];
    reg [8:0]  rrs [0:127];
    reg        first_done [0:15], started [0:15];
    // ---------------- globals
    reg [31:0] mblank;
    reg signed [31:0] sel_next, sel_t, sel_end, out_last, emitted_upto;
    reg signed [4:0]  sel_k;
    reg [8:0]  rrbuf [0:4]; reg [2:0] nrro;
    reg [15:0] fhr_x10;
    reg [6:0]  m125;

    // ---------------- working registers
    reg [7:0]  s = 0;
    reg [7:0]  rt_arg, rt_loc, rt_beat, rt_msg, rt_div;
    reg signed [31:0] sv, q, m, lo, hi, i, iend, p, rr, bestq;
    reg signed [63:0] rmed;
    reg [4:0]  k;
    reg [1:0]  l;
    reg        bstart;
    reg [6:0]  rrw;
    reg [63:0] zw, xw;
    reg signed [63:0] acc, em, bv;
    reg signed [31:0] y, bp;
    reg [15:0] ec, mx, bvc;
    integer n, sh;
    reg signed [63:0] sum;
    reg signed [63:0] best;
    reg [7:0]  lag, bestlag;
    reg [3:0]  pipe;
    reg [9:0]  j0;
    reg [63:0] srt [0:7];                     // sorting network
    reg [3:0]  ns, ph;
    // median125 buffer
    reg [12:0] mbuf [0:124];
    reg [12:0] pref; reg [3:0] bit_; reg [6:0] kk, cnt0; reg [7:0] mi;
    // divider
    reg [31:0] dnum, dden, dq, drem; reg [5:0] dcnt;
    // message staging
    reg [63:0] wq [0:3]; reg [3:0] wnb [0:3]; reg [2:0] nw, wi;

    wire signed [15:0] w_kl = cal_w[64 * k + 16 * l +: 16];
    wire signed [15:0] src_kl = cal_src[k] ? xw[16 * l +: 16] : zw[16 * l +: 16];

    // generic message: header (cmd, len) + up to 4 staged words, then -> rt_msg
    task send_msg(input [7:0] cmd, input [15:0] len, input [2:0] nwords, input [7:0] ret);
        begin msg_cmd <= cmd; msg_len <= len; nw <= nwords; wi <= 0; rt_msg <= ret; s <= 200; end
    endtask

    always @(posedge clk) begin
        done <= 1'b0; ewe <= 1'b0; bwe <= 1'b0; pwe <= 1'b0; awe <= 1'b0; xwe <= 1'b0;
        so_start <= 1'b0; so_clear <= 1'b0; so_copy <= 1'b0; mw_start <= 1'b0; mw_clear <= 1'b0; mw_copy <= 1'b0;
        d_init <= 1'b0; d_start <= 1'b0; cal_clr <= 1'b0; sel_clr <= 1'b0; msg_start <= 1'b0;
        if (w_valid && w_ready) w_valid <= 1'b0;
        if (clear) begin
            calibrated <= 1'b0; ntr <= 0; mblank <= 0;
            sel_next <= SEL_START; sel_k <= -1; out_last <= -1; emitted_upto <= -1; nrro <= 0; fhr_x10 <= 0;
            m125 <= 0; w_valid <= 1'b0;
            so_clear <= 1'b1; s <= 250;
        end else case (s)
        // ======================================================== per sample
        0: if (start) begin
            sv <= s_in;
            zr_ra <= s_in[11:0]; xr_ra <= s_in[11:0];
            s <= 1;
        end
        1: s <= 2;
        2: begin
            zw <= zr_rd; xw <= xr_rd;
            if (!calibrated) s <= (sv == CAL_END) ? 10 : 3;
            else s <= 30;
        end
        // ---- before calibration: lead-0 band-pass of Z (inst 16) and Xf (inst 17)
        3: begin so_inst <= 16; so_x <= $signed(zw[15:0]) <<< 8; so_start <= 1'b1; s <= 4; end
        4: if (so_done) begin ma <= so_y; mb <= so_y; s <= 5; end
        5: s <= 6;
        6: begin mw_inst <= 16; mw_sq <= mp; mw_start <= 1'b1; s <= 7; end
        7: if (mw_done) begin so_inst <= 17; so_x <= $signed(xw[15:0]) <<< 8; so_start <= 1'b1; s <= 8; end
        8: if (so_done) begin ma <= so_y; mb <= so_y; s <= 9; end
        9: s <= 11;
        11: begin mw_inst <= 17; mw_sq <= mp; mw_start <= 1'b1; s <= 12; end
        12: if (mw_done) s <= 190;
        // ---- calibration
        10: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h86; msg_len <= 0; s <= 13; end
        13: if (cal_valid && msg_idle) begin cal_clr <= 1'b1; ntr <= cal_ntr; k <= 0; s <= 14; end
        14: begin so_inst <= k; so_from <= cal_src[k] ? 5'd17 : 5'd16; so_copy <= 1'b1; s <= 15; end
        15: if (so_done) begin mw_inst <= k; mw_from <= cal_src[k] ? 5'd17 : 5'd16; mw_copy <= 1'b1; s <= 16; end
        16: if (mw_done) begin
            ehold[k] <= 0; blank_until[k] <= 0; tt[k] <= 0; RR[k] <= 0; ts[k] <= 0; aa[k] <= 0;
            dec[k] <= T0_TRACK + 999; st[k] <= 0; misses[k] <= 0; nrr[k] <= 0; namp[k] <= 0;
            npk[k] <= 0; nfeat[k] <= 0; first_done[k] <= 0; started[k] <= 0;
            ewe <= 1'b1; ewa <= {k[3:0], 11'd1701}; ewd <= 0;                // e[3749 & 2047] = 0
            if (cal_kind[k]) begin d_init <= 1'b1; d_inst <= {1'b0, k[1:0]}; s <= 17; end
            else s <= 18;
        end
        17: if (d_done) s <= 18;
        18: if (k + 1'b1 == ntr) begin calibrated <= 1'b1; s <= 30; end else begin k <= k + 1'b1; s <= 14; end
        // ---- calibrated: maternal blanking start
        30: begin bstart <= 1'b0; s <= 31; end
        31: if (mblank < nmpk) begin mpk_ra <= mblank[8:0]; s <= 32; end else s <= 34;
        32: s <= 33;
        33: if (mpk_rd <= sv) begin if (mpk_rd == sv) bstart <= 1'b1; mblank <= mblank + 1'b1; s <= 31; end
            else s <= 34;
        34: begin rrw <= (sv - (CAL_END - 1) > 64) ? 7'd64 : sv - (CAL_END - 1); k <= 0; s <= 35; end
        // ---- track k: projection (Q20 weights) -> Q8
        35: if (k == ntr) s <= 120; else begin acc <= 0; l <= 0; s <= 36; end
        36: begin
            ma <= ((l == 0) ? 32'sd1048576 : 32'sd0) + (w_kl - ((l == 0) ? 32'sd16384 : 32'sd0)) * $signed({25'd0, rrw});
            mb <= src_kl;
            s <= 37;
        end
        37: s <= 38;
        38: begin acc <= acc + mp; if (l == 3) s <= 39; else begin l <= l + 1'b1; s <= 36; end end
        39: begin y = (acc + 64'sd2048) >>> 12; so_inst <= k; so_x <= y; so_start <= 1'b1; s <= 40; end
        40: if (so_done) begin bp <= so_y; ma <= so_y; mb <= so_y; s <= 41; end
        41: s <= 42;
        42: begin mw_inst <= k; mw_sq <= mp; mw_start <= 1'b1; s <= 43; end
        43: if (mw_done) begin
            ec <= enc_e(mw_sum);
            ea <= {k[3:0], sv[10:0] - 11'd1};                              // e[s-1]
            s <= 44;
        end
        44: s <= 45;
        45: begin
            if (cal_blank[k]) begin
                if (bstart) begin ehold[k] <= erd; blank_until[k] <= sv + 45; ec <= erd; end
                else if (sv < blank_until[k]) ec <= ehold[k];
            end
            s <= 46;
        end
        46: begin
            ewe <= 1'b1; ewa <= {k[3:0], sv[10:0]}; ewd <= ec;
            bwe <= 1'b1; bwa <= {k[3:0], sv[7:0]}; bwd <= bp;
            s <= cal_kind[k] ? 47 : 50;
        end
        47: begin d_inst <= {1'b0, k[1:0]}; d_t <= sv; d_e <= dec_e(ec); d_ab <= (bp < 0) ? -bp : bp; d_start <= 1'b1; s <= 48; end
        48: if (d_done) begin
            if (d_out >= 0) begin q <= d_out; rt_beat <= 100; s <= 180; end
            else s <= 100;
        end
        50: begin                                                     // tracker
            if (sv >= T0_TRACK) begin
                if (!started[k]) begin started[k] <= 1'b1; ts[k] <= T0_TRACK; end
                s <= (sv == dec[k]) ? 51 : 100;
            end else s <= 100;
        end
        // ======================================================== tracker_step
        51: case (st[k])
                0: s <= 52;
                1: s <= 60;
                default: s <= 70;
            endcase
        // st 0: R = autocorr(ts, 1000)
        52: begin i <= 0; mx <= 0; s <= 53; end
        53: begin ea <= {k[3:0], ts[k][10:0] + i[10:0]}; s <= 54; end
        54: s <= 55;
        55: begin
            if (erd > mx) mx <= erd;
            if (i == 999) s <= 56; else begin i <= i + 1; s <= 53; end
        end
        56: begin
            sh = (mx[15:7] > 8) ? mx[15:7] - 8 : 0;
            bvc <= sh; sum <= 0; i <= 0; s <= 57;
        end
        57: begin ea <= {k[3:0], ts[k][10:0] + i[10:0]}; s <= 58; end
        58: s <= 59;
        59: begin
            xwe <= 1'b1; xwa <= i[9:0]; xwd <= dec_e(erd) >> bvc;
            sum <= sum + (dec_e(erd) >> bvc);
            if (i == 999) begin i <= 0; s <= 150; end else begin i <= i + 1; s <= 57; end
        end
        150: begin xa0 <= i[9:0]; s <= 151; end                         // d_i = 1000 v_i - sum
        151: s <= 152;
        152: begin
            xwe <= 1'b1; xwa <= i[9:0]; xwd <= $signed(xrd0) * 32'sd1000 - sum[31:0];
            if (i == 999) begin lag <= 75; s <= 153; end else begin i <= i + 1; s <= 150; end
        end
        // lags 75..166: pipelined MAC  sum_{i < 1000-lag} d_i d_{i+lag}
        153: begin acc <= 0; i <= 0; pipe <= 0; s <= 154; end
        154: begin
            // stage 0: issue addresses
            if (i < 1000 - lag) begin xa0 <= i[9:0]; xa1 <= i[9:0] + lag; i <= i + 1; pipe[0] <= 1'b1; end
            else pipe[0] <= 1'b0;
            // stage 2: data -> multiplier;   stage 3: accumulate
            pipe[3:1] <= pipe[2:0];
            ma <= xrd0; mb <= xrd1;
            if (pipe[3]) acc <= acc + mp;
            if (i >= 1000 - lag && pipe == 4'b0000 && i != 0) s <= 155;
        end
        155: begin
            if (lag == 75 || acc > best) begin best <= acc; bestlag <= lag; end
            if (lag == 166) s <= 156; else begin lag <= lag + 1'b1; s <= 153; end
        end
        156: begin
            RR[k] <= bestlag; aa[k] <= ts[k] + 1000; st[k] <= 1;
            dec[k] <= ts[k] + 1000 + bestlag - 1;
            s <= (ts[k] + 1000 + bestlag - 1 > sv) ? 100 : 60;
        end
        // st 1: anchor
        60: begin lo <= aa[k]; hi <= aa[k] + RR[k] - 1; rt_arg <= 61; s <= 160; end
        61: begin
            tt[k] <= m;
            if (!first_done[k]) begin rt_loc <= 62; s <= 170; end
            else begin
                if (RR[k] < 60) RR[k] <= 60;
                if (RR[k] > 190) RR[k] <= 190;
                s <= 63;
            end
        end
        62: begin first_done[k] <= 1'b1; rt_beat <= 63; s <= 180; end      // q = localise(m)
        63: begin
            nrr[k] <= 1; rrs[{k[3:0], 3'd0}] <= RR[k][8:0];
            namp[k] <= 1; awe <= 1'b1; awa <= {k[3:0], 3'd0}; awd <= dec_e(bvc);  // bvc = e[m]
            misses[k] <= 0; st[k] <= 2;
            dec[k] <= tt[k] + div100(130 * RR[k]);
            s <= (tt[k] + div100(130 * RR[k]) > sv) ? 100 : 70;
        end
        // st 2: running
        70: begin lo <= tt[k] + div100(70 * RR[k]); hi <= tt[k] + div100(130 * RR[k]); rt_arg <= 71; s <= 160; end
        71: begin em <= dec_e(bvc); ns <= (namp[k] < 8) ? namp[k][3:0] : 4'd8; i <= 0; s <= 72; end
        72: begin                                                     // load amps (oldest first)
            if (i == ns) begin ph <= 0; s <= 75; end
            else begin aa_ <= {k[3:0], namp[k][2:0] - ns[2:0] + i[2:0]}; s <= 73; end
        end
        73: s <= 74;
        74: begin srt[i[2:0]] <= ard; i <= i + 1; s <= 72; end
        75: begin                                                     // fill unused, sort
            for (n = 0; n < 8; n = n + 1) if (n >= ns) srt[n] <= 64'h7FFFFFFFFFFFFFFF;
            ph <= 0; s <= 76;
        end
        76: begin
            for (n = 0; n < 7; n = n + 1)
                if ((n % 2) == ph[0] && $signed(srt[n]) > $signed(srt[n + 1])) begin srt[n] <= srt[n + 1]; srt[n + 1] <= srt[n]; end
            if (ph == 7) s <= 77; else ph <= ph + 1'b1;
        end
        77: begin
            if (ns[0] ? (4 * em > $signed(srt[ns >> 1])) : (8 * em > $signed(srt[(ns >> 1) - 1]) + $signed(srt[ns >> 1]))) begin
                rr <= m - tt[k]; tt[k] <= m; rt_loc <= 78; s <= 170;     // accept
            end else begin
                tt[k] <= tt[k] + RR[k]; misses[k] <= misses[k] + 1'b1;
                s <= 85;
            end
        end
        78: begin rt_beat <= 79; s <= 180; end
        79: begin
            awe <= 1'b1; awa <= {k[3:0], namp[k][2:0]}; awd <= em; namp[k] <= namp[k] + 1;
            rrs[{k[3:0], nrr[k][2:0]}] <= rr[8:0]; nrr[k] <= nrr[k] + 1;
            misses[k] <= 0;
            s <= 80;
        end
        80: begin                                                     // R = rr_median5
            ns <= (nrr[k] < 5) ? nrr[k][3:0] : 4'd5;
            for (n = 0; n < 8; n = n + 1) srt[n] <= 64'h7FFFFFFFFFFFFFFF;
            i <= 0; s <= 81;
        end
        81: if (i == ns) begin ph <= 0; s <= 82; end
            else begin srt[i[2:0]] <= {55'd0, rrs[{k[3:0], nrr[k][2:0] - ns[2:0] + i[2:0]}]}; i <= i + 1; end
        82: begin
            for (n = 0; n < 7; n = n + 1)
                if ((n % 2) == ph[0] && $signed(srt[n]) > $signed(srt[n + 1])) begin srt[n] <= srt[n + 1]; srt[n + 1] <= srt[n]; end
            if (ph == 7) s <= 83; else ph <= ph + 1'b1;
        end
        83: begin
            rmed = ns[0] ? srt[ns >> 1] : (srt[(ns >> 1) - 1] + srt[ns >> 1]) >> 1;
            RR[k] <= (rmed < 60) ? 60 : (rmed > 190) ? 190 : rmed;
            s <= 84;
        end
        84: begin
            dec[k] <= tt[k] + div100(130 * RR[k]);
            s <= (tt[k] + div100(130 * RR[k]) > sv) ? 100 : 70;
        end
        85: begin                                                     // miss
            if (misses[k] >= 4) begin
                ts[k] <= (tt[k] - 1000 < T0_TRACK) ? T0_TRACK : tt[k] - 1000;
                st[k] <= 0;
                dec[k] <= ((tt[k] - 1000 < T0_TRACK) ? T0_TRACK : tt[k] - 1000) + 999;
                s <= (((tt[k] - 1000 < T0_TRACK) ? T0_TRACK : tt[k] - 1000) + 999 > sv) ? 100 : 52;
            end else s <= 84;
        end
        // ======================================================== capture_features, block median
        100: if (nfeat[k] < npk[k]) begin pa_ <= {k[3:0], nfeat[k][4:0]}; s <= 101; end else s <= 110;
        101: s <= 102;
        102: begin
            q <= prd;
            if (sv < prd + 40) s <= 110;
            else begin i <= prd + 13; bvc <= 0; s <= 103; end
        end
        103: begin ea <= {k[3:0], i[10:0]}; s <= 104; end                   // pem = max e[q+13 .. q+39]
        104: s <= 105;
        105: begin
            if (i == q + 13 || erd > bvc) bvc <= erd;
            if (i == q + 39) s <= 106; else begin i <= i + 1; s <= 103; end
        end
        106: if (msg_idle) begin
            msg_start <= 1'b1; msg_cmd <= 8'h88; msg_len <= 131;
            i <= -1; s <= 107;
        end
        107: if (!w_valid && w_ready) begin
            if (i == -1) begin w_valid <= 1'b1; w_data <= {q, 4'd0, k[3:0]}; w_nb <= 5; i <= 0; end
            else if (i == 31) begin w_valid <= 1'b1; w_data <= bvc; w_nb <= 2; s <= 109; end
            else begin ba <= {k[3:0], q[7:0] - 8'd15 + i[7:0]}; s <= 108; end
        end
        108: s <= 140;
        140: s <= 141;
        141: begin w_valid <= 1'b1; w_data <= brd; w_nb <= 4; i <= i + 1; s <= 107; end
        109: if (!w_valid) begin nfeat[k] <= nfeat[k] + 1; s <= 100; end
        110: begin
            if (sv >= CAL_END + 126 && m125 == 1) begin i <= 0; s <= 111; end
            else s <= 119;
        end
        111: begin ea <= {k[3:0], sv[10:0] - 11'd124 + i[10:0]}; s <= 112; end
        112: s <= 113;
        113: begin mbuf[i] <= erd[12:0]; if (i == 124) begin pref <= 0; bit_ <= 12; kk <= 62; s <= 114; end else begin i <= i + 1; s <= 111; end end
        114: begin cnt0 <= 0; mi <= 0; s <= 115; end
        115: begin                                                    // radix select (63rd smallest)
            if ((mbuf[mi] >> (bit_ + 1)) == (pref >> (bit_ + 1)) && !mbuf[mi][bit_]) cnt0 <= cnt0 + 1'b1;
            if (mi == 124) s <= 116; else mi <= mi + 1'b1;
        end
        116: begin
            if (kk >= cnt0) begin pref[bit_] <= 1'b1; kk <= kk - cnt0; end
            if (bit_ == 0) s <= 117; else begin bit_ <= bit_ - 1'b1; s <= 114; end
        end
        117: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h89; msg_len <= 3; s <= 118; end
        118: if (!w_valid && w_ready) begin w_valid <= 1'b1; w_data <= {pref, 4'd0, k[3:0]}; w_nb <= 3; s <= 119; end
        119: if (!w_valid) begin k <= k + 1'b1; s <= 35; end
        // ======================================================== selection, output
        120: begin
            if (sv == sel_next + 150) begin rt_div <= 121; s <= 130; end    // emit (old segment) first
            else begin rt_div <= 125; s <= 130; end
        end
        121: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h8A; msg_len <= 4; s <= 122; end
        122: if (!w_valid && w_ready) begin w_valid <= 1'b1; w_data <= sel_next; w_nb <= 4; s <= 123; end
        123: if (!w_valid && sel_valid) begin
            sel_clr <= 1'b1; sel_k <= {1'b0, sel_in}; sel_t <= sel_next; sel_end <= sel_next + 625; sel_next <= sel_next + 625;
            rt_div <= 125; s <= 130;
        end
        125: s <= 190;
        // ---- emit_beats -> rt_div
        130: if (sel_k < 0) s <= rt_div;
            else begin
                k <= sel_k[3:0];
                i <= (npk[sel_k[3:0]] > 32) ? npk[sel_k[3:0]] - 32 : 0;
                s <= 131;
            end
        131: if (i >= npk[k]) s <= rt_div; else begin pa_ <= {k[3:0], i[4:0]}; s <= 132; end
        132: s <= 133;
        133: begin
            q <= prd;
            if (prd < sel_t || prd >= sel_end || prd <= out_last) begin i <= i + 1; s <= 131; end
            else s <= 134;
        end
        134: begin
            out_last <= q;
            p = (q - 13 < 0) ? 0 : q - 13;
            bestq <= p;
            if (emitted_upto >= 0 && p - emitted_upto >= 50 && p - emitted_upto <= 300) begin
                if (nrro < 5) begin rrbuf[nrro] <= p - emitted_upto; nrro <= nrro + 1'b1; end
                else begin rrbuf[0] <= rrbuf[1]; rrbuf[1] <= rrbuf[2]; rrbuf[2] <= rrbuf[3]; rrbuf[3] <= rrbuf[4]; rrbuf[4] <= p - emitted_upto; end
                s <= 135;
            end else s <= 138;
        end
        135: begin
            for (n = 0; n < 8; n = n + 1) srt[n] <= (n < nrro) ? {55'd0, rrbuf[n]} : 64'h7FFFFFFFFFFFFFFF;
            ns <= nrro; ph <= 0; s <= 136;
        end
        136: begin
            for (n = 0; n < 7; n = n + 1)
                if ((n % 2) == ph[0] && $signed(srt[n]) > $signed(srt[n + 1])) begin srt[n] <= srt[n + 1]; srt[n + 1] <= srt[n]; end
            if (ph == 7) s <= 137; else ph <= ph + 1'b1;
        end
        137: begin                                                    // fhr_x10 = (300000+M)/(2M) or (600000+M2)/(2M2)
            if (ns[0]) begin dnum <= 300000 + srt[ns >> 1]; dden <= 2 * srt[ns >> 1]; end
            else begin dnum <= 600000 + srt[(ns >> 1) - 1] + srt[ns >> 1]; dden <= 2 * (srt[(ns >> 1) - 1] + srt[ns >> 1]); end
            dq <= 0; drem <= 0; dcnt <= 0; s <= 145;
        end
        145: begin                                                    // restoring division, 20 bits
            if ({drem[30:0], dnum[19 - dcnt]} >= dden) begin
                drem <= {drem[30:0], dnum[19 - dcnt]} - dden; dq[19 - dcnt] <= 1'b1;
            end else drem <= {drem[30:0], dnum[19 - dcnt]};
            if (dcnt == 19) s <= 146; else dcnt <= dcnt + 1'b1;
        end
        146: begin fhr_x10 <= dq[15:0]; s <= 138; end
        138: begin emitted_upto <= bestq; s <= 139; end
        139: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h8B; msg_len <= 7; s <= 142; end
        142: if (!w_valid && w_ready) begin w_valid <= 1'b1; w_data <= {4'd0, sel_k[3:0], fhr_x10, bestq}; w_nb <= 7; s <= 143; end
        143: if (!w_valid) begin i <= i + 1; s <= 131; end
        // ======================================================== subroutines
        // argmax_e(lo, hi) -> m, bvc = e[m]
        160: begin i <= lo; s <= 161; end
        161: begin ea <= {k[3:0], i[10:0]}; s <= 162; end
        162: s <= 163;
        163: begin
            if (i == lo || erd > bvc) begin bvc <= erd; m <= i; end
            if (i == hi) s <= rt_arg; else begin i <= i + 1; s <= 161; end
        end
        // localise(m) -> q: first max of |bp| over [m-25, m]
        170: begin i <= m - 25; s <= 171; end
        171: begin ba <= {k[3:0], i[7:0]}; s <= 172; end
        172: s <= 173;
        173: begin
            if (i == m - 25 || ((brd < 0) ? -brd : brd) > bv) begin bv <= (brd < 0) ? -brd : brd; q <= i; end
            if (i == m) s <= rt_loc; else begin i <= i + 1; s <= 171; end
        end
        // add_beat(k, q) -> rt_beat
        180: begin pwe <= 1'b1; pwa <= {k[3:0], npk[k][4:0]}; pwd <= q; npk[k] <= npk[k] + 1; s <= 181; end
        181: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h87; msg_len <= 5; s <= 182; end
        182: if (!w_valid && w_ready) begin w_valid <= 1'b1; w_data <= {q, 4'd0, k[3:0]}; w_nb <= 5; s <= 183; end
        183: if (!w_valid) s <= rt_beat;
        // ======================================================== end of sample
        190: begin m125 <= (m125 == 124) ? 7'd0 : m125 + 1'b1; done <= 1'b1; s <= 0; end
        250: if (so_done) begin mw_clear <= 1'b1; s <= 251; end
        251: if (mw_done) s <= 0;
        default: s <= 0;
        endcase
    end
endmodule

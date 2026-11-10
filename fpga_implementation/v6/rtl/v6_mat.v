// FECG v6 - maternal R peaks.
//  T < 2500 : store ym, accumulate the 4x4 covariance over [256, 2500); at T = 2499 send
//             COV, wait for the PCA projections (RSP_V), replay the 2500 stored samples
//  T >= 2500: 4 projections -> y^2 -> MWI(38) -> adaptive detector; final peaks -> MDET
//  every 5 s (REQ_MK) the PC picks the train; its peaks inside the segment are emitted
//  as maternal R peaks (refractory 75) -> MPK, and kept in a 512-entry queue.
`timescale 1ns / 1ps

module v6_mat (
    input  wire               clk,
    input  wire               clear,
    input  wire               start,
    input  wire [31:0]        T,
    input  wire [127:0]       ym_in,
    output reg                done,
    // PC responses
    input  wire               v_valid,
    input  wire [255:0]       v_q,
    output reg                v_clr,
    input  wire               mk_valid,
    input  wire [1:0]         mk_in,
    output reg                mk_clr,
    // maternal peak queue
    output reg  [31:0]        nmpk,
    input  wire [8:0]         mpk_ra,
    output reg  signed [31:0] mpk_rd,
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
    localparam MAT_INIT = 2500, LAGM = 104, MAT_HOP = 1250;
    // stored maternal-band samples
    reg [127:0] ymem [0:2499];
    reg [11:0]  ya; reg [127:0] yrd; reg ywe;
    always @(posedge clk) begin if (ywe) ymem[ya] <= ym_in; yrd <= ymem[ya]; end
    // trains: 4 x 96 peaks (ring index = i mod 96)
    reg signed [31:0] tmem [0:511];
    reg [8:0] ta, twa; reg twe; reg signed [31:0] twd, trd;
    always @(posedge clk) begin if (twe) tmem[twa] <= twd; trd <= tmem[ta]; end
    reg [31:0] nmtr [0:3];
    reg [6:0]  twp [0:3];                                            // nmtr mod 96
    // emitted peaks
    reg signed [31:0] qmem [0:511];
    reg qwe; reg [8:0] qwa; reg signed [31:0] qwd;
    always @(posedge clk) begin if (qwe) qmem[qwa] <= qwd; mpk_rd <= qmem[mpk_ra]; end

    reg signed [63:0] cov [0:9];
    reg signed [15:0] V [0:15];
    reg have_V;
    reg signed [31:0] mk, mseg_t, mseg_end, mlast, lastp;

    // engines
    reg mw_start, mw_clear; reg [4:0] mw_inst; reg signed [63:0] mw_sq; wire mw_done; wire signed [63:0] mw_sum;
    v6_mwi #(.NINST(4)) mwi(.clk(clk), .clear(mw_clear), .start(mw_start), .inst(mw_inst), .w(6'd38), .sq(mw_sq),
                            .copy(1'b0), .copy_from(5'd0), .done(mw_done), .sum(mw_sum));
    reg d_init, d_start; reg [2:0] d_inst; reg signed [31:0] d_t; reg signed [63:0] d_e, d_ab; wire d_done; wire signed [31:0] d_out;
    v6_det #(.NINST(4)) det(.clk(clk), .init(d_init), .i_start(32'sd0), .i_refr(8'd75), .i_loc(8'd30), .i_rrmin(8'd75),
                            .start(d_start), .inst(d_inst), .t(d_t), .e(d_e), .ab(d_ab), .done(d_done), .out(d_out));
    reg signed [31:0] pa, pb; reg signed [63:0] prod;
    integer n;
    always @(posedge clk) prod <= pa * pb;

    reg [5:0]  s = 0, ret;
    reg [31:0] tt;
    reg [127:0] yv;
    reg [1:0]  k, l;
    reg [3:0]  ci; reg [1:0] ca, cb;
    reg signed [63:0] acc, y;
    reg [31:0] i, iend; reg [6:0] ri; reg [1:0] tk;
    reg signed [31:0] p;
    reg [3:0]  wi;
    reg [1:0]  mode;                                                  // scan: 0 = burst (<2500), 1 = flush
    wire signed [31:0] ylane = yv[32 * l +: 32];
    wire signed [15:0] vkl = V[{k, l}];

    always @(posedge clk) begin
        done <= 1'b0; ywe <= 1'b0; twe <= 1'b0; qwe <= 1'b0;
        mw_start <= 1'b0; mw_clear <= 1'b0; d_init <= 1'b0; d_start <= 1'b0;
        v_clr <= 1'b0; mk_clr <= 1'b0; msg_start <= 1'b0;
        if (w_valid && w_ready) w_valid <= 1'b0;
        if (clear) begin
            for (n = 0; n < 10; n = n + 1) cov[n] <= 0;
            nmtr[0] <= 0; nmtr[1] <= 0; nmtr[2] <= 0; nmtr[3] <= 0;
            twp[0] <= 0; twp[1] <= 0; twp[2] <= 0; twp[3] <= 0;
            nmpk <= 0; have_V <= 0; mk <= -1; mlast <= -1; mseg_t <= 0; mseg_end <= 0;
            w_valid <= 1'b0; mw_clear <= 1'b1; s <= 63;
        end else case (s)
        0: if (start) begin
            tt <= T; yv <= ym_in;
            if (T < MAT_INIT) begin ya <= T[11:0]; ywe <= 1'b1; ci <= 0; ca <= 0; cb <= 0; s <= (T >= 256) ? 1 : 4; end
            else begin k <= 0; ret <= 20; s <= 10; end                  // mat_det_step(T, ym)
        end
        // covariance accumulation (upper triangle, a <= b)
        1: begin pa <= $signed(yv[32 * ca +: 32]); pb <= $signed(yv[32 * cb +: 32]); s <= 2; end
        2: s <= 3;
        3: begin
            cov[ci] <= cov[ci] + prod; ci <= ci + 1'b1;
            if (cb == 3) begin
                if (ca == 3) s <= 4; else begin ca <= ca + 1'b1; cb <= ca + 1'b1; s <= 1; end
            end else begin cb <= cb + 1'b1; s <= 1; end
        end
        4: if (tt == MAT_INIT - 1) begin
               if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h80; msg_len <= 80; ci <= 0; s <= 5; end
           end else s <= 20;
        5: if (!w_valid) begin
               if (ci == 10) s <= 6;
               else begin w_valid <= 1'b1; w_data <= cov[ci]; w_nb <= 8; ci <= ci + 1'b1; end
           end
        6: if (v_valid) begin                                        // projections from the PC
               for (n = 0; n < 16; n = n + 1) V[n] <= v_q[16 * n +: 16];
               v_clr <= 1'b1; k <= 0; s <= 7;
           end
        7: begin d_init <= 1'b1; d_inst <= {1'b0, k}; s <= 8; end
        8: if (d_done) begin if (k == 3) begin i <= 0; s <= 9; end else begin k <= k + 1'b1; s <= 7; end end
        9: begin                                                     // replay t = 0 .. 2499
            if (i == MAT_INIT) begin have_V <= 1'b1; s <= 20; end
            else begin ya <= i[11:0]; s <= 18; end
        end
        18: s <= 19;
        19: begin yv <= yrd; tt <= i; k <= 0; ret <= 21; s <= 10; end
        21: begin i <= i + 1'b1; tt <= T; s <= 9; end
        // ---- mat_det_step(tt, yv): k = 0..3, then -> ret
        10: begin acc <= 0; l <= 0; s <= 11; end
        11: begin pa <= ylane; pb <= vkl; s <= 12; end
        12: s <= 13;
        13: begin
            acc <= acc + prod;
            if (l == 3) s <= 14; else begin l <= l + 1'b1; s <= 11; end
        end
        14: begin
            y = (acc + 64'sd8192) >>> 14;
            pa <= y; pb <= y; d_ab <= (y < 0) ? -y : y; s <= 15;
        end
        15: s <= 16;
        16: begin mw_inst <= {3'd0, k}; mw_sq <= prod; mw_start <= 1'b1; s <= 17; end
        17: if (mw_done) begin d_inst <= {1'b0, k}; d_t <= tt; d_e <= mw_sum; d_start <= 1'b1; s <= 22; end
        22: if (d_done) begin
            if (d_out >= 0) begin
                twe <= 1'b1; twa <= {k, 7'd0} + twp[k]; twd <= d_out;
                twp[k] <= (twp[k] == 95) ? 7'd0 : twp[k] + 1'b1;
                nmtr[k] <= nmtr[k] + 1'b1;
                p <= d_out; s <= 23;
            end else s <= 25;
        end
        23: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h81; msg_len <= 5; s <= 24; end
        24: if (!w_valid && w_ready) begin w_valid <= 1'b1; w_data <= {p, 6'd0, k}; w_nb <= 5; s <= 25; end
        25: if (!w_valid) begin if (k == 3) s <= ret; else begin k <= k + 1'b1; s <= 10; end end
        // ---- after detection at T: segment logic
        20: begin
            if (!have_V) s <= 62;
            else if (tt == MAT_INIT + LAGM) begin p <= MAT_INIT; s <= 30; end          // initial choice
            else if (mk >= 0 && tt == mseg_end + LAGM) begin mode <= 1; s <= 40; end   // flush, then choice
            else s <= 50;
        end
        // REQ_MK(p) -> mk
        30: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h82; msg_len <= 4; s <= 31; end
        31: if (!w_valid && w_ready) begin w_valid <= 1'b1; w_data <= p; w_nb <= 4; s <= 32; end
        32: if (!w_valid && mk_valid) begin
            mk_clr <= 1'b1;
            if (tt == MAT_INIT + LAGM) begin mk <= mk_in; mode <= 0; s <= 40; end      // emit burst of train k0
            else begin mk <= mk_in; mseg_t <= mseg_end; mseg_end <= mseg_end + MAT_HOP; s <= 50; end
        end
        // ---- scan train mk (mode 0: p < 2500; mode 1: flush segment)
        40: begin
            tk <= mk[1:0];
            i <= (nmtr[mk[1:0]] > 96) ? nmtr[mk[1:0]] - 96 : 0;
            ri <= (nmtr[mk[1:0]] > 96) ? twp[mk[1:0]] : 7'd0;
            s <= 41;
        end
        41: if (i >= nmtr[tk]) s <= (mode == 0) ? 48 : 49;
            else begin ta <= {tk, 7'd0} + ri; s <= 42; end
        42: s <= 43;
        43: begin
            p <= trd;
            if (mode == 0 ? (trd < MAT_INIT) : (trd >= mseg_t && trd < mseg_end && trd > mlast)) s <= 44;
            else s <= 47;
        end
        44: begin                                                    // mat_emit(p); mlast = p
            mlast <= p;
            if (nmpk > 0 && p - lastp < 75) s <= 47;
            else begin
                qwe <= 1'b1; qwa <= nmpk[8:0]; qwd <= p; nmpk <= nmpk + 1'b1; lastp <= p;
                s <= 45;
            end
        end
        45: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h83; msg_len <= 4; s <= 46; end
        46: if (!w_valid && w_ready) begin w_valid <= 1'b1; w_data <= p; w_nb <= 4; s <= 47; end
        47: if (!w_valid) begin i <= i + 1'b1; ri <= (ri == 95) ? 7'd0 : ri + 1'b1; s <= 41; end
        48: begin mseg_t <= MAT_INIT; mseg_end <= MAT_INIT + MAT_HOP; s <= 50; end      // after the burst
        49: begin p <= mseg_end; s <= 30; end                                          // after flush: choose
        // ---- every sample with a train: flush
        50: if (mk >= 0) begin mode <= 1; s <= 51; end else s <= 62;
        51: begin
            tk <= mk[1:0];
            i <= (nmtr[mk[1:0]] > 96) ? nmtr[mk[1:0]] - 96 : 0;
            ri <= (nmtr[mk[1:0]] > 96) ? twp[mk[1:0]] : 7'd0;
            s <= 52;
        end
        52: if (i >= nmtr[tk]) s <= 62;
            else begin ta <= {tk, 7'd0} + ri; s <= 53; end
        53: s <= 54;
        54: begin
            p <= trd;
            if (trd >= mseg_t && trd < mseg_end && trd > mlast) s <= 55; else s <= 58;
        end
        55: begin
            mlast <= p;
            if (nmpk > 0 && p - lastp < 75) s <= 58;
            else begin qwe <= 1'b1; qwa <= nmpk[8:0]; qwd <= p; nmpk <= nmpk + 1'b1; lastp <= p; s <= 56; end
        end
        56: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h83; msg_len <= 4; s <= 57; end
        57: if (!w_valid && w_ready) begin w_valid <= 1'b1; w_data <= p; w_nb <= 4; s <= 58; end
        58: if (!w_valid) begin i <= i + 1'b1; ri <= (ri == 95) ? 7'd0 : ri + 1'b1; s <= 52; end
        62: begin done <= 1'b1; s <= 0; end
        63: if (mw_done) s <= 0;
        default: s <= 0;
        endcase
    end
endmodule

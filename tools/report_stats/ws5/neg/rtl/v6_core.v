// FECG v6 - core: link layer + per-sample sequencer (the order of fm_push in the C model)
//   pop sample -> front end -> maternal -> cancellation -> calibration data -> tracks (s=T-176)
//   -> DONE after the last sample of each SAMPLES frame.
`timescale 1ns / 1ps

module v6_core (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] rx_data,
    input  wire       rx_valid,
    output wire [7:0] tx_data,
    output wire       tx_valid,
    input  wire       tx_ready,
    output wire [7:0] status
);
    // ---------------- link
    wire smp_empty, smp_last, soft_reset, err, flush;
    reg  smp_pop;
    wire [63:0] smp_x;
    wire v_valid, mk_valid, basis_valid, cal_valid, sel_valid;
    wire v_clr, mk_clr, basis_clr, cal_clr, sel_clr;
    wire [255:0] v_q; wire [1:0] mk; wire [7:0] basis_nb; wire [10:0] basis_raddr; wire signed [23:0] basis_rdata;
    wire [4:0] cal_ntr; wire [15:0] cal_kind, cal_src, cal_blank; wire [1023:0] cal_w; wire [3:0] sel;
    reg  msg_start; reg [7:0] msg_cmd; reg [15:0] msg_len; wire msg_idle_l, msg_idle;
    reg  w_valid; reg [63:0] w_data; reg [3:0] w_nb; wire w_ready;
    v6_link link(.clk(clk), .rst(rst | soft_reset), .rx_data(rx_data), .rx_valid(rx_valid), .tx_data(tx_data), .tx_valid(tx_valid), .tx_ready(tx_ready),
        .smp_empty(smp_empty), .smp_pop(smp_pop), .smp_x(smp_x), .smp_last(smp_last), .soft_reset(soft_reset), .flush(flush), .err(err),
        .v_valid(v_valid), .v_clr(v_clr), .v_q(v_q), .mk_valid(mk_valid), .mk_clr(mk_clr), .mk(mk),
        .basis_valid(basis_valid), .basis_clr(basis_clr), .basis_nb(basis_nb), .basis_raddr(basis_raddr), .basis_rdata(basis_rdata),
        .cal_valid(cal_valid), .cal_clr(cal_clr), .cal_ntr(cal_ntr), .cal_kind(cal_kind), .cal_src(cal_src), .cal_blank(cal_blank), .cal_w(cal_w),
        .sel_valid(sel_valid), .sel_clr(sel_clr), .sel(sel),
        .msg_start(msg_start), .msg_cmd(msg_cmd), .msg_len(msg_len), .msg_idle(msg_idle_l),
        .w_valid(w_valid), .w_data(w_data), .w_nb(w_nb), .w_ready(w_ready));

    // ---------------- rings (Xf, Z): 4096 x 4 x s16
    (* ram_style = "block" *) reg [63:0] xring [0:4095];
    (* ram_style = "block" *) reg [63:0] zring [0:4095];
    reg [11:0] xr_ra, zr_ra; reg [63:0] xr_rd, zr_rd;
    wire       fe_we;  wire [11:0] fe_wa;  wire [63:0] fe_wd;
    wire       ca_zwe; wire [11:0] ca_zwa; wire [63:0] ca_zwd;
    wire        z_we = fe_we | ca_zwe;                // one write port: front end or canceller
    wire [11:0] z_wa = fe_we ? fe_wa : ca_zwa;
    wire [63:0] z_wd = fe_we ? fe_wd : ca_zwd;
    always @(posedge clk) begin
        if (fe_we) xring[fe_wa] <= fe_wd;
        xr_rd <= xring[xr_ra];
    end
    always @(posedge clk) begin
        if (z_we) zring[z_wa] <= z_wd;
        zr_rd <= zring[zr_ra];
    end

    // shared memory ports (memory below): v6_mat writes/reads it only for T < 2500,
    // v6_trk only once calibrated (s >= 3750), so the two uses never overlap
    wire        y_we, e_we;
    wire [14:0] y_a, e_ra, e_wa;
    wire [12:0] y_wd;
    wire [15:0] e_wd;
    reg  [12:0] u_rd;

    // ---------------- units
    reg clear, fe_go, mat_go, ca_go, tk_go;
    reg [31:0] T;
    reg [63:0] xs;
    wire fe_done, mat_done, ca_done, tk_done;
    wire [127:0] ym;
    v6_fe fe(.clk(clk), .clear(clear), .start(fe_go), .x(xs), .T(T), .done(fe_done), .ym(ym),
             .ring_we(fe_we), .ring_wa(fe_wa), .ring_wd(fe_wd));

    wire [31:0] nmpk; wire [8:0] mt_mpk_ra; reg [8:0] mpk_ra; wire signed [31:0] mpk_rd;
    wire mt_ms, mt_wv; wire [7:0] mt_mc; wire [15:0] mt_ml; wire [63:0] mt_wd; wire [3:0] mt_wn;
    v6_mat mat(.clk(clk), .clear(clear), .start(mat_go), .T(T), .ym_in(ym), .done(mat_done),
               .ya(y_a), .ywe(y_we), .ywd(y_wd), .yrd(u_rd),
               .v_valid(v_valid), .v_q(v_q), .v_clr(v_clr), .mk_valid(mk_valid), .mk_in(mk), .mk_clr(mk_clr),
               .nmpk(nmpk), .mpk_ra(mpk_ra), .mpk_rd(mpk_rd),
               .msg_start(mt_ms), .msg_cmd(mt_mc), .msg_len(mt_ml), .msg_idle(msg_idle),
               .w_valid(mt_wv), .w_data(mt_wd), .w_nb(mt_wn), .w_ready(w_ready));

    wire [8:0] ca_mpk_ra; wire [11:0] ca_xra, ca_zra;
    wire ca_ms, ca_wv; wire [7:0] ca_mc; wire [15:0] ca_ml; wire [63:0] ca_wd; wire [3:0] ca_wn;
    v6_canc canc(.clk(clk), .clear(clear), .start(ca_go), .T(T), .done(ca_done),
                 .nmpk(nmpk), .mpk_ra(ca_mpk_ra), .mpk_rd(mpk_rd),
                 .xr_ra(ca_xra), .xr_rd(xr_rd), .zr_ra(ca_zra), .zr_rd(zr_rd), .zr_we(ca_zwe), .zr_wa(ca_zwa), .zr_wd(ca_zwd),
                 .basis_valid(basis_valid), .basis_nb(basis_nb), .basis_raddr(basis_raddr), .basis_rdata(basis_rdata), .basis_clr(basis_clr),
                 .msg_start(ca_ms), .msg_cmd(ca_mc), .msg_len(ca_ml), .msg_idle(msg_idle),
                 .w_valid(ca_wv), .w_data(ca_wd), .w_nb(ca_wn), .w_ready(w_ready));

    wire [8:0] tk_mpk_ra; wire [11:0] tk_xra, tk_zra;
    wire tk_ms, tk_wv; wire [7:0] tk_mc; wire [15:0] tk_ml; wire [63:0] tk_wd; wire [3:0] tk_wn;
    v6_trk trk(.clk(clk), .clear(clear), .start(tk_go), .s_in(T - 32'd176), .done(tk_done),
               .cal_valid(cal_valid), .cal_ntr(cal_ntr), .cal_kind(cal_kind), .cal_src(cal_src), .cal_blank(cal_blank), .cal_w(cal_w), .cal_clr(cal_clr),
               .sel_valid(sel_valid), .sel_in(sel), .sel_clr(sel_clr),
               .nmpk(nmpk), .mpk_ra(tk_mpk_ra), .mpk_rd(mpk_rd),
               .xr_ra(tk_xra), .xr_rd(xr_rd), .zr_ra(tk_zra), .zr_rd(zr_rd),
               .ea(e_ra), .erd({3'd0, u_rd}), .ewe(e_we), .ewa(e_wa), .ewd(e_wd),
               .msg_start(tk_ms), .msg_cmd(tk_mc), .msg_len(tk_ml), .msg_idle(msg_idle),
               .w_valid(tk_wv), .w_data(tk_wd), .w_nb(tk_wn), .w_ready(w_ready));

    // ---------------- v7-DL look-ahead unit (listens to the uplink words; ph 5 when it runs)
    reg v7_go, v7_fl, v_seen;
    wire v7_busy, v7_want, v7_done;
    wire v7_ms, v7_wv; wire [7:0] v7_mc; wire [15:0] v7_ml; wire [63:0] v7_wd; wire [3:0] v7_wn;
`ifdef V7
    v7_la v7(.clk(clk), .clear(clear), .t_ms(msg_start), .t_mc(msg_cmd), .t_wv(w_valid & w_ready), .t_wd(w_data),
             .v_seen(v_seen), .v_q(v_q), .mk(mk), .busy(v7_busy),
             .start(v7_go), .fl(v7_fl), .T(T), .want(v7_want), .done(v7_done),
             .msg_start(v7_ms), .msg_cmd(v7_mc), .msg_len(v7_ml), .msg_idle(msg_idle),
             .w_valid(v7_wv), .w_data(v7_wd), .w_nb(v7_wn), .w_ready(w_ready));
    assign msg_idle = msg_idle_l & ~v7_busy;      // FEAT shape math in progress: hold new messages
`else
    assign v7_busy = 1'b0, v7_want = 1'b0, v7_done = 1'b0, v7_ms = 1'b0, v7_wv = 1'b0;
    assign v7_mc = 0, v7_ml = 0, v7_wd = 0, v7_wn = 0;
    assign msg_idle = msg_idle_l;
`endif
    always @(posedge clk) if (rst || soft_reset) v_seen <= 1'b0; else if (v_valid) v_seen <= 1'b1;

    // ---------------- port muxes (by active unit)
    reg [2:0] ph;                               // 0 core, 1 fe, 2 mat, 3 canc, 4 trk
    reg c_ms, c_wv; reg [7:0] c_mc; reg [15:0] c_ml; reg [63:0] c_wd; reg [3:0] c_wn;
    reg [11:0] c_ra;
    always @* begin
        case (ph)
        3'd2: begin msg_start = mt_ms; msg_cmd = mt_mc; msg_len = mt_ml; w_valid = mt_wv; w_data = mt_wd; w_nb = mt_wn; end
        3'd3: begin msg_start = ca_ms; msg_cmd = ca_mc; msg_len = ca_ml; w_valid = ca_wv; w_data = ca_wd; w_nb = ca_wn; end
        3'd4: begin msg_start = tk_ms; msg_cmd = tk_mc; msg_len = tk_ml; w_valid = tk_wv; w_data = tk_wd; w_nb = tk_wn; end
        3'd5: begin msg_start = v7_ms; msg_cmd = v7_mc; msg_len = v7_ml; w_valid = v7_wv; w_data = v7_wd; w_nb = v7_wn; end
        default: begin msg_start = c_ms; msg_cmd = c_mc; msg_len = c_ml; w_valid = c_wv; w_data = c_wd; w_nb = c_wn; end
        endcase
        case (ph)
        3'd3: begin xr_ra = ca_xra; zr_ra = ca_zra; mpk_ra = ca_mpk_ra; end
        3'd4: begin xr_ra = tk_xra; zr_ra = tk_zra; mpk_ra = tk_mpk_ra; end
        default: begin xr_ra = c_ra; zr_ra = c_ra; mpk_ra = 9'd0; end
        endcase
    end

    // ---------------- shared memory, 32K x 13: maternal samples (10 words each, T < 2500),
    // then track envelope codes (enc_e < 2^13). Saves the separate 2500 x 128 ymem.
    (* ram_style = "block" *) reg [12:0] umem [0:32767];
    wire        u_we = y_we | e_we;
    wire [14:0] u_wa = y_we ? y_a : e_wa;
    wire [12:0] u_wd = y_we ? y_wd : e_wd[12:0];
    wire [14:0] u_ra = (ph == 3'd2) ? y_a : e_ra;
    always @(posedge clk) begin
        if (u_we) umem[u_wa] <= u_wd;
        u_rd <= umem[u_ra];
    end

    // ---------------- sequencer
    localparam S_RST = 0, S_RW = 1, S_IDLE = 2, S_P1 = 3, S_P2 = 4, S_FE = 5, S_MAT = 6, S_CA = 7,
               S_CD0 = 8, S_CD1 = 9, S_CD2 = 10, S_CD3 = 11, S_CD4 = 12, S_CD5 = 13, S_CD6 = 14, S_CD7 = 15,
               S_TK0 = 16, S_TK = 17, S_DN = 18, S_DN2 = 19, S_NX = 20, S_V0 = 21, S_V1 = 22, S_VF = 23;
`ifdef V7
    localparam S_AFTK = S_V0;                   // v7 step after the tracks
`else
    localparam S_AFTK = S_DN;
`endif
    reg flush_pend;
    reg [4:0]  st = S_RST;
    reg [11:0] cnt;
    reg        last;
    reg [31:0] zc, n, j;
    wire [31:0] lim1 = 32'd3750 - zc, lim2 = T - 32'd176 - zc + 32'd1;
    always @(posedge clk) begin
        clear <= 1'b0; fe_go <= 1'b0; mat_go <= 1'b0; ca_go <= 1'b0; tk_go <= 1'b0; v7_go <= 1'b0;
        if (flush) flush_pend <= 1'b1;
        smp_pop <= 1'b0; c_ms <= 1'b0;
        if (c_wv && w_ready && ph == 0) c_wv <= 1'b0;
        if (rst || soft_reset) st <= S_RST;
        else case (st)
        S_RST: begin clear <= 1'b1; cnt <= 0; T <= 0; zc <= 750; ph <= 0; c_wv <= 1'b0; flush_pend <= 1'b0; st <= S_RW; end
        S_RW: if (cnt == 12'd4000) st <= S_IDLE; else cnt <= cnt + 1'b1;
        S_IDLE: if (!smp_empty) st <= S_P1;
                else if (flush_pend) begin flush_pend <= 1'b0; ph <= 5; v7_go <= 1'b1; v7_fl <= 1'b1; st <= S_VF; end
        S_VF: if (v7_done) begin ph <= 0; st <= S_IDLE; end
        S_P1: st <= S_P2;
        S_P2: begin xs <= smp_x; last <= smp_last; smp_pop <= 1'b1; ph <= 1; fe_go <= 1'b1; st <= S_FE; end
        S_FE: if (fe_done) begin ph <= 2; mat_go <= 1'b1; st <= S_MAT; end
        S_MAT: if (mat_done) begin ph <= 3; ca_go <= 1'b1; st <= S_CA; end
        S_CA: if (ca_done) begin ph <= 0; st <= S_CD0; end
        // calibration data (Z, Xf) for the PC
        S_CD0: if (T > 2718 && zc < 3750 && zc + 176 <= T) begin
                   n <= (lim1 < lim2) ? ((lim1 < 2048) ? lim1 : 2048) : ((lim2 < 2048) ? lim2 : 2048);
                   st <= S_CD1;
               end else st <= S_TK0;
        S_CD1: if (msg_idle) begin c_ms <= 1'b1; c_mc <= 8'h85; c_ml <= 6 + 16 * n[15:0]; st <= S_CD2; end
        S_CD2: if (!c_wv && w_ready) begin c_wv <= 1'b1; c_wd <= {n[15:0], zc}; c_wn <= 6; j <= 0; st <= S_CD3; end
        S_CD3: if (!c_wv) begin c_ra <= zc[11:0] + j[11:0]; st <= S_CD4; end
        S_CD4: st <= S_CD5;
        S_CD5: if (w_ready) begin c_wv <= 1'b1; c_wd <= zr_rd; c_wn <= 8; st <= S_CD6; end
        S_CD6: if (!c_wv && w_ready) begin c_wv <= 1'b1; c_wd <= xr_rd; c_wn <= 8; st <= S_CD7; end
        S_CD7: if (!c_wv) begin
                   if (j + 1 == n) begin zc <= zc + n; st <= S_TK0; end
                   else begin j <= j + 1; st <= S_CD3; end
               end
        S_TK0: if (T >= 176) begin ph <= 4; tk_go <= 1'b1; st <= S_TK; end else st <= S_AFTK;
        S_TK: if (tk_done) begin ph <= 0; st <= S_AFTK; end
        S_V0: if (v7_want) begin ph <= 5; v7_go <= 1'b1; v7_fl <= 1'b0; st <= S_V1; end else st <= S_DN;
        S_V1: if (v7_done) begin ph <= 0; st <= S_DN; end
        S_DN: if (last) begin
                  if (msg_idle) begin c_ms <= 1'b1; c_mc <= 8'h8C; c_ml <= 4; st <= S_DN2; end
              end else st <= S_NX;
        S_DN2: if (!c_wv && w_ready) begin c_wv <= 1'b1; c_wd <= T + 1; c_wn <= 4; st <= S_NX; end
        S_NX: if (!c_wv) begin T <= T + 1; st <= S_IDLE; end
        default: st <= S_RST;
        endcase
    end

    reg calibrated_seen;
    always @(posedge clk) if (rst || soft_reset) calibrated_seen <= 1'b0; else if (cal_valid) calibrated_seen <= 1'b1;
    assign status = {err, ~smp_empty, calibrated_seen, 2'b00, ph};
endmodule

// FECG v6 - per-lead maternal template cancellation (cancel_beat in the C model).
// For every maternal peak p whose segment [p-44, p+114) has arrived:
//   lag = argmax_k sum_i sum_l Xf[p+k-40+i][l] * hsum[i][l]   (k = -4..4, if history)
//   seg = Xf[p+lag-40 .. p+lag+110)
//   if >= 4 beats of history: wait for the PC basis (orthonormal, s24 Q22, nb <= 3/lead)
//       c_j = rnd(<bo_j, seg>, 14);  fit = rnd(sum_j c_j bo_j, 22)  (Q8)
//       Z = sat16(rnd((seg << 8) - rnd(fit * taper, 15), 8))
//   history (last 20 beats) += seg; send SEG(p, seg)
`timescale 1ns / 1ps

module v6_canc (
    input  wire               clk,
    input  wire               clear,
    input  wire               start,
    input  wire [31:0]        T,
    output reg                done,
    input  wire [31:0]        nmpk,
    output reg  [8:0]         mpk_ra,
    input  wire signed [31:0] mpk_rd,
    output reg  [11:0]        xr_ra,
    input  wire [63:0]        xr_rd,
    output reg  [11:0]        zr_ra,
    input  wire [63:0]        zr_rd,
    output reg                zr_we,
    output reg  [11:0]        zr_wa,
    output reg  [63:0]        zr_wd,
    input  wire               basis_valid,
    input  wire [7:0]         basis_nb,
    output reg  [10:0]        basis_raddr,
    input  wire signed [23:0] basis_rdata,
    output reg                basis_clr,
    output reg                msg_start,
    output reg  [7:0]         msg_cmd,
    output reg  [15:0]        msg_len,
    input  wire               msg_idle,
    output reg                w_valid,
    output reg  [63:0]        w_data,
    output reg  [3:0]         w_nb,
    input  wire               w_ready
);
    // memories
    reg [63:0] hist [0:2999];                                         // 20 beats x 150 x 4 x s16
    reg [11:0] ha, hwa; reg hwe; reg [63:0] hwd, hrd;
    always @(posedge clk) begin if (hwe) hist[hwa] <= hwd; hrd <= hist[ha]; end
    reg [127:0] hsum [0:149];                                         // 4 x s32
    reg [7:0] sa, swa; reg swe; reg [127:0] swd, srd;
    always @(posedge clk) begin if (swe) hsum[swa] <= swd; srd <= hsum[sa]; end
    reg [63:0] seg [0:149];
    reg [7:0] ga, gwa; reg gwe; reg [63:0] gwd, grd;
    always @(posedge clk) begin if (gwe) seg[gwa] <= gwd; grd <= seg[ga]; end

    function [15:0] tap(input [7:0] i);
        reg [7:0] j;
        begin
            j = (i < 8) ? i : (i > 141) ? 8'd149 - i : 8'd8;
            case (j)
            0: tap = 0; 1: tap = 4681; 2: tap = 9362; 3: tap = 14043; 4: tap = 18725; 5: tap = 23406; 6: tap = 28087;
            default: tap = 32768;
            endcase
        end
    endfunction
    function signed [15:0] sat16(input signed [63:0] v);
        sat16 = (v > 32767) ? 16'sh7FFF : (v < -32768) ? 16'sh8000 : v[15:0];
    endfunction

    reg [31:0] mproc;
    reg [4:0]  nhist, hhead;
    reg [5:0]  s = 0;
    reg signed [31:0] p, kk;
    reg [7:0]  i;
    reg [3:0]  k;
    reg signed [63:0] c, bc, a, f;
    reg signed [63:0] fit8, zq;                                       // combinational temporaries
    reg signed [3:0] lag;
    reg [1:0]  l, j, nb;
    reg signed [63:0] cj [0:2];
    reg signed [63:0] pr0, pr1, pr2, pr3;
    reg [8:0]  cnt;
    integer n;
    wire [11:0] ring_i = p[11:0] - 12'd40 + {4'd0, i};               // (p - 40 + i) & 4095

    always @(posedge clk) begin
        done <= 1'b0; hwe <= 1'b0; swe <= 1'b0; gwe <= 1'b0; zr_we <= 1'b0;
        basis_clr <= 1'b0; msg_start <= 1'b0;
        if (w_valid && w_ready) w_valid <= 1'b0;
        if (clear) begin
            mproc <= 0; nhist <= 0; hhead <= 0; cnt <= 0; w_valid <= 1'b0; s <= 60;
        end else case (s)
        0: if (start) s <= 1;
        // ---- loop over pending maternal peaks
        1: if (mproc < nmpk) begin mpk_ra <= mproc[8:0]; s <= 2; end else begin done <= 1'b1; s <= 0; end
        2: s <= 3;
        3: begin
            p <= mpk_rd;
            if (mpk_rd + 114 > $signed(T)) begin done <= 1'b1; s <= 0; end
            else if (mpk_rd - 44 >= 0 && mpk_rd - 44 > $signed(T) - 4095) s <= 4;
            else begin mproc <= mproc + 1'b1; s <= 1; end
        end
        // ---- lag search
        4: begin
            if (nhist >= 1) begin k <= 0; lag <= 0; s <= 5; end
            else begin lag <= 0; s <= 12; end
        end
        5: begin c <= 0; i <= 0; s <= 6; end
        6: begin xr_ra <= p[11:0] + {8'd0, k} - 12'd44 + {4'd0, i}; sa <= i; s <= 7; end   // p + (k-4) - 40 + i
        7: s <= 8;
        8: begin
            pr0 <= $signed(xr_rd[15:0])  * $signed(srd[31:0]);
            pr1 <= $signed(xr_rd[31:16]) * $signed(srd[63:32]);
            pr2 <= $signed(xr_rd[47:32]) * $signed(srd[95:64]);
            pr3 <= $signed(xr_rd[63:48]) * $signed(srd[127:96]);
            s <= 9;
        end
        9: begin
            c <= c + pr0 + pr1 + pr2 + pr3;
            if (i == 149) s <= 10; else begin i <= i + 1'b1; s <= 6; end
        end
        10: begin
            if (k == 0 || c > bc) begin bc <= c; lag <= $signed({1'b0, k}) - 4'sd4; end
            if (k == 8) s <= 11; else begin k <= k + 1'b1; s <= 5; end
        end
        11: begin p <= p + lag; s <= 12; end
        // ---- segment
        12: begin i <= 0; s <= 13; end
        13: begin xr_ra <= ring_i; s <= 14; end
        14: s <= 15;
        15: begin
            gwe <= 1'b1; gwa <= i; gwd <= xr_rd;
            if (i == 149) s <= (nhist >= 4) ? 16 : 40; else begin i <= i + 1'b1; s <= 13; end
        end
        // ---- fit and subtract, lead by lead
        16: if (basis_valid) begin l <= 0; s <= 17; end
        17: begin nb <= basis_nb[2 * l +: 2]; j <= 0; s <= 18; end
        18: if (j == nb) begin i <= 0; s <= (nb == 0) ? 30 : 24; end
            else begin a <= 0; i <= 0; s <= 19; end
        19: begin ga <= i; basis_raddr <= {9'd0, l} * 11'd450 + {9'd0, j} * 11'd150 + {3'd0, i}; s <= 20; end
        20: s <= 21;
        21: begin a <= a + basis_rdata * $signed(grd[16 * l +: 16]); s <= 22; end
        22: if (i == 149) s <= 23; else begin i <= i + 1'b1; s <= 19; end
        23: begin cj[j] <= (a + 64'sd8192) >>> 14; j <= j + 1'b1; s <= 18; end
        // per sample: f = sum_j c_j bo_j[i]
        24: begin f <= 0; j <= 0; ga <= i; zr_ra <= ring_i; s <= 25; end
        25: begin basis_raddr <= {9'd0, l} * 11'd450 + {9'd0, j} * 11'd150 + {3'd0, i}; s <= 26; end
        26: s <= 27;
        27: begin
            f <= f + cj[j] * basis_rdata;
            if (j + 1'b1 == nb) s <= 28; else begin j <= j + 1'b1; s <= 25; end
        end
        28: begin                                                    // grd = seg[i], zr_rd = Z word
            fit8 = (f + 64'sd2097152) >>> 22;                         // fit, Q8
            zq = ($signed(grd[16 * l +: 16]) <<< 8) - ((fit8 * $signed({1'b0, tap(i)}) + 64'sd16384) >>> 15);
            zr_wd <= zr_rd;
            zr_wd[16 * l +: 16] <= sat16((zq + 64'sd128) >>> 8);
            zr_wa <= ring_i; zr_we <= 1'b1;
            s <= 29;
        end
        29: if (i == 149) s <= 30; else begin i <= i + 1'b1; s <= 24; end
        30: if (l == 3) begin basis_clr <= 1'b1; s <= 40; end else begin l <= l + 1'b1; s <= 17; end
        // ---- history update
        40: begin i <= 0; s <= 41; end
        41: begin ha <= hhead * 8'd150 + i; sa <= i; ga <= i; s <= 42; end
        42: s <= 43;
        43: begin
            hwe <= 1'b1; hwa <= ha; hwd <= grd;
            for (n = 0; n < 4; n = n + 1)
                swd[32 * n +: 32] <= $signed(srd[32 * n +: 32]) + $signed(grd[16 * n +: 16])
                                     - ((nhist >= 20) ? $signed(hrd[16 * n +: 16]) : 32'sd0);
            swe <= 1'b1; swa <= i;
            if (i == 149) s <= 44; else begin i <= i + 1'b1; s <= 41; end
        end
        44: begin
            hhead <= (hhead == 19) ? 5'd0 : hhead + 1'b1;
            if (nhist < 20) nhist <= nhist + 1'b1;
            s <= 45;
        end
        // ---- SEG message
        45: if (msg_idle) begin msg_start <= 1'b1; msg_cmd <= 8'h84; msg_len <= 1204; s <= 46; end
        46: if (!w_valid && w_ready) begin w_valid <= 1'b1; w_data <= p; w_nb <= 4; i <= 0; s <= 47; end
        47: if (!w_valid) begin ga <= i; s <= 48; end
        48: s <= 49;
        49: if (!w_valid && w_ready) begin
            w_valid <= 1'b1; w_data <= grd; w_nb <= 8;
            if (i == 149) s <= 50; else begin i <= i + 1'b1; s <= 47; end
        end
        50: if (!w_valid) begin mproc <= mproc + 1'b1; s <= 1; end
        // ---- clear hsum
        60: begin swe <= 1'b1; swa <= cnt[7:0]; swd <= 0; if (cnt == 149) s <= 0; cnt <= cnt + 1'b1; end
        default: s <= 0;
        endcase
    end
endmodule

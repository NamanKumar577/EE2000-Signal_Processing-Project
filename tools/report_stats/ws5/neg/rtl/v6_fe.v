// FECG v6 - front end, per lead: HP1 baseline removal (Q8 out), LP SOS -> Xf (int16),
// maternal-band SOS -> ym (Q8).  Writes Xf into the Xf and Z rings at T.
`timescale 1ns / 1ps

module v6_fe (
    input  wire               clk,
    input  wire               clear,        // pulse: reset state
    input  wire               start,
    input  wire [63:0]        x,            // 4 x s16 raw
    input  wire [31:0]        T,
    output reg                done,
    output reg  [127:0]       ym,           // 4 x s32 Q8
    // ring write port (Xf and Z rings, same data)
    output reg                ring_we,
    output reg  [11:0]        ring_wa,
    output reg  [63:0]        ring_wd
);
    reg signed [63:0] B [0:3];
    reg [1:0] l;
    reg [2:0] s = 0;
    reg sos_start, sos_clear; reg [4:0] sos_inst; reg [1:0] sos_set; reg signed [31:0] sos_x;
    wire sos_busy, sos_done; wire signed [31:0] sos_y;
    v6_sos #(.NINST(8)) sos(.clk(clk), .clear(sos_clear), .start(sos_start), .inst(sos_inst), .fset(sos_set), .x(sos_x),
                            .copy(1'b0), .copy_from(5'd0), .busy(sos_busy), .done(sos_done), .y(sos_y));
    reg signed [31:0] h;
    reg [63:0] xfw;
    wire signed [15:0] xl = x[16 * l +: 16];
    // rnd(xf, 8) saturated to int16
    function [15:0] q16(input signed [31:0] v);
        reg signed [31:0] r;
        begin
            r = (v + 32'sd128) >>> 8;
            q16 = (r > 32767) ? 16'h7FFF : (r < -32768) ? 16'h8000 : r[15:0];
        end
    endfunction
    always @(posedge clk) begin
        sos_start <= 1'b0; sos_clear <= 1'b0; done <= 1'b0; ring_we <= 1'b0;
        if (clear) begin
            B[0] <= 0; B[1] <= 0; B[2] <= 0; B[3] <= 0; sos_clear <= 1'b1; s <= 6;
        end else case (s)
        0: if (start) begin l <= 0; s <= 1; end
        1: begin                                                     // HP1 then LP
            h = ($signed({{48{xl[15]}}, xl}) <<< 8) - ((B[l] + 64'sd128) >>> 8);
            B[l] <= B[l] + ((($signed({{48{xl[15]}}, xl}) <<< 16) - B[l]) >>> 6);
            sos_inst <= {3'd0, l}; sos_set <= 2'd0; sos_x <= h; sos_start <= 1'b1;
            s <= 2;
        end
        2: if (sos_done) begin
            xfw[16 * l +: 16] <= q16(sos_y);
            sos_inst <= {3'd1, l}; sos_set <= 2'd1; sos_x <= h; sos_start <= 1'b1;   // maternal band
            s <= 3;
        end
        3: if (sos_done) begin
            ym[32 * l +: 32] <= sos_y;
            if (l == 3) s <= 4; else begin l <= l + 1'b1; s <= 1; end
        end
        4: begin ring_we <= 1'b1; ring_wa <= T[11:0]; ring_wd <= xfw; done <= 1'b1; s <= 0; end
        6: if (sos_done) s <= 0;                                     // clearing
        default: s <= 0;
        endcase
    end
endmodule

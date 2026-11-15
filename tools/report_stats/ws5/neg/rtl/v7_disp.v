// FECG v7-DL - shows the final answer on the Boolean board's two 4-digit displays.
// It reads the uplink bytes as they leave for the UART (no change to the stream):
//   display 0: fetal heart rate in bpm of the latest OUT7 frame ("----" before the first one)
//   display 1: number of final beats sent (OUT7 frames, modulo 10000)
// Both are cleared when a new recording starts (COV frame, sent once per run at 10 s).
// Segments and anodes are active low; seg[6:0] = g..a, seg[7] = decimal point, an[0] = right digit.
`timescale 1ns / 1ps

module v7_disp (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] tx_byte,
    input  wire       tx_stb,          // tx_byte accepted by the UART
    output reg  [3:0] an0,
    output reg  [7:0] seg0,
    output reg  [3:0] an1,
    output reg  [7:0] seg1
);
    // ---------------- uplink frame parser: A5 5A cmd len_lo len_hi payload xor
    reg [2:0]  ps;
    reg [7:0]  cmd;
    reg [15:0] len, pi;
    reg [15:0] f10, f10s;
    reg        have;
    reg [15:0] cnt;                     // 4 BCD digits
    always @(posedge clk) begin
        if (rst) begin ps <= 0; have <= 1'b0; cnt <= 0; f10s <= 0; end
        else if (tx_stb) case (ps)
            0: if (tx_byte == 8'hA5) ps <= 1;
            1: ps <= (tx_byte == 8'h5A) ? 3'd2 : (tx_byte == 8'hA5 ? 3'd1 : 3'd0);
            2: begin cmd <= tx_byte; ps <= 3; end
            3: begin len[7:0] <= tx_byte; ps <= 4; end
            4: begin len[15:8] <= tx_byte; pi <= 0; ps <= ({tx_byte, len[7:0]} == 0) ? 3'd6 : 3'd5; end
            5: begin
                if (cmd == 8'h8D && pi == 4) f10[7:0] <= tx_byte;
                if (cmd == 8'h8D && pi == 5) f10[15:8] <= tx_byte;
                pi <= pi + 1'b1;
                if (pi + 1'b1 == len) ps <= 6;
            end
            6: begin                     // checksum byte: frame complete
                ps <= 0;
                if (cmd == 8'h80) begin have <= 1'b0; cnt <= 0; end
                if (cmd == 8'h8D) begin
                    if (f10 != 0) begin f10s <= f10; have <= 1'b1; end
                    cnt <= bcd_inc(cnt);
                end
            end
            default: ps <= 0;
        endcase
    end

    function [15:0] bcd_inc(input [15:0] v);
        reg [15:0] r; integer i; reg c;
        begin
            r = v; c = 1'b1;
            for (i = 0; i < 4; i = i + 1)
                if (c) begin
                    if (r[4 * i +: 4] == 4'd9) r[4 * i +: 4] = 4'd0;
                    else begin r[4 * i +: 4] = r[4 * i +: 4] + 1'b1; c = 1'b0; end
                end
            bcd_inc = r;
        end
    endfunction

    // ---------------- FHR in bpm (rounded) -> 3 digits, registered
    reg [8:0] bpm;
    reg [3:0] h, t, u;
    always @(posedge clk) begin
        bpm <= (f10s + 16'd5) / 16'd10;
        h <= bpm / 100;
        t <= (bpm / 10) % 10;
        u <= bpm % 10;
    end

    function [7:0] seg7(input [4:0] d);           // 0-9, 10 = blank, 11 = '-'; active low
        case (d)
        0: seg7 = ~8'b0011_1111;  1: seg7 = ~8'b0000_0110;  2: seg7 = ~8'b0101_1011;  3: seg7 = ~8'b0100_1111;
        4: seg7 = ~8'b0110_0110;  5: seg7 = ~8'b0110_1101;  6: seg7 = ~8'b0111_1101;  7: seg7 = ~8'b0000_0111;
        8: seg7 = ~8'b0111_1111;  9: seg7 = ~8'b0110_1111;  11: seg7 = ~8'b0100_0000;
        default: seg7 = 8'hFF;
        endcase
    endfunction

    // ---------------- multiplexing: each digit lit 1/4 of the time (~190 Hz frame rate)
    reg [17:0] rc;
    always @(posedge clk) rc <= rc + 1'b1;
    wire [1:0] dg = rc[17:16];
    reg [4:0] d0, d1;
    always @* begin
        case (dg)                       // display 0: FHR
        0: d0 = have ? {1'b0, u} : 5'd11;
        1: d0 = have ? ((h != 0 || t != 0) ? {1'b0, t} : 5'd10) : 5'd11;
        2: d0 = have ? ((h != 0) ? {1'b0, h} : 5'd10) : 5'd11;
        default: d0 = have ? 5'd10 : 5'd11;
        endcase
        d1 = {1'b0, cnt[4 * dg +: 4]};  // display 1: beats
    end
    always @(posedge clk) begin
        an0 <= ~(4'b0001 << dg); seg0 <= seg7(d0);
        an1 <= ~(4'b0001 << dg); seg1 <= seg7(d1);
    end
endmodule

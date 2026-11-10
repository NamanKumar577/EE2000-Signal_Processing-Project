// FECG v6 - UART 8-N-1 receiver and transmitter.
`timescale 1ns / 1ps

module v6_uart_rx #(parameter integer CLKS_PER_BIT = 54) (
    input  wire       clk,
    input  wire       rst,
    input  wire       rxd,
    output reg  [7:0] data,
    output reg        valid
);
    reg r0 = 1'b1, r1 = 1'b1;
    reg [1:0]  st = 0;
    reg [15:0] cnt = 0;
    reg [2:0]  bit_i = 0;
    reg [7:0]  sh = 0;
    always @(posedge clk) begin
        r0 <= rxd; r1 <= r0;
        valid <= 1'b0;
        if (rst) begin
            st <= 0; cnt <= 0;
        end else case (st)
            0: if (!r1) begin st <= 1; cnt <= 0; end
            1: if (cnt == CLKS_PER_BIT / 2 - 1) begin            // middle of the start bit
                   if (!r1) begin st <= 2; cnt <= 0; bit_i <= 0; end else st <= 0;
               end else cnt <= cnt + 1'b1;
            2: if (cnt == CLKS_PER_BIT - 1) begin
                   cnt <= 0; sh <= {r1, sh[7:1]};
                   if (bit_i == 7) st <= 3; else bit_i <= bit_i + 1'b1;
               end else cnt <= cnt + 1'b1;
            3: if (cnt == CLKS_PER_BIT - 1) begin                // stop bit
                   st <= 0; cnt <= 0;
                   if (r1) begin data <= sh; valid <= 1'b1; end
               end else cnt <= cnt + 1'b1;
        endcase
    end
endmodule

module v6_uart_tx #(parameter integer CLKS_PER_BIT = 54) (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] data,
    input  wire       valid,      // accepted when ready
    output wire       ready,
    output reg        txd = 1'b1
);
    reg [15:0] cnt = 0;
    reg [3:0]  n = 0;             // bits left (0 = idle)
    reg [8:0]  sh = 9'h1FF;
    assign ready = (n == 0);
    always @(posedge clk) begin
        if (rst) begin
            n <= 0; txd <= 1'b1; cnt <= 0;
        end else if (n == 0) begin
            if (valid) begin sh <= {1'b1, data}; txd <= 1'b0; n <= 10; cnt <= 0; end
        end else if (cnt == CLKS_PER_BIT - 1) begin
            cnt <= 0;
            txd <= sh[0]; sh <= {1'b1, sh[8:1]};
            n <= n - 1'b1;
        end else cnt <= cnt + 1'b1;
    end
endmodule

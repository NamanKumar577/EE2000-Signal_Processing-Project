// FECG v6 - board top (Boolean board, xc7s50): 100 MHz -> 50 MHz PLL, UART 921600 8-N-1,
// v6_core.  LEDs: [7] link error, [6] samples pending, [5] calibrated, [2:0] active unit.
`timescale 1ns / 1ps
module v6_top (
    input  wire       clk,          // 100 MHz, F14
    input  wire       rst_pin,      // BTN0, active high
    input  wire       uart_rxd,
    output wire       uart_txd,
    output wire [7:0] led
`ifdef V7
    ,
    output wire [3:0] d0_an,        // v7: final FHR / beat count on the two 4-digit displays
    output wire [7:0] d0_seg,
    output wire [3:0] d1_an,
    output wire [7:0] d1_seg
`endif
);
    wire clk_fb, clk50_u, clk50, locked;
    PLLE2_BASE #(.BANDWIDTH("OPTIMIZED"), .CLKFBOUT_MULT(8), .CLKIN1_PERIOD(10.0),
                 .CLKOUT0_DIVIDE(16), .DIVCLK_DIVIDE(1), .STARTUP_WAIT("FALSE"))
        pll (.CLKIN1(clk), .CLKFBIN(clk_fb), .CLKFBOUT(clk_fb), .CLKOUT0(clk50_u), .LOCKED(locked),
             .PWRDWN(1'b0), .RST(1'b0), .CLKOUT1(), .CLKOUT2(), .CLKOUT3(), .CLKOUT4(), .CLKOUT5());
    BUFG bufg (.I(clk50_u), .O(clk50));

    reg [3:0] rs = 4'hF;
    always @(posedge clk50) rs <= {rs[2:0], rst_pin | ~locked};
    wire rst = rs[3];

    wire [7:0] rx_data, tx_data; wire rx_valid, tx_valid, tx_ready;
    v6_uart_rx #(.CLKS_PER_BIT(54)) urx(.clk(clk50), .rst(rst), .rxd(uart_rxd), .data(rx_data), .valid(rx_valid));
    v6_uart_tx #(.CLKS_PER_BIT(54)) utx(.clk(clk50), .rst(rst), .data(tx_data), .valid(tx_valid), .ready(tx_ready), .txd(uart_txd));
    v6_core core(.clk(clk50), .rst(rst), .rx_data(rx_data), .rx_valid(rx_valid),
                 .tx_data(tx_data), .tx_valid(tx_valid), .tx_ready(tx_ready), .status(led));
`ifdef V7
    v7_disp disp(.clk(clk50), .rst(rst), .tx_byte(tx_data), .tx_stb(tx_valid & tx_ready),
                 .an0(d0_an), .seg0(d0_seg), .an1(d1_an), .seg1(d1_seg));
`endif
endmodule

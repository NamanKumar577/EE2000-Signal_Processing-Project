// =============================================================================
// Module: lp40_filter
// Description: 4th-Order Butterworth Lowpass Filter (fc = 40.0 Hz @ 250 Hz)
//              composed of two cascaded Direct Form II Transposed (DF2T) biquads.
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Structure:
//   x_in -> [Biquad Sec 0] -> [Biquad Sec 1] -> y_out (Clean FECG Tap)
//
// Coefficients (Signed 18-bit Q3.15, Scale = 32768):
//   Sec 0: b = [749, 1499, 749],           a_neg = [19727, -4049]
//   Sec 1: b = [32768, 65536, 32768],     a_neg = [26540, -16764]
//
// Latency: 2 clock cycles (1 cycle per biquad stage)
// =============================================================================

`timescale 1ns / 1ps

module lp40_filter #(
    parameter integer DATA_WIDTH  = 24,         // Input and output sample width
    parameter integer COEF_WIDTH  = 18,         // Coefficient width
    parameter integer COEF_FRAC   = 15,         // Fractional bits in coefficient
    parameter integer STATE_WIDTH = 48          // State accumulator width
)(
    input  wire                          clk,            // Master system clock (100 MHz)
    input  wire                          rst_n,          // Synchronous active-low reset
    input  wire                          enable,         // Block enable / clock enable
    input  wire                          valid_in,       // 1-cycle input strobe
    input  wire signed [DATA_WIDTH-1:0]  x_in,           // Input sample (Signed 24-bit Q20)

    output wire signed [DATA_WIDTH-1:0]  y_out,          // Clean lowpass filtered output
    output wire                          valid_out,      // 1-cycle output strobe
    output wire                          overflow_flag   // High if any biquad saturated
);

    // -------------------------------------------------------------------------
    // Frozen Static Integer Coefficients (Signed 18-bit Q3.15)
    // -------------------------------------------------------------------------
    localparam signed [COEF_WIDTH-1:0] S0_B0     = 18'sd749;
    localparam signed [COEF_WIDTH-1:0] S0_B1     = 18'sd1499;
    localparam signed [COEF_WIDTH-1:0] S0_B2     = 18'sd749;
    localparam signed [COEF_WIDTH-1:0] S0_A1_NEG = 18'sd19727;
    localparam signed [COEF_WIDTH-1:0] S0_A2_NEG = -18'sd4049;

    localparam signed [COEF_WIDTH-1:0] S1_B0     = 18'sd32768;
    localparam signed [COEF_WIDTH-1:0] S1_B1     = 18'sd65536; // +2.0 in Q3.15
    localparam signed [COEF_WIDTH-1:0] S1_B2     = 18'sd32768;
    localparam signed [COEF_WIDTH-1:0] S1_A1_NEG = 18'sd26540;
    localparam signed [COEF_WIDTH-1:0] S1_A2_NEG = -18'sd16764;

    // -------------------------------------------------------------------------
    // Inter-Stage Wires
    // -------------------------------------------------------------------------
    wire signed [DATA_WIDTH-1:0] sec0_out;
    wire                         sec0_valid;
    wire                         sec0_state_ovf;
    wire                         sec0_out_sat;

    wire                         sec1_state_ovf;
    wire                         sec1_out_sat;

    assign overflow_flag = sec0_state_ovf | sec0_out_sat | sec1_state_ovf | sec1_out_sat;

    // -------------------------------------------------------------------------
    // Section 0 Biquad Instantiation
    // -------------------------------------------------------------------------
    biquad_df2t #(
        .DATA_WIDTH(DATA_WIDTH),
        .COEF_WIDTH(COEF_WIDTH),
        .COEF_FRAC(COEF_FRAC),
        .STATE_WIDTH(STATE_WIDTH)
    ) u_biquad_sec0 (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(valid_in),
        .x_in(x_in),
        .b0(S0_B0),
        .b1(S0_B1),
        .b2(S0_B2),
        .a1_neg(S0_A1_NEG),
        .a2_neg(S0_A2_NEG),
        .y_out(sec0_out),
        .valid_out(sec0_valid),
        .s1_out(),
        .s2_out(),
        .state_overflow(sec0_state_ovf),
        .out_saturated(sec0_out_sat)
    );

    // -------------------------------------------------------------------------
    // Section 1 Biquad Instantiation
    // -------------------------------------------------------------------------
    biquad_df2t #(
        .DATA_WIDTH(DATA_WIDTH),
        .COEF_WIDTH(COEF_WIDTH),
        .COEF_FRAC(COEF_FRAC),
        .STATE_WIDTH(STATE_WIDTH)
    ) u_biquad_sec1 (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(sec0_valid),
        .x_in(sec0_out),
        .b0(S1_B0),
        .b1(S1_B1),
        .b2(S1_B2),
        .a1_neg(S1_A1_NEG),
        .a2_neg(S1_A2_NEG),
        .y_out(y_out),
        .valid_out(valid_out),
        .s1_out(),
        .s2_out(),
        .state_overflow(sec1_state_ovf),
        .out_saturated(sec1_out_sat)
    );

endmodule

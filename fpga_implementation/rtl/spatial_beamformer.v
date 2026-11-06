// =============================================================================
// Module: spatial_beamformer
// Description: Synthesizable 4-Channel Spatial PCA Beamforming Engine.
//              Applies spatial projection weights to 4 abdominal ECG leads:
//                raw_acc = sum_{c=0}^3 (w[c] * x[c])
//              Clamps to Signed 32-bit accumulator, applies convergent rounding
//              (Q27 >>> 7 -> Q20), and clamps to Signed 24-bit Q20 datapath.
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Latency: 1 clock cycle (Registered output)
// =============================================================================

`timescale 1ns / 1ps

module spatial_beamformer #(
    parameter integer SAMPLE_WIDTH    = 16, // Signed 16-bit Q3.12 (ADC input)
    parameter integer WEIGHT_WIDTH    = 17, // Signed 17-bit Q2.15 ([-32768, +32768])
    parameter integer PROD_WIDTH      = 33, // 17b * 16b = 33b signed
    parameter integer ACC_WIDTH       = 35, // 4-channel sum requires 35b
    parameter integer PROJ_ACC_WIDTH  = 32, // Clamped internal 32-bit accumulator
    parameter integer PROJ_WIDTH      = 24, // Signed 24-bit Q3.20 output tap
    parameter integer PROJ_SHIFT      = 7   // Q27 >>> 7 -> Q20
)(
    input  wire                               clk,           // Master system clock
    input  wire                               rst_n,         // Synchronous active-low reset
    input  wire                               enable,        // Block enable
    input  wire                               valid_in,      // 1-cycle sample arrival strobe

    // 4 Synchronized Input Channels (Signed 16-bit Q3.12)
    input  wire signed [SAMPLE_WIDTH-1:0]     x0_in,
    input  wire signed [SAMPLE_WIDTH-1:0]     x1_in,
    input  wire signed [SAMPLE_WIDTH-1:0]     x2_in,
    input  wire signed [SAMPLE_WIDTH-1:0]     x3_in,

    // 4 Active Spatial Weights (Signed 17-bit Q2.15)
    input  wire signed [WEIGHT_WIDTH-1:0]     w0_in,
    input  wire signed [WEIGHT_WIDTH-1:0]     w1_in,
    input  wire signed [WEIGHT_WIDTH-1:0]     w2_in,
    input  wire signed [WEIGHT_WIDTH-1:0]     w3_in,

    // Extracted Single-Channel Clean Waveform Feed
    output reg  signed [PROJ_WIDTH-1:0]       proj_out,      // Beamformed output sample (Signed 24-bit Q20)
    output reg                                valid_out,     // 1-cycle output strobe
    output reg                                acc_overflow,  // Sticky flag for accumulator overflow
    output reg                                out_saturated  // Sticky flag for output saturation
);

    // -------------------------------------------------------------------------
    // Four Signed Multiplications (DSP48E1 Mapped)
    // -------------------------------------------------------------------------
    wire signed [PROD_WIDTH-1:0] prod0;
    wire signed [PROD_WIDTH-1:0] prod1;
    wire signed [PROD_WIDTH-1:0] prod2;
    wire signed [PROD_WIDTH-1:0] prod3;

    assign prod0 = w0_in * x0_in;
    assign prod1 = w1_in * x1_in;
    assign prod2 = w2_in * x2_in;
    assign prod3 = w3_in * x3_in;

    // -------------------------------------------------------------------------
    // 4-Channel Accumulation Tree (35-bit Signed)
    // -------------------------------------------------------------------------
    wire signed [ACC_WIDTH-1:0] prod0_ext = $signed({{2{prod0[PROD_WIDTH-1]}}, prod0});
    wire signed [ACC_WIDTH-1:0] prod1_ext = $signed({{2{prod1[PROD_WIDTH-1]}}, prod1});
    wire signed [ACC_WIDTH-1:0] prod2_ext = $signed({{2{prod2[PROD_WIDTH-1]}}, prod2});
    wire signed [ACC_WIDTH-1:0] prod3_ext = $signed({{2{prod3[PROD_WIDTH-1]}}, prod3});

    wire signed [ACC_WIDTH-1:0] raw_acc;
    assign raw_acc = prod0_ext + prod1_ext + prod2_ext + prod3_ext;

    // -------------------------------------------------------------------------
    // 32-bit Accumulator Clamping: sat(raw_acc, 32)
    // -------------------------------------------------------------------------
    localparam signed [ACC_WIDTH-1:0] SAT_MAX_ACC32 = 35'sd2147483647;
    localparam signed [ACC_WIDTH-1:0] SAT_MIN_ACC32 = -35'sd2147483648;

    wire acc_ovf_comb;
    assign acc_ovf_comb = (raw_acc > SAT_MAX_ACC32) || (raw_acc < SAT_MIN_ACC32);

    wire signed [PROJ_ACC_WIDTH-1:0] acc_clamped;
    assign acc_clamped = (raw_acc > SAT_MAX_ACC32) ? 32'sd2147483647 :
                         (raw_acc < SAT_MIN_ACC32) ? -32'sd2147483648 :
                         raw_acc[PROJ_ACC_WIDTH-1:0];

    // -------------------------------------------------------------------------
    // Convergent Rounding: rshift_round_nearest_even(acc_clamped, 7)
    // -------------------------------------------------------------------------
    wire signed [PROJ_ACC_WIDTH-1:0] q_proj;
    wire [PROJ_SHIFT-1:0]            rem_proj;
    wire signed [PROJ_ACC_WIDTH-1:0] proj_rounded;

    assign q_proj   = acc_clamped >>> PROJ_SHIFT;
    assign rem_proj = acc_clamped[PROJ_SHIFT-1:0];

    assign proj_rounded = (rem_proj > 7'd64) ? (q_proj + 32'sd1) :
                          (rem_proj < 7'd64) ? q_proj :
                          (q_proj + (q_proj[0] ? 32'sd1 : 32'sd0)); // Round to nearest even

    // -------------------------------------------------------------------------
    // 24-bit Output Saturation: sat(proj_rounded, 24)
    // -------------------------------------------------------------------------
    localparam signed [PROJ_ACC_WIDTH-1:0] SAT_MAX_PROJ24 = 32'sd8388607;
    localparam signed [PROJ_ACC_WIDTH-1:0] SAT_MIN_PROJ24 = -32'sd8388608;

    wire proj_sat_comb;
    assign proj_sat_comb = (proj_rounded > SAT_MAX_PROJ24) || (proj_rounded < SAT_MIN_PROJ24);

    wire signed [PROJ_WIDTH-1:0] proj_comb;
    assign proj_comb = (proj_rounded > SAT_MAX_PROJ24) ? 24'sd8388607 :
                       (proj_rounded < SAT_MIN_PROJ24) ? -24'sd8388608 :
                       proj_rounded[PROJ_WIDTH-1:0];

    // -------------------------------------------------------------------------
    // Sequential State Registers (Deterministic 1-Cycle Latency)
    // -------------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            proj_out      <= {PROJ_WIDTH{1'b0}};
            valid_out     <= 1'b0;
            acc_overflow  <= 1'b0;
            out_saturated <= 1'b0;
        end else if (enable) begin
            if (valid_in) begin
                proj_out  <= proj_comb;
                valid_out <= 1'b1;

                if (acc_ovf_comb)
                    acc_overflow <= 1'b1;

                if (proj_sat_comb)
                    out_saturated <= 1'b1;
            end else begin
                valid_out <= 1'b0;
            end
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule

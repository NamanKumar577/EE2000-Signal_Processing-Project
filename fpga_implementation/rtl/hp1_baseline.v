// =============================================================================
// Module: hp1_baseline
// Description: Multiplier-Free First-Order IIR Highpass Baseline Wander Remover
//              using shift-and-subtract recurrence (fc ~ 0.62 Hz @ 250 Hz, k = 6).
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Mathematical Model:
//   base[n]         = acc[n-1] >>> k
//   sub[n]          = x[n] - base[n]
//   y[n]            = sat_s24(sub[n])
//   acc_next_raw[n] = acc[n-1] + sub[n]
//   acc[n]          = sat_s32(acc_next_raw[n])
//
// Features:
//   - Zero DSP multipliers (pure arithmetic shift and add)
//   - Sized intermediate arithmetic (33-bit sub, 34-bit accumulator adder)
//   - Explicitly signed comparison thresholds to prevent unsigned coercion
//   - Deterministic 1-cycle registered latency
//   - Synchronous active-low reset and clock enable gating
// =============================================================================

`timescale 1ns / 1ps

module hp1_baseline #(
    parameter integer DATA_WIDTH = 24,         // Input/output sample width (Signed Q4.20)
    parameter integer ACC_WIDTH  = 32,         // Accumulator register width (Signed 32-bit)
    parameter integer K_SHIFT    = 6           // Shift factor: fc ~ fs / (2 * pi * 2^k) = 0.6217 Hz
)(
    input  wire                          clk,            // Master system clock (100 MHz)
    input  wire                          rst_n,          // Synchronous active-low reset
    input  wire                          enable,         // Block enable / clock enable
    input  wire                          valid_in,       // 1-cycle input valid strobe
    input  wire signed [DATA_WIDTH-1:0]  x_in,           // Input sample (Signed 24-bit Q20)

    output reg  signed [DATA_WIDTH-1:0]  y_out,          // Baseline-removed output sample
    output reg                           valid_out,      // 1-cycle output valid strobe
    output wire signed [ACC_WIDTH-1:0]   acc_out,        // Internal accumulator monitor
    output wire signed [ACC_WIDTH-1:0]   base_out,       // Computed baseline estimate monitor
    output reg                           acc_overflow,   // Sticky flag: accumulator saturated at 32 bits
    output reg                           out_saturated   // Sticky flag: output saturated at 24 bits
);

    // -------------------------------------------------------------------------
    // Constants & Saturation Limits (Explicitly Sized & Signed)
    // -------------------------------------------------------------------------
    localparam signed [DATA_WIDTH-1:0] SAT_MAX_DATA = {1'b0, {(DATA_WIDTH-1){1'b1}}}; // +8,388,607
    localparam signed [DATA_WIDTH-1:0] SAT_MIN_DATA = {1'b1, {(DATA_WIDTH-1){1'b0}}}; // -8,388,608

    localparam signed [ACC_WIDTH-1:0]  SAT_MAX_ACC  = {1'b0, {(ACC_WIDTH-1){1'b1}}};  // +2,147,483,647
    localparam signed [ACC_WIDTH-1:0]  SAT_MIN_ACC  = {1'b1, {(ACC_WIDTH-1){1'b0}}};  // -2,147,483,648

    // Internal intermediate widths
    localparam integer SUB_WIDTH = ACC_WIDTH + 1; // 32 + 1 = 33 bits
    localparam integer RAW_ACC_WIDTH = ACC_WIDTH + 2; // 32 + 2 = 34 bits

    // Explicitly signed comparison thresholds
    localparam signed [SUB_WIDTH-1:0] SAT_MAX_DATA_EXT = $signed({{(SUB_WIDTH - DATA_WIDTH){1'b0}}, SAT_MAX_DATA});
    localparam signed [SUB_WIDTH-1:0] SAT_MIN_DATA_EXT = $signed({{(SUB_WIDTH - DATA_WIDTH){1'b1}}, SAT_MIN_DATA});

    localparam signed [RAW_ACC_WIDTH-1:0] SAT_MAX_ACC_EXT = $signed({{(RAW_ACC_WIDTH - ACC_WIDTH){1'b0}}, SAT_MAX_ACC});
    localparam signed [RAW_ACC_WIDTH-1:0] SAT_MIN_ACC_EXT = $signed({{(RAW_ACC_WIDTH - ACC_WIDTH){1'b1}}, SAT_MIN_ACC});

    // -------------------------------------------------------------------------
    // Internal State Register (Signed 32-bit)
    // -------------------------------------------------------------------------
    reg signed [ACC_WIDTH-1:0] acc;

    assign acc_out = acc;

    // -------------------------------------------------------------------------
    // Baseline Estimate: base[n] = acc[n-1] >>> K_SHIFT
    // Arithmetic right-shift copies sign bit across top K_SHIFT bits.
    // -------------------------------------------------------------------------
    wire signed [ACC_WIDTH-1:0] base;
    assign base = acc >>> K_SHIFT;
    assign base_out = base;

    // -------------------------------------------------------------------------
    // Subtraction: sub[n] = x[n] - base[n]
    // Sign-extends 24-bit x_in and 32-bit base to 33 bits.
    // Max magnitude ~ 4.19 x 10^7, fitting comfortably in 33 bits signed.
    // -------------------------------------------------------------------------
    wire signed [SUB_WIDTH-1:0] x_ext33;
    wire signed [SUB_WIDTH-1:0] base_ext33;
    wire signed [SUB_WIDTH-1:0] sub;

    assign x_ext33    = $signed({{(SUB_WIDTH - DATA_WIDTH){x_in[DATA_WIDTH-1]}}, x_in});
    assign base_ext33 = $signed({base[ACC_WIDTH-1], base});
    assign sub        = x_ext33 - base_ext33;

    // -------------------------------------------------------------------------
    // Output Saturation: sat_s24(sub[n])
    // Symmetrically clamps 33-bit sub to Signed 24-bit boundaries.
    // -------------------------------------------------------------------------
    wire signed [DATA_WIDTH-1:0] y_comb;
    wire                         y_saturated_comb;

    assign y_saturated_comb = (sub > SAT_MAX_DATA_EXT) || (sub < SAT_MIN_DATA_EXT);

    assign y_comb = (sub > SAT_MAX_DATA_EXT) ? SAT_MAX_DATA :
                    (sub < SAT_MIN_DATA_EXT) ? SAT_MIN_DATA :
                    sub[DATA_WIDTH-1:0];

    // -------------------------------------------------------------------------
    // Accumulator Update: acc_next[n] = acc[n-1] + sub[n]
    // 34-bit signed addition prevents overflow before 32-bit clamping.
    // -------------------------------------------------------------------------
    wire signed [RAW_ACC_WIDTH-1:0] acc_ext34;
    wire signed [RAW_ACC_WIDTH-1:0] sub_ext34;
    wire signed [RAW_ACC_WIDTH-1:0] acc_next_raw;

    assign acc_ext34     = $signed({{(RAW_ACC_WIDTH - ACC_WIDTH){acc[ACC_WIDTH-1]}}, acc});
    assign sub_ext34     = $signed({sub[SUB_WIDTH-1], sub});
    assign acc_next_raw  = acc_ext34 + sub_ext34;

    // 32-bit Accumulator Saturation Clamping
    wire signed [ACC_WIDTH-1:0] next_acc;
    wire                        acc_overflow_comb;

    assign acc_overflow_comb = (acc_next_raw > SAT_MAX_ACC_EXT) || (acc_next_raw < SAT_MIN_ACC_EXT);

    assign next_acc = (acc_next_raw > SAT_MAX_ACC_EXT) ? SAT_MAX_ACC :
                      (acc_next_raw < SAT_MIN_ACC_EXT) ? SAT_MIN_ACC :
                      acc_next_raw[ACC_WIDTH-1:0];

    // -------------------------------------------------------------------------
    // Sequential State Registers & Output Logic (Deterministic 1-Cycle Latency)
    // -------------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            acc           <= {ACC_WIDTH{1'b0}};
            y_out         <= {DATA_WIDTH{1'b0}};
            valid_out     <= 1'b0;
            acc_overflow  <= 1'b0;
            out_saturated <= 1'b0;
        end else if (enable) begin
            if (valid_in) begin
                acc       <= next_acc;
                y_out     <= y_comb;
                valid_out <= 1'b1;

                if (acc_overflow_comb)
                    acc_overflow <= 1'b1;

                if (y_saturated_comb)
                    out_saturated <= 1'b1;
            end else begin
                valid_out <= 1'b0;
            end
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule

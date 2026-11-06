// =============================================================================
// Module: biquad_df2t
// Description: Second-Order Section (Biquad) Digital Filter in Transposed
//              Direct Form II (DF2T) with Convergent Rounding (Nearest-Even)
//              and Enforced 48-bit State Saturation.
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Mathematical Model:
//   acc[n]  = b0 * x[n] + s1[n-1]
//   y[n]    = sat_s24(rshift_round_nearest_even(acc[n], 15))
//   s1[n]   = sat_s48(b1 * x[n] + a1_neg * y[n] + s2[n-1])
//   s2[n]   = sat_s48(b2 * x[n] + a2_neg * y[n])
//
// Source-Level Verification Status:
//   - All expressions explicitly sized and signed (IEEE 1364-2001 compliant)
//   - Intermediate accumulation evaluated at 49 bits to prevent pre-saturation wraparound
//   - Convergent rounding ties break to even quotient
//   - Disconnected naive PIPELINED mode; deterministic 1-cycle latency enforced
// =============================================================================

`timescale 1ns / 1ps

module biquad_df2t #(
    parameter integer DATA_WIDTH  = 24,         // Input and output sample bit-width
    parameter integer COEF_WIDTH  = 18,         // Coefficient bit-width (Signed Q3.15)
    parameter integer COEF_FRAC   = 15,         // Fractional bits in coefficient
    parameter integer STATE_WIDTH = 48          // Filter state register bit-width (DSP48 P-register)
)(
    input  wire                          clk,            // Master system clock (100 MHz)
    input  wire                          rst_n,          // Synchronous active-low reset
    input  wire                          enable,         // Block enable / clock enable
    input  wire                          valid_in,       // Input sample valid strobe (1 cycle)
    input  wire signed [DATA_WIDTH-1:0]  x_in,           // Input sample (Signed Q4.20 or Q1.23)

    // Filter Coefficients (Signed 18-bit Q3.15, Scale = 32768)
    // Note: a1_neg = -a1, a2_neg = -a2
    input  wire signed [COEF_WIDTH-1:0]  b0,
    input  wire signed [COEF_WIDTH-1:0]  b1,
    input  wire signed [COEF_WIDTH-1:0]  b2,
    input  wire signed [COEF_WIDTH-1:0]  a1_neg,
    input  wire signed [COEF_WIDTH-1:0]  a2_neg,

    // Filter Output & Status
    output reg  signed [DATA_WIDTH-1:0]  y_out,          // Filtered output sample
    output reg                           valid_out,      // Output sample valid strobe (1 cycle)
    output wire signed [STATE_WIDTH-1:0] s1_out,         // State register s1 monitor
    output wire signed [STATE_WIDTH-1:0] s2_out,         // State register s2 monitor
    output reg                           state_overflow, // Sticky flag: state saturation occurred
    output reg                           out_saturated   // Sticky flag: output saturation occurred
);

    // -------------------------------------------------------------------------
    // Constants & Saturation Limits (Explicitly Sized & Signed)
    // -------------------------------------------------------------------------
    localparam signed [DATA_WIDTH-1:0]  SAT_MAX_DATA = {1'b0, {(DATA_WIDTH-1){1'b1}}};  // +8,388,607 for 24-bit
    localparam signed [DATA_WIDTH-1:0]  SAT_MIN_DATA = {1'b1, {(DATA_WIDTH-1){1'b0}}};  // -8,388,608 for 24-bit

    localparam signed [STATE_WIDTH-1:0] SAT_MAX_STATE = {1'b0, {(STATE_WIDTH-1){1'b1}}}; // +140,737,488,355,327
    localparam signed [STATE_WIDTH-1:0] SAT_MIN_STATE = {1'b1, {(STATE_WIDTH-1){1'b0}}}; // -140,737,488,355,328

    localparam integer PROD_WIDTH = DATA_WIDTH + COEF_WIDTH; // 24 + 18 = 42 bits

    // Explicit 49-bit signed boundaries to guarantee signed comparisons
    localparam signed [STATE_WIDTH:0] SAT_MAX_DATA_EXT = $signed({{(STATE_WIDTH + 1 - DATA_WIDTH){1'b0}}, SAT_MAX_DATA});
    localparam signed [STATE_WIDTH:0] SAT_MIN_DATA_EXT = $signed({{(STATE_WIDTH + 1 - DATA_WIDTH){1'b1}}, SAT_MIN_DATA});

    localparam signed [STATE_WIDTH:0] SAT_MAX_STATE_EXT = $signed({1'b0, SAT_MAX_STATE});
    localparam signed [STATE_WIDTH:0] SAT_MIN_STATE_EXT = $signed({1'b1, SAT_MIN_STATE});

    // -------------------------------------------------------------------------
    // Internal Registers & State Variables
    // -------------------------------------------------------------------------
    reg signed [STATE_WIDTH-1:0] s1;
    reg signed [STATE_WIDTH-1:0] s2;

    assign s1_out = s1;
    assign s2_out = s2;

    // -------------------------------------------------------------------------
    // Full-Precision Products (42-bit signed: 18b x 24b)
    // Evaluated with both operands signed -> 42-bit signed result.
    // -------------------------------------------------------------------------
    wire signed [PROD_WIDTH-1:0] prod_b0;
    wire signed [PROD_WIDTH-1:0] prod_b1;
    wire signed [PROD_WIDTH-1:0] prod_b2;

    assign prod_b0 = b0 * x_in;
    assign prod_b1 = b1 * x_in;
    assign prod_b2 = b2 * x_in;

    // -------------------------------------------------------------------------
    // Feedforward Multiply-Accumulate: acc = b0 * x + s1
    // Explicit 49-bit signed addition:
    // Sign-extends 42-bit product and 48-bit s1 to 49 bits, preventing overflow
    // before saturation clamping.
    // -------------------------------------------------------------------------
    wire signed [STATE_WIDTH:0] prod_b0_ext49;
    wire signed [STATE_WIDTH:0] s1_ext49;
    wire signed [STATE_WIDTH:0] acc;

    assign prod_b0_ext49 = $signed({{(STATE_WIDTH + 1 - PROD_WIDTH){prod_b0[PROD_WIDTH-1]}}, prod_b0});
    assign s1_ext49      = $signed({s1[STATE_WIDTH-1], s1});
    assign acc           = prod_b0_ext49 + s1_ext49;

    // -------------------------------------------------------------------------
    // Convergent Rounding (Round-to-Nearest-Even)
    // Arithmetic right-shift: acc >>> 15 copies sign bit across top 15 bits.
    // -------------------------------------------------------------------------
    wire signed [STATE_WIDTH:0]  q_acc;
    wire [COEF_FRAC-1:0]         rem_acc;
    wire signed [STATE_WIDTH:0]  q_rounded;

    assign q_acc   = acc >>> COEF_FRAC;
    assign rem_acc = acc[COEF_FRAC-1:0];

    // Halfway threshold: 2^(COEF_FRAC - 1) = 16384 for COEF_FRAC = 15 (unsigned 15-bit)
    localparam [COEF_FRAC-1:0] HALF_THRESHOLD = 1'b1 << (COEF_FRAC - 1);

    // Explicitly signed constants (49'sd1, 49'sd0) ensure addition is signed
    assign q_rounded = (rem_acc > HALF_THRESHOLD) ? (q_acc + 49'sd1) :
                       (rem_acc < HALF_THRESHOLD) ? q_acc :
                       (q_acc + (q_acc[0] ? 49'sd1 : 49'sd0)); // Tie-break to nearest even

    // -------------------------------------------------------------------------
    // Output Saturation: sat_s24(q_rounded)
    // Symmetrically clamps 49-bit q_rounded to Signed 24-bit boundaries.
    // Both sides of comparison are explicitly 49-bit signed.
    // -------------------------------------------------------------------------
    wire signed [DATA_WIDTH-1:0] y_comb;
    wire                         y_saturated_comb;

    assign y_saturated_comb = (q_rounded > SAT_MAX_DATA_EXT) ||
                              (q_rounded < SAT_MIN_DATA_EXT);

    assign y_comb = (q_rounded > SAT_MAX_DATA_EXT) ? SAT_MAX_DATA :
                    (q_rounded < SAT_MIN_DATA_EXT) ? SAT_MIN_DATA :
                    q_rounded[DATA_WIDTH-1:0];

    // -------------------------------------------------------------------------
    // Feedback Products with y_comb: a1_neg * y, a2_neg * y (42-bit signed)
    // -------------------------------------------------------------------------
    wire signed [PROD_WIDTH-1:0] prod_a1;
    wire signed [PROD_WIDTH-1:0] prod_a2;

    assign prod_a1 = a1_neg * y_comb;
    assign prod_a2 = a2_neg * y_comb;

    // -------------------------------------------------------------------------
    // State Updates with 48-bit Saturation Protection
    // 49-bit arithmetic detects overflow prior to 48-bit clamping.
    // Explicit $signed() wrappers guarantee signed addition tree.
    // -------------------------------------------------------------------------
    wire signed [STATE_WIDTH:0] prod_b1_ext49;
    wire signed [STATE_WIDTH:0] prod_a1_ext49;
    wire signed [STATE_WIDTH:0] s2_ext49;
    wire signed [STATE_WIDTH:0] next_s1_raw;

    assign prod_b1_ext49 = $signed({{(STATE_WIDTH + 1 - PROD_WIDTH){prod_b1[PROD_WIDTH-1]}}, prod_b1});
    assign prod_a1_ext49 = $signed({{(STATE_WIDTH + 1 - PROD_WIDTH){prod_a1[PROD_WIDTH-1]}}, prod_a1});
    assign s2_ext49      = $signed({s2[STATE_WIDTH-1], s2});

    assign next_s1_raw   = prod_b1_ext49 + prod_a1_ext49 + s2_ext49;

    wire signed [STATE_WIDTH:0] prod_b2_ext49;
    wire signed [STATE_WIDTH:0] prod_a2_ext49;
    wire signed [STATE_WIDTH:0] next_s2_raw;

    assign prod_b2_ext49 = $signed({{(STATE_WIDTH + 1 - PROD_WIDTH){prod_b2[PROD_WIDTH-1]}}, prod_b2});
    assign prod_a2_ext49 = $signed({{(STATE_WIDTH + 1 - PROD_WIDTH){prod_a2[PROD_WIDTH-1]}}, prod_a2});

    assign next_s2_raw   = prod_b2_ext49 + prod_a2_ext49;

    // 48-bit State Saturation Clamping (Explicit 49-bit signed comparisons)
    wire signed [STATE_WIDTH-1:0] next_s1;
    wire signed [STATE_WIDTH-1:0] next_s2;
    wire                          s1_overflow_comb;
    wire                          s2_overflow_comb;

    assign s1_overflow_comb = (next_s1_raw > SAT_MAX_STATE_EXT) ||
                              (next_s1_raw < SAT_MIN_STATE_EXT);

    assign s2_overflow_comb = (next_s2_raw > SAT_MAX_STATE_EXT) ||
                              (next_s2_raw < SAT_MIN_STATE_EXT);

    assign next_s1 = (next_s1_raw > SAT_MAX_STATE_EXT) ? SAT_MAX_STATE :
                     (next_s1_raw < SAT_MIN_STATE_EXT) ? SAT_MIN_STATE :
                     next_s1_raw[STATE_WIDTH-1:0];

    assign next_s2 = (next_s2_raw > SAT_MAX_STATE_EXT) ? SAT_MAX_STATE :
                     (next_s2_raw < SAT_MIN_STATE_EXT) ? SAT_MIN_STATE :
                     next_s2_raw[STATE_WIDTH-1:0];

    // -------------------------------------------------------------------------
    // Sequential State Registers & Output Logic (Deterministic 1-Cycle Latency)
    // -------------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            s1             <= {STATE_WIDTH{1'b0}};
            s2             <= {STATE_WIDTH{1'b0}};
            y_out          <= {DATA_WIDTH{1'b0}};
            valid_out      <= 1'b0;
            state_overflow <= 1'b0;
            out_saturated  <= 1'b0;
        end else if (enable) begin
            if (valid_in) begin
                s1             <= next_s1;
                s2             <= next_s2;
                y_out          <= y_comb;
                valid_out      <= 1'b1;

                if (s1_overflow_comb || s2_overflow_comb)
                    state_overflow <= 1'b1;

                if (y_saturated_comb)
                    out_saturated  <= 1'b1;
            end else begin
                valid_out <= 1'b0;
            end
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule

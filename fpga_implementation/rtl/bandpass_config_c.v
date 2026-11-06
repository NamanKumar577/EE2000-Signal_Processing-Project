// =============================================================================
// Module: bandpass_config_c
// Description: Config C 8th-Order Butterworth Bandpass Filter (12.0 - 35.0 Hz @ 250 Hz)
//              composed of four cascaded Direct Form II Transposed (DF2T) biquads,
//              followed by a convergent-rounding downscaler to Signed 16-bit Q12.
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Downscaling:
//   bp_rounded = rshift_round_nearest_even(sec3_out, 8)
//   bp16_out   = sat_s16(bp_rounded)
//
// Latency: 5 clock cycles (4 biquad stages + 1 registered downscale stage)
// =============================================================================

`timescale 1ns / 1ps

module bandpass_config_c #(
    parameter integer DATA_WIDTH = 24,         // Internal datapath width (Signed 24-bit Q20)
    parameter integer OUT_WIDTH  = 16,         // Output detector word width (Signed 16-bit Q12)
    parameter integer COEF_WIDTH = 18,         // Coefficient bit-width (Signed Q3.15)
    parameter integer COEF_FRAC  = 15,         // Fractional bits in coefficient
    parameter integer STATE_WIDTH = 48,        // State accumulator width
    parameter integer DET_SHIFT  = 8           // Downscale shift count (24b Q20 -> 16b Q12)
)(
    input  wire                          clk,            // Master system clock (100 MHz)
    input  wire                          rst_n,          // Synchronous active-low reset
    input  wire                          enable,         // Block enable / clock enable
    input  wire                          valid_in,       // 1-cycle input strobe
    input  wire signed [DATA_WIDTH-1:0]  x_in,           // Input sample from LP40 (Signed 24-bit Q20)

    output reg  signed [OUT_WIDTH-1:0]   bp16_out,       // Saturated detector word (Signed 16-bit Q12)
    output wire signed [DATA_WIDTH-1:0]  bp24_raw_out,   // Full-precision 24-bit bandpass tap
    output reg                           valid_out,      // 1-cycle output strobe
    output wire                          overflow_flag   // High if any biquad or downscaler saturated
);

    // -------------------------------------------------------------------------
    // Frozen Static Integer Coefficients (Signed 18-bit Q3.15)
    // -------------------------------------------------------------------------
    localparam signed [COEF_WIDTH-1:0] S0_B0     = 18'sd119;
    localparam signed [COEF_WIDTH-1:0] S0_B1     = 18'sd238;
    localparam signed [COEF_WIDTH-1:0] S0_B2     = 18'sd119;
    localparam signed [COEF_WIDTH-1:0] S0_A1_NEG = 18'sd38563;
    localparam signed [COEF_WIDTH-1:0] S0_A2_NEG = -18'sd16484;

    localparam signed [COEF_WIDTH-1:0] S1_B0     = 18'sd32768;
    localparam signed [COEF_WIDTH-1:0] S1_B1     = 18'sd65536; // +2.0 in Q3.15
    localparam signed [COEF_WIDTH-1:0] S1_B2     = 18'sd32768;
    localparam signed [COEF_WIDTH-1:0] S1_A1_NEG = 18'sd49834;
    localparam signed [COEF_WIDTH-1:0] S1_A2_NEG = -18'sd21435;

    localparam signed [COEF_WIDTH-1:0] S2_B0     = 18'sd32768;
    localparam signed [COEF_WIDTH-1:0] S2_B1     = -18'sd65536; // -2.0 in Q3.15
    localparam signed [COEF_WIDTH-1:0] S2_B2     = 18'sd32768;
    localparam signed [COEF_WIDTH-1:0] S2_A1_NEG = 18'sd37298;
    localparam signed [COEF_WIDTH-1:0] S2_A2_NEG = -18'sd24206;

    localparam signed [COEF_WIDTH-1:0] S3_B0     = 18'sd32768;
    localparam signed [COEF_WIDTH-1:0] S3_B1     = -18'sd65536; // -2.0 in Q3.15
    localparam signed [COEF_WIDTH-1:0] S3_B2     = 18'sd32768;
    localparam signed [COEF_WIDTH-1:0] S3_A1_NEG = 18'sd58829;
    localparam signed [COEF_WIDTH-1:0] S3_A2_NEG = -18'sd29016;

    // -------------------------------------------------------------------------
    // Inter-Stage Biquad Wires
    // -------------------------------------------------------------------------
    wire signed [DATA_WIDTH-1:0] sec0_out, sec1_out, sec2_out, sec3_out;
    wire                         sec0_valid, sec1_valid, sec2_valid, sec3_valid;
    wire                         s0_ovf, s1_ovf, s2_ovf, s3_ovf;
    wire                         s0_sat, s1_sat, s2_sat, s3_sat;
    reg                          downscale_sat;

    assign bp24_raw_out = sec3_out;
    assign overflow_flag = s0_ovf | s1_ovf | s2_ovf | s3_ovf | s0_sat | s1_sat | s2_sat | s3_sat | downscale_sat;

    // Section 0
    biquad_df2t #(.DATA_WIDTH(DATA_WIDTH), .COEF_WIDTH(COEF_WIDTH), .COEF_FRAC(COEF_FRAC), .STATE_WIDTH(STATE_WIDTH))
    u_sec0 (
        .clk(clk), .rst_n(rst_n), .enable(enable), .valid_in(valid_in), .x_in(x_in),
        .b0(S0_B0), .b1(S0_B1), .b2(S0_B2), .a1_neg(S0_A1_NEG), .a2_neg(S0_A2_NEG),
        .y_out(sec0_out), .valid_out(sec0_valid), .s1_out(), .s2_out(),
        .state_overflow(s0_ovf), .out_saturated(s0_sat)
    );

    // Section 1
    biquad_df2t #(.DATA_WIDTH(DATA_WIDTH), .COEF_WIDTH(COEF_WIDTH), .COEF_FRAC(COEF_FRAC), .STATE_WIDTH(STATE_WIDTH))
    u_sec1 (
        .clk(clk), .rst_n(rst_n), .enable(enable), .valid_in(sec0_valid), .x_in(sec0_out),
        .b0(S1_B0), .b1(S1_B1), .b2(S1_B2), .a1_neg(S1_A1_NEG), .a2_neg(S1_A2_NEG),
        .y_out(sec1_out), .valid_out(sec1_valid), .s1_out(), .s2_out(),
        .state_overflow(s1_ovf), .out_saturated(s1_sat)
    );

    // Section 2
    biquad_df2t #(.DATA_WIDTH(DATA_WIDTH), .COEF_WIDTH(COEF_WIDTH), .COEF_FRAC(COEF_FRAC), .STATE_WIDTH(STATE_WIDTH))
    u_sec2 (
        .clk(clk), .rst_n(rst_n), .enable(enable), .valid_in(sec1_valid), .x_in(sec1_out),
        .b0(S2_B0), .b1(S2_B1), .b2(S2_B2), .a1_neg(S2_A1_NEG), .a2_neg(S2_A2_NEG),
        .y_out(sec2_out), .valid_out(sec2_valid), .s1_out(), .s2_out(),
        .state_overflow(s2_ovf), .out_saturated(s2_sat)
    );

    // Section 3
    biquad_df2t #(.DATA_WIDTH(DATA_WIDTH), .COEF_WIDTH(COEF_WIDTH), .COEF_FRAC(COEF_FRAC), .STATE_WIDTH(STATE_WIDTH))
    u_sec3 (
        .clk(clk), .rst_n(rst_n), .enable(enable), .valid_in(sec2_valid), .x_in(sec2_out),
        .b0(S3_B0), .b1(S3_B1), .b2(S3_B2), .a1_neg(S3_A1_NEG), .a2_neg(S3_A2_NEG),
        .y_out(sec3_out), .valid_out(sec3_valid), .s1_out(), .s2_out(),
        .state_overflow(s3_ovf), .out_saturated(s3_sat)
    );

    // -------------------------------------------------------------------------
    // Convergent Rounding Downscaler: >>> 8 to Signed 16-bit Q12
    // -------------------------------------------------------------------------
    localparam signed [OUT_WIDTH-1:0] SAT_MAX_16 = 16'sh7FFF;  // +32767
    localparam signed [OUT_WIDTH-1:0] SAT_MIN_16 = -16'sh8000; // -32768

    localparam signed [DATA_WIDTH-1:0] SAT_MAX_16_EXT = $signed({{(DATA_WIDTH - OUT_WIDTH){1'b0}}, SAT_MAX_16});
    localparam signed [DATA_WIDTH-1:0] SAT_MIN_16_EXT = $signed({{(DATA_WIDTH - OUT_WIDTH){1'b1}}, SAT_MIN_16});

    wire signed [DATA_WIDTH-1:0] q_shift;
    wire [DET_SHIFT-1:0]         rem_shift;
    wire signed [DATA_WIDTH-1:0] q_round;

    assign q_shift   = sec3_out >>> DET_SHIFT;
    assign rem_shift = sec3_out[DET_SHIFT-1:0];

    localparam [DET_SHIFT-1:0] HALF_THRESHOLD = 1'b1 << (DET_SHIFT - 1); // 128 for shift=8

    assign q_round = (rem_shift > HALF_THRESHOLD) ? (q_shift + 24'sd1) :
                     (rem_shift < HALF_THRESHOLD) ? q_shift :
                     (q_shift + (q_shift[0] ? 24'sd1 : 24'sd0)); // Nearest-even

    wire signed [OUT_WIDTH-1:0] bp16_comb;
    wire                        bp16_sat_comb;

    assign bp16_sat_comb = (q_round > SAT_MAX_16_EXT) || (q_round < SAT_MIN_16_EXT);

    assign bp16_comb = (q_round > SAT_MAX_16_EXT) ? SAT_MAX_16 :
                       (q_round < SAT_MIN_16_EXT) ? SAT_MIN_16 :
                       q_round[OUT_WIDTH-1:0];

    // Registered Downscale Output
    always @(posedge clk) begin
        if (!rst_n) begin
            bp16_out      <= {OUT_WIDTH{1'b0}};
            valid_out     <= 1'b0;
            downscale_sat <= 1'b0;
        end else if (enable) begin
            if (sec3_valid) begin
                bp16_out  <= bp16_comb;
                valid_out <= 1'b1;
                if (bp16_sat_comb)
                    downscale_sat <= 1'b1;
            end else begin
                valid_out <= 1'b0;
            end
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule

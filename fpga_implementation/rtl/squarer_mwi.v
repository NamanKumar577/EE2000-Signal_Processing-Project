// =============================================================================
// Module: squarer_mwi
// Description: Energy Squarer and 30-Sample Moving-Window Integrator (MWI).
//              Computes instantaneous energy y[n] = (bp16[n])^2 and maintains
//              a running rectangular sum over a sliding window of W = 30 samples
//              (120 ms at 250 Hz).
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Mathematical Model:
//   sq[n]      = bp16[n] * bp16[n]                (Unsigned 32-bit product)
//   old_sq     = ring_mem[ptr]                    (Sample from 30 steps ago)
//   mwi_sub    = mwi_sum[n-1] + sq[n] - old_sq    (Signed 37-bit accumulator)
//   mwi_sum[n] = sat_u36(mwi_sub)                 (Unsigned 36-bit saturated sum)
//   ring_mem[ptr] <= sq[n]
//   ptr        <= (ptr == 29) ? 0 : ptr + 1
//
// Latency: 1 clock cycle (registered output)
// =============================================================================

`timescale 1ns / 1ps

module squarer_mwi #(
    parameter integer IN_WIDTH   = 16,         // Input detector word width (Signed 16-bit Q12)
    parameter integer SQ_WIDTH   = 32,         // Squared energy width (Unsigned 32-bit)
    parameter integer MWI_WIDTH  = 36,         // MWI accumulator width (Unsigned 36-bit)
    parameter integer MWI_LEN    = 30          // Window length (30 samples = 120 ms @ 250 Hz)
)(
    input  wire                          clk,            // Master system clock (100 MHz)
    input  wire                          rst_n,          // Synchronous active-low reset
    input  wire                          enable,         // Block enable / clock enable
    input  wire                          valid_in,       // 1-cycle input strobe
    input  wire signed [IN_WIDTH-1:0]    bp16_in,        // Input sample from bandpass filter

    output reg  [MWI_WIDTH-1:0]          mwi_out,        // Integrated energy window sum
    output wire [SQ_WIDTH-1:0]           sq_out,         // Instantaneous squared energy tap
    output reg                           valid_out,      // 1-cycle output strobe
    output reg                           mwi_overflow    // Sticky flag: accumulator saturated at 36 bits
);

    // -------------------------------------------------------------------------
    // Constants & Saturation Limits
    // -------------------------------------------------------------------------
    localparam [MWI_WIDTH-1:0] SAT_MAX_U36 = {MWI_WIDTH{1'b1}}; // 36'hFFFFFFFFF (68,719,476,735)

    // -------------------------------------------------------------------------
    // Squarer: sq = bp16 * bp16
    // Both operands signed 16-bit. Product is always non-negative unsigned 32-bit.
    // In Spartan-7, maps cleanly into 1 DSP48E1 slice (16x16 multiply).
    // -------------------------------------------------------------------------
    wire signed [31:0] sq_mult_signed;
    assign sq_mult_signed = bp16_in * bp16_in;

    wire [SQ_WIDTH-1:0] sq;
    // For -32768 * -32768 = +1,073,741,824 (0x40000000), fits in unsigned 32-bit
    assign sq = sq_mult_signed[31:0];
    assign sq_out = sq;

    // -------------------------------------------------------------------------
    // 30-Word Ring Memory Buffer (Distributed LUT RAM)
    // -------------------------------------------------------------------------
    reg [SQ_WIDTH-1:0] ring_mem [0:MWI_LEN-1];
    reg [4:0]          ptr;
    reg [MWI_WIDTH-1:0] mwi_sum;

    integer i;

    // Read the oldest sample currently at pointer
    wire [SQ_WIDTH-1:0] old_sq;
    assign old_sq = ring_mem[ptr];

    // -------------------------------------------------------------------------
    // Arithmetic Accumulator: mwi_sum + sq - old_sq
    // Evaluated at 37 bits signed to prevent overflow or underflow before clamp.
    // -------------------------------------------------------------------------
    wire signed [MWI_WIDTH:0] mwi_sum_ext37;
    wire signed [MWI_WIDTH:0] sq_ext37;
    wire signed [MWI_WIDTH:0] old_sq_ext37;
    wire signed [MWI_WIDTH:0] mwi_diff;

    assign mwi_sum_ext37 = $signed({1'b0, mwi_sum});
    assign sq_ext37      = $signed({1'b0, sq});
    assign old_sq_ext37  = $signed({1'b0, old_sq});

    assign mwi_diff      = mwi_sum_ext37 + sq_ext37 - old_sq_ext37;

    // Unsigned 36-bit Saturation Clamping: sat_u36(mwi_diff)
    wire [MWI_WIDTH-1:0] next_mwi_sum;
    wire                 overflow_comb;

    assign overflow_comb = (mwi_diff > $signed({1'b0, SAT_MAX_U36}));

    assign next_mwi_sum  = (mwi_diff < 37'sd0) ? {MWI_WIDTH{1'b0}} :
                           (mwi_diff > $signed({1'b0, SAT_MAX_U36})) ? SAT_MAX_U36 :
                           mwi_diff[MWI_WIDTH-1:0];

    // -------------------------------------------------------------------------
    // Sequential Ring Buffer & Accumulator Logic (1-Cycle Latency)
    // -------------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            mwi_sum      <= {MWI_WIDTH{1'b0}};
            mwi_out      <= {MWI_WIDTH{1'b0}};
            valid_out    <= 1'b0;
            ptr          <= 5'd0;
            mwi_overflow <= 1'b0;
            for (i = 0; i < MWI_LEN; i = i + 1) begin
                ring_mem[i] <= {SQ_WIDTH{1'b0}};
            end
        end else if (enable) begin
            if (valid_in) begin
                mwi_sum       <= next_mwi_sum;
                mwi_out       <= next_mwi_sum;
                valid_out     <= 1'b1;
                ring_mem[ptr] <= sq;

                if (ptr == MWI_LEN - 1)
                    ptr <= 5'd0;
                else
                    ptr <= ptr + 1'b1;

                if (overflow_comb)
                    mwi_overflow <= 1'b1;
            end else begin
                valid_out <= 1'b0;
            end
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule

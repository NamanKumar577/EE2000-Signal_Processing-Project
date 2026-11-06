// =============================================================================
// Module: adaptive_detector
// Description: Causal Adaptive Dual-Threshold QRS Peak Detector & Warm-up Engine.
//              Implements Pan-Tompkins style adaptive thresholding with 512-sample
//              warm-up initialization, 1/8 exponential moving average (EMA)
//              tracking, and 50-sample (200 ms) refractory blanking period.
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Dynamic Threshold Formula:
//   thr = (peak_level >> 2) + noise_level - (noise_level >> 2)
//   Multiplier-free: evaluated purely with bit-shifts and additions.
//
// Latency: 1 clock cycle (registered detection strobe at m = t - 1)
// =============================================================================

`timescale 1ns / 1ps

module adaptive_detector #(
    parameter integer MWI_WIDTH      = 36,     // MWI energy width
    parameter integer TIME_WIDTH     = 24,     // Timestamp width (24 bits = 16.7M samples)
    parameter integer WARMUP_LEN     = 512,    // Warmup duration (512 samples ~ 2.05 s)
    parameter integer REFRACTORY_LEN = 50      // Refractory blanking (50 samples = 200 ms @ 250 Hz)
)(
    input  wire                          clk,               // Master system clock (100 MHz)
    input  wire                          rst_n,             // Synchronous active-low reset
    input  wire                          enable,            // Block enable / clock enable
    input  wire                          valid_in,          // 1-cycle sample strobe
    input  wire [MWI_WIDTH-1:0]          mwi_in,            // Current MWI sample at time t

    output reg                           candidate_strobe,  // 1-cycle pulse on declared candidate
    output reg  [TIME_WIDTH-1:0]         cand_timestamp,    // Timestamp index m of candidate
    output reg  [MWI_WIDTH-1:0]          cand_energy,       // MWI energy at peak m
    output wire [MWI_WIDTH-1:0]          peak_level_out,    // Dynamic peak level monitor
    output wire [MWI_WIDTH-1:0]          noise_level_out,   // Dynamic noise level monitor
    output wire [MWI_WIDTH-1:0]          threshold_out,     // Active detection threshold monitor
    output reg                           detector_active,   // High when warmup completed
    output reg  [TIME_WIDTH-1:0]         t_counter          // Global sample counter
);

    // -------------------------------------------------------------------------
    // Internal Registers & State Variables
    // -------------------------------------------------------------------------
    reg [MWI_WIDTH-1:0]  xint_m;      // MWI sample at m = t - 1
    reg [MWI_WIDTH-1:0]  xint_m_prev; // MWI sample at m - 1 = t - 2

    reg [MWI_WIDTH-1:0]  peak_level;
    reg [MWI_WIDTH-1:0]  noise_level;

    reg [MWI_WIDTH-1:0]  warm_max;
    reg [MWI_WIDTH+8:0]  warm_sum;    // 36 + 9 = 45 bits (holds sum of 512 samples)

    reg signed [TIME_WIDTH:0] last_cand_m; // Signed 25-bit to handle initial -10^6

    assign peak_level_out  = peak_level;
    assign noise_level_out = noise_level;

    // -------------------------------------------------------------------------
    // Multiplier-Free Threshold Evaluation:
    //   thr = (peak_level >> 2) + noise_level - (noise_level >> 2)
    // -------------------------------------------------------------------------
    wire [MWI_WIDTH-1:0] pk_div4;
    wire [MWI_WIDTH-1:0] ns_div4;
    wire [MWI_WIDTH-1:0] thr;

    assign pk_div4 = peak_level >> 2;
    assign ns_div4 = noise_level >> 2;
    assign thr     = pk_div4 + noise_level - ns_div4;
    assign threshold_out = thr;

    // -------------------------------------------------------------------------
    // Local Peak Detection at m = t - 1:
    //   xint_m_prev < xint_m and xint_m >= mwi_in
    // -------------------------------------------------------------------------
    wire is_local_max;
    assign is_local_max = (xint_m_prev < xint_m) && (xint_m >= mwi_in);

    // Refractory Check: (m - last_cand_m) >= REFRACTORY_LEN
    wire [TIME_WIDTH-1:0] m_idx;
    assign m_idx = (t_counter > 24'd0) ? (t_counter - 24'd1) : 24'd0;

    wire signed [TIME_WIDTH:0] m_signed;
    assign m_signed = $signed({1'b0, m_idx});

    wire refractory_ok;
    assign refractory_ok = (m_signed - last_cand_m) >= $signed({1'b0, REFRACTORY_LEN[TIME_WIDTH-1:0]});

    // EMA 1/8 Update Calculations
    wire signed [MWI_WIDTH:0] diff_pk;
    wire signed [MWI_WIDTH:0] diff_ns;
    wire signed [MWI_WIDTH:0] step_pk;
    wire signed [MWI_WIDTH:0] step_ns;

    assign diff_pk = $signed({1'b0, xint_m}) - $signed({1'b0, peak_level});
    assign diff_ns = $signed({1'b0, xint_m}) - $signed({1'b0, noise_level});

    assign step_pk = diff_pk >>> 3; // Shift right by 3 = divide by 8
    assign step_ns = diff_ns >>> 3;

    // -------------------------------------------------------------------------
    // Sequential State Update Logic
    // -------------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            t_counter        <= {TIME_WIDTH{1'b0}};
            xint_m           <= {MWI_WIDTH{1'b0}};
            xint_m_prev      <= {MWI_WIDTH{1'b0}};
            peak_level       <= {MWI_WIDTH{1'b0}};
            noise_level      <= {MWI_WIDTH{1'b0}};
            warm_max         <= {MWI_WIDTH{1'b0}};
            warm_sum         <= {(MWI_WIDTH+9){1'b0}};
            detector_active  <= 1'b0;
            candidate_strobe <= 1'b0;
            cand_timestamp   <= {TIME_WIDTH{1'b0}};
            cand_energy      <= {MWI_WIDTH{1'b0}};
            last_cand_m      <= -25'sd1000000;
        end else if (enable) begin
            if (valid_in) begin
                candidate_strobe <= 1'b0; // Default deassert

                // Advance delay pipeline
                xint_m_prev <= xint_m;
                xint_m      <= mwi_in;

                // 1. Warm-up Phase (t < WARMUP_LEN)
                if (t_counter < WARMUP_LEN) begin
                    if (mwi_in > warm_max)
                        warm_max <= mwi_in;

                    warm_sum <= warm_sum + mwi_in;

                    if (t_counter == WARMUP_LEN - 1) begin
                        peak_level  <= (mwi_in > warm_max) ? mwi_in : warm_max;
                        noise_level <= (warm_sum + mwi_in) >> 9; // Divide by 512
                    end
                end else if (t_counter == WARMUP_LEN) begin
                    detector_active <= 1'b1;
                end
                // 2. Detection Phase (t >= WARMUP_LEN and t >= 2)
                else if (detector_active && t_counter >= 24'd2) begin
                    if (is_local_max) begin
                        if (xint_m > thr) begin
                            if (refractory_ok) begin
                                candidate_strobe <= 1'b1;
                                cand_timestamp   <= m_idx;
                                cand_energy      <= xint_m;
                                last_cand_m      <= m_signed;

                                // Update peak level via 1/8 EMA
                                peak_level <= $unsigned($signed({1'b0, peak_level}) + step_pk);
                            end
                        end else begin
                            // Update noise level via 1/8 EMA
                            noise_level <= $unsigned($signed({1'b0, noise_level}) + step_ns);
                        end
                    end
                end

                t_counter <= t_counter + 1'b1;
            end else begin
                candidate_strobe <= 1'b0;
            end
        end else begin
            candidate_strobe <= 1'b0;
        end
    end

endmodule

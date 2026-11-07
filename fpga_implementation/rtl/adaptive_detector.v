// =============================================================================
// Module: adaptive_detector
// Description: Causal Adaptive Dual-Threshold QRS Peak Detector & Warm-up Engine.
//              Implements Pan-Tompkins style adaptive thresholding with 512-sample
//              warm-up initialization, 1/8 exponential moving average (EMA)
//              tracking, and 50-sample (200 ms) refractory blanking period.
//
//              Restartable warm-up (0xC4 calibration packets): a 1-cycle
//              restart_req pulse loads a RESTART_DELAY countdown on the next
//              sample; when it expires the warm-up is re-run so the peak/noise
//              levels are learned on the NEW spatial weights.  Bit-exact with
//              src/fecg/hardware/bit_accurate_reference.py (DET_RESTART_DELAY).
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
    parameter integer REFRACTORY_LEN = 50,     // Refractory blanking (50 samples = 200 ms @ 250 Hz)
    parameter integer RESTART_DELAY  = 128     // Samples from 0xC4 weights to warm-up restart
)(
    input  wire                          clk,               // Master system clock (100 MHz)
    input  wire                          rst_n,             // Synchronous active-low reset
    input  wire                          enable,            // Block enable / clock enable
    input  wire                          valid_in,          // 1-cycle sample strobe
    input  wire [MWI_WIDTH-1:0]          mwi_in,            // Current MWI sample at time t
    input  wire                          restart_req,       // 1-cycle pulse: 0xC4 accepted

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

    reg [9:0]            warm_cnt;        // samples of the current warm-up (0..WARMUP_LEN)
    reg [TIME_WIDTH-1:0] warm_done_t;     // t of the last warm-up sample
    reg                  restart_pending; // restart_req seen, load countdown on next sample
    reg [7:0]            restart_cd;      // RESTART_DELAY countdown (0 = idle)
    reg                  det_enabled;     // warm-up result: peak > noise (gates detection)

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
    // Countdown / warm-up restart evaluation for the current sample
    wire [7:0] cd_loaded = restart_pending ? RESTART_DELAY[7:0] : restart_cd;
    wire       cd_fire   = (cd_loaded == 8'd1);           // decrements to 0 this sample
    wire [7:0] cd_next   = (cd_loaded != 8'd0) ? (cd_loaded - 8'd1) : 8'd0;
    wire [9:0] wc_eff    = cd_fire ? 10'd0 : warm_cnt;     // warm-up counter seen by this sample
    wire [MWI_WIDTH-1:0]   wmax_eff = cd_fire ? {MWI_WIDTH{1'b0}} : warm_max;
    wire [MWI_WIDTH+8:0]   wsum_eff = cd_fire ? {(MWI_WIDTH+9){1'b0}} : warm_sum;
    wire [MWI_WIDTH-1:0]   wmax_new = (mwi_in > wmax_eff) ? mwi_in : wmax_eff;
    wire [MWI_WIDTH+8:0]   wsum_new = wsum_eff + mwi_in;

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
            warm_cnt         <= 10'd0;
            warm_done_t      <= {TIME_WIDTH{1'b0}};
            restart_pending  <= 1'b0;
            restart_cd       <= 8'd0;
            det_enabled      <= 1'b0;
            detector_active  <= 1'b0;
            candidate_strobe <= 1'b0;
            cand_timestamp   <= {TIME_WIDTH{1'b0}};
            cand_energy      <= {MWI_WIDTH{1'b0}};
            last_cand_m      <= -25'sd1000000;
        end else if (enable) begin
            if (restart_req)
                restart_pending <= 1'b1;

            if (valid_in) begin
                candidate_strobe <= 1'b0; // Default deassert

                // Advance delay pipeline
                xint_m_prev <= xint_m;
                xint_m      <= mwi_in;

                restart_cd <= cd_next;
                if (!restart_req)
                    restart_pending <= 1'b0;

                // 1. Warm-up Phase (first WARMUP_LEN samples after reset or restart)
                if (wc_eff < WARMUP_LEN) begin
                    warm_max <= wmax_new;
                    warm_sum <= wsum_new;
                    warm_cnt <= wc_eff + 1'b1;
                    detector_active <= 1'b0;                          // warm-up in progress
                    if (cd_fire)
                        det_enabled <= 1'b0;
                    if (wc_eff == WARMUP_LEN - 1) begin
                        peak_level  <= wmax_new;
                        noise_level <= wsum_new >> 9;                   // Divide by 512
                        det_enabled <= (wmax_new > (wsum_new >> 9));    // peak > noise
                        warm_done_t <= t_counter;
                    end
                end
                // 2. Detection Phase (m = t-1 >= last warm-up sample, t >= 2)
                else begin
                    detector_active <= 1'b1;                          // warm-up complete
                    if (det_enabled && t_counter >= 24'd2 && m_idx >= warm_done_t) begin
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

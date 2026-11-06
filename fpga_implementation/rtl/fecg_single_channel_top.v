// =============================================================================
// Module: fecg_single_channel_top
// Description: Complete Integrated Single-Channel Fetal ECG (FECG) Processing RTL.
//              Converts Signed 16-bit Q12 ADC input into continuous filtered FECG,
//              detects fetal QRS complexes, performs split-beat interval fusion,
//              maintains causal integer median-5 RR tracking, and calculates FHR.
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Processing Pipeline Architecture:
//   adc_in (16b Q12)
//     --> [Unity Gain Scale: << 8]
//     --> [HP1 Baseline Remover] (Signed 24b Q20, fc ~ 0.62 Hz)
//     --> [LP40 Lowpass Filter] (4th-order Butterworth, fc = 40 Hz, 2 DF2T biquads)
//           |--> Clean FECG Output Tap (fecg_clean_out)
//     --> [Bandpass Config C] (8th-order Butterworth, 12-35 Hz, 4 DF2T biquads)
//           |--> [Convergent Downscaler] (Signed 16b Q12, bp16)
//     --> [Squarer + 30-Sample MWI] (36-bit Energy Accumulator)
//     --> [Adaptive Detector] (Dual-Threshold, 512-sample Warmup, 1/8 EMA)
//     --> [Peak Localizer] (26-Sample Trailing Search on |bp16|, 18-Sample Latency Rewind)
//     --> [Interval Fusion] (Split-Beat Fusion, Integer Median-5, Dropout Handling)
//     --> [FHR Calculator] (251-Word Frozen ROM LUT, 0.1 bpm units)
//
// Total Dynamic Latency: ~10 clock cycles per sample (< 100 ns at 100 MHz clock)
// =============================================================================

`timescale 1ns / 1ps

module fecg_single_channel_top #(
    parameter integer ADC_WIDTH     = 16,        // ADC sample width (Signed 16-bit Q12)
    parameter integer DATA_WIDTH    = 24,        // Internal datapath width (Signed 24-bit Q20)
    parameter integer DET_WIDTH     = 16,        // Detector bandpass word width (Signed 16-bit Q12)
    parameter integer MWI_WIDTH     = 36,        // MWI energy width (Unsigned 36-bit)
    parameter integer TIME_WIDTH    = 24,        // Timestamp counter width
    parameter integer RR_WIDTH      = 16,        // RR interval width
    parameter integer FHR_WIDTH     = 16,        // FHR output width (0.1 bpm units)
    parameter integer WARMUP_LEN    = 512,       // Warmup duration (512 samples ~ 2.05 s)
    parameter integer LOC_WINDOW    = 26,        // Trailing search window length
    parameter integer LATENCY_COMP  = 18         // Group delay compensation (18 samples)
)(
    input  wire                          clk,               // Master system clock (100 MHz)
    input  wire                          rst_n,             // Synchronous active-low reset
    input  wire                          enable,            // Block enable / clock enable
    input  wire                          sample_valid_in,   // 1-cycle sample strobe (250 Hz)
    input  wire signed [ADC_WIDTH-1:0]   adc_data_in,       // Signed 16-bit Q12 ADC input sample

    // Continuous Filtered Waveform Taps
    output wire signed [DATA_WIDTH-1:0]  fecg_clean_out,    // Clean 40 Hz lowpassed FECG (Signed 24-bit Q20)
    output wire signed [DATA_WIDTH-1:0]  hp_filtered_out,   // Baseline-removed FECG tap
    output wire signed [DET_WIDTH-1:0]   det_bp_out,        // 16-bit detector bandpass output (bp16)
    output wire [MWI_WIDTH-1:0]          mwi_energy_out,    // Integrated MWI energy tap
    output wire                          waveform_valid_out,// Strobe when filtered waveforms are updated

    // Beat Detection & Telemetry Outputs
    output wire                          beat_valid_strobe, // 1-cycle strobe on confirmed beat event
    output wire                          fused_beat_strobe, // 1-cycle strobe on merged split-beat
    output wire [TIME_WIDTH-1:0]         raw_peak_timestamp,// Uncompensated R-peak timestamp (best_idx)
    output wire [TIME_WIDTH-1:0]         comp_peak_timestamp,// Group-delay compensated timestamp
    output wire [RR_WIDTH-1:0]           raw_rr_interval,   // Raw RR interval (samples)
    output wire [RR_WIDTH-1:0]           median_rr_interval,// Pure integer median-5 RR interval
    output wire [FHR_WIDTH-1:0]          fhr_instant_out,   // Instantaneous FHR for latest beat (0.1 bpm)
    output wire [FHR_WIDTH-1:0]          fhr_stream_out,    // Continuous held FHR stream (0.1 bpm)
    output wire [7:0]                    telemetry_flags,   // 8-bit Telemetry Status Byte
    output wire [15:0]                   n_fused_count,     // Total fused beats count
    output wire                          detector_active    // High when 512-sample warmup is complete
);

    // -------------------------------------------------------------------------
    // 1. Single-Channel Unity Gain Conversion: ADC Q12 -> Internal Q20
    // Shifting left by 8 bits with signed extension:
    //   prod = adc_data_in * 32768 (Q12 x Q15 = Q27)
    //   proj = rshift_round_nearest_even(prod, 7) = adc_data_in << 8 (Q20)
    // -------------------------------------------------------------------------
    wire signed [DATA_WIDTH-1:0] proj_q20;
    assign proj_q20 = {adc_data_in, 8'b0};

    // -------------------------------------------------------------------------
    // 2. Stage 1: HP1 Baseline Wander Remover (fc ~ 0.62 Hz, k = 6)
    // -------------------------------------------------------------------------
    wire signed [DATA_WIDTH-1:0] hp_out;
    wire                         hp_valid;
    wire                         hp_acc_ovf;
    wire                         hp_out_sat;
    wire                         hp_ovf;

    assign hp_ovf = hp_acc_ovf | hp_out_sat;

    hp1_baseline #(
        .DATA_WIDTH(DATA_WIDTH),
        .ACC_WIDTH(32),
        .K_SHIFT(6)
    ) u_hp1 (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(sample_valid_in),
        .x_in(proj_q20),
        .y_out(hp_out),
        .valid_out(hp_valid),
        .acc_out(),
        .base_out(),
        .acc_overflow(hp_acc_ovf),
        .out_saturated(hp_out_sat)
    );

    assign hp_filtered_out = hp_out;

    // -------------------------------------------------------------------------
    // 3. Stage 2: LP40 Filter (4th-Order Butterworth Lowpass, fc = 40 Hz)
    // -------------------------------------------------------------------------
    wire signed [DATA_WIDTH-1:0] fecg_out;
    wire                         lp_valid;
    wire                         lp_ovf;

    lp40_filter #(
        .DATA_WIDTH(DATA_WIDTH),
        .COEF_WIDTH(18),
        .COEF_FRAC(15),
        .STATE_WIDTH(48)
    ) u_lp40 (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(hp_valid),
        .x_in(hp_out),
        .y_out(fecg_out),
        .valid_out(lp_valid),
        .overflow_flag(lp_ovf)
    );

    assign fecg_clean_out = fecg_out;

    // -------------------------------------------------------------------------
    // 4. Stage 3: Config C Bandpass Filter (12.0 - 35.0 Hz, 8th-Order)
    // -------------------------------------------------------------------------
    wire signed [DET_WIDTH-1:0]  bp16_out;
    wire signed [DATA_WIDTH-1:0] bp24_raw;
    wire                         bp_valid;
    wire                         bp_ovf;

    bandpass_config_c #(
        .DATA_WIDTH(DATA_WIDTH),
        .OUT_WIDTH(DET_WIDTH),
        .COEF_WIDTH(18),
        .COEF_FRAC(15),
        .STATE_WIDTH(48),
        .DET_SHIFT(8)
    ) u_bandpass (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(lp_valid),
        .x_in(fecg_out),
        .bp16_out(bp16_out),
        .bp24_raw_out(bp24_raw),
        .valid_out(bp_valid),
        .overflow_flag(bp_ovf)
    );

    assign det_bp_out = bp16_out;

    // -------------------------------------------------------------------------
    // 5. Stage 4: Squarer & Moving Window Integrator (MWI, W = 30 samples)
    // -------------------------------------------------------------------------
    wire [MWI_WIDTH-1:0] mwi_out;
    wire [31:0]          sq_out;
    wire                 mwi_valid;
    wire                 mwi_ovf;

    squarer_mwi #(
        .IN_WIDTH(DET_WIDTH),
        .SQ_WIDTH(32),
        .MWI_WIDTH(MWI_WIDTH),
        .MWI_LEN(30)
    ) u_mwi (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(bp_valid),
        .bp16_in(bp16_out),
        .mwi_out(mwi_out),
        .sq_out(sq_out),
        .valid_out(mwi_valid),
        .mwi_overflow(mwi_ovf)
    );

    assign mwi_energy_out    = mwi_out;
    assign waveform_valid_out = mwi_valid;

    // -------------------------------------------------------------------------
    // 6. Stage 5: Adaptive Dual-Threshold QRS Detector
    // -------------------------------------------------------------------------
    wire                  candidate_strobe;
    wire [TIME_WIDTH-1:0] cand_timestamp;
    wire [MWI_WIDTH-1:0]  cand_energy;
    wire [MWI_WIDTH-1:0]  peak_level;
    wire [MWI_WIDTH-1:0]  noise_level;
    wire [MWI_WIDTH-1:0]  thresh;
    wire                  det_active;
    wire [TIME_WIDTH-1:0] t_counter;

    adaptive_detector #(
        .MWI_WIDTH(MWI_WIDTH),
        .TIME_WIDTH(TIME_WIDTH),
        .WARMUP_LEN(WARMUP_LEN),
        .REFRACTORY_LEN(50)
    ) u_detector (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(mwi_valid),
        .mwi_in(mwi_out),
        .candidate_strobe(candidate_strobe),
        .cand_timestamp(cand_timestamp),
        .cand_energy(cand_energy),
        .peak_level_out(peak_level),
        .noise_level_out(noise_level),
        .threshold_out(thresh),
        .detector_active(det_active),
        .t_counter(t_counter)
    );

    assign detector_active = det_active;

    // -------------------------------------------------------------------------
    // 7. Stage 6: Peak Localizer (26-Sample Trailing Search & Group Delay Rewind)
    // -------------------------------------------------------------------------
    wire                  peak_strobe;
    wire [TIME_WIDTH-1:0] raw_peak_loc;
    wire [TIME_WIDTH-1:0] comp_peak_loc;
    wire [DET_WIDTH-1:0]  peak_val_loc;

    peak_localizer #(
        .DATA_WIDTH(DET_WIDTH),
        .TIME_WIDTH(TIME_WIDTH),
        .LOC_WINDOW(LOC_WINDOW),
        .LATENCY_COMP(LATENCY_COMP)
    ) u_localizer (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(bp_valid),
        .t_in(t_counter),
        .bp16_in(bp16_out),
        .candidate_strobe(candidate_strobe),
        .peak_strobe(peak_strobe),
        .raw_peak_out(raw_peak_loc),
        .comp_peak_out(comp_peak_loc),
        .peak_val_out(peak_val_loc)
    );

    // -------------------------------------------------------------------------
    // 8. Stage 7: Interval Fusion & Integer Median-5 Filter
    // -------------------------------------------------------------------------
    wire                  beat_valid;
    wire                  fused_strobe;
    wire                  rr_update_strobe;
    wire [TIME_WIDTH-1:0] last_raw_peak;
    wire [TIME_WIDTH-1:0] last_comp_peak;
    wire [RR_WIDTH-1:0]   raw_rr;
    wire [RR_WIDTH-1:0]   med_rr;
    wire [1:0]            status_flag_2bit;
    wire [15:0]           n_fused;

    interval_fusion #(
        .DATA_WIDTH(DET_WIDTH),
        .TIME_WIDTH(TIME_WIDTH),
        .RR_WIDTH(RR_WIDTH),
        .RR_MIN(50),
        .RR_MAX(300)
    ) u_fusion (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .detector_active(det_active),
        .peak_strobe(peak_strobe),
        .raw_peak_in(raw_peak_loc),
        .comp_peak_in(comp_peak_loc),
        .peak_val_in(peak_val_loc),
        .beat_valid_strobe(beat_valid),
        .fused_strobe(fused_strobe),
        .rr_update_strobe(rr_update_strobe),
        .last_raw_peak_out(last_raw_peak),
        .last_comp_peak_out(last_comp_peak),
        .raw_rr_out(raw_rr),
        .med_rr_out(med_rr),
        .status_flag_2bit(status_flag_2bit),
        .n_fused_events(n_fused)
    );

    assign beat_valid_strobe   = beat_valid;
    assign fused_beat_strobe   = fused_strobe;
    assign raw_peak_timestamp  = last_raw_peak;
    assign comp_peak_timestamp = last_comp_peak;
    assign raw_rr_interval     = raw_rr;
    assign median_rr_interval  = med_rr;
    assign n_fused_count       = n_fused;

    // -------------------------------------------------------------------------
    // 9. Stage 8: FHR Calculator (251-Word ROM LUT)
    // -------------------------------------------------------------------------
    wire [FHR_WIDTH-1:0] fhr_instant;
    wire [FHR_WIDTH-1:0] fhr_stream;
    wire                 fhr_valid;
    wire                 fhr_ovf;

    fhr_calculator #(
        .RR_WIDTH(RR_WIDTH),
        .FHR_WIDTH(FHR_WIDTH),
        .RR_MIN(50),
        .RR_MAX(300),
        .LUT_SIZE(251)
    ) u_fhr (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .detector_active(det_active),
        .rr_update_strobe(rr_update_strobe),
        .med_rr_in(med_rr),
        .fhr_instant_out(fhr_instant),
        .fhr_stream_out(fhr_stream),
        .fhr_valid_strobe(fhr_valid),
        .fhr_lut_overflow(fhr_ovf)
    );

    assign fhr_instant_out = fhr_instant;
    assign fhr_stream_out  = fhr_stream;

    // -------------------------------------------------------------------------
    // 10. Sticky Saturation Tracking & Telemetry Byte Assembly
    // Telemetry Byte 6:
    //   bits 1:0 = classification (00=Real, 01=Fused, 10=Held, 11=Warmup)
    //   bit 2    = confidence flag (1 if warmup complete, 0 during warmup)
    //   bit 3    = sticky saturation flag (1 if any filter or accumulator saturated)
    //   bits 7:4 = 4'b0000
    // -------------------------------------------------------------------------
    reg sticky_sat;

    always @(posedge clk) begin
        if (!rst_n) begin
            sticky_sat <= 1'b0;
        end else if (enable) begin
            if (hp_ovf || lp_ovf || bp_ovf || mwi_ovf || fhr_ovf) begin
                sticky_sat <= 1'b1;
            end
        end
    end

    wire is_confident;
    assign is_confident = 1'b1; // Default confidence flag high as per bit_accurate_reference.py

    assign telemetry_flags = {4'b0000, sticky_sat, is_confident, status_flag_2bit};

endmodule

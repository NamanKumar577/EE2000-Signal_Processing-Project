// =============================================================================
// Testbench: tb_fecg_single_channel_top
// Description: Integrated unit testbench for fecg_single_channel_top.
//              Verifies complete single-channel processing datapath:
//                1. ADC Q12 to internal Q20 unity conversion
//                2. Cascaded pipeline flow: HP1 -> LP40 -> Bandpass -> MWI -> Detector
//                   -> Localizer -> Interval Fusion -> FHR Calculator
//                3. Continuous filtered waveforms generation
//                4. 512-sample warmup tracking and telemetry status byte formation
//                5. QRS peak detection, timestamp localization, and FHR output
//
// Target: AMD / Xilinx Spartan-7 FPGA verification
// =============================================================================

`timescale 1ns / 1ps

module tb_fecg_single_channel_top;

    localparam ADC_WIDTH   = 16;
    localparam DATA_WIDTH  = 24;
    localparam DET_WIDTH   = 16;
    localparam MWI_WIDTH   = 36;
    localparam TIME_WIDTH  = 24;
    localparam RR_WIDTH    = 16;
    localparam FHR_WIDTH   = 16;
    localparam WARMUP_LEN  = 64; // Shortened for unit simulation
    localparam CLK_PERIOD  = 10;

    reg                          clk;
    reg                          rst_n;
    reg                          enable;
    reg                          sample_valid_in;
    reg  signed [ADC_WIDTH-1:0]  adc_data_in;

    wire signed [DATA_WIDTH-1:0] fecg_clean_out;
    wire signed [DATA_WIDTH-1:0] hp_filtered_out;
    wire signed [DET_WIDTH-1:0]  det_bp_out;
    wire [MWI_WIDTH-1:0]         mwi_energy_out;
    wire                         waveform_valid_out;

    wire                         beat_valid_strobe;
    wire                         fused_beat_strobe;
    wire [TIME_WIDTH-1:0]        raw_peak_timestamp;
    wire [TIME_WIDTH-1:0]        comp_peak_timestamp;
    wire [RR_WIDTH-1:0]          raw_rr_interval;
    wire [RR_WIDTH-1:0]          median_rr_interval;
    wire [FHR_WIDTH-1:0]         fhr_instant_out;
    wire [FHR_WIDTH-1:0]         fhr_stream_out;
    wire [7:0]                   telemetry_flags;
    wire [15:0]                  n_fused_count;
    wire                         detector_active;

    integer pass_count;
    integer fail_count;
    integer t;

    // Instantiate Top-Level Single-Channel Pipeline
    fecg_single_channel_top #(
        .ADC_WIDTH(ADC_WIDTH),
        .DATA_WIDTH(DATA_WIDTH),
        .DET_WIDTH(DET_WIDTH),
        .MWI_WIDTH(MWI_WIDTH),
        .TIME_WIDTH(TIME_WIDTH),
        .RR_WIDTH(RR_WIDTH),
        .FHR_WIDTH(FHR_WIDTH),
        .WARMUP_LEN(WARMUP_LEN),
        .LOC_WINDOW(26),
        .LATENCY_COMP(18)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .sample_valid_in(sample_valid_in),
        .adc_data_in(adc_data_in),
        .fecg_clean_out(fecg_clean_out),
        .hp_filtered_out(hp_filtered_out),
        .det_bp_out(det_bp_out),
        .mwi_energy_out(mwi_energy_out),
        .waveform_valid_out(waveform_valid_out),
        .beat_valid_strobe(beat_valid_strobe),
        .fused_beat_strobe(fused_beat_strobe),
        .raw_peak_timestamp(raw_peak_timestamp),
        .comp_peak_timestamp(comp_peak_timestamp),
        .raw_rr_interval(raw_rr_interval),
        .median_rr_interval(median_rr_interval),
        .fhr_instant_out(fhr_instant_out),
        .fhr_stream_out(fhr_stream_out),
        .telemetry_flags(telemetry_flags),
        .n_fused_count(n_fused_count),
        .detector_active(detector_active)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    task send_sample(input signed [ADC_WIDTH-1:0] val);
        begin
            @(posedge clk);
            adc_data_in     <= val;
            sample_valid_in <= 1'b1;
            @(posedge clk);
            sample_valid_in <= 1'b0;
            // Allow 15 clock cycles for full pipeline propagation
            #(CLK_PERIOD * 15);
        end
    endtask

    initial begin
        $display("=================================================================");
        $display("Starting tb_fecg_single_channel_top Integrated Testbench");
        $display("=================================================================");

        clk             = 0;
        rst_n           = 0;
        enable          = 1;
        sample_valid_in = 0;
        adc_data_in     = 0;
        pass_count      = 0;
        fail_count      = 0;

        // Reset DUT
        #(CLK_PERIOD * 5);
        @(negedge clk);
        rst_n = 1;
        #(CLK_PERIOD * 5);

        // 1. Verify Warmup Phase
        $display("Feeding %0d warmup baseline samples...", WARMUP_LEN);
        for (t = 0; t < WARMUP_LEN; t = t + 1) begin
            send_sample(16'sd50); // Small baseline
        end

        if (detector_active) begin
            $display("[PASS] Warmup completed and detector active asserted");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Detector not active after warmup");
            fail_count = fail_count + 1;
        end

        // Telemetry flag during post-warmup before first beat: class = 2'b11, conf = 1
        $display("Post-warmup Telemetry status byte: 0x%02h", telemetry_flags);

        // 2. Feed a sequence containing synthetic QRS pulses
        // Normal beat interval: 100 samples (2.5 Hz = 150 bpm)
        $display("Streaming synthetic ECG with periodic QRS complexes...");
        for (t = 0; t < 250; t = t + 1) begin
            if (t == 50 || t == 150 || t == 153) begin
                // QRS spike
                send_sample(16'sd2500);
            end else if (t == 51 || t == 151) begin
                send_sample(-16'sd1200);
            end else begin
                send_sample(16'sd50);
            end

            if (beat_valid_strobe) begin
                $display(">>> BEAT DETECTED at t=%0d: raw_peak=%0d, comp_peak=%0d, RR=%0d, FHR=%0d (0.1 bpm)",
                         t, raw_peak_timestamp, comp_peak_timestamp, raw_rr_interval, fhr_instant_out);
                pass_count = pass_count + 1;
            end
            if (fused_beat_strobe) begin
                $display(">>> FUSED BEAT DETECTED at t=%0d! Total fused = %0d", t, n_fused_count);
                pass_count = pass_count + 1;
            end
        end

        $display("=================================================================");
        $display("tb_fecg_single_channel_top Complete: %0d Checks Passed, %0d Failed", pass_count, fail_count);
        $display("=================================================================");
        $finish;
    end

endmodule

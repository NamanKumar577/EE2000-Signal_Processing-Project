// =============================================================================
// Testbench: tb_fecg_single_channel_verifier
// Description: Automated Vivado End-to-End Verification Testbench.
//              Reads input stimulus samples from "stimulus_adc.hex", executes
//              fecg_single_channel_top.v in Vivado xsim, and writes all
//              waveforms and beat events to output text files for Python comparison.
//
// Target: AMD Vivado Simulator (xsim)
// =============================================================================

`timescale 1ns / 1ps

module tb_fecg_single_channel_verifier;

    parameter integer MAX_SAMPLES = 20000;
    localparam CLK_PERIOD = 10;

    reg                          clk;
    reg                          rst_n;
    reg                          enable;
    reg                          sample_valid_in;
    reg  signed [15:0]           adc_data_in;

    wire signed [23:0]           fecg_clean_out;
    wire signed [23:0]           hp_filtered_out;
    wire signed [15:0]           det_bp_out;
    wire [35:0]                  mwi_energy_out;
    wire                         waveform_valid_out;

    wire                         beat_valid_strobe;
    wire                         fused_beat_strobe;
    wire [23:0]                  raw_peak_timestamp;
    wire [23:0]                  comp_peak_timestamp;
    wire [15:0]                  raw_rr_interval;
    wire [15:0]                  median_rr_interval;
    wire [15:0]                  fhr_instant_out;
    wire [15:0]                  fhr_stream_out;
    wire [7:0]                   telemetry_flags;
    wire [15:0]                  n_fused_count;
    wire                         detector_active;

    reg signed [15:0]            stim_mem [0:MAX_SAMPLES-1];
    integer                      total_samples;
    integer                      sample_idx;
    integer                      fd_wave;
    integer                      fd_event;
    integer                      fd_count;

    fecg_single_channel_top #(
        .WARMUP_LEN(512),
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

    // Continuously monitor beat events on every clock cycle
    always @(posedge clk) begin
        if (rst_n && beat_valid_strobe) begin
            $fdisplay(fd_event, "%d %d %d %d %d %d %d",
                      sample_idx,
                      raw_peak_timestamp,
                      comp_peak_timestamp,
                      raw_rr_interval,
                      median_rr_interval,
                      fhr_instant_out,
                      fused_beat_strobe);
        end
    end

    initial begin
        clk             = 0;
        rst_n           = 0;
        enable          = 1;
        sample_valid_in = 0;
        adc_data_in     = 0;

        // Open input file and output files
        $readmemh("stimulus_adc.hex", stim_mem);
        fd_count = $fopen("stimulus_count.txt", "r");
        if (fd_count) begin
            $fscanf(fd_count, "%d", total_samples);
            $fclose(fd_count);
        end else begin
            total_samples = 15000;
        end

        fd_wave = $fopen("vivado_waveform_out.txt", "w");
        fd_event = $fopen("vivado_events_out.txt", "w");

        // Reset DUT
        #(CLK_PERIOD * 5);
        @(negedge clk);
        rst_n = 1;
        #(CLK_PERIOD * 5);

        // Stream all samples: 16 clock cycles per sample (160 ns simulation step)
        for (sample_idx = 0; sample_idx < total_samples; sample_idx = sample_idx + 1) begin
            @(posedge clk);
            adc_data_in     <= stim_mem[sample_idx];
            sample_valid_in <= 1'b1;
            @(posedge clk);
            sample_valid_in <= 1'b0;

            // Allow 15 clock cycles for full pipeline to complete and settle
            repeat (15) @(posedge clk);
            #1; // Allow NBA settling

            // Record waveform sample
            $fdisplay(fd_wave, "%d %d %d %d %d %d %d",
                      sample_idx,
                      hp_filtered_out,
                      fecg_clean_out,
                      det_bp_out,
                      mwi_energy_out,
                      fhr_stream_out,
                      telemetry_flags);
        end

        $fclose(fd_wave);
        $fclose(fd_event);
        $display("Vivado simulation complete! Processed %d samples.", total_samples);
        $finish;
    end

endmodule

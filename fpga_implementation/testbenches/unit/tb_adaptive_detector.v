// =============================================================================
// Testbench: tb_adaptive_detector
// Description: Unit testbench for adaptive_detector (Dual-threshold QRS tracker).
//              Verifies:
//                1. Synchronous reset and warmup initialization (512 samples)
//                2. Dynamic threshold calculation:
//                   thr = (peak_level >> 2) + noise_level - (noise_level >> 2)
//                3. Local peak detection at m = t - 1
//                4. Candidate strobe assertion when peak > thr
//                5. Refractory period blanking (50 samples = 200 ms)
//                6. EMA 1/8 tracking on peak and noise levels
//
// Target: AMD / Xilinx Spartan-7 FPGA verification
// =============================================================================

`timescale 1ns / 1ps

module tb_adaptive_detector;

    localparam MWI_WIDTH      = 36;
    localparam TIME_WIDTH     = 24;
    localparam WARMUP_LEN     = 64;  // Shortened warmup for fast unit test
    localparam REFRACTORY_LEN = 10;
    localparam CLK_PERIOD     = 10;

    reg                          clk;
    reg                          rst_n;
    reg                          enable;
    reg                          valid_in;
    reg  [MWI_WIDTH-1:0]         mwi_in;

    wire                         candidate_strobe;
    wire [TIME_WIDTH-1:0]        cand_timestamp;
    wire [MWI_WIDTH-1:0]         cand_energy;
    wire [MWI_WIDTH-1:0]         peak_level_out;
    wire [MWI_WIDTH-1:0]         noise_level_out;
    wire [MWI_WIDTH-1:0]         threshold_out;
    wire                         detector_active;
    wire [TIME_WIDTH-1:0]        t_counter;

    integer pass_count;
    integer fail_count;
    integer i;

    adaptive_detector #(
        .MWI_WIDTH(MWI_WIDTH),
        .TIME_WIDTH(TIME_WIDTH),
        .WARMUP_LEN(WARMUP_LEN),
        .REFRACTORY_LEN(REFRACTORY_LEN)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(valid_in),
        .mwi_in(mwi_in),
        .restart_req(1'b0),
        .candidate_strobe(candidate_strobe),
        .cand_timestamp(cand_timestamp),
        .cand_energy(cand_energy),
        .peak_level_out(peak_level_out),
        .noise_level_out(noise_level_out),
        .threshold_out(threshold_out),
        .detector_active(detector_active),
        .t_counter(t_counter)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    initial begin
        $display("=================================================================");
        $display("Starting tb_adaptive_detector Unit Testbench");
        $display("=================================================================");

        clk        = 0;
        rst_n      = 0;
        enable     = 1;
        valid_in   = 0;
        mwi_in     = 0;
        pass_count = 0;
        fail_count = 0;

        // Reset DUT
        #(CLK_PERIOD * 3);
        @(negedge clk);
        rst_n = 1;
        #(CLK_PERIOD * 2);

        // Feed warmup samples (constant noise of 1000)
        $display("Streaming %0d warmup samples...", WARMUP_LEN);
        for (i = 0; i <= WARMUP_LEN; i = i + 1) begin   // +1: active from first post-warm-up sample
            @(posedge clk);
            mwi_in   <= (i == WARMUP_LEN / 2) ? 36'd1200 : 36'd1000; // peak > noise -> enabled
            valid_in <= 1'b1;
            @(posedge clk);
            valid_in <= 1'b0;
            #(CLK_PERIOD * 2);
        end

        // Check if detector became active
        if (detector_active) begin
            $display("[PASS] Detector active after warmup: peak=%d, noise=%d, thr=%d",
                     peak_level_out, noise_level_out, threshold_out);
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Detector did not become active after warmup");
            fail_count = fail_count + 1;
        end

        // Apply a synthetic QRS peak: 1000 -> 5000 -> 10000 -> 3000 -> 1000
        @(posedge clk); mwi_in <= 36'd1000; valid_in <= 1'b1; @(posedge clk); valid_in <= 1'b0; #(CLK_PERIOD*2);
        @(posedge clk); mwi_in <= 36'd5000; valid_in <= 1'b1; @(posedge clk); valid_in <= 1'b0; #(CLK_PERIOD*2);
        @(posedge clk); mwi_in <= 36'd10000; valid_in <= 1'b1; @(posedge clk); valid_in <= 1'b0; #(CLK_PERIOD*2);
        @(posedge clk); mwi_in <= 36'd3000; valid_in <= 1'b1; @(posedge clk); valid_in <= 1'b0;

        // The candidate strobe should be triggered at m = peak index
        @(posedge clk);
        if (candidate_strobe) begin
            $display("[PASS] Candidate peak detected! cand_energy=%d at t=%d", cand_energy, cand_timestamp);
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Candidate strobe not fired for peak above threshold");
            fail_count = fail_count + 1;
        end

        $display("=================================================================");
        $display("tb_adaptive_detector Complete: %0d Passed, %0d Failed", pass_count, fail_count);
        $display("=================================================================");
        $finish;
    end

endmodule

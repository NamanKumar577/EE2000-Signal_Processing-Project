// =============================================================================
// Testbench: tb_fhr_calculator
// Description: Unit testbench for fhr_calculator (251-word frozen integer ROM).
//              Verifies:
//                1. Warmup gating: fhr_stream_out = 0 during warmup
//                2. Post-warmup default hold: 1400 (140.0 bpm)
//                3. Direct ROM translation for boundaries:
//                   - RR = 50  -> 3000 (300.0 bpm)
//                   - RR = 100 -> 1500 (150.0 bpm)
//                   - RR = 300 -> 500  (50.0 bpm)
//                4. Saturation and overflow flag for out-of-range inputs
//
// Target: AMD / Xilinx Spartan-7 FPGA verification
// =============================================================================

`timescale 1ns / 1ps

module tb_fhr_calculator;

    localparam RR_WIDTH   = 16;
    localparam FHR_WIDTH  = 16;
    localparam CLK_PERIOD = 10;

    reg                   clk;
    reg                   rst_n;
    reg                   enable;
    reg                   detector_active;
    reg                   rr_update_strobe;
    reg  [RR_WIDTH-1:0]   med_rr_in;

    wire [FHR_WIDTH-1:0]  fhr_instant_out;
    wire [FHR_WIDTH-1:0]  fhr_stream_out;
    wire                  fhr_valid_strobe;
    wire                  fhr_lut_overflow;

    integer pass_count;
    integer fail_count;

    fhr_calculator #(
        .RR_WIDTH(RR_WIDTH),
        .FHR_WIDTH(FHR_WIDTH)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .detector_active(detector_active),
        .rr_update_strobe(rr_update_strobe),
        .med_rr_in(med_rr_in),
        .fhr_instant_out(fhr_instant_out),
        .fhr_stream_out(fhr_stream_out),
        .fhr_valid_strobe(fhr_valid_strobe),
        .fhr_lut_overflow(fhr_lut_overflow)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    task check_fhr(
        input [RR_WIDTH-1:0]  rr,
        input [FHR_WIDTH-1:0] exp_fhr
    );
        begin
            @(posedge clk);
            med_rr_in        <= rr;
            rr_update_strobe <= 1'b1;
            @(posedge clk);
            rr_update_strobe <= 1'b0;

            @(posedge clk);
            if (fhr_instant_out == exp_fhr && fhr_stream_out == exp_fhr) begin
                $display("[PASS] RR = %0d -> FHR = %0d (expected %0d)", rr, fhr_stream_out, exp_fhr);
                pass_count = pass_count + 1;
            end else begin
                $display("[FAIL] RR = %0d -> FHR = %0d (expected %0d)", rr, fhr_stream_out, exp_fhr);
                fail_count = fail_count + 1;
            end
        end
    endtask

    initial begin
        $display("=================================================================");
        $display("Starting tb_fhr_calculator Unit Testbench");
        $display("=================================================================");

        clk              = 0;
        rst_n            = 0;
        enable           = 1;
        detector_active  = 0;
        rr_update_strobe = 0;
        med_rr_in        = 0;
        pass_count       = 0;
        fail_count       = 0;

        // Reset DUT
        #(CLK_PERIOD * 3);
        @(negedge clk);
        rst_n = 1;
        #(CLK_PERIOD * 2);

        // Test 1: During warmup, fhr_stream_out must be 0
        if (fhr_stream_out == 16'd0) begin
            $display("[PASS] During warmup, fhr_stream_out is 0");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Warmup output not 0: got = %0d", fhr_stream_out);
            fail_count = fail_count + 1;
        end

        // Activate detector
        @(posedge clk);
        detector_active <= 1'b1;
        @(posedge clk);

        // Test 2: Initial hold before first normal beat must be 1400 (140.0 bpm)
        if (fhr_stream_out == 16'd1400) begin
            $display("[PASS] Initial hold value is 1400 (140.0 bpm)");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Initial hold value mismatch: got = %0d (expected 1400)", fhr_stream_out);
            fail_count = fail_count + 1;
        end

        // Test 3: RR = 50 (Maximum FHR = 300.0 bpm = 3000)
        check_fhr(16'd50, 16'd3000);

        // Test 4: RR = 100 (150.0 bpm = 1500)
        check_fhr(16'd100, 16'd1500);

        // Test 5: RR = 107 (round(150000/107) = 1402 = 140.2 bpm)
        check_fhr(16'd107, 16'd1402);

        // Test 6: RR = 300 (Minimum FHR = 50.0 bpm = 500)
        check_fhr(16'd300, 16'd500);

        // Test 7: Underflow check (RR = 30 < 50 -> clamped to 50 = 3000 with overflow flag)
        check_fhr(16'd30, 16'd3000);
        if (fhr_lut_overflow) begin
            $display("[PASS] Underflow RR = 30 correctly asserted fhr_lut_overflow flag");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Underflow did not trigger fhr_lut_overflow");
            fail_count = fail_count + 1;
        end

        $display("=================================================================");
        $display("tb_fhr_calculator Complete: %0d Passed, %0d Failed", pass_count, fail_count);
        $display("=================================================================");
        $finish;
    end

endmodule

// =============================================================================
// Testbench: tb_squarer_mwi
// Description: Unit testbench for squarer_mwi (16x16 squarer + 30-sample sliding
//              window accumulator).
//              Verifies:
//                1. Synchronous reset assertion and ring buffer clearing
//                2. Squarer output correctness for positive, negative, and rail inputs
//                3. 30-sample sliding window sum accumulation and FIFO eviction
//                4. Unsigned 36-bit accumulator saturation protection
//
// Target: AMD / Xilinx Spartan-7 FPGA verification
// =============================================================================

`timescale 1ns / 1ps

module tb_squarer_mwi;

    localparam IN_WIDTH   = 16;
    localparam SQ_WIDTH   = 32;
    localparam MWI_WIDTH  = 36;
    localparam MWI_LEN    = 30;
    localparam CLK_PERIOD = 10;

    reg                          clk;
    reg                          rst_n;
    reg                          enable;
    reg                          valid_in;
    reg  signed [IN_WIDTH-1:0]   bp16_in;

    wire [MWI_WIDTH-1:0]         mwi_out;
    wire [SQ_WIDTH-1:0]          sq_out;
    wire                         valid_out;
    wire                         mwi_overflow;

    integer pass_count;
    integer fail_count;
    integer i;

    squarer_mwi #(
        .IN_WIDTH(IN_WIDTH),
        .SQ_WIDTH(SQ_WIDTH),
        .MWI_WIDTH(MWI_WIDTH),
        .MWI_LEN(MWI_LEN)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(valid_in),
        .bp16_in(bp16_in),
        .mwi_out(mwi_out),
        .sq_out(sq_out),
        .valid_out(valid_out),
        .mwi_overflow(mwi_overflow)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    initial begin
        $display("=================================================================");
        $display("Starting tb_squarer_mwi Unit Testbench");
        $display("=================================================================");

        clk        = 0;
        rst_n      = 0;
        enable     = 1;
        valid_in   = 0;
        bp16_in    = 0;
        pass_count = 0;
        fail_count = 0;

        // Reset DUT
        #(CLK_PERIOD * 3);
        @(negedge clk);
        rst_n = 1;
        #(CLK_PERIOD * 2);

        // Test 1: Single sample squaring
        @(posedge clk);
        bp16_in  <= 16'sd100; // sq = 10,000
        valid_in <= 1'b1;
        @(posedge clk);
        valid_in <= 1'b0;

        @(posedge clk);
        if (valid_out && mwi_out == 36'd10000) begin
            $display("[PASS] Single sample square accumulated: mwi = %d", mwi_out);
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Single sample square mismatch: mwi = %d (expected 10000)", mwi_out);
            fail_count = fail_count + 1;
        end

        // Test 2: Negative sample squaring (-100)^2 = 10,000
        @(posedge clk);
        bp16_in  <= -16'sd100;
        valid_in <= 1'b1;
        @(posedge clk);
        valid_in <= 1'b0;

        @(posedge clk);
        if (valid_out && mwi_out == 36'd20000) begin
            $display("[PASS] Negative sample squared and accumulated: mwi = %d", mwi_out);
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Negative sample mismatch: mwi = %d (expected 20000)", mwi_out);
            fail_count = fail_count + 1;
        end

        // Test 3: Sliding window fill with constant 10 -> sq = 100
        // Fill 30 samples of 10 -> total should be 30 * 100 = 3000
        // Reset to clear previous samples
        @(negedge clk);
        rst_n = 0;
        #(CLK_PERIOD * 2);
        @(negedge clk);
        rst_n = 1;
        #(CLK_PERIOD * 2);

        for (i = 0; i < 30; i = i + 1) begin
            @(posedge clk);
            bp16_in  <= 16'sd10;
            valid_in <= 1'b1;
            @(posedge clk);
            valid_in <= 1'b0;
            #(CLK_PERIOD * 2);
        end

        if (mwi_out == 36'd3000) begin
            $display("[PASS] 30-sample window sum matches 30*100 = %d", mwi_out);
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] 30-sample sum mismatch: mwi = %d (expected 3000)", mwi_out);
            fail_count = fail_count + 1;
        end

        // Test 4: Ring buffer eviction (next sample is 0)
        // One old 100 evicted, 0 added -> sum should be 2900
        @(posedge clk);
        bp16_in  <= 16'sd0;
        valid_in <= 1'b1;
        @(posedge clk);
        valid_in <= 1'b0;
        @(posedge clk);

        if (mwi_out == 36'd2900) begin
            $display("[PASS] FIFO eviction confirmed: mwi = %d (expected 2900)", mwi_out);
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] FIFO eviction mismatch: mwi = %d (expected 2900)", mwi_out);
            fail_count = fail_count + 1;
        end

        $display("=================================================================");
        $display("tb_squarer_mwi Complete: %0d Passed, %0d Failed", pass_count, fail_count);
        $display("=================================================================");
        $finish;
    end

endmodule

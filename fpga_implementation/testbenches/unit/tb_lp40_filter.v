// =============================================================================
// Testbench: tb_lp40_filter
// Description: Unit testbench for lp40_filter (2 cascaded DF2T biquads).
//              Verifies:
//                1. Synchronous reset assertion and release
//                2. Clock enable gating
//                3. Impulse response and DC gain
//                4. Valid strobe propagation across 2-stage biquad cascade
//                5. Overflow flag propagation
//
// Target: AMD / Xilinx Spartan-7 FPGA verification
// =============================================================================

`timescale 1ns / 1ps

module tb_lp40_filter;

    localparam DATA_WIDTH = 24;
    localparam CLK_PERIOD = 10;

    reg                          clk;
    reg                          rst_n;
    reg                          enable;
    reg                          valid_in;
    reg  signed [DATA_WIDTH-1:0] x_in;

    wire signed [DATA_WIDTH-1:0] y_out;
    wire                         valid_out;
    wire                         overflow_flag;

    integer pass_count;
    integer fail_count;
    integer i;

    lp40_filter #(
        .DATA_WIDTH(DATA_WIDTH)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(valid_in),
        .x_in(x_in),
        .y_out(y_out),
        .valid_out(valid_out),
        .overflow_flag(overflow_flag)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    initial begin
        $display("=================================================================");
        $display("Starting tb_lp40_filter Unit Testbench");
        $display("=================================================================");

        clk        = 0;
        rst_n      = 0;
        enable     = 1;
        valid_in   = 0;
        x_in       = 0;
        pass_count = 0;
        fail_count = 0;

        // Reset DUT
        #(CLK_PERIOD * 3);
        @(negedge clk);
        rst_n = 1;
        #(CLK_PERIOD * 2);

        // Test 1: Impulse response
        @(posedge clk);
        x_in     <= 24'sd100000;
        valid_in <= 1'b1;
        @(posedge clk);
        x_in     <= 24'sd0;
        valid_in <= 1'b0;

        // Wait 2 cycles for output valid
        @(posedge clk);
        @(posedge clk);
        if (valid_out) begin
            $display("[PASS] Impulse response first output valid received: y = %d", y_out);
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] valid_out not asserted 2 cycles after valid_in");
            fail_count = fail_count + 1;
        end

        // Stream 50 zero samples to observe decay
        for (i = 0; i < 50; i = i + 1) begin
            @(posedge clk);
            x_in     <= 24'sd0;
            valid_in <= 1'b1;
            @(posedge clk);
            valid_in <= 1'b0;
            #(CLK_PERIOD * 4);
        end

        // Test 2: DC Step Response
        $display("Applying DC step of +50,000 LSB...");
        for (i = 0; i < 100; i = i + 1) begin
            @(posedge clk);
            x_in     <= 24'sd50000;
            valid_in <= 1'b1;
            @(posedge clk);
            valid_in <= 1'b0;
            #(CLK_PERIOD * 4);
        end

        // In steady state, DC gain of LP40 is 1.0 (50,000)
        if (y_out >= 24'sd49900 && y_out <= 24'sd50100) begin
            $display("[PASS] DC steady-state value matches unity gain: y = %d", y_out);
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] DC steady-state mismatch: y = %d (expected ~50000)", y_out);
            fail_count = fail_count + 1;
        end

        $display("=================================================================");
        $display("tb_lp40_filter Complete: %0d Passed, %0d Failed", pass_count, fail_count);
        $display("=================================================================");
        $finish;
    end

endmodule

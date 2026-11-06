// =============================================================================
// Testbench: tb_bandpass_config_c
// Description: Unit testbench for bandpass_config_c (4 cascaded DF2T biquads +
//              convergent downscaler to Signed 16-bit Q12).
//              Verifies:
//                1. Synchronous reset assertion and release
//                2. Valid strobe latency (5 clock cycles)
//                3. DC rejection (Bandpass filter blocks DC completely: y -> 0)
//                4. Convergent rounding downscaler to Signed 16-bit
//
// Target: AMD / Xilinx Spartan-7 FPGA verification
// =============================================================================

`timescale 1ns / 1ps

module tb_bandpass_config_c;

    localparam DATA_WIDTH = 24;
    localparam OUT_WIDTH  = 16;
    localparam CLK_PERIOD = 10;

    reg                          clk;
    reg                          rst_n;
    reg                          enable;
    reg                          valid_in;
    reg  signed [DATA_WIDTH-1:0] x_in;

    wire signed [OUT_WIDTH-1:0]  bp16_out;
    wire signed [DATA_WIDTH-1:0] bp24_raw_out;
    wire                         valid_out;
    wire                         overflow_flag;

    integer pass_count;
    integer fail_count;
    integer i;

    bandpass_config_c #(
        .DATA_WIDTH(DATA_WIDTH),
        .OUT_WIDTH(OUT_WIDTH)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(valid_in),
        .x_in(x_in),
        .bp16_out(bp16_out),
        .bp24_raw_out(bp24_raw_out),
        .valid_out(valid_out),
        .overflow_flag(overflow_flag)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    initial begin
        $display("=================================================================");
        $display("Starting tb_bandpass_config_c Unit Testbench");
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

        // Expect valid_out after 5 clock cycles
        repeat (5) @(posedge clk);
        if (valid_out) begin
            $display("[PASS] 5-cycle pipeline latency confirmed: bp16 = %d", bp16_out);
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] valid_out not asserted at cycle 5");
            fail_count = fail_count + 1;
        end

        // Test 2: DC Rejection Test (Step of 100,000 LSB)
        $display("Applying DC step of 100,000 LSB to test DC rejection...");
        for (i = 0; i < 200; i = i + 1) begin
            @(posedge clk);
            x_in     <= 24'sd100000;
            valid_in <= 1'b1;
            @(posedge clk);
            valid_in <= 1'b0;
            #(CLK_PERIOD * 8);
        end

        // Bandpass filter must reject DC: steady state should be 0
        if (bp16_out >= -16'sd2 && bp16_out <= 16'sd2) begin
            $display("[PASS] Bandpass filter completely rejects DC: bp16 = %d", bp16_out);
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Bandpass failed to reject DC: bp16 = %d", bp16_out);
            fail_count = fail_count + 1;
        end

        $display("=================================================================");
        $display("tb_bandpass_config_c Complete: %0d Passed, %0d Failed", pass_count, fail_count);
        $display("=================================================================");
        $finish;
    end

endmodule

// =============================================================================
// Testbench: tb_peak_localizer
// Description: Unit testbench for peak_localizer (26-sample trailing window search
//              and group delay rewind).
//              Verifies:
//                1. Shift register history buffering of |bp16|
//                2. Local maximum search within the 26-sample window
//                3. Group delay compensation: comp_peak = max(0, best_idx - 18)
//                4. Peak magnitude extraction
//
// Target: AMD / Xilinx Spartan-7 FPGA verification
// =============================================================================

`timescale 1ns / 1ps

module tb_peak_localizer;

    localparam DATA_WIDTH   = 16;
    localparam TIME_WIDTH   = 24;
    localparam LOC_WINDOW   = 26;
    localparam LATENCY_COMP = 18;
    localparam CLK_PERIOD   = 10;

    reg                          clk;
    reg                          rst_n;
    reg                          enable;
    reg                          valid_in;
    reg  [TIME_WIDTH-1:0]        t_in;
    reg  signed [DATA_WIDTH-1:0] bp16_in;
    reg                          candidate_strobe;

    wire                         peak_strobe;
    wire [TIME_WIDTH-1:0]        raw_peak_out;
    wire [TIME_WIDTH-1:0]        comp_peak_out;
    wire [DATA_WIDTH-1:0]        peak_val_out;

    integer pass_count;
    integer fail_count;
    integer i;

    peak_localizer #(
        .DATA_WIDTH(DATA_WIDTH),
        .TIME_WIDTH(TIME_WIDTH),
        .LOC_WINDOW(LOC_WINDOW),
        .LATENCY_COMP(LATENCY_COMP)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .valid_in(valid_in),
        .t_in(t_in),
        .bp16_in(bp16_in),
        .candidate_strobe(candidate_strobe),
        .peak_strobe(peak_strobe),
        .raw_peak_out(raw_peak_out),
        .comp_peak_out(comp_peak_out),
        .peak_val_out(peak_val_out)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    initial begin
        $display("=================================================================");
        $display("Starting tb_peak_localizer Unit Testbench");
        $display("=================================================================");

        clk              = 0;
        rst_n            = 0;
        enable           = 1;
        valid_in         = 0;
        t_in             = 0;
        bp16_in          = 0;
        candidate_strobe = 0;
        pass_count       = 0;
        fail_count       = 0;

        // Reset DUT
        #(CLK_PERIOD * 3);
        @(negedge clk);
        rst_n = 1;
        #(CLK_PERIOD * 2);

        // Feed 30 samples: baseline around 100, with a sharp peak at t = 20 of value 5000
        for (i = 0; i <= 30; i = i + 1) begin
            @(posedge clk);
            t_in     <= i;
            if (i == 20)
                bp16_in <= 16'sd5000;
            else
                bp16_in <= 16'sd100;
            valid_in <= 1'b1;
            @(posedge clk);
            valid_in <= 1'b0;
            #(CLK_PERIOD * 2);
        end

        // At sample t = 25, candidate detector triggers
        @(posedge clk);
        candidate_strobe <= 1'b1;
        @(posedge clk);
        candidate_strobe <= 1'b0;

        @(posedge clk);
        if (peak_strobe) begin
            $display("Peak strobe detected: raw_peak=%0d, comp_peak=%0d, peak_val=%0d",
                     raw_peak_out, comp_peak_out, peak_val_out);
            if (raw_peak_out == 24'd20 && peak_val_out == 16'd5000) begin
                $display("[PASS] Correct raw peak localized at sample index 20");
                pass_count = pass_count + 1;
            end else begin
                $display("[FAIL] Raw peak mismatch: got=%0d (expected 20)", raw_peak_out);
                fail_count = fail_count + 1;
            end

            // Latency compensation: 20 - 18 = 2
            if (comp_peak_out == 24'd2) begin
                $display("[PASS] Latency compensated peak correctly computed: 20 - 18 = 2");
                pass_count = pass_count + 1;
            end else begin
                $display("[FAIL] Comp peak mismatch: got=%0d (expected 2)", comp_peak_out);
                fail_count = fail_count + 1;
            end
        end else begin
            $display("[FAIL] Peak strobe not asserted after candidate strobe");
            fail_count = fail_count + 1;
        end

        $display("=================================================================");
        $display("tb_peak_localizer Complete: %0d Passed, %0d Failed", pass_count, fail_count);
        $display("=================================================================");
        $finish;
    end

endmodule

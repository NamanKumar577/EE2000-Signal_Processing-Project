// =============================================================================
// Testbench: tb_detector_golden
// Streams a real MWI energy sequence (from the bit-accurate model run on a
// FECGSYNDB record with the host 0xC4/0xC3 schedule) through adaptive_detector
// with production parameters, including the 0xC4 warm-up restart pulses, and
// dumps every candidate (m, energy) for bit-exact comparison in Python.
// Stimulus line format: <mwi 9 hex digits> <restart_before_this_sample 1 hex>
// =============================================================================
`timescale 1ns / 1ps

module tb_detector_golden;
    localparam MWI_WIDTH = 36;
    localparam TIME_WIDTH = 24;
    localparam MAXN = 80000;

    reg clk = 0, rst_n = 0, valid_in = 0, restart_req = 0;
    reg [MWI_WIDTH-1:0] mwi_in = 0;
    wire candidate_strobe, detector_active;
    wire [TIME_WIDTH-1:0] cand_timestamp, t_counter;
    wire [MWI_WIDTH-1:0] cand_energy, pk, ns, th;

    reg [MWI_WIDTH+3:0] stim [0:MAXN-1];   // {restart(4b), mwi(36b)}
    integer n, i, fo, ncand;

    adaptive_detector #(.MWI_WIDTH(36), .TIME_WIDTH(24), .WARMUP_LEN(512),
                        .REFRACTORY_LEN(50), .RESTART_DELAY(128)) dut (
        .clk(clk), .rst_n(rst_n), .enable(1'b1), .valid_in(valid_in), .mwi_in(mwi_in),
        .restart_req(restart_req), .candidate_strobe(candidate_strobe),
        .cand_timestamp(cand_timestamp), .cand_energy(cand_energy),
        .peak_level_out(pk), .noise_level_out(ns), .threshold_out(th),
        .detector_active(detector_active), .t_counter(t_counter));

    always #5 clk = ~clk;

    always @(posedge clk) if (candidate_strobe) begin
        $fdisplay(fo, "%0d %0d", cand_timestamp, cand_energy);
        ncand = ncand + 1;
    end

    initial begin
        $readmemh("detector_stim.hex", stim);
        n = 0;
        while (n < MAXN && stim[n] !== {(MWI_WIDTH+4){1'bx}}) n = n + 1;
        fo = $fopen("detector_cand_rtl.txt", "w");
        ncand = 0;
        repeat (4) @(posedge clk);
        rst_n = 1;
        repeat (2) @(posedge clk);
        for (i = 0; i < n; i = i + 1) begin
            if (stim[i][MWI_WIDTH+3:MWI_WIDTH] != 0) begin   // 0xC4 accepted before sample i
                @(negedge clk) restart_req = 1;
                @(negedge clk) restart_req = 0;
            end
            @(negedge clk) begin mwi_in = stim[i][MWI_WIDTH-1:0]; valid_in = 1; end
            @(negedge clk) valid_in = 0;
            repeat (2) @(negedge clk);
        end
        repeat (4) @(posedge clk);
        $display("TB_DONE samples=%0d candidates=%0d", n, ncand);
        $fclose(fo);
        $finish;
    end
endmodule

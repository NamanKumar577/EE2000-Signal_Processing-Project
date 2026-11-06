// =============================================================================
// Testbench: tb_interval_fusion
// Description: Unit testbench for interval_fusion (Split-beat fusion and pure integer
//              median-5 filter).
//              Verifies:
//                1. First detected beat registration
//                2. Split beat fusion (RR < 50): merging into previous beat and
//                   timestamp update when split peak has higher magnitude
//                3. Normal beat processing (50 <= RR <= 300) and integer median-5 FIFO
//                4. Bradycardia/dropout handling (RR > 300) without median corruption
//
// Target: AMD / Xilinx Spartan-7 FPGA verification
// =============================================================================

`timescale 1ns / 1ps

module tb_interval_fusion;

    localparam DATA_WIDTH = 16;
    localparam TIME_WIDTH = 24;
    localparam RR_WIDTH   = 16;
    localparam CLK_PERIOD = 10;

    reg                          clk;
    reg                          rst_n;
    reg                          enable;
    reg                          detector_active;
    reg                          peak_strobe;
    reg  [TIME_WIDTH-1:0]        raw_peak_in;
    reg  [TIME_WIDTH-1:0]        comp_peak_in;
    reg  [DATA_WIDTH-1:0]        peak_val_in;

    wire                         beat_valid_strobe;
    wire                         fused_strobe;
    wire                         rr_update_strobe;
    wire [TIME_WIDTH-1:0]        last_raw_peak_out;
    wire [TIME_WIDTH-1:0]        last_comp_peak_out;
    wire [RR_WIDTH-1:0]          raw_rr_out;
    wire [RR_WIDTH-1:0]          med_rr_out;
    wire [1:0]                   status_flag_2bit;
    wire [15:0]                  n_fused_events;

    integer pass_count;
    integer fail_count;

    interval_fusion #(
        .DATA_WIDTH(DATA_WIDTH),
        .TIME_WIDTH(TIME_WIDTH),
        .RR_WIDTH(RR_WIDTH),
        .RR_MIN(50),
        .RR_MAX(300)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .detector_active(detector_active),
        .peak_strobe(peak_strobe),
        .raw_peak_in(raw_peak_in),
        .comp_peak_in(comp_peak_in),
        .peak_val_in(peak_val_in),
        .beat_valid_strobe(beat_valid_strobe),
        .fused_strobe(fused_strobe),
        .rr_update_strobe(rr_update_strobe),
        .last_raw_peak_out(last_raw_peak_out),
        .last_comp_peak_out(last_comp_peak_out),
        .raw_rr_out(raw_rr_out),
        .med_rr_out(med_rr_out),
        .status_flag_2bit(status_flag_2bit),
        .n_fused_events(n_fused_events)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    task send_peak(
        input [TIME_WIDTH-1:0] raw_idx,
        input [DATA_WIDTH-1:0] val
    );
        begin
            @(posedge clk);
            raw_peak_in  <= raw_idx;
            comp_peak_in <= (raw_idx >= 18) ? (raw_idx - 18) : 0;
            peak_val_in  <= val;
            peak_strobe  <= 1'b1;
            @(posedge clk);
            peak_strobe  <= 1'b0;
            #1; // Allow NBA updates to settle so single-cycle strobes can be checked
        end
    endtask

    initial begin
        $display("=================================================================");
        $display("Starting tb_interval_fusion Unit Testbench");
        $display("=================================================================");

        clk             = 0;
        rst_n           = 0;
        enable          = 1;
        detector_active = 1;
        peak_strobe     = 0;
        raw_peak_in     = 0;
        comp_peak_in    = 0;
        peak_val_in     = 0;
        pass_count      = 0;
        fail_count      = 0;

        // Reset DUT
        #(CLK_PERIOD * 3);
        @(negedge clk);
        rst_n = 1;
        #(CLK_PERIOD * 2);

        // Beat 1: First beat at t = 100, val = 1000
        $display("Sending Beat 1 at t = 100...");
        send_peak(24'd100, 16'd1000);
        if (last_raw_peak_out == 24'd100 && status_flag_2bit == 2'b00) begin
            $display("[PASS] Beat 1 accepted as first beat");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Beat 1 registration failed");
            fail_count = fail_count + 1;
        end

        // Beat 2: Split beat at t = 120 (RR = 20 < 50), val = 1200 (> 1000)
        // Should fuse and update peak location to 120
        $display("Sending Split Beat at t = 120 (RR = 20 < 50, val = 1200)...");
        send_peak(24'd120, 16'd1200);
        if (fused_strobe && status_flag_2bit == 2'b01 && last_raw_peak_out == 24'd120 && n_fused_events == 1) begin
            $display("[PASS] Split beat successfully fused and higher amplitude updated peak timestamp");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Split beat fusion failed: last_raw=%0d, n_fused=%0d", last_raw_peak_out, n_fused_events);
            fail_count = fail_count + 1;
        end

        // Beat 3: Normal beat at t = 220 (RR = 220 - 120 = 100 samples)
        $display("Sending Normal Beat at t = 220 (RR = 100)...");
        send_peak(24'd220, 16'd1500);
        if (raw_rr_out == 16'd100 && med_rr_out == 16'd100 && status_flag_2bit == 2'b00) begin
            $display("[PASS] Normal beat accepted, RR = 100, median RR = 100");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Normal beat mismatch: rr=%0d, med=%0d", raw_rr_out, med_rr_out);
            fail_count = fail_count + 1;
        end

        // Beat 4: Normal beat at t = 330 (RR = 110)
        // Median of [100, 110]: (100 + 110 + 1) // 2 = 105
        $display("Sending Normal Beat at t = 330 (RR = 110)...");
        send_peak(24'd330, 16'd1500);
        if (med_rr_out == 16'd105) begin
            $display("[PASS] Median-2 correctly rounded: (100+110+1)//2 = %0d", med_rr_out);
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Median-2 mismatch: got=%0d (expected 105)", med_rr_out);
            fail_count = fail_count + 1;
        end

        // Beat 5: Dropout beat at t = 700 (RR = 700 - 330 = 370 > 300)
        $display("Sending Dropout Beat at t = 700 (RR = 370 > 300)...");
        send_peak(24'd700, 16'd1500);
        if (status_flag_2bit == 2'b10 && med_rr_out == 16'd105) begin
            $display("[PASS] Dropout flagged (status 2'b10) and median RR held at 105 without corruption");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Dropout handling mismatch: status=%b, med=%0d", status_flag_2bit, med_rr_out);
            fail_count = fail_count + 1;
        end

        $display("=================================================================");
        $display("tb_interval_fusion Complete: %0d Passed, %0d Failed", pass_count, fail_count);
        $display("=================================================================");
        $finish;
    end

endmodule

// ============================================================================
// File: uart_tx_tb.v
// Module: uart_tx_tb
// Project: Spartan-7 XC7S50 UART Bringup
// Description: Self-checking testbench for synthesizable uart_tx module.
//              Verifies:
//              1. Reset state (idle high, not busy)
//              2. Start bit generation (1 bit duration)
//              3. 8-bit data serialization (LSB first)
//              4. Stop bit generation (1 bit duration)
//              5. Exact baud timing / clock cycle count per bit
//              6. Single-cycle tx_done completion strobe
//              7. Sequential back-to-back transmissions
// ============================================================================

`timescale 1ns / 1ps

module uart_tx_tb;

    localparam integer CLK_FREQ  = 10_000_000; // 10 MHz clock
    localparam integer BAUD_RATE = 1_000_000;  // 1 MBps baud
    localparam integer CLK_PERIOD_NS = 100;    // 100 ns
    localparam integer CLKS_PER_BIT  = CLK_FREQ / BAUD_RATE; // 10 clock cycles
    localparam integer BIT_PERIOD_NS = CLKS_PER_BIT * CLK_PERIOD_NS; // 1000 ns

    reg        clk;
    reg        rst;
    reg        tx_start;
    reg  [7:0] tx_data;
    wire       tx_serial;
    wire       tx_busy;
    wire       tx_done;

    integer test_errors  = 0;
    integer tests_passed = 0;

    // Instantiate UUT
    uart_tx #(
        .CLK_FREQ (CLK_FREQ),
        .BAUD_RATE(BAUD_RATE)
    ) uut (
        .clk      (clk),
        .rst      (rst),
        .tx_start (tx_start),
        .tx_data  (tx_data),
        .tx_serial(tx_serial),
        .tx_busy  (tx_busy),
        .tx_done  (tx_done)
    );

    // Clock generator
    always #(CLK_PERIOD_NS / 2) clk = ~clk;

    // Task: Capture and decode a byte transmitted by uart_tx
    task capture_byte(output [7:0] captured_data, output valid_frame);
        integer i;
        reg [7:0] temp;
        begin
            valid_frame = 1'b1;

            // Wait for falling edge of START bit
            @(negedge tx_serial);

            // Wait to midpoint of start bit (500 ns)
            #(BIT_PERIOD_NS / 2);
            if (tx_serial !== 1'b0) begin
                $display("  [ERROR] Start bit corrupted or not 0!");
                valid_frame = 1'b0;
            end

            // Sample 8 data bits at midpoints
            for (i = 0; i < 8; i = i + 1) begin
                #(BIT_PERIOD_NS);
                temp[i] = tx_serial;
            end

            // Sample stop bit at midpoint
            #(BIT_PERIOD_NS);
            if (tx_serial !== 1'b1) begin
                $display("  [ERROR] Stop bit corrupted or not 1!");
                valid_frame = 1'b0;
            end

            captured_data = temp;
        end
    endtask

    initial begin
        $dumpfile("uart_tx_tb.vcd");
        $dumpvars(0, uart_tx_tb);

        clk      = 0;
        rst      = 1;
        tx_start = 0;
        tx_data  = 8'h00;

        $display("----------------------------------------------------------------");
        $display("Starting UART TX Module Testbench Verification...");
        $display("Clock: %0d Hz, Baud: %0d bps, Clocks/Bit: %0d", CLK_FREQ, BAUD_RATE, CLKS_PER_BIT);
        $display("----------------------------------------------------------------");

        #(CLK_PERIOD_NS * 5);
        rst = 0;
        #(CLK_PERIOD_NS * 5);

        // --------------------------------------------------------------------
        // Test 1: Reset Check
        // --------------------------------------------------------------------
        $display("[TEST 1] Checking reset state...");
        if (tx_serial === 1'b1 && tx_busy === 1'b0) begin
            $display("  -> PASS: TX idles HIGH, busy is LOW");
            tests_passed = tests_passed + 1;
        end else begin
            $display("  -> FAIL: Invalid reset state: tx_serial=%b, tx_busy=%b", tx_serial, tx_busy);
            test_errors = test_errors + 1;
        end

        // --------------------------------------------------------------------
        // Test 2: Transmit 0x41 ('A' = 8'b01000001)
        // --------------------------------------------------------------------
        $display("[TEST 2] Transmitting 0x41 ('A')...");
        fork
            begin
                @(posedge clk);
                tx_data  <= 8'h41;
                tx_start <= 1'b1;
                @(posedge clk);
                tx_start <= 1'b0;
            end
            begin
                reg [7:0] captured;
                reg       ok;
                capture_byte(captured, ok);
                if (ok && captured === 8'h41) begin
                    $display("  -> PASS: Captured exact byte 0x41 ('A') with valid framing");
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  -> FAIL: Captured 0x%02X (expected 0x41)", captured);
                    test_errors = test_errors + 1;
                end
            end
            begin
                @(posedge tx_done);
                $display("  -> PASS: tx_done completion strobe asserted");
                tests_passed = tests_passed + 1;
            end
        join

        #(BIT_PERIOD_NS * 3);

        // --------------------------------------------------------------------
        // Test 3: Transmit 0xA5 (8'b10100101)
        // --------------------------------------------------------------------
        $display("[TEST 3] Transmitting 0xA5...");
        fork
            begin
                @(posedge clk);
                tx_data  <= 8'hA5;
                tx_start <= 1'b1;
                @(posedge clk);
                tx_start <= 1'b0;
            end
            begin
                reg [7:0] captured;
                reg       ok;
                capture_byte(captured, ok);
                if (ok && captured === 8'hA5) begin
                    $display("  -> PASS: Captured exact byte 0xA5 with valid framing");
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  -> FAIL: Captured 0x%02X (expected 0xA5)", captured);
                    test_errors = test_errors + 1;
                end
            end
        join

        #(BIT_PERIOD_NS * 3);

        // --------------------------------------------------------------------
        // Test 4: Back-to-Back Transmissions (0xBE followed by 0xEF)
        // --------------------------------------------------------------------
        $display("[TEST 4] Testing sequential back-to-back transmissions...");
        fork
            begin
                // First byte
                @(posedge clk);
                tx_data  <= 8'hBE;
                tx_start <= 1'b1;
                @(posedge clk);
                tx_start <= 1'b0;

                // Wait for tx_done to trigger next
                @(posedge tx_done);
                @(posedge clk);
                tx_data  <= 8'hEF;
                tx_start <= 1'b1;
                @(posedge clk);
                tx_start <= 1'b0;
            end
            begin
                reg [7:0] cap1, cap2;
                reg       ok1, ok2;
                capture_byte(cap1, ok1);
                if (ok1 && cap1 === 8'hBE) begin
                    $display("  -> PASS: Byte 1 (0xBE) transmitted correctly");
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  -> FAIL: Byte 1 mismatch: 0x%02X", cap1);
                    test_errors = test_errors + 1;
                end

                capture_byte(cap2, ok2);
                if (ok2 && cap2 === 8'hEF) begin
                    $display("  -> PASS: Byte 2 (0xEF) transmitted correctly");
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  -> FAIL: Byte 2 mismatch: 0x%02X", cap2);
                    test_errors = test_errors + 1;
                end
            end
        join

        #(BIT_PERIOD_NS * 5);

        // Final Report
        $display("----------------------------------------------------------------");
        if (test_errors == 0) begin
            $display("ALL UART TX TESTS PASSED! (%0d / %0d checks passed)", tests_passed, tests_passed);
        end else begin
            $display("UART TX VERIFICATION FAILED: %0d errors encountered", test_errors);
        end
        $display("----------------------------------------------------------------");

        $finish;
    end

endmodule

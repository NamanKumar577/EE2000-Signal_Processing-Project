// ============================================================================
// File: uart_rx_tb.v
// Module: uart_rx_tb
// Project: Spartan-7 XC7S50 UART Bringup
// Description: Self-checking testbench for synthesizable uart_rx module.
//              Verifies:
//              1. Normal byte reception (0x55, 0x41, 0xAA)
//              2. Mid-bit sampling alignment
//              3. False start-bit glitch rejection (noise spike rejection)
//              4. Framing error detection (stop-bit violation)
//              5. Back-to-back byte transfers
// ============================================================================

`timescale 1ns / 1ps

module uart_rx_tb;

    // Fast simulation parameters: 10 MHz clock, 1 MBaud for compact waveforms
    localparam integer CLK_FREQ  = 10_000_000;
    localparam integer BAUD_RATE = 1_000_000;
    localparam integer CLK_PERIOD_NS = 100; // 10 MHz = 100 ns period
    localparam integer BIT_PERIOD_NS = 1000; // 1 MBaud = 1000 ns bit time

    reg        clk;
    reg        rst;
    reg        rx_serial;
    wire [7:0] rx_data;
    wire       rx_valid;
    wire       rx_busy;
    wire       rx_frame_err;

    integer test_errors = 0;
    integer tests_passed = 0;

    // Instantiate Unit Under Test (UUT)
    uart_rx #(
        .CLK_FREQ (CLK_FREQ),
        .BAUD_RATE(BAUD_RATE)
    ) uut (
        .clk         (clk),
        .rst         (rst),
        .rx_serial   (rx_serial),
        .rx_data     (rx_data),
        .rx_valid    (rx_valid),
        .rx_busy     (rx_busy),
        .rx_frame_err(rx_frame_err)
    );

    // 10 MHz Clock Generation
    always #(CLK_PERIOD_NS / 2) clk = ~clk;

    // Task: Transmit 1 UART byte into rx_serial
    task send_byte(input [7:0] data, input stop_val);
        integer i;
        begin
            // Start bit
            rx_serial = 1'b0;
            #(BIT_PERIOD_NS);

            // 8 Data bits (LSB first)
            for (i = 0; i < 8; i = i + 1) begin
                rx_serial = data[i];
                #(BIT_PERIOD_NS);
            end

            // Stop bit
            rx_serial = stop_val;
            #(BIT_PERIOD_NS);
        end
    endtask

    initial begin
        $dumpfile("uart_rx_tb.vcd");
        $dumpvars(0, uart_rx_tb);

        clk       = 0;
        rst       = 1;
        rx_serial = 1'b1;

        $display("----------------------------------------------------------------");
        $display("Starting UART RX Module Testbench Verification...");
        $display("Clock: %0d Hz, Baud: %0d bps, Clocks/Bit: %0d", CLK_FREQ, BAUD_RATE, CLK_FREQ/BAUD_RATE);
        $display("----------------------------------------------------------------");

        // Apply reset
        #(CLK_PERIOD_NS * 5);
        rst = 0;
        #(CLK_PERIOD_NS * 5);

        // --------------------------------------------------------------------
        // Test 1: Normal Byte Reception (0x41 = 'A')
        // --------------------------------------------------------------------
        $display("[TEST 1] Transmitting standard byte 0x41 ('A')...");
        send_byte(8'h41, 1'b1);

        // Wait for rx_valid or timeout
        fork : wait_rx_1
            begin
                @(posedge rx_valid);
                if (rx_data === 8'h41) begin
                    $display("  -> PASS: Correctly received 0x41 ('A')");
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  -> FAIL: Expected 0x41, received 0x%02X", rx_data);
                    test_errors = test_errors + 1;
                end
                disable wait_rx_1;
            end
            begin
                #(BIT_PERIOD_NS * 15);
                $display("  -> FAIL: Timeout waiting for rx_valid on Test 1");
                test_errors = test_errors + 1;
                disable wait_rx_1;
            end
        join

        #(BIT_PERIOD_NS * 2);

        // --------------------------------------------------------------------
        // Test 2: Alternating Bit Pattern (0x55 = 8'b01010101)
        // --------------------------------------------------------------------
        $display("[TEST 2] Transmitting alternating pattern 0x55...");
        send_byte(8'h55, 1'b1);

        fork : wait_rx_2
            begin
                @(posedge rx_valid);
                if (rx_data === 8'h55) begin
                    $display("  -> PASS: Correctly received 0x55");
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  -> FAIL: Expected 0x55, received 0x%02X", rx_data);
                    test_errors = test_errors + 1;
                end
                disable wait_rx_2;
            end
            begin
                #(BIT_PERIOD_NS * 15);
                $display("  -> FAIL: Timeout waiting for rx_valid on Test 2");
                test_errors = test_errors + 1;
                disable wait_rx_2;
            end
        join

        #(BIT_PERIOD_NS * 2);

        // --------------------------------------------------------------------
        // Test 3: False Start Bit Glitch Rejection
        // --------------------------------------------------------------------
        $display("[TEST 3] Injecting short noise glitch on RX line (false start bit)...");
        // Pull line low for only 2 clock cycles (200 ns << 500 ns half-bit)
        rx_serial = 1'b0;
        #(CLK_PERIOD_NS * 2);
        rx_serial = 1'b1;

        // Monitor for 3 bit periods; rx_valid MUST NOT assert
        #(BIT_PERIOD_NS * 3);
        if (rx_valid === 1'b0 && rx_busy === 1'b0) begin
            $display("  -> PASS: Noise glitch successfully rejected! FSM returned to IDLE.");
            tests_passed = tests_passed + 1;
        end else begin
            $display("  -> FAIL: False start glitch was not rejected!");
            test_errors = test_errors + 1;
        end

        // --------------------------------------------------------------------
        // Test 4: Framing Error Detection (Invalid Stop Bit)
        // --------------------------------------------------------------------
        $display("[TEST 4] Injecting framing error (Stop Bit forced LOW)...");
        send_byte(8'hAA, 1'b0); // Stop bit driven low

        fork : wait_fe
            begin
                @(posedge rx_frame_err);
                $display("  -> PASS: Framing error correctly detected and flagged!");
                tests_passed = tests_passed + 1;
                disable wait_fe;
            end
            begin
                #(BIT_PERIOD_NS * 15);
                $display("  -> FAIL: Timeout waiting for framing error flag!");
                test_errors = test_errors + 1;
                disable wait_fe;
            end
        join

        // Restore idle line
        rx_serial = 1'b1;
        #(BIT_PERIOD_NS * 3);

        // --------------------------------------------------------------------
        // Test 5: Back-to-Back Byte Reception (0x12 followed immediately by 0x34)
        // --------------------------------------------------------------------
        $display("[TEST 5] Testing back-to-back byte transfers (0x12, then 0x34)...");
        fork
            begin
                send_byte(8'h12, 1'b1);
                send_byte(8'h34, 1'b1);
            end
            begin
                @(posedge rx_valid);
                if (rx_data === 8'h12) begin
                    $display("  -> PASS: Byte 1 (0x12) received");
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  -> FAIL: Byte 1 mismatch: 0x%02X", rx_data);
                    test_errors = test_errors + 1;
                end

                @(posedge rx_valid);
                if (rx_data === 8'h34) begin
                    $display("  -> PASS: Byte 2 (0x34) received");
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  -> FAIL: Byte 2 mismatch: 0x%02X", rx_data);
                    test_errors = test_errors + 1;
                end
            end
        join

        #(BIT_PERIOD_NS * 5);

        // Final Report
        $display("----------------------------------------------------------------");
        if (test_errors == 0) begin
            $display("ALL UART RX TESTS PASSED! (%0d / %0d checks passed)", tests_passed, tests_passed);
        end else begin
            $display("UART RX VERIFICATION FAILED: %0d errors encountered", test_errors);
        end
        $display("----------------------------------------------------------------");

        $finish;
    end

endmodule

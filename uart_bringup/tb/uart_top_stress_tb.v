// ============================================================================
// File: uart_top_stress_tb.v
// Module: uart_top_stress_tb
// Project: Spartan-7 XC7S50 UART Bringup
// Description: Advanced Stress & Corner-Case Testbench for uart_top.
//              Features:
//              1. Clock-cycle bounded timeouts (no simulator-dependent fork/disable delays)
//              2. Timestamped progress telemetry before and after every test group
//              3. Global watchdog timer (2.0 ms) to catch any infinite stalls
//              4. Independent tx_idx and rx_idx loop counters (zero race conditions)
//              5. Framing error injection and immediate resynchronization recovery
//              6. Mid-byte reset testing during active TX and active RX
//              7. FIFO pointer wraparound verification across 48 continuous bytes
//
// Target Hardware: AMD/Xilinx Spartan-7 XC7S50 (RealDigital Boolean Board)
// ============================================================================

`timescale 1ns / 1ps

module uart_top_stress_tb;

    // Simulation timing parameters (50 MHz clock, 1 MBaud for crisp, fast simulation)
    localparam integer CLK_FREQ        = 50_000_000;
    localparam integer BAUD_RATE       = 1_000_000;
    localparam integer CLK_PERIOD_NS   = 20;   // 50 MHz = 20 ns period
    localparam integer CLKS_PER_BIT    = CLK_FREQ / BAUD_RATE; // 50 cycles
    localparam integer BIT_PERIOD_NS   = CLKS_PER_BIT * CLK_PERIOD_NS; // 1000 ns (1 us)
    localparam integer FRAME_PERIOD_NS = 10 * BIT_PERIOD_NS; // 10 us per byte

    reg        clk;
    reg        rst_pin;
    reg        uart_rxd;
    wire       uart_txd;
    wire [7:0] led;

    integer test_errors  = 0;
    integer tests_passed = 0;

    // Independent sender and receiver variables (avoids parallel thread race conditions)
    integer   tx_idx;
    integer   rx_idx;
    reg [7:0] rx_temp;
    reg       rx_ok;
    reg [7:0] exp_byte;
    integer   err_cnt;

    // Helper variables for Test Group 2 bounded wait
    integer wait_cycles_tg2;
    reg     prev_txd_tg2;
    reg     edge_detected_tg2;

    // Variables for Test Group 5 (FIFO saturation & overflow stress test)
    integer   fifo_idx;
    integer   drain_idx;
    integer   fifo_err_cnt;
    reg [3:0] wr_ptr_before_overflow;
    reg [7:0] fill_pattern [0:15];

    // Instantiate Unit Under Test (UUT)
    uart_top #(
        .CLK_FREQ           (CLK_FREQ),
        .BAUD_RATE          (BAUD_RATE),
        .RESET_POLARITY_LOW (0) // Active-high pushbutton reset
    ) uut (
        .clk     (clk),
        .rst_pin (rst_pin),
        .uart_rxd(uart_rxd),
        .uart_txd(uart_txd),
        .led     (led)
    );

    // 50 MHz Clock Generator
    always #(CLK_PERIOD_NS / 2) clk = ~clk;

    // ------------------------------------------------------------------------
    // Global Watchdog Timer: Terminates simulation if it ever exceeds 2.5 ms
    // ------------------------------------------------------------------------
    initial begin
        #(2_500_000); // 2.5 ms (entire 5-group simulation terminates in ~950 us)
        $display("\n================================================================");
        $display("[%0t ns] [FATAL ERROR] Global Watchdog Timer Expired (2.5 ms)!", $time);
        $display("Simulation aborted to prevent indefinite hang in Vivado.");
        $display("DUT State at Watchdog: fifo_count=%0d, wr_ptr=%0d, rd_ptr=%0d, rx_busy=%b, tx_busy=%b",
                 uut.fifo_count, uut.fifo_wr_ptr, uut.fifo_rd_ptr, uut.rx_busy, uut.tx_busy);
        $display("================================================================");
        $finish;
    end

    // ------------------------------------------------------------------------
    // Host Transmitter Task
    // ------------------------------------------------------------------------
    task host_send_byte(input [7:0] data, input stop_bit_val);
        integer i;
        begin
            // Start bit
            uart_rxd = 1'b0;
            #(BIT_PERIOD_NS);

            // 8 Data bits (LSB first)
            for (i = 0; i < 8; i = i + 1) begin
                uart_rxd = data[i];
                #(BIT_PERIOD_NS);
            end

            // Stop bit
            uart_rxd = stop_bit_val;
            #(BIT_PERIOD_NS);

            // Always return serial line to IDLE (MARK = 1) after frame completes
            uart_rxd = 1'b1;
        end
    endtask

    // ------------------------------------------------------------------------
    // Host Receiver Task with Clock-Synchronous Bounded Timeout
    // (Uses @(posedge clk) cycle counter; avoids Vivado XSim fork/disable stalls)
    // ------------------------------------------------------------------------
    task host_receive_byte(output [7:0] data, output valid);
        integer i;
        reg [7:0] temp;
        integer   wait_cycles;
        reg       prev_txd;
        reg       edge_detected;
        begin
            valid         = 1'b0;
            data          = 8'h00;
            edge_detected = 1'b0;
            wait_cycles   = 0;
            prev_txd      = uart_txd;

            // Bounded wait for falling edge on uart_txd (max 30 bit periods = 1500 cycles = 30 us)
            while (!edge_detected && (wait_cycles < (CLKS_PER_BIT * 30))) begin
                @(posedge clk);
                wait_cycles = wait_cycles + 1;
                if (prev_txd == 1'b1 && uart_txd == 1'b0) begin
                    edge_detected = 1'b1;
                end
                prev_txd = uart_txd;
            end

            if (!edge_detected) begin
                $display("  [%0t ns] [TIMEOUT] Host RX: Timed out waiting for start bit on uart_txd (waited %0d cycles)!",
                         $time, wait_cycles);
                valid = 1'b0;
            end else begin
                valid = 1'b1;

                // Midpoint of start bit: advance by half bit period
                #(BIT_PERIOD_NS / 2);
                if (uart_txd !== 1'b0) begin
                    $display("  [%0t ns] [ERROR] Host RX: Start bit corrupted (expected 0)!", $time);
                    valid = 1'b0;
                end

                // Sample 8 data bits at midpoints
                for (i = 0; i < 8; i = i + 1) begin
                    #(BIT_PERIOD_NS);
                    temp[i] = uart_txd;
                end

                // Sample stop bit at midpoint
                #(BIT_PERIOD_NS);
                if (uart_txd !== 1'b1) begin
                    $display("  [%0t ns] [ERROR] Host RX: Stop bit corrupted (expected 1)!", $time);
                    valid = 1'b0;
                end

                data = temp;
            end
        end
    endtask

    initial begin
        $dumpfile("uart_top_stress_tb.vcd");
        $dumpvars(0, uart_top_stress_tb);

        clk      = 0;
        rst_pin  = 1;
        uart_rxd = 1'b1;

        $display("================================================================");
        $display("[%0t ns] STARTING ADVANCED UART CORNER-CASE & STRESS SIMULATION", $time);
        $display("Target: AMD/Xilinx Spartan-7 XC7S50 (RealDigital Boolean Board)");
        $display("Clock: %0d Hz, Baud: %0d bps, Clocks/Bit: %0d", CLK_FREQ, BAUD_RATE, CLKS_PER_BIT);
        $display("================================================================");

        // Reset system
        #(CLK_PERIOD_NS * 10);
        rst_pin = 0;
        #(CLK_PERIOD_NS * 10);
        $display("[%0t ns] Power-on reset deasserted cleanly.", $time);

        // Preload distinct 16-byte pattern for Test Group 5 (0x10, 0x21, 0x32, ..., 0x0F)
        fill_pattern[0]  = 8'h10; fill_pattern[1]  = 8'h21;
        fill_pattern[2]  = 8'h32; fill_pattern[3]  = 8'h43;
        fill_pattern[4]  = 8'h54; fill_pattern[5]  = 8'h65;
        fill_pattern[6]  = 8'h76; fill_pattern[7]  = 8'h87;
        fill_pattern[8]  = 8'h98; fill_pattern[9]  = 8'hA9;
        fill_pattern[10] = 8'hBA; fill_pattern[11] = 8'hCB;
        fill_pattern[12] = 8'hDC; fill_pattern[13] = 8'hED;
        fill_pattern[14] = 8'hFE; fill_pattern[15] = 8'h0F;

        // --------------------------------------------------------------------
        // TEST GROUP 1: Framing Error & Immediate Resynchronization Recovery
        // --------------------------------------------------------------------
        $display("\n[%0t ns] [TEST GROUP 1] Framing Error Injection & Immediate Recovery...", $time);
        // Send byte 0xAA with corrupted stop bit (0 instead of 1)
        host_send_byte(8'hAA, 1'b0);
        #(CLK_PERIOD_NS * 50);

        if (led[2] === 1'b1) begin
            $display("  [%0t ns] -> PASS: Framing error correctly asserted (led[2]=1)", $time);
            tests_passed = tests_passed + 1;
        end else begin
            $display("  [%0t ns] -> FAIL: Framing error was NOT flagged on led[2]!", $time);
            test_errors = test_errors + 1;
        end

        // Ensure idle line restored
        uart_rxd = 1'b1;
        #(BIT_PERIOD_NS * 3);

        // Send valid byte 0x5A immediately after framing error
        $display("  [%0t ns] Injecting valid byte 0x5A to verify resynchronization recovery...", $time);
        fork
            begin
                host_send_byte(8'h5A, 1'b1);
            end
            begin
                host_receive_byte(rx_temp, rx_ok);
                if (rx_ok && rx_temp === 8'h5A) begin
                    $display("  [%0t ns] -> PASS: Resynchronization successful! Echoed 0x5A cleanly.", $time);
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  [%0t ns] -> FAIL: Resynchronization failed, received 0x%02X (Valid=%b)", $time, rx_temp, rx_ok);
                    test_errors = test_errors + 1;
                end
            end
        join

        #(BIT_PERIOD_NS * 5);
        $display("[%0t ns] [TEST GROUP 1 COMPLETE]", $time);

        // --------------------------------------------------------------------
        // TEST GROUP 2: Reset During Active Transmission
        // --------------------------------------------------------------------
        $display("\n[%0t ns] [TEST GROUP 2] Reset During Active Transmission...", $time);
        // Initiate transmission of 0xC3
        fork
            begin
                host_send_byte(8'hC3, 1'b1);
            end
            begin
                // Bounded wait for FPGA echo start (clock-cycle polling)
                wait_cycles_tg2   = 0;
                edge_detected_tg2 = 0;
                prev_txd_tg2      = uart_txd;
                while (!edge_detected_tg2 && (wait_cycles_tg2 < (CLKS_PER_BIT * 25))) begin
                    @(posedge clk);
                    wait_cycles_tg2 = wait_cycles_tg2 + 1;
                    if (prev_txd_tg2 == 1'b1 && uart_txd == 1'b0) begin
                        edge_detected_tg2 = 1'b1;
                    end
                    prev_txd_tg2 = uart_txd;
                end

                #(BIT_PERIOD_NS * 3); // Let it transmit 3 data bits
                $display("  [%0t ns] Asserting rst_pin mid-transmission...", $time);
                rst_pin = 1'b1;
                #(CLK_PERIOD_NS * 10);
                rst_pin = 1'b0;

                // After reset release, tx line MUST return to IDLE (HIGH)
                #(CLK_PERIOD_NS * 5);
                if (uart_txd === 1'b1 && uut.tx_busy === 1'b0 && uut.fifo_count === 0) begin
                    $display("  [%0t ns] -> PASS: Reset cleanly aborted transmission. TX idles HIGH, FIFO cleared.", $time);
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  [%0t ns] -> FAIL: TX not idle or FIFO not cleared after reset! (txd=%b, busy=%b, count=%0d)",
                             $time, uart_txd, uut.tx_busy, uut.fifo_count);
                    test_errors = test_errors + 1;
                end
            end
        join

        #(BIT_PERIOD_NS * 5);
        $display("[%0t ns] [TEST GROUP 2 COMPLETE]", $time);

        // --------------------------------------------------------------------
        // TEST GROUP 3: Reset During Active Reception
        // --------------------------------------------------------------------
        $display("\n[%0t ns] [TEST GROUP 3] Reset During Active Reception...", $time);
        fork
            begin
                // Start sending 0xE5
                uart_rxd = 1'b0; // start
                #(BIT_PERIOD_NS);
                uart_rxd = 1'b1; // bit 0
                #(BIT_PERIOD_NS);
                uart_rxd = 1'b0; // bit 1
                #(BIT_PERIOD_NS);
                // Reset triggered mid-byte
                $display("  [%0t ns] Asserting rst_pin mid-reception...", $time);
                rst_pin = 1'b1;
                #(CLK_PERIOD_NS * 10);
                rst_pin = 1'b0;
                uart_rxd = 1'b1; // return to idle
            end
            begin
                #(BIT_PERIOD_NS * 12);
                if (uut.rx_busy === 1'b0 && uut.rx_valid === 1'b0 && uut.fifo_count === 0) begin
                    $display("  [%0t ns] -> PASS: Reset cleanly aborted reception. No corrupt byte pushed to FIFO.", $time);
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  [%0t ns] -> FAIL: Spurious byte or dirty state after reset! (rx_busy=%b, valid=%b, count=%0d)",
                             $time, uut.rx_busy, uut.rx_valid, uut.fifo_count);
                    test_errors = test_errors + 1;
                end
            end
        join

        #(BIT_PERIOD_NS * 5);
        $display("[%0t ns] [TEST GROUP 3 COMPLETE]", $time);

        // --------------------------------------------------------------------
        // TEST GROUP 4: FIFO Pointer Wraparound Across 16-Word Boundaries
        // --------------------------------------------------------------------
        $display("\n[%0t ns] [TEST GROUP 4] FIFO Circular Pointer Wraparound Test (48 Sequential Bytes)...", $time);
        fork
            begin : proc_send_wraparound
                for (tx_idx = 0; tx_idx < 48; tx_idx = tx_idx + 1) begin
                    host_send_byte(8'h10 + tx_idx[7:0], 1'b1);
                end
                $display("  [%0t ns] Host Sender: Finished sending all 48 bytes.", $time);
            end
            begin : proc_recv_wraparound
                err_cnt = 0;
                for (rx_idx = 0; rx_idx < 48; rx_idx = rx_idx + 1) begin
                    exp_byte = 8'h10 + rx_idx[7:0];
                    host_receive_byte(rx_temp, rx_ok);
                    if (!rx_ok || rx_temp !== exp_byte) begin
                        $display("  [%0t ns] [ERROR] Byte %0d mismatch: Expected 0x%02X, Got 0x%02X (Valid=%b)",
                                 $time, rx_idx, exp_byte, rx_temp, rx_ok);
                        err_cnt = err_cnt + 1;
                    end else if (rx_idx == 0 || rx_idx == 15 || rx_idx == 31 || rx_idx == 47) begin
                        $display("  [%0t ns] [PROGRESS] Byte %0d/48 verified: 0x%02X echoed cleanly (FIFO count=%0d)",
                                 $time, rx_idx + 1, rx_temp, uut.fifo_count);
                    end
                end
                if (err_cnt == 0) begin
                    $display("  [%0t ns] -> PASS: All 48 bytes across 3 FIFO wraparounds verified with 100%% integrity!", $time);
                    tests_passed = tests_passed + 1;
                end else begin
                    $display("  [%0t ns] -> FAIL: %0d byte errors during pointer wraparound test!", $time, err_cnt);
                    test_errors = test_errors + err_cnt;
                end
            end
        join

        #(BIT_PERIOD_NS * 10);
        $display("[%0t ns] [TEST GROUP 4 COMPLETE]", $time);

        // --------------------------------------------------------------------
        // TEST GROUP 5: FIFO Saturation, Overflow Rejection & In-Order Drain
        // --------------------------------------------------------------------
        $display("\n[%0t ns] [TEST GROUP 5] FIFO Saturation, Overflow & In-Order Draining...", $time);

        // Subtest 5A: Stall TX and fill FIFO to 16/16 capacity
        $display("  [%0t ns] [SUBTEST 5A] Stalling TX and filling FIFO with 16 distinct bytes...", $time);
        force uut.tx_busy = 1'b1;
        #(CLK_PERIOD_NS * 2);

        if (uut.fifo_count !== 0 || uut.fifo_empty !== 1'b1) begin
            $display("  [%0t ns] -> ERROR: FIFO not empty before starting Test Group 5! (count=%0d)", $time, uut.fifo_count);
            test_errors = test_errors + 1;
        end

        fifo_err_cnt = 0;
        for (fifo_idx = 0; fifo_idx < 16; fifo_idx = fifo_idx + 1) begin
            host_send_byte(fill_pattern[fifo_idx], 1'b1);
            #(CLK_PERIOD_NS * 5); // Allow rx_valid, wr_en and FIFO registers to update

            // Verify count increments by exactly 1
            if (uut.fifo_count !== (fifo_idx + 1)) begin
                $display("  [%0t ns] -> ERROR: FIFO count mismatch after byte %0d! Expected %0d, got %0d",
                         $time, fifo_idx + 1, fifo_idx + 1, uut.fifo_count);
                fifo_err_cnt = fifo_err_cnt + 1;
            end

            // Verify write pointer advances
            if (uut.fifo_wr_ptr !== ((fifo_idx + 1) % 16)) begin
                $display("  [%0t ns] -> ERROR: Write pointer mismatch after byte %0d! Expected %0d, got %0d",
                         $time, fifo_idx + 1, (fifo_idx + 1) % 16, uut.fifo_wr_ptr);
                fifo_err_cnt = fifo_err_cnt + 1;
            end

            // Verify data correctly stored in internal memory slot
            if (uut.fifo_mem[fifo_idx] !== fill_pattern[fifo_idx]) begin
                $display("  [%0t ns] -> ERROR: fifo_mem[%0d] corrupted! Expected 0x%02X, got 0x%02X",
                         $time, fifo_idx, fill_pattern[fifo_idx], uut.fifo_mem[fifo_idx]);
                fifo_err_cnt = fifo_err_cnt + 1;
            end

            // Verify fifo_full status (must only be 1 when count == 16)
            if (fifo_idx < 15 && uut.fifo_full !== 1'b0) begin
                $display("  [%0t ns] -> ERROR: fifo_full prematurely asserted at count %0d!", $time, uut.fifo_count);
                fifo_err_cnt = fifo_err_cnt + 1;
            end else if (fifo_idx == 15 && uut.fifo_full !== 1'b1) begin
                $display("  [%0t ns] -> ERROR: fifo_full NOT asserted at count 16!", $time);
                fifo_err_cnt = fifo_err_cnt + 1;
            end
        end

        if (uut.fifo_count === 16 && uut.fifo_full === 1'b1 && fifo_err_cnt == 0) begin
            $display("  [%0t ns] -> PASS: Subtest 5A: FIFO filled to 16/16 capacity (fifo_full=1, count=16, memory verified).", $time);
            tests_passed = tests_passed + 1;
        end else begin
            $display("  [%0t ns] -> FAIL: Subtest 5A: FIFO capacity check failed! (count=%0d, full=%b, errors=%0d)",
                     $time, uut.fifo_count, uut.fifo_full, fifo_err_cnt);
            test_errors = test_errors + 1;
        end

        // Subtest 5B: Overflow Attempt (17th byte)
        $display("\n  [%0t ns] [SUBTEST 5B] Injecting 17th byte (0xFE) to verify overflow protection...", $time);
        wr_ptr_before_overflow = uut.fifo_wr_ptr; // Should be 0
        host_send_byte(8'hFE, 1'b1);
        #(CLK_PERIOD_NS * 5); // Wait for RX completion and write rejection

        fifo_err_cnt = 0;

        // 1. FIFO count must remain 16 (never exceed 16)
        if (uut.fifo_count !== 16) begin
            $display("  [%0t ns] -> ERROR: FIFO count exceeded 16 on overflow! Got %0d", $time, uut.fifo_count);
            fifo_err_cnt = fifo_err_cnt + 1;
        end

        // 2. Write pointer must NOT advance
        if (uut.fifo_wr_ptr !== wr_ptr_before_overflow) begin
            $display("  [%0t ns] -> ERROR: Write pointer advanced on overflow write! Expected %0d, got %0d",
                     $time, wr_ptr_before_overflow, uut.fifo_wr_ptr);
            fifo_err_cnt = fifo_err_cnt + 1;
        end

        // 3. Overflow sticky flag and LED[3] must be asserted
        if (uut.overflow_sticky !== 1'b1 || led[3] !== 1'b1) begin
            $display("  [%0t ns] -> ERROR: Overflow flag not asserted! (sticky=%b, led[3]=%b)",
                     $time, uut.overflow_sticky, led[3]);
            fifo_err_cnt = fifo_err_cnt + 1;
        end

        // 4. Original 16 bytes in FIFO memory must remain intact (no overwrite of fifo_mem[0] or any other slot)
        for (fifo_idx = 0; fifo_idx < 16; fifo_idx = fifo_idx + 1) begin
            if (uut.fifo_mem[fifo_idx] !== fill_pattern[fifo_idx]) begin
                $display("  [%0t ns] -> ERROR: fifo_mem[%0d] overwritten! Expected 0x%02X, got 0x%02X",
                         $time, fifo_idx, fill_pattern[fifo_idx], uut.fifo_mem[fifo_idx]);
                fifo_err_cnt = fifo_err_cnt + 1;
            end
        end

        if (fifo_err_cnt == 0) begin
            $display("  [%0t ns] -> PASS: Subtest 5B: 17th byte rejected cleanly! Count=16, wr_ptr held, led[3]=1, memory preserved.", $time);
            tests_passed = tests_passed + 1;
        end else begin
            $display("  [%0t ns] -> FAIL: Subtest 5B: Overflow protection check failed with %0d errors!", $time, fifo_err_cnt);
            test_errors = test_errors + 1;
        end

        // Subtest 5C: Drain and In-Order Verification
        $display("\n  [%0t ns] [SUBTEST 5C] Releasing TX stall and verifying in-order draining of all 16 bytes...", $time);
        release uut.tx_busy;

        fifo_err_cnt = 0;
        for (drain_idx = 0; drain_idx < 16; drain_idx = drain_idx + 1) begin
            host_receive_byte(rx_temp, rx_ok);
            if (!rx_ok || rx_temp !== fill_pattern[drain_idx]) begin
                $display("  [%0t ns] -> ERROR: Drained byte %0d mismatch! Expected 0x%02X, got 0x%02X (Valid=%b)",
                         $time, drain_idx + 1, fill_pattern[drain_idx], rx_temp, rx_ok);
                fifo_err_cnt = fifo_err_cnt + 1;
            end else if (drain_idx == 0 || drain_idx == 7 || drain_idx == 15) begin
                $display("  [%0t ns] [PROGRESS] Drained byte %0d/16: 0x%02X verified (remaining FIFO count=%0d)",
                         $time, drain_idx + 1, rx_temp, uut.fifo_count);
            end
        end

        #(BIT_PERIOD_NS * 5); // Wait for TX stop bit to settle to idle

        // 1. FIFO count must be 0 and fifo_empty must be 1
        if (uut.fifo_count !== 0 || uut.fifo_empty !== 1'b1) begin
            $display("  [%0t ns] -> ERROR: FIFO not empty after draining! (count=%0d, empty=%b)",
                     $time, uut.fifo_count, uut.fifo_empty);
            fifo_err_cnt = fifo_err_cnt + 1;
        end

        // 2. TX must be idle
        if (uut.tx_busy !== 1'b0 || uart_txd !== 1'b1) begin
            $display("  [%0t ns] -> ERROR: TX line not idle after draining! (busy=%b, txd=%b)",
                     $time, uut.tx_busy, uart_txd);
            fifo_err_cnt = fifo_err_cnt + 1;
        end

        // 3. Overflow sticky flag MUST remain latched (sticky diagnostic property)
        if (uut.overflow_sticky !== 1'b1 || led[3] !== 1'b1) begin
            $display("  [%0t ns] -> ERROR: overflow_sticky unlatched prematurely after drain! (sticky=%b, led[3]=%b)",
                     $time, uut.overflow_sticky, led[3]);
            fifo_err_cnt = fifo_err_cnt + 1;
        end

        if (fifo_err_cnt == 0) begin
            $display("  [%0t ns] -> PASS: Subtest 5C: All 16 bytes drained in 100%% exact order! FIFO empty, overflow sticky latched.", $time);
            tests_passed = tests_passed + 1;
        end else begin
            $display("  [%0t ns] -> FAIL: Subtest 5C: Draining and ordering verification failed with %0d errors!", $time, fifo_err_cnt);
            test_errors = test_errors + 1;
        end

        #(BIT_PERIOD_NS * 5);
        $display("[%0t ns] [TEST GROUP 5 COMPLETE]", $time);

        // --------------------------------------------------------------------
        // Final Scorecard
        // --------------------------------------------------------------------
        $display("\n================================================================");
        if (test_errors == 0) begin
            $display("[%0t ns] ALL ADVANCED CORNER-CASE TESTS PASSED! (%0d / %0d checks passed)", $time, tests_passed, tests_passed);
            $display("STATUS: VERIFIED ROBUST UNDER RESET, FRAMING ERROR, WRAPAROUND & FIFO OVERFLOW");
        end else begin
            $display("[%0t ns] ADVANCED TESTS FAILED: %0d errors encountered", $time, test_errors);
        end
        $display("================================================================");

        $finish;
    end

endmodule

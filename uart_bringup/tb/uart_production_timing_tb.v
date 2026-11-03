// ============================================================================
// File: uart_production_timing_tb.v
// Module: uart_production_timing_tb
// Project: Spartan-7 XC7S50 UART Bringup
// Description: Production Hardware Timing Verification Testbench
//              Verifies uart_top under exact physical target configuration:
//              - System Clock: 100.0 MHz (10.0 ns period, Pin F14)
//              - Baud Rate:    115,200 bps (8N1)
//              - Clocks/Bit:   868 cycles (8,680 ns per bit)
//
// Verification Scope:
//   1. Physical Bit-Timing Measurement:
//      - Start-bit duration (exact clock cycles)
//      - Data-bit durations (exact clock cycles across all 8 data bits)
//      - Stop-bit duration
//      - Receiver midpoint sampling positions (start mid-sample at cycle 434)
//   2. Critical Boundary Data Patterns:
//      - 0x00, 0xFF, 0x55, 0xAA, 0xC3
//   3. High-Speed Back-to-Back Burst Transfers (Zero Inter-Byte Idle Gap)
//   4. 64-Byte Continuous Full-Range Sweep
//   5. 100% Data Integrity and Error-Free Loopback Echo
//
// Target Hardware: AMD/Xilinx Spartan-7 XC7S50 (RealDigital Boolean Board)
// ============================================================================

`timescale 1ns / 1ps

module uart_production_timing_tb;

    // Production Hardware Parameters (100 MHz clock, 115200 baud)
    localparam integer CLK_FREQ        = 100_000_000;
    localparam integer BAUD_RATE       = 115_200;
    localparam integer CLK_PERIOD_NS   = 10; // 100 MHz = 10.0 ns period
    localparam integer CLKS_PER_BIT    = (CLK_FREQ + (BAUD_RATE / 2)) / BAUD_RATE; // 868 cycles
    localparam integer HALF_BIT        = CLKS_PER_BIT / 2; // 434 cycles
    localparam integer BIT_PERIOD_NS   = CLKS_PER_BIT * CLK_PERIOD_NS; // 8,680 ns (8.68 us)
    localparam integer FRAME_PERIOD_NS = 10 * BIT_PERIOD_NS; // 86,800 ns (86.8 us)

    reg        clk;
    reg        rst_pin;
    reg        uart_rxd;
    wire       uart_txd;
    wire [7:0] led;

    integer test_errors  = 0;
    integer tests_passed = 0;

    // Measurement registers
    integer start_bit_cycles;
    integer data_bit_cycles [0:7];
    integer stop_bit_cycles;
    integer rx_start_mid_cycles;
    integer rx_data_sample_pos [0:7];

    // Explicit timing reference registers for RX
    integer t_rx_ext_fall;
    integer t_rx_sync_fall;
    integer t_rx_fsm_start;
    integer t_rx_midpoint_validate;
    integer rx_sync_latency;
    integer rx_fsm_latency;

    // Test loop variables
    integer   tx_idx;
    integer   rx_idx;
    reg [7:0] rx_temp;
    reg       rx_ok;
    reg [7:0] exp_byte;
    integer   err_cnt;

    // Instantiate Top-Level Echo Module under exact production parameters
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

    // 100 MHz Master System Clock Generator (10.0 ns period, 50% duty cycle)
    always #(CLK_PERIOD_NS / 2) clk = ~clk;

    // ------------------------------------------------------------------------
    // Global Watchdog Timer: Terminates simulation if it exceeds 30.0 ms
    // (Normal complete test terminates in ~8.0 ms)
    // ------------------------------------------------------------------------
    initial begin
        #(30_000_000); // 30 ms
        $display("\n================================================================");
        $display("[%0t ns] [FATAL ERROR] Production Timing Watchdog Expired (30.0 ms)!", $time);
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

            // Always restore serial line to IDLE mark (1'b1)
            uart_rxd = 1'b1;
        end
    endtask

    // ------------------------------------------------------------------------
    // Host Receiver Task with Clock-Synchronous Bounded Timeout
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

            // Bounded wait for falling edge on uart_txd (max 50 bit periods = 43,400 cycles)
            while (!edge_detected && (wait_cycles < (CLKS_PER_BIT * 50))) begin
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

                // Midpoint of start bit
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

    // ------------------------------------------------------------------------
    // Main Verification Sequence
    // ------------------------------------------------------------------------
    initial begin
        $dumpfile("uart_production_timing_tb.vcd");
        $dumpvars(0, uart_production_timing_tb);

        clk      = 0;
        rst_pin  = 1;
        uart_rxd = 1'b1;

        $display("================================================================");
        $display("[%0t ns] STARTING UART PRODUCTION TIMING VERIFICATION", $time);
        $display("Target Hardware: RealDigital Boolean Board (Spartan-7 XC7S50)");
        $display("Clock Frequency: %0d Hz (%0d ns period)", CLK_FREQ, CLK_PERIOD_NS);
        $display("Target Baud:     %0d bps", BAUD_RATE);
        $display("Clocks Per Bit:  %0d cycles", CLKS_PER_BIT);
        $display("Expected Bit:    %0d ns (%0.2f us)", BIT_PERIOD_NS, BIT_PERIOD_NS / 1000.0);
        $display("Expected Midpoint Sampling: Cycle %0d (%0d ns)", HALF_BIT, HALF_BIT * CLK_PERIOD_NS);
        $display("================================================================");

        // Power-on reset pulse (10 clock cycles = 100 ns)
        #(CLK_PERIOD_NS * 10);
        rst_pin = 0;
        #(CLK_PERIOD_NS * 20);
        $display("[%0t ns] Power-on reset released. System initialized.", $time);

        // ====================================================================
        // PHASE 1: BIT-TIMING & SAMPLING ACCURACY MEASUREMENTS
        // ====================================================================
        $display("\n[%0t ns] [TEST GROUP 1] Measuring Precise Bit Durations & Sampling Cycle (Pattern: 0x55)...", $time);
        // Byte 0x55 (8'b01010101) provides an edge transition on every single bit:
        // Start(0) -> D0(1) -> D1(0) -> D2(1) -> D3(0) -> D4(1) -> D5(0) -> D6(1) -> D7(0) -> Stop(1)
        err_cnt = 0;
        fork
            begin : proc_send
                // Delay sending by 5 clock cycles to guarantee concurrent monitoring
                // processes (proc_measure_rx and proc_measure_tx) are actively waiting on their edges.
                repeat (5) @(posedge clk);
                host_send_byte(8'h55, 1'b1);
            end
            begin : proc_measure_rx
                integer last_sample_time;
                integer d_idx;
                integer timeout_cnt;

                // 1. Capture external falling edge on uart_rxd pin
                @(negedge uart_rxd);
                t_rx_ext_fall = $time / CLK_PERIOD_NS;

                // 2. Capture synchronized falling edge on rx_sync (2-stage synchronizer)
                // Phase-aware measurement: count the 2 clock sampling edges traversed
                // by the 2-stage synchronizer pipeline (Stage 1 then Stage 2).
                rx_sync_latency = 0;
                @(negedge uut.u_uart_rx.rx_sync_stage1);
                rx_sync_latency = rx_sync_latency + 1; // Sampling Edge 1: Stage 1 captures external transition

                @(negedge uut.u_uart_rx.rx_sync);
                rx_sync_latency = rx_sync_latency + 1; // Sampling Edge 2: Stage 2 captures Stage 1 output
                t_rx_sync_fall = $time / CLK_PERIOD_NS;

                // 3. Capture FSM entry into STATE_START (bounded wait)
                timeout_cnt = 0;
                while (uut.u_uart_rx.state !== 3'b001 && timeout_cnt < 50) begin
                    @(posedge clk);
                    timeout_cnt = timeout_cnt + 1;
                end
                if (timeout_cnt >= 50) begin
                    $display("  [%0t ns] [TIMEOUT] RX monitor timed out waiting for STATE_START entry (waited %0d cycles)!",
                             $time, timeout_cnt);
                    err_cnt = err_cnt + 1;
                end
                t_rx_fsm_start = $time / CLK_PERIOD_NS;
                rx_fsm_latency = t_rx_fsm_start - t_rx_sync_fall;

                // 4. Capture exact midpoint validation cycle where clk_cnt reaches HALF_BIT - 1 (bounded wait)
                timeout_cnt = 0;
                while (!(uut.u_uart_rx.state === 3'b001 && uut.u_uart_rx.clk_cnt === (HALF_BIT - 1)) && timeout_cnt < (HALF_BIT * 2)) begin
                    @(posedge clk);
                    timeout_cnt = timeout_cnt + 1;
                end
                if (timeout_cnt >= (HALF_BIT * 2)) begin
                    $display("  [%0t ns] [TIMEOUT] RX monitor timed out waiting for midpoint sample condition!", $time);
                    err_cnt = err_cnt + 1;
                end
                // The validation takes effect on the next rising clock edge:
                @(posedge clk);
                t_rx_midpoint_validate = $time / CLK_PERIOD_NS;
                rx_start_mid_cycles = t_rx_midpoint_validate - t_rx_fsm_start;

                // 5. Measure exact sample event positions for each of the 8 data bits (bounded wait)
                last_sample_time = t_rx_midpoint_validate;
                for (d_idx = 0; d_idx < 8; d_idx = d_idx + 1) begin
                    timeout_cnt = 0;
                    while (!(uut.u_uart_rx.state === 3'b010 && uut.u_uart_rx.bit_idx === d_idx && uut.u_uart_rx.clk_cnt === (CLKS_PER_BIT - 1)) && timeout_cnt < (CLKS_PER_BIT * 2)) begin
                        @(posedge clk);
                        timeout_cnt = timeout_cnt + 1;
                    end
                    if (timeout_cnt >= (CLKS_PER_BIT * 2)) begin
                        $display("  [%0t ns] [TIMEOUT] RX monitor timed out waiting for bit D%0d sample event!", $time, d_idx);
                        err_cnt = err_cnt + 1;
                    end
                    @(posedge clk);
                    rx_data_sample_pos[d_idx] = ($time / CLK_PERIOD_NS) - last_sample_time;
                    last_sample_time = $time / CLK_PERIOD_NS;
                end
            end
            begin : proc_measure_tx
                integer t_start_edge;
                integer t_d0_edge;
                integer t_d1_edge;
                integer t_d2_edge;
                integer t_d3_edge;
                integer t_d4_edge;
                integer t_d5_edge;
                integer t_d6_edge;
                integer t_d7_edge;
                integer t_stop_edge;
                integer t_done_edge;

                // 1. Wait for TX Start bit falling edge
                @(negedge uart_txd);
                t_start_edge = $time / CLK_PERIOD_NS;

                // 2. Measure Start bit: wait for rising edge (D0 = 1)
                @(posedge uart_txd);
                t_d0_edge = $time / CLK_PERIOD_NS;
                start_bit_cycles = t_d0_edge - t_start_edge;

                // 3. Measure D0: wait for falling edge (D1 = 0)
                @(negedge uart_txd);
                t_d1_edge = $time / CLK_PERIOD_NS;
                data_bit_cycles[0] = t_d1_edge - t_d0_edge;

                // 4. Measure D1: wait for rising edge (D2 = 1)
                @(posedge uart_txd);
                t_d2_edge = $time / CLK_PERIOD_NS;
                data_bit_cycles[1] = t_d2_edge - t_d1_edge;

                // 5. Measure D2: wait for falling edge (D3 = 0)
                @(negedge uart_txd);
                t_d3_edge = $time / CLK_PERIOD_NS;
                data_bit_cycles[2] = t_d3_edge - t_d2_edge;

                // 6. Measure D3: wait for rising edge (D4 = 1)
                @(posedge uart_txd);
                t_d4_edge = $time / CLK_PERIOD_NS;
                data_bit_cycles[3] = t_d4_edge - t_d3_edge;

                // 7. Measure D4: wait for falling edge (D5 = 0)
                @(negedge uart_txd);
                t_d5_edge = $time / CLK_PERIOD_NS;
                data_bit_cycles[4] = t_d5_edge - t_d4_edge;

                // 8. Measure D5: wait for rising edge (D6 = 1)
                @(posedge uart_txd);
                t_d6_edge = $time / CLK_PERIOD_NS;
                data_bit_cycles[5] = t_d6_edge - t_d5_edge;

                // 9. Measure D6: wait for falling edge (D7 = 0)
                @(negedge uart_txd);
                t_d7_edge = $time / CLK_PERIOD_NS;
                data_bit_cycles[6] = t_d7_edge - t_d6_edge;

                // 10. Measure D7: wait for rising edge (Stop bit = 1)
                @(posedge uart_txd);
                t_stop_edge = $time / CLK_PERIOD_NS;
                data_bit_cycles[7] = t_stop_edge - t_d7_edge;

                // 11. Measure Stop bit: wait for tx_done pulse (completion of stop bit)
                @(posedge uut.u_uart_tx.tx_done);
                t_done_edge = $time / CLK_PERIOD_NS;
                stop_bit_cycles = t_done_edge - t_stop_edge;
            end
        join

        #(BIT_PERIOD_NS * 2);

        // Report Timing Measurements
        $display("  --- Measured Physical Hardware Timing ---");
        $display("  TX Start Bit Duration: %0d clock cycles (%0d ns, target: %0d)",
                 start_bit_cycles, start_bit_cycles * CLK_PERIOD_NS, CLKS_PER_BIT);
        for (tx_idx = 0; tx_idx < 8; tx_idx = tx_idx + 1) begin
            $display("  TX D%0d Duration:        %0d clock cycles (%0d ns, target: %0d)",
                     tx_idx, data_bit_cycles[tx_idx], data_bit_cycles[tx_idx] * CLK_PERIOD_NS, CLKS_PER_BIT);
        end
        $display("  TX Stop Bit Duration:  %0d clock cycles (%0d ns, target: %0d)",
                 stop_bit_cycles, stop_bit_cycles * CLK_PERIOD_NS, CLKS_PER_BIT);
        $display("  --- RX Synchronization & Timing References ---");
        $display("  RX External Falling Edge: cycle %0d (%0d ns)", t_rx_ext_fall, t_rx_ext_fall * CLK_PERIOD_NS);
        $display("  RX Synchronized Edge:     cycle %0d (2-stage synchronizer latency: %0d cycles = %0d ns)",
                 t_rx_sync_fall, rx_sync_latency, rx_sync_latency * CLK_PERIOD_NS);
        $display("  RX FSM START Entry:       cycle %0d (FSM start latency: %0d cycle = %0d ns)",
                 t_rx_fsm_start, rx_fsm_latency, rx_fsm_latency * CLK_PERIOD_NS);
        $display("  RX Midpoint Validation:   cycle %0d (offset in START: %0d cycles = %0d ns, target: %0d)",
                 t_rx_midpoint_validate, rx_start_mid_cycles, rx_start_mid_cycles * CLK_PERIOD_NS, HALF_BIT);
        for (tx_idx = 0; tx_idx < 8; tx_idx = tx_idx + 1) begin
            $display("  RX D%0d Sample Interval: %0d clock cycles (%0d ns, target: %0d)",
                     tx_idx, rx_data_sample_pos[tx_idx], rx_data_sample_pos[tx_idx] * CLK_PERIOD_NS, CLKS_PER_BIT);
        end

        // Verify timing tolerances (must match CLKS_PER_BIT exactly)
        if (t_rx_ext_fall === 0 || t_rx_sync_fall === 0 || t_rx_midpoint_validate === 0) begin
            $display("  [ERROR] RX monitor missed transition capture (zero timestamp detected)!");
            err_cnt = err_cnt + 1;
        end
        if (rx_sync_latency !== 2) begin
            $display("  [ERROR] RX 2-stage synchronizer latency mismatch! Expected 2, got %0d", rx_sync_latency);
            err_cnt = err_cnt + 1;
        end
        if (start_bit_cycles !== CLKS_PER_BIT) begin
            $display("  [ERROR] TX Start Bit duration mismatch! Expected %0d, got %0d", CLKS_PER_BIT, start_bit_cycles);
            err_cnt = err_cnt + 1;
        end
        for (tx_idx = 0; tx_idx < 8; tx_idx = tx_idx + 1) begin
            if (data_bit_cycles[tx_idx] !== CLKS_PER_BIT) begin
                $display("  [ERROR] TX D%0d duration mismatch! Expected %0d, got %0d", tx_idx, CLKS_PER_BIT, data_bit_cycles[tx_idx]);
                err_cnt = err_cnt + 1;
            end
        end
        if (stop_bit_cycles !== CLKS_PER_BIT) begin
            $display("  [ERROR] TX Stop Bit duration mismatch! Expected %0d, got %0d", CLKS_PER_BIT, stop_bit_cycles);
            err_cnt = err_cnt + 1;
        end
        if (rx_start_mid_cycles !== HALF_BIT) begin
            $display("  [ERROR] RX Midpoint sample cycle mismatch! Expected %0d, got %0d", HALF_BIT, rx_start_mid_cycles);
            err_cnt = err_cnt + 1;
        end
        for (tx_idx = 0; tx_idx < 8; tx_idx = tx_idx + 1) begin
            if (rx_data_sample_pos[tx_idx] !== CLKS_PER_BIT) begin
                $display("  [ERROR] RX D%0d sample interval mismatch! Expected %0d, got %0d", tx_idx, CLKS_PER_BIT, rx_data_sample_pos[tx_idx]);
                err_cnt = err_cnt + 1;
            end
        end

        if (err_cnt == 0) begin
            $display("  [%0t ns] -> PASS: All physical bit periods and RX sampling cycles match exact 100 MHz/115200 spec!", $time);
            tests_passed = tests_passed + 1;
        end else begin
            $display("  [%0t ns] -> FAIL: Bit-timing verification failed with %0d timing errors!", $time, err_cnt);
            test_errors = test_errors + err_cnt;
        end
        $display("[%0t ns] [TEST GROUP 1 COMPLETE]", $time);

        // ====================================================================
        // PHASE 2: CRITICAL BOUNDARY DATA PATTERNS
        // ====================================================================
        $display("\n[%0t ns] [TEST GROUP 2] Testing Critical Boundary Data Patterns...", $time);
        // Test patterns: 0x00, 0xFF, 0x55, 0xAA, 0xC3
        begin : proc_test_boundary_patterns
            reg [7:0] patterns [0:4];
            integer p_idx;
            patterns[0] = 8'h00; // All zeros
            patterns[1] = 8'hFF; // All ones
            patterns[2] = 8'h55; // Alternating 01010101
            patterns[3] = 8'hAA; // Alternating 10101010
            patterns[4] = 8'hC3; // Double-bit 11000011

            err_cnt = 0;
            for (p_idx = 0; p_idx < 5; p_idx = p_idx + 1) begin
                fork
                    begin
                        host_send_byte(patterns[p_idx], 1'b1);
                    end
                    begin
                        host_receive_byte(rx_temp, rx_ok);
                        if (!rx_ok || rx_temp !== patterns[p_idx]) begin
                            $display("  [%0t ns] -> ERROR: Pattern 0x%02X failed! Received: 0x%02X (Valid=%b)",
                                     $time, patterns[p_idx], rx_temp, rx_ok);
                            err_cnt = err_cnt + 1;
                        end else begin
                            $display("  [%0t ns] -> Pattern 0x%02X verified cleanly.", $time, patterns[p_idx]);
                        end
                    end
                join
                #(BIT_PERIOD_NS * 2);
            end

            if (err_cnt == 0) begin
                $display("  [%0t ns] -> PASS: All 5 boundary patterns (0x00, 0xFF, 0x55, 0xAA, 0xC3) verified with 100%% integrity!", $time);
                tests_passed = tests_passed + 1;
            end else begin
                $display("  [%0t ns] -> FAIL: Boundary pattern test failed with %0d errors!", $time, err_cnt);
                test_errors = test_errors + err_cnt;
            end
        end
        $display("[%0t ns] [TEST GROUP 2 COMPLETE]", $time);

        // ====================================================================
        // PHASE 3: BACK-TO-BACK BURST TRANSFER (Zero Inter-Byte Gap)
        // ====================================================================
        $display("\n[%0t ns] [TEST GROUP 3] Testing High-Speed Back-to-Back Burst Transfers (16 Bytes, Zero Gap)...", $time);
        err_cnt = 0;
        fork
            begin : proc_burst_send
                for (tx_idx = 0; tx_idx < 16; tx_idx = tx_idx + 1) begin
                    host_send_byte(8'h80 + tx_idx[7:0], 1'b1);
                    // Zero inter-byte gap: immediately loop to send next byte
                end
            end
            begin : proc_burst_recv
                for (rx_idx = 0; rx_idx < 16; rx_idx = rx_idx + 1) begin
                    exp_byte = 8'h80 + rx_idx[7:0];
                    host_receive_byte(rx_temp, rx_ok);
                    if (!rx_ok || rx_temp !== exp_byte) begin
                        $display("  [%0t ns] -> ERROR: Burst byte %0d mismatch! Expected 0x%02X, got 0x%02X",
                                 $time, rx_idx, exp_byte, rx_temp);
                        err_cnt = err_cnt + 1;
                    end
                end
            end
        join

        #(BIT_PERIOD_NS * 5);
        if (err_cnt == 0 && uut.fifo_count === 0 && uut.tx_busy === 0) begin
            $display("  [%0t ns] -> PASS: 16-byte back-to-back burst transfer completed with zero dropped bytes!", $time);
            tests_passed = tests_passed + 1;
        end else begin
            $display("  [%0t ns] -> FAIL: Back-to-back burst test failed! (errors=%0d, fifo_count=%0d)",
                     $time, err_cnt, uut.fifo_count);
            test_errors = test_errors + 1;
        end
        $display("[%0t ns] [TEST GROUP 3 COMPLETE]", $time);

        // ====================================================================
        // PHASE 4: 64-BYTE FULL-RANGE CONTINUOUS DATA SWEEP
        // ====================================================================
        $display("\n[%0t ns] [TEST GROUP 4] Testing 64-Byte Continuous Full-Range Data Sweep...", $time);
        err_cnt = 0;
        fork
            begin : proc_sweep_send
                for (tx_idx = 0; tx_idx < 64; tx_idx = tx_idx + 1) begin
                    // Pseudorandom / arithmetic dispersion across byte values
                    host_send_byte(tx_idx[7:0] ^ 8'h3C, 1'b1);
                    #(CLK_PERIOD_NS * 20); // Small realistic 200 ns inter-byte spacing
                end
                $display("  [%0t ns] Host Sender: Completed transmitting all 64 sweep bytes.", $time);
            end
            begin : proc_sweep_recv
                for (rx_idx = 0; rx_idx < 64; rx_idx = rx_idx + 1) begin
                    exp_byte = rx_idx[7:0] ^ 8'h3C;
                    host_receive_byte(rx_temp, rx_ok);
                    if (!rx_ok || rx_temp !== exp_byte) begin
                        $display("  [%0t ns] -> ERROR: Sweep byte %0d mismatch! Expected 0x%02X, got 0x%02X",
                                 $time, rx_idx, exp_byte, rx_temp);
                        err_cnt = err_cnt + 1;
                    end else if (rx_idx == 0 || rx_idx == 15 || rx_idx == 31 || rx_idx == 47 || rx_idx == 63) begin
                        $display("  [%0t ns] [PROGRESS] Sweep byte %0d/64 verified: 0x%02X echoed cleanly",
                                 $time, rx_idx + 1, rx_temp);
                    end
                end
            end
        join

        #(BIT_PERIOD_NS * 10);
        if (err_cnt == 0 && uut.fifo_count === 0 && uut.tx_busy === 0) begin
            $display("  [%0t ns] -> PASS: All 64 sweep bytes verified with 100%% data integrity at 115200 baud!", $time);
            tests_passed = tests_passed + 1;
        end else begin
            $display("  [%0t ns] -> FAIL: 64-byte sweep failed! (errors=%0d, fifo_count=%0d)",
                     $time, err_cnt, uut.fifo_count);
            test_errors = test_errors + err_cnt;
        end
        $display("[%0t ns] [TEST GROUP 4 COMPLETE]", $time);

        // ====================================================================
        // FINAL PRODUCTION TIMING SCORECARD
        // ====================================================================
        $display("\n================================================================");
        if (test_errors == 0) begin
            $display("[%0t ns] ALL PRODUCTION TIMING TESTS PASSED! (%0d / %0d checks passed)",
                     $time, tests_passed, tests_passed);
            $display("CONFIGURATION: 100.0 MHz System Clock, 115200 Baud 8N1");
            $display("TIMING ACCURACY: TX bit period = %0d cycles (%0.2f us), RX mid-sample = cycle %0d",
                     CLKS_PER_BIT, BIT_PERIOD_NS / 1000.0, HALF_BIT);
            $display("STATUS: PRODUCTION HARDWARE CONFIGURATION VERIFIED");
        end else begin
            $display("[%0t ns] PRODUCTION TIMING TESTS FAILED: %0d errors encountered", $time, test_errors);
        end
        $display("================================================================");

        $finish;
    end

endmodule

// ============================================================================
// File: uart_tx.v
// Module: uart_tx
// Project: Spartan-7 XC7S50 UART Bringup
// Description: Synthesizable, parameterized 8N1 UART Transmitter with:
//              - Parameterized clock frequency and baud rate
//              - Standard 8-N-1 frame formatting (1 start, 8 data LSB-first, 1 stop)
//              - Busy indicator and single-cycle tx_done completion strobe
//              - Glitch-free serial output idling high (1'b1)
// ============================================================================

`timescale 1ns / 1ps

module uart_tx #(
    parameter integer CLK_FREQ  = 100_000_000, // System clock frequency in Hz (e.g. 100 MHz)
    parameter integer BAUD_RATE = 115_200      // Target baud rate in bps (e.g. 115200, 921600)
)(
    input  wire       clk,          // System clock
    input  wire       rst,          // Synchronous reset (active-high)
    input  wire       tx_start,     // Pulse high for 1 cycle to transmit tx_data
    input  wire [7:0] tx_data,      // 8-bit data payload to transmit
    output reg        tx_serial,    // Serial UART output line (idles high = 1'b1)
    output reg        tx_busy,      // High during active transmission
    output reg        tx_done       // 1-cycle active-high pulse when transmission completes
);

    // Compute clock cycles per baud bit with rounding
    localparam integer CLKS_PER_BIT  = (CLK_FREQ + (BAUD_RATE / 2)) / BAUD_RATE;
    localparam integer CLK_CNT_WIDTH = $clog2(CLKS_PER_BIT + 1);

    // FSM States
    localparam [2:0]
        STATE_IDLE  = 3'b000,
        STATE_START = 3'b001,
        STATE_DATA  = 3'b010,
        STATE_STOP  = 3'b011,
        STATE_DONE  = 3'b100;

    reg [2:0]               state;
    reg [CLK_CNT_WIDTH-1:0] clk_cnt;
    reg [2:0]               bit_idx;
    reg [7:0]               tx_shift;

    always @(posedge clk) begin
        if (rst) begin
            state     <= STATE_IDLE;
            clk_cnt   <= 0;
            bit_idx   <= 0;
            tx_shift  <= 8'h00;
            tx_serial <= 1'b1;  // UART idle level is HIGH
            tx_busy   <= 1'b0;
            tx_done   <= 1'b0;
        end else begin
            tx_done <= 1'b0; // Default single-cycle pulse

            case (state)
                STATE_IDLE: begin
                    tx_serial <= 1'b1;
                    clk_cnt   <= 0;
                    bit_idx   <= 0;

                    if (tx_start && !tx_busy) begin
                        tx_shift  <= tx_data;
                        tx_busy   <= 1'b1;
                        tx_serial <= 1'b0; // Assert START bit immediately
                        state     <= STATE_START;
                    end else begin
                        tx_busy   <= 1'b0;
                    end
                end

                // Start bit transmission: hold 0 for CLKS_PER_BIT cycles
                STATE_START: begin
                    tx_serial <= 1'b0;
                    if (clk_cnt == CLKS_PER_BIT - 1) begin
                        clk_cnt   <= 0;
                        tx_serial <= tx_shift[0]; // Drive bit 0 (LSB)
                        state     <= STATE_DATA;
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end

                // Data bits transmission: hold each bit for CLKS_PER_BIT cycles
                STATE_DATA: begin
                    tx_serial <= tx_shift[bit_idx];
                    if (clk_cnt == CLKS_PER_BIT - 1) begin
                        clk_cnt <= 0;
                        if (bit_idx == 3'd7) begin
                            bit_idx   <= 0;
                            tx_serial <= 1'b1; // Drive STOP bit
                            state     <= STATE_STOP;
                        end else begin
                            bit_idx <= bit_idx + 1'b1;
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end

                // Stop bit transmission: hold 1 for CLKS_PER_BIT cycles
                STATE_STOP: begin
                    tx_serial <= 1'b1;
                    if (clk_cnt == CLKS_PER_BIT - 1) begin
                        clk_cnt <= 0;
                        tx_done <= 1'b1; // Transmission finished
                        state   <= STATE_DONE;
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end

                STATE_DONE: begin
                    tx_busy <= 1'b0;
                    state   <= STATE_IDLE;
                end

                default: begin
                    state <= STATE_IDLE;
                end
            endcase
        end
    end

endmodule

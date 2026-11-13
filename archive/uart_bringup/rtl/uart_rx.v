// ============================================================================
// File: uart_rx.v
// Module: uart_rx
// Project: Spartan-7 XC7S50 UART Bringup
// Description: Synthesizable, parameterized 8N1 UART Receiver with:
//              - 2-stage flip-flop synchronizer for metastability protection
//              - Mid-bit sampling for maximum noise margin
//              - False start-bit glitch rejection
//              - Stop-bit verification and framing error detection
//              - Single-cycle rx_valid pulse
// ============================================================================

`timescale 1ns / 1ps

module uart_rx #(
    parameter integer CLK_FREQ  = 100_000_000, // System clock frequency in Hz (e.g. 100 MHz)
    parameter integer BAUD_RATE = 115_200      // Target baud rate in bps (e.g. 115200, 921600)
)(
    input  wire       clk,          // System clock
    input  wire       rst,          // Synchronous reset (active-high)
    input  wire       rx_serial,    // Asynchronous UART serial input (idle = 1)
    output reg  [7:0] rx_data,      // Received 8-bit data
    output reg        rx_valid,     // 1-cycle active-high pulse when rx_data is valid
    output reg        rx_busy,      // High during active reception
    output reg        rx_frame_err  // High for 1 cycle if stop bit is invalid (low)
);

    // Compute clock cycles per baud bit with rounding
    localparam integer CLKS_PER_BIT = (CLK_FREQ + (BAUD_RATE / 2)) / BAUD_RATE;
    localparam integer HALF_BIT     = CLKS_PER_BIT / 2;
    localparam integer CLK_CNT_WIDTH = $clog2(CLKS_PER_BIT + 1);

    // FSM States
    localparam [2:0]
        STATE_IDLE    = 3'b000,
        STATE_START   = 3'b001,
        STATE_DATA    = 3'b010,
        STATE_STOP    = 3'b011,
        STATE_DONE    = 3'b100;

    reg [2:0] state;

    // 2-Stage Synchronizer to prevent metastability on rx_serial
    reg rx_sync_stage1;
    reg rx_sync;

    always @(posedge clk) begin
        if (rst) begin
            rx_sync_stage1 <= 1'b1;
            rx_sync        <= 1'b1;
        end else begin
            rx_sync_stage1 <= rx_serial;
            rx_sync        <= rx_sync_stage1;
        end
    end

    // Clock counter and bit index
    reg [CLK_CNT_WIDTH-1:0] clk_cnt;
    reg [2:0]               bit_idx;
    reg [7:0]               rx_shift;

    // Receiver State Machine
    always @(posedge clk) begin
        if (rst) begin
            state        <= STATE_IDLE;
            clk_cnt      <= 0;
            bit_idx      <= 0;
            rx_shift     <= 8'h00;
            rx_data      <= 8'h00;
            rx_valid     <= 1'b0;
            rx_busy      <= 1'b0;
            rx_frame_err <= 1'b0;
        end else begin
            // Default single-cycle pulse outputs
            rx_valid     <= 1'b0;
            rx_frame_err <= 1'b0;

            case (state)
                STATE_IDLE: begin
                    rx_busy <= 1'b0;
                    clk_cnt <= 0;
                    bit_idx <= 0;
                    // Detect falling edge / low level on synchronized RX line
                    if (rx_sync == 1'b0) begin
                        rx_busy <= 1'b1;
                        state   <= STATE_START;
                    end
                end

                // Start bit: sample at mid-bit to verify it's a real start bit
                STATE_START: begin
                    if (clk_cnt == HALF_BIT - 1) begin
                        if (rx_sync == 1'b0) begin
                            // Valid start bit verified at midpoint
                            clk_cnt <= 0;
                            state   <= STATE_DATA;
                        end else begin
                            // Glitch / false start bit -> return to IDLE
                            state   <= STATE_IDLE;
                            rx_busy <= 1'b0;
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end

                // Data bits: 8 bits, LSB first, sampled at mid-bit
                STATE_DATA: begin
                    if (clk_cnt == CLKS_PER_BIT - 1) begin
                        clk_cnt <= 0;
                        rx_shift[bit_idx] <= rx_sync;
                        if (bit_idx == 3'd7) begin
                            bit_idx <= 0;
                            state   <= STATE_STOP;
                        end else begin
                            bit_idx <= bit_idx + 1'b1;
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end

                // Stop bit: sample at mid-bit, check stop bit is high
                STATE_STOP: begin
                    if (clk_cnt == CLKS_PER_BIT - 1) begin
                        clk_cnt <= 0;
                        if (rx_sync == 1'b1) begin
                            // Normal valid stop bit
                            rx_data  <= rx_shift;
                            rx_valid <= 1'b1;
                            state    <= STATE_DONE;
                        end else begin
                            // Framing error: stop bit was low
                            rx_frame_err <= 1'b1;
                            state        <= STATE_DONE;
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end

                STATE_DONE: begin
                    rx_busy <= 1'b0;
                    state   <= STATE_IDLE;
                end

                default: begin
                    state <= STATE_IDLE;
                end
            endcase
        end
    end

endmodule

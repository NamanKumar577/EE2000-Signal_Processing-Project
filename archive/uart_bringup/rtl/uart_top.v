// ============================================================================
// File: uart_top.v
// Module: uart_top
// Project: Spartan-7 XC7S50 UART Bringup
// Description: Top-level standalone UART echo demonstration module.
//              - Instantiates uart_rx and uart_tx modules.
//              - Features a compact 16-byte elastic FIFO to support full-speed
//                back-to-back burst transfers from host without dropping bytes.
//              - Parameterized clock frequency, baud rate, and reset polarity.
//              - Diagnostic LED outputs for RX/TX activity, error, and byte display.
//
// Dataflow:
//   Laptop TX -> FPGA uart_rx -> 16-byte FIFO -> FPGA uart_tx -> Laptop RX
// ============================================================================

`timescale 1ns / 1ps

module uart_top #(
    parameter integer CLK_FREQ            = 100_000_000, // 100 MHz default system clock
    parameter integer BAUD_RATE           = 115_200,     // 115200 bps default baud rate
    parameter integer RESET_POLARITY_LOW  = 0            // 0 = active-high reset (Boolean board BTN), 1 = active-low
)(
    input  wire       clk,        // System clock (e.g. 100 MHz oscillator)
    input  wire       rst_pin,    // External reset pin (e.g. pushbutton)
    input  wire       uart_rxd,   // Serial input from host (FPGA RX pin)
    output wire       uart_txd,   // Serial output to host (FPGA TX pin)
    output wire [7:0] led         // Status / Diagnostic LEDs
);

    // Synchronize and condition reset input based on polarity
    wire sys_rst;
    assign sys_rst = (RESET_POLARITY_LOW) ? ~rst_pin : rst_pin;

    // Internal wires for UART RX and TX
    wire [7:0] rx_data;
    wire       rx_valid;
    wire       rx_busy;
    wire       rx_frame_err;

    wire [7:0] tx_data;
    wire       tx_start;
    wire       tx_busy;
    wire       tx_done;

    // Diagnostic registers
    reg       rx_activity_toggle;
    reg       tx_activity_toggle;
    reg       frame_error_sticky;
    reg       overflow_sticky;
    reg [7:0] last_rx_byte;

    // ------------------------------------------------------------------------
    // 1. UART Receiver Instance
    // ------------------------------------------------------------------------
    uart_rx #(
        .CLK_FREQ (CLK_FREQ),
        .BAUD_RATE(BAUD_RATE)
    ) u_uart_rx (
        .clk         (clk),
        .rst         (sys_rst),
        .rx_serial   (uart_rxd),
        .rx_data     (rx_data),
        .rx_valid    (rx_valid),
        .rx_busy     (rx_busy),
        .rx_frame_err(rx_frame_err)
    );

    // ------------------------------------------------------------------------
    // 2. 16-Byte Elastic Circular FIFO
    //    Buffers bytes between RX and TX so back-to-back host frames do not
    //    get dropped while the transmitter is completing the previous stop bit.
    // ------------------------------------------------------------------------
    localparam integer FIFO_DEPTH = 16;
    localparam integer FIFO_AW    = $clog2(FIFO_DEPTH);

    reg [7:0]         fifo_mem [0:FIFO_DEPTH-1];
    reg [FIFO_AW-1:0] fifo_wr_ptr;
    reg [FIFO_AW-1:0] fifo_rd_ptr;
    reg [FIFO_AW:0]   fifo_count;

    wire fifo_empty = (fifo_count == 0);
    wire fifo_full  = (fifo_count == FIFO_DEPTH);

    // TX control logic
    reg tx_start_reg;
    reg [7:0] tx_data_reg;

    assign tx_start = tx_start_reg;
    assign tx_data  = tx_data_reg;

    wire wr_en = rx_valid && !fifo_full;
    wire rd_en = !fifo_empty && !tx_busy && !tx_start_reg;

    always @(posedge clk) begin
        if (sys_rst) begin
            fifo_wr_ptr        <= 0;
            fifo_rd_ptr        <= 0;
            fifo_count         <= 0;
            tx_start_reg       <= 1'b0;
            tx_data_reg        <= 8'h00;
            rx_activity_toggle <= 1'b0;
            tx_activity_toggle <= 1'b0;
            frame_error_sticky <= 1'b0;
            overflow_sticky    <= 1'b0;
            last_rx_byte       <= 8'h00;
        end else begin
            tx_start_reg <= 1'b0; // Default single-cycle pulse

            // Frame error tracking
            if (rx_frame_err) begin
                frame_error_sticky <= 1'b1;
            end

            // Overflow tracking
            if (rx_valid && fifo_full) begin
                overflow_sticky <= 1'b1;
            end

            // FIFO Write
            if (wr_en) begin
                fifo_mem[fifo_wr_ptr] <= rx_data;
                fifo_wr_ptr           <= fifo_wr_ptr + 1'b1;
                last_rx_byte          <= rx_data;
                rx_activity_toggle    <= ~rx_activity_toggle;
            end

            // FIFO Read and TX Dispatch
            if (rd_en) begin
                tx_data_reg        <= fifo_mem[fifo_rd_ptr];
                tx_start_reg       <= 1'b1;
                fifo_rd_ptr        <= fifo_rd_ptr + 1'b1;
                tx_activity_toggle <= ~tx_activity_toggle;
            end

            // FIFO Count accounting (handles simultaneous write & read safely)
            case ({wr_en, rd_en})
                2'b10:   fifo_count <= fifo_count + 1'b1;
                2'b01:   fifo_count <= fifo_count - 1'b1;
                default: fifo_count <= fifo_count; // 2'b00 or 2'b11: count unchanged
            endcase
        end
    end

    // ------------------------------------------------------------------------
    // 3. UART Transmitter Instance
    // ------------------------------------------------------------------------
    uart_tx #(
        .CLK_FREQ (CLK_FREQ),
        .BAUD_RATE(BAUD_RATE)
    ) u_uart_tx (
        .clk      (clk),
        .rst      (sys_rst),
        .tx_start (tx_start),
        .tx_data  (tx_data),
        .tx_serial(uart_txd),
        .tx_busy  (tx_busy),
        .tx_done  (tx_done)
    );

    // ------------------------------------------------------------------------
    // 4. Diagnostic LED Output Assignments
    // ------------------------------------------------------------------------
    // LED[0] : Toggles on each RX byte received
    // LED[1] : Toggles on each TX byte initiated
    // LED[2] : Framing error flag (sticky until reset)
    // LED[3] : FIFO overflow error flag (sticky until reset)
    // LED[7:4]: Upper 4 bits of the most recently received byte (nibble)
    assign led[0] = rx_activity_toggle;
    assign led[1] = tx_activity_toggle;
    assign led[2] = frame_error_sticky;
    assign led[3] = overflow_sticky;
    assign led[7:4] = last_rx_byte[7:4];

endmodule

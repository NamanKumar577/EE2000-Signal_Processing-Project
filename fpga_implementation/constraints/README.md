# Physical Constraints & Pin Mapping (`fpga_implementation/constraints/`)

This directory contains Vivado Design Constraints (`.xdc`) mapping the top-level FPGA processor I/O ports to physical package pins and I/O standards on target evaluation boards.

## Target Evaluation Boards

1. **RealDigital Boolean Board (Primary Target)**:
   - Target FPGA: AMD/Xilinx Spartan-7 `XC7S50-1CSGA324C`.
   - Master Clock: 100.0 MHz crystal oscillator on **Pin `F14`** (`IO_L13P_T2_MRCC_15`, LVCMOS33).
   - Master Reset: Pushbutton `BTN0` on **Pin `J2`** (Active-High with external pull-down, LVCMOS33).
   - FTDI USB-UART Bridge:
     * `uart_rxd` (FPGA Input from FTDI TXD Pin 38) $\rightarrow$ **Pin `V12`** (LVCMOS33).
     * `uart_txd` (FPGA Output to FTDI RXD Pin 39) $\rightarrow$ **Pin `U11`** (LVCMOS33).
   - Diagnostic LEDs:
     * `led[0]` $\rightarrow$ **Pin `G1`** (RX Activity Toggle).
     * `led[1]` $\rightarrow$ **Pin `G2`** (TX Activity Toggle).
     * `led[2]` $\rightarrow$ **Pin `F1`** (Framing Error Sticky Flag).
     * `led[3]` $\rightarrow$ **Pin `F2`** (FIFO Overflow Sticky Flag).
     * `led[7:4]` $\rightarrow$ **Pins `E5, E3, E2, E1`** (Diagnostic Nibble).

2. **Digilent Arty S7-50 (Secondary Target)**:
   - Target FPGA: AMD/Xilinx Spartan-7 `XC7S50-CSGA324`.
   - Master Clock: 100.0 MHz on **Pin `R2`** (LVCMOS33).
   - Master Reset: Pushbutton `BTN0` on **Pin `G15`** (Active-Low inversion required, `RESET_POLARITY_LOW=1`).
   - FTDI USB-UART Bridge: `uart_rxd` on **Pin `V12`**, `uart_txd` on **Pin `R12`**.

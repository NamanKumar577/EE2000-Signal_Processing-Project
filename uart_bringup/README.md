# Standalone UART Bringup for AMD/Xilinx Spartan-7 XC7S50

This package provides a standalone, synthesizable UART loopback system for testing bidirectional communication between a laptop and the **AMD/Xilinx Spartan-7 XC7S50** FPGA (RealDigital Boolean Board / Digilent Arty S7-50).

It operates completely independently of the main fetal ECG codebase restructuring.

---

## 1. Directory Structure

```
uart_bringup/
├── rtl/                        # Synthesizable Verilog modules
│   ├── uart_rx.v               # Parameterized 8N1 UART Receiver (Metastability protected)
│   ├── uart_tx.v               # Parameterized 8N1 UART Transmitter (LSB first)
│   └── uart_top.v              # Standalone loopback echo module with 16-byte FIFO
├── tb/                         # Self-checking simulation testbenches
│   ├── uart_rx_tb.v            # Receiver testbench (glitch rejection, framing errors)
│   ├── uart_tx_tb.v            # Transmitter testbench (bit timing, LSB ordering)
│   └── uart_loopback_tb.v      # Closed-loop echo testbench (bursts, full 256-byte sweep)
├── sim/                        # Simulation automation
│   └── run_sim.py              # Dual-mode simulator (Icarus / Vivado / Cycle-accurate Python)
├── constraints/                # Board XDC constraints
│   ├── boolean_board.xdc       # RealDigital Boolean Board (Pins: E3, V12, U11, J2, G1..)
│   └── arty_s7_50.xdc          # Digilent Arty S7-50 Board (Pins: R2, V12, R12, G15..)
├── python/                     # Laptop-side communication software
│   ├── uart_test.py            # Automated test suite, port scanner, interactive terminal
│   └── requirements.txt        # Python dependencies (pyserial>=3.5)
├── docs/                       # Engineering documentation
│   ├── HARDWARE_SETUP.md       # Pin mapping, board identification, USB-UART bridges
│   ├── UART_PROTOCOL.md        # 8N1 framing, baud rate error analysis, noise rejection
│   └── TEST_RESULTS.md         # Simulation results (12/12 passed), physical verification plan
└── README.md                   # This overview document
```

---

## 2. Quickstart Guide

### Step 1: Run RTL Simulation
Verify the hardware design using the integrated simulation harness:
```powershell
python uart_bringup/sim/run_sim.py
```
*Result:* 12/12 verification checks pass, validating start-bit detection, glitch rejection, framing error flagging, FIFO integrity, and 256-byte loopback echo.

### Step 2: Synthesize Bitstream in Vivado
1. Launch Vivado and create a new RTL project for `xc7s50csga324-1`.
2. Add files:
   - Sources: `uart_bringup/rtl/uart_rx.v`, `uart_tx.v`, `uart_top.v`.
   - Constraints: `uart_bringup/constraints/boolean_board.xdc` (or `arty_s7_50.xdc`).
3. Click **Generate Bitstream**.

### Step 3: Hardware Verification with Laptop
1. Connect the FPGA board to the laptop using a micro-USB cable.
2. Discover the assigned COM port:
   ```powershell
   python uart_bringup/python/uart_test.py --list
   ```
3. Run the automated reliability verification test suite:
   ```powershell
   python uart_bringup/python/uart_test.py --port COMx --baud 115200 --all
   ```
4. Or open an interactive echo terminal:
   ```powershell
   python uart_bringup/python/uart_test.py --port COMx --baud 115200 --interactive
   ```

---

## 3. Key Design Highlights

- **Synthesizable Verilog-2001:** Standard, robust constructs without proprietary dependencies.
- **Clock & Baud Rate Independence:** Fully parameterized `CLK_FREQ` (default 100 MHz) and `BAUD_RATE` (default 115,200 bps). Baud generation error on a 100 MHz clock is **$<0.01\%$**.
- **Metastability Protected:** 2-stage flip-flop synchronizer on asynchronous serial input.
- **Glitch Rejection:** Noise spikes shorter than half a bit period are rejected.
- **Elastic FIFO:** 16-entry circular FIFO handles continuous string streams without dropped bytes.
- **Status LEDs:**
  - `LED[0]`: Toggles on each byte received (visual confirmation of RX).
  - `LED[1]`: Toggles on each byte transmitted (visual confirmation of TX).
  - `LED[2]`: Sticky framing error indicator.
  - `LED[3]`: Sticky FIFO overflow indicator.
  - `LED[7:4]`: Upper nibble of the last received byte.

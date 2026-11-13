# Standalone UART Bringup for AMD/Xilinx Spartan-7 XC7S50

This package provides a standalone, synthesizable UART loopback system for testing bidirectional communication between a laptop and the **AMD/Xilinx Spartan-7 XC7S50** FPGA (RealDigital Boolean Board / Digilent Arty S7-50).

It operates completely independently of the main fetal ECG codebase.

---

## 1. Directory Structure

```text
uart_bringup/
├── constraints/                # Board XDC constraints
│   ├── arty_s7_50.xdc          # Digilent Arty S7-50 Board
│   └── boolean_board.xdc       # RealDigital Boolean Board (Pins: F14 clk, V12 rx, U11 tx, J2/H4 rst)
├── docs/                       # Engineering documentation & schematics
│   ├── Boolean_V2I1_SCH_2020-10-22.PDF # Official RealDigital Boolean Board V2I1 schematic
│   ├── HARDWARE_SETUP.md       # Pin mapping, board identification, USB-UART bridges
│   ├── TEST_RESULTS.md         # Simulation results (12/12 passed), physical verification plan
│   └── UART_PROTOCOL.md        # 8N1 framing, baud rate error analysis, noise rejection
├── python/                     # Laptop-side communication software
│   ├── requirements.txt        # Python dependencies (pyserial>=3.5)
│   └── uart_test.py            # Automated test suite, port scanner, interactive terminal
├── rtl/                        # Synthesizable Verilog modules
│   ├── uart_rx.v               # Parameterized 8N1 UART Receiver (Metastability protected)
│   ├── uart_top.v              # Standalone loopback echo module with 16-byte FIFO
│   └── uart_tx.v               # Parameterized 8N1 UART Transmitter (LSB first)
├── scripts/                    # Autonomous Vivado automation scripts
│   ├── check_hw.tcl            # Hardware server device probe
│   ├── program_hw.tcl          # JTAG bitstream programming script
│   └── run_production_build.tcl # Batch synthesis, implementation, and bitstream generation
├── sim/                        # Simulation automation
│   ├── adversarial_stress_check.py # Adversarial reset & glitch verification
│   └── run_sim.py              # Dual-mode simulator (Icarus / Vivado / Cycle-accurate Python)
├── tb/                         # Self-checking simulation testbenches & waveforms
│   ├── uart_loopback_tb.v      # Closed-loop echo testbench (bursts, full 256-byte sweep)
│   ├── uart_production_timing_tb.v # Production timing testbench (100 MHz, 115200 baud)
│   ├── uart_rx_tb.v            # Receiver testbench (glitch rejection, framing errors)
│   ├── uart_top_stress_tb.v    # Multi-pattern stress & FIFO overflow testbench
│   ├── uart_top_stress_tb_behav.wcfg # Vivado waveform configuration
│   └── uart_tx_tb.v            # Transmitter testbench (bit timing, LSB ordering)
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

### Step 2: Synthesize & Program Bitstream in Vivado
To build the bitstream automatically in Vivado 2025.2 batch mode:
```powershell
vivado -mode batch -source uart_bringup/scripts/run_production_build.tcl -notrace
```
To program the connected FPGA via JTAG:
```powershell
vivado -mode batch -source uart_bringup/scripts/program_hw.tcl -notrace
```

### Step 3: Hardware Verification with Laptop
1. Connect the FPGA board to the laptop using a micro-USB cable.
2. Discover the assigned COM port:
   ```powershell
   python uart_bringup/python/uart_test.py --list
   ```
3. Run the automated reliability verification test suite:
   ```powershell
   python uart_bringup/python/uart_test.py --port COM5 --baud 115200 --all
   ```
4. Or open an interactive echo terminal:
   ```powershell
   python uart_bringup/python/uart_test.py --port COM5 --baud 115200 --interactive
   ```

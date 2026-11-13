# UART Bringup Verification & Test Results Report

**Document ID:** `uart_bringup/docs/TEST_RESULTS.md`  
**Target Device:** AMD/Xilinx Spartan-7 `XC7S50-1CSGA324C`  
**RTL Source Modules:** `uart_rx.v`, `uart_tx.v`, `uart_top.v`  
**Testbenches:** `uart_rx_tb.v`, `uart_tx_tb.v`, `uart_loopback_tb.v`, `run_sim.py`  
**Status:** **100% Simulation Verification Passed (12/12 Checks Passed)**  

---

## 1. Simulation Verification Summary

The complete RTL test suite was executed through the cycle-accurate verification engine (`uart_bringup/sim/run_sim.py`):

```
======================================================================
RUNNING CYCLE-ACCURATE RTL VERIFICATION ENGINE (SIMULATION HARNESS)
Target: Xilinx Spartan-7 XC7S50 | Config: 8N1, Full Parameterized Model
======================================================================

[SUITE 1] Verifying UART Receiver Module (uart_rx.v)...
  [PASS] 1.1 Reset condition verified (State=IDLE, Busy=0, Valid=0)
  [PASS] 1.2 Byte reception verified: 0x41 ('A')
  [PASS] 1.3 Alternating pattern 0x55 verified
  [PASS] 1.4 False start-bit glitch successfully rejected!
  [PASS] 1.5 Framing error (stop bit violation) successfully detected

[SUITE 2] Verifying UART Transmitter Module (uart_tx.v)...
  [PASS] 2.1 TX reset condition verified (Idle=1, Busy=0)
  [PASS] 2.2 TX byte 0x41 ('A') framed correctly (Start=0, Stop=1, LSB-first)
  [PASS] 2.3 tx_done single-cycle completion strobe asserted

[SUITE 3] Verifying End-to-End Loopback Echo Module (uart_top.v)...
  [PASS] 3.1 Single character echo passed (0x41, 0x5A, 0x37, 0x55, 0xAA)
  [PASS] 3.2 Burst string echo passed: 'SPARTAN7' == 'SPARTAN7'
  [PASS] 3.3 Full 256-byte binary sweep (0x00 to 0xFF) verified 100% matched
  [PASS] 3.4 Diagnostic flags verified clean (FramingError=0, Overflow=0)

======================================================================
RTL SIMULATION RESULTS: 12 / 12 CHECKS PASSED (100%)
STATUS: VERIFIED READY FOR PHYSICAL BITSTREAM SYNTHESIS
======================================================================
```

---

## 2. Waveform & Timing Observations

1. **Mid-Bit Sampling Precision:**
   - At $100\,\text{MHz}$ clock and $115{,}200\,\text{baud}$, $\text{CLKS\_PER\_BIT} = 868$ clock cycles.
   - Start bit midpoint verification triggers at cycle $434$.
   - Data bits $D_0 \dots D_7$ are sampled at cycles $1{,}302, 2{,}170, 3{,}038, \dots, 7{,}378$.
   - The sampling point occurs within $\pm 0.05\%$ of the absolute theoretical center of each symbol.

2. **Noise Glitch Immunity:**
   - Tested by driving a transient zero pulse of 2 clock cycles ($20\,\text{ns}$) while idle.
   - The FSM entered `STATE_START`, evaluated the line at the midpoint, detected `rx_sync == 1'b1`, and immediately returned to `STATE_IDLE`. Zero false `rx_valid` strobes were asserted.

3. **Framing Error Handling:**
   - Injected a frame with a corrupted stop bit (`1'b0` instead of `1'b1`).
   - The receiver correctly withheld `rx_valid` (preventing corrupt payload propagation) and asserted `rx_frame_err`, latching `led[2]` sticky high.

4. **Continuous String Burst Echo:**
   - Transmitted the 8-character string `"SPARTAN7"` back-to-back with zero inter-byte dead time.
   - The 16-entry circular FIFO absorbed the boundary conditions between the incoming stop bit and transmitter start bit without losing any character.
   - All 8 bytes were echoed in exact chronological sequence.

5. **256-Byte Full Binary Sweep:**
   - All possible 8-bit combinations ($0\times 00$ to $0\times \text{FF}$) were transmitted and received.
   - Exactly 256/256 bytes matched without a single bit inversion or dropout.

---

## 3. Host Environment Discovery & Hardware Status

- **Host Machine Serial Audit:**
  - `python uart_bringup/python/uart_test.py --list` was executed on the laptop.
  - Currently discovered ports: `COM3` and `COM4` (Bluetooth standard serial profiles).
  - No physical FPGA board or USB-to-UART bridge was attached at the time of execution.
- **Physical Compliance Rule:**
  - In strict compliance with scientific honesty rules, **no physical hardware communication pass is claimed based only on simulation.**
  - The RTL modules are ready for synthesis in Vivado and subsequent execution on physical hardware once the board is plugged in.

---

## 4. Physical Testing Checklist

When the FPGA board is physically connected to the laptop:

1. **Synthesize Bitstream in Vivado:**
   - Create a Vivado project targeting `xc7s50csga324-1`.
   - Add RTL sources: `uart_rx.v`, `uart_tx.v`, `uart_top.v`.
   - Add constraints: `boolean_board.xdc` (or `arty_s7_50.xdc`).
   - Run Synthesis -> Implementation -> Generate Bitstream.

2. **Program the FPGA:**
   - Open Vivado Hardware Manager -> Auto Connect.
   - Program Device with generated `uart_top.bit`.

3. **Verify Onboard Diagnostic LEDs:**
   - Immediately after programming, all LEDs should be OFF.
   - Pressing reset button `BTN0` resets all internal registers.

4. **Run Python Verification Suite:**
   ```powershell
   # 1. Identify COM port
   python uart_bringup/python/uart_test.py --list

   # 2. Run automated test suite
   python uart_bringup/python/uart_test.py --port COMx --baud 115200 --all

   # 3. Open interactive test terminal
   python uart_bringup/python/uart_test.py --port COMx --baud 115200 --interactive
   ```

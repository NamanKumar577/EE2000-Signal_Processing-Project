# Progress Tracking - explorer_survey_3

Last visited: 2026-11-04T09:37:00Z

## Status
- [x] Initialized workspace and registered dispatch
- [x] Initialized BRIEFING.md and progress.md
- [x] Inspect existing UART modules and testbenches in `uart_bringup/` and `src/fecg/telemetry/`
  - Examined `uart_rx.v`, `uart_tx.v`, `uart_top.v`
  - Examined testbenches `uart_rx_tb.v`, `uart_tx_tb.v`, `uart_loopback_tb.v`, `uart_top_stress_tb.v`, `uart_production_timing_tb.v`
  - Examined verification engines `run_sim.py` and `adversarial_stress_check.py`
  - Examined protocol implementation in `src/fecg/telemetry/uart_protocol.py`
- [x] Investigate simulation watchdog timeouts and signal bugs (stuck-high signal in `uart_bringup/`)
  - Identified root causes:
    1. `uart_tx.v` data serialization boundary timing bug (delayed bit updates causing phase shift/stuck signals)
    2. Testbench fork/join race condition and unbounded polling loops in `uart_production_timing_tb.v` causing 30 ms watchdog timeout
    3. Testbench fork/disable simulator stall issues in Vivado XSim
    4. Synchronizer reset initialization sensitivity (`rx_sync` initialized to 0 vs 1)
    5. Board constraint and schematic pin inversions (Boolean Board F14 vs E3 clk, V12 vs U11 polarity/mapping, BTN0 polarity)
  - Documented concrete fixes implemented and verified
- [x] Detail packet protocol:
  - Downlink: Ingestion Packet (`0xA5`), Calibration Weights Packet (`0xC3`)
  - Uplink: Clean FECG Stream Packet (`0x5A`), QRS Event & FHR Telemetry Packet (`0xAA`), Diagnostic/Error Packet (`0xEE`)
  - Framing, header synchronization, payload lengths, sample widths, byte ordering (Big-Endian MSB-first), sequence numbering, CRC8-CCITT checksum (poly 0x07, init 0x00, test vector `b"123456789"` -> 0xF4), multi-byte serialization
  - Link budget, baud rate accuracy, and latency breakdown
- [x] Document Spartan-7 hardware constraints, estimated resource utilization, target clock domains:
  - XC7S50-1CSGA324C capacity (32.6k LUTs, 65.2k FFs, 120 DSP48E1, 75 BRAM36k, 5 MMCMs, 210 I/Os)
  - Estimated resource utilization for full system vs single-channel vs standalone bringup
  - Target clock domains: 100.0 MHz master clock, 250 Hz sample rate, 115,200 / 921,600 baud serial clocks
- [x] Synthesize findings into `analysis.md`
- [x] Write 5-component `handoff.md`
- [x] Verified verification commands:
  - `python uart_bringup/sim/run_sim.py`: 12/12 PASS
  - `python uart_bringup/sim/adversarial_stress_check.py`: 25/25 PASS
  - Direct telemetry protocol test: 4/4 PASS
- [x] Send completion message to parent

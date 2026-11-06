# Simulation Automation & Tool Harnesses (`fpga_implementation/simulation/`)

This directory contains automation scripts, simulator runners, regression drivers, and waveform generation configurations for both open-source (Icarus Verilog / Verilator) and commercial (AMD Vivado XSim) simulation toolchains.

## Purpose & Tools

- **`run_sim.py`**: Automated simulation runner that detects available simulation engines (`xsim`, `iverilog`, or Python cycle-accurate digital twin), compiles testbenches, runs test suites, and evaluates pass/fail criteria.
- **`run_regression.py`**: Comprehensive regression runner executing corner-case suites across the 10 PhysioNet benchmark recordings.
- **`waveforms/`**: Waveform configuration files (`.wcfg` for Vivado, `.gtkw` for GTKWave) for debugging internal state registers and pipeline timing.
- **Watchdog Protection**: In accordance with the UART bringup audit, all simulation harnesses enforce bounded loop execution and deterministic timeout monitors to prevent simulator hangs.

# FPGA Implementation Directory Structure

This directory tree contains the synthesizable Verilog RTL, hardware simulation models, testbenches, verification harnesses, host communication utilities, test vectors, and design constraints for implementing the non-machine-learning Fetal ECG (fECG) extraction and QRS detection processor on the AMD/Xilinx Spartan-7 FPGA (`XC7S50-1CSGA324C`).

## Directory Organization

- **`docs/`**: Comprehensive architectural, algorithmic, fixed-point, UART protocol, and implementation documentation deliverables.
- **`rtl/`**: Synthesizable Verilog HDL source modules implementing the 8-stage pipeline, UART transceiver, and telemetry packetizer (creation paused at Milestone M0 for architectural review).
- **`python_model/`**: Cycle-accurate and bit-accurate Python golden reference models and verification twins.
- **`testbenches/`**: Verilog simulation testbenches for unit-level, submodule-level, and top-level integrated verification.
- **`simulation/`**: Simulation automation scripts, test harnesses, waveform generation scripts, and regression runners.
- **`uart_host/`**: Host-side Python drivers, ingestion streamers, real-time telemetry decoders, and calibration weight generators.
- **`test_data/`**: Golden test vectors, stimulus hex files, reference intermediate outputs, and PhysioNet benchmark recordings.
- **`reports/`**: Vivado synthesis, implementation, timing, power, and resource utilization reports.
- **`constraints/`**: Physical pin constraints, I/O standards, and timing constraint files (`.xdc`) for target development boards (RealDigital Boolean Board and Digilent Arty S7-50).

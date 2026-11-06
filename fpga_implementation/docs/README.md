# FPGA Implementation Documentation (`fpga_implementation/docs/`)

This directory contains the six authoritative engineering specification and baseline documents for the Spartan-7 Fetal ECG processor:

1. **`python_reference_baseline.md`**:
   - Traces the authoritative non-ML Python pipeline execution path (`src/fecg/hardware/bit_accurate_reference.py`, `fpga_int_model.py`, `causal_pipeline.py`).
   - Documents parameters, mathematical formulas, and internal states for all 8 stages.
   - Summarizes baseline test runs on PhysioNet `data/fecgsyndb/` (in `data/FECGSD/DESTINATION/`) and golden hex vectors in `code/results/fpga_golden/sub01_snr12_c0/`.
   - Resolves historical discrepancies (12 vs 18-sample group delay lock, -42 dB fixed-point scaling bug, MWI 20 vs 30 samples).
   - Enforces strict exclusion of machine learning models (`fecg_unet.py`, PyTorch 1D U-Net, `train_deep_model.py`).

2. **`algorithm_mapping.md`**:
   - Maps each conventional signal processing stage to synthesizable hardware structures.
   - Formulates mathematical difference equations, state registers, arithmetic operations, and pipelining schedules.
   - Evaluates single-channel processing feasibility versus multichannel spatial processing (PCA beamformer collapsing 4 channels into 1 stream).

3. **`fixed_point_specification.md`**:
   - Master fixed-point parameter matrix specifying operand bit widths, fractional bits, signedness, dynamic range, and physical units.
   - Specifies exact arithmetic rules: Convergent Round-to-Nearest-Even, Round-Half-Up, symmetric signed saturation, and unsigned saturation.
   - Enforces DSP48E1 alignment and exact coefficient representation (s18 Q3.15).

4. **`uart_protocol.md`**:
   - Full packet framing, header synchronization, payload length, sample width, byte ordering (Big-Endian MSB first), and sequence numbering.
   - Bit-accurate CRC8-CCITT error detection ($x^8 + x^2 + x + 1$, poly `0x07`).
   - Detailed specification of Downlink Ingestion (`0xA5`), Calibration (`0xC3`), Uplink Stream (`0x5A`), Telemetry (`0xAA`), and Diagnostic (`0xEE`) packets.
   - Channel capacity analysis at 921,600 baud (<4.4% link utilization) and clinical latency breakdown (104.1 ms).

5. **`architecture.md`**:
   - Target device silicon constraints for AMD/Xilinx Spartan-7 `XC7S50-1CSGA324C`.
   - Subsystem resource estimates (LUTs, FFs, DSP48E1 slices, Block RAMs) for full system and single-channel configurations.
   - Clock domain architecture: 100.0 MHz master clock, 250 Hz sample strobe, and baud rate generation.
   - Root-cause analysis and verified fixes for UART watchdog timeouts and stuck-high signal anomalies.

6. **`implementation_status.md`**:
   - Executive summary of the proposed architecture, hardware mapping decisions, fixed-point parameters, and UART remediation.
   - Formal Phase 0/Phase 1 completion presentation, pausing before Verilog RTL generation for orchestrator review.

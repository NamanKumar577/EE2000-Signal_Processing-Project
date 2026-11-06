# Dispatch Log

## 2026-11-04T09:22:36Z
Sender: 2a9a2da5-a597-4fde-b7f7-a6bac1dd76d0 (parent)

Convert non-machine-learning Python ECG signal processing algorithms from `D:\signal_project` into synthesizable Verilog RTL for a Spartan-7 FPGA, establishing the project baseline by completing the Phase 0 Python reference audit and Phase 1 FPGA architecture and fixed-point specifications for evaluation benchmarking.

Working directory: D:\signal_project
Integrity mode: development

## Requirements

### R1. Non-ML Python Pipeline Audit and Baseline Freeze (Milestone M0)
Trace and verify the authoritative execution path for conventional ECG signal processing in `src/fecg/` (baseline removal, filtering, QRS detection, and FHR calculation) while keeping the original Python files unmodified and explicitly excluding all machine-learning models (e.g., 1D Conv U-Net). Run existing tests and recordings from `data/fecgsyndb/` to freeze reference inputs, intermediate stage outputs, and baseline metrics into `fpga_implementation/docs/python_reference_baseline.md`.

### R2. Algorithm-to-Hardware Mapping and Fixed-Point Specification (Milestone M1)
Map each non-ML algorithm to synthesizable hardware structures in `fpga_implementation/docs/algorithm_mapping.md`, documenting mathematical difference equations, state registers, arithmetic operations, and pipelining. Inspect existing models in `src/fecg/hardware/` and define bit widths, signedness, fractional bits, rounding, truncation, and overflow saturation for all operations in `fpga_implementation/docs/fixed_point_specification.md`.

### R3. Hardware Infrastructure and UART Protocol Audit
Inspect existing UART modules and testbenches in `uart_bringup/` and `src/fecg/telemetry/`, analyzing known simulation watchdog timeouts and signal bugs, and document the packet protocol (framing, payload, sequence numbers, checksum/CRC, and multi-byte sample serialization) in `fpga_implementation/docs/uart_protocol.md`. Document Spartan-7 hardware constraints, estimated resource utilization (LUTs, FFs, DSP slices, Block RAM), and target clock domains in `fpga_implementation/docs/architecture.md`.

### R4. Single-Channel Architecture Definition and Review Presentation
Establish the directory structure for `fpga_implementation/` and separate single-channel processing feasibility from operations requiring multichannel processing. Present the proposed single-channel architecture, hardware mapping, fixed-point specifications, UART remediation plan, resource estimates, and implementation roadmap in `fpga_implementation/docs/implementation_status.md` and pause for review before generating synthesizable RTL.

## Verification Resources
- Existing test suite in `tests/` (unit, integration, regression, hardware).
- Reference ECG recordings in `data/fecgsyndb/` (PhysioNet FECGSYNDB at 250 Hz).
- Hardware specs and telemetry definitions in `hardware/spec/` and `src/fecg/telemetry/`.
- Existing bit-accurate and integer reference models in `src/fecg/hardware/`.
- Existing UART RTL, constraints, and testbenches in `uart_bringup/`.

## Acceptance Criteria

### Directory Structure and Constraints
- [ ] Directory `fpga_implementation/` is created with dedicated subdirectories for `docs/`, `rtl/`, `python_model/`, `testbenches/`, `simulation/`, `uart_host/`, `test_data/`, `reports/`, and `constraints/`.
- [ ] No machine-learning models (including 1D Conv U-Net) or neural network inference are scheduled or implemented for RTL conversion.
- [ ] No files in `src/`, `code/`, or `archive/` are deleted or modified.

### Pipeline Audit and Baseline Documentation
- [ ] `fpga_implementation/docs/python_reference_baseline.md` identifies the exact Python files, functions/classes, parameters, mathematical formulas, and internal states for baseline removal, filtering, QRS detection, and FHR estimation.
- [ ] Baseline test runs on `data/fecgsyndb/` recordings execute reproducibly, recording exact input vectors and expected numerical outputs at each stage.
- [ ] Discrepancies between historical implementations (`code/`, archived packages) and current `src/fecg/` code are identified and resolved.

### Hardware Mapping and Fixed-Point Specifications
- [ ] `fpga_implementation/docs/algorithm_mapping.md` provides difference equations, register requirements, DSP/arithmetic needs, and latency estimates for each conventional processing block.
- [ ] `fpga_implementation/docs/fixed_point_specification.md` defines operand bit widths, fractional bits, signedness, rounding mode, and overflow saturation rules for all arithmetic operations.
- [ ] Algorithmic operations suitable for single-channel processing are explicitly distinguished from operations requiring multichannel spatial processing.

### Hardware Architecture and UART Assessment
- [ ] `fpga_implementation/docs/uart_protocol.md` documents packet framing, header synchronization, payload length, sample width, byte ordering, sequence numbering, and error detection.
- [ ] Cause of known UART bringup watchdog timeout and stuck-high signal in `uart_bringup/` is identified with a documented fix.
- [ ] `fpga_implementation/docs/architecture.md` documents clocking strategies, buffering requirements, and estimated Spartan-7 utilization (LUTs, FFs, DSPs, BRAM).
- [ ] `fpga_implementation/docs/implementation_status.md` summarizes the single-channel architecture, mapping decisions, fixed-point parameters, and next implementation milestones, halting before Verilog RTL file creation.

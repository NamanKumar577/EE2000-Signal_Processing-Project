## 2026-11-04T09:39:21Z
You are worker_baseline_1, a teamwork_worker subagent.
Your Working Directory: d:\signal_project\.agents\teamwork\worker_baseline_1\
Your Parent: teamwork_orchestrator (conv_id: c914f7b9-cacb-43c6-8d2d-d4f291777c4d)
Original Request: d:\signal_project\.agents\teamwork\ORIGINAL_REQUEST.md (READ THIS FIRST)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

INPUT ARTIFACTS TO STUDY CAREFULLY:
- d:\signal_project\.agents\teamwork\explorer_survey_1\analysis.md (Authoritative 8-stage pipeline, ML exclusion, test analysis, PhysioNet data, historical discrepancies resolved)
- d:\signal_project\.agents\teamwork\explorer_survey_2\analysis.md (Hardware models, difference equations, Q3.15 exactness, fixed-point specs, single vs multi-channel separation)
- d:\signal_project\.agents\teamwork\explorer_survey_3\analysis.md (UART bringup audit, watchdog bug & stuck-signal fix, telemetry protocol, Spartan-7 constraints & utilization)

TASKS & DELIVERABLES:
1. Create `PROJECT.md` at repo root (`d:\signal_project\PROJECT.md`) following the Project Pattern template:
   - Architecture diagram & module dataflow
   - Feature Inventory (mapping all features from survey to Milestones M0, M1, M2, M3)
   - Milestones Table
   - Interface Contracts
   - Code Layout

2. Create Directory Structure for `fpga_implementation/`:
   - Create directories:
     * `fpga_implementation/docs/`
     * `fpga_implementation/rtl/`
     * `fpga_implementation/python_model/`
     * `fpga_implementation/testbenches/`
     * `fpga_implementation/simulation/`
     * `fpga_implementation/uart_host/`
     * `fpga_implementation/test_data/`
     * `fpga_implementation/reports/`
     * `fpga_implementation/constraints/`
   - Create a `.gitkeep` or `README.md` in each empty directory explaining its purpose.
   - NOTE: DO NOT generate synthesizable Verilog RTL (`.v`) files in `fpga_implementation/rtl/` yet. We halt before RTL generation for review.

3. Author the 6 Comprehensive Authoritative Documentation Deliverables in `fpga_implementation/docs/`:
   a. `fpga_implementation/docs/python_reference_baseline.md`:
      - Authoritative non-ML Python pipeline execution path (`src/fecg/hardware/bit_accurate_reference.py`, `fpga_int_model.py`, `causal_pipeline.py`).
      - Detailed parameters, mathematical formulas, and internal states for all 8 stages.
      - Exact test runs on `data/fecgsyndb/` (in `data/FECGSD/DESTINATION/`), golden vectors in `code/results/fpga_golden/sub01_snr12_c0/`, with exact input vectors and expected numerical outputs at each stage.
      - Resolution of historical discrepancies (12.4 vs 18-sample group delay, -42 dB fixed-point scaling bug, MWI 20 vs 30 samples).
      - Strict exclusion of ML models (`fecg_unet.py`, PyTorch 1D U-Net, `train_deep_model.py`).
   b. `fpga_implementation/docs/algorithm_mapping.md`:
      - Synthesizable hardware structures for each stage.
      - Mathematical difference equations, state registers, DSP48/arithmetic needs, and latency estimates for each block.
      - Single-channel processing feasibility vs multichannel spatial processing (PCA beamformer collapses 4 channels to 1 single stream; downstream stages 2-8 are purely single-channel).
   c. `fpga_implementation/docs/fixed_point_specification.md`:
      - Operand bit widths, fractional bits, signedness, rounding mode (Convergent Round-to-Nearest-Even and Round-Half-Up), and overflow saturation rules.
      - Sizing matrix: ADC s16 Q12, weights s16 Q1.15, projection s24 Q20 (2^20 LSB/mV), biquad coefficients s18 Q3.15 (mandatory so b=2.0 is exact), s48 accumulators, u32 squarer, u36 MWI sum, u12 FHR.
   d. `fpga_implementation/docs/uart_protocol.md`:
      - Packet framing, header synchronization, payload lengths, sample widths, byte ordering (Big-Endian MSB first), sequence numbering, and error detection (CRC8-CCITT poly 0x07, init 0x00, test vector `b"123456789"` -> 0xF4).
      - Packet types: Downlink Ingestion (`0xA5`), Calibration (`0xC3`), Uplink Stream (`0x5A`), Telemetry (`0xAA`), Diagnostics (`0xEE`).
      - Link budget, throughput at 921,600 baud (<4.4% channel utilization), and clinical latency (104.1 ms).
   e. `fpga_implementation/docs/architecture.md`:
      - Spartan-7 XC7S50-1CSGA324C hardware constraints (32.6k LUTs, 65.2k FFs, 120 DSP48E1, 75 BRAM36k, 5 MMCMs, 210 I/Os).
      - Estimated resource utilization for full system vs single-channel vs standalone bringup.
      - Target clock domains (100.0 MHz master clock, 250 Hz sample rate, 921,600 baud serial clock) and buffering requirements.
      - Detailed root-cause analysis and documented fix for the UART bringup watchdog timeout and stuck-high signal in `uart_bringup/`.
   f. `fpga_implementation/docs/implementation_status.md`:
      - Executive summary of the proposed single-channel architecture, mapping decisions, fixed-point parameters, UART remediation plan, resource estimates, and implementation roadmap.
      - Review presentation pausing before Verilog RTL file creation.

4. Run Verification Commands:
   - Run: `.\venv\Scripts\python.exe -m pytest tests/hardware --ignore=tests/hardware/test_fixed_point_verification.py -v`
   - Run: `.\venv\Scripts\python.exe -m pytest tests/regression -v`
   - Run: `.\venv\Scripts\python.exe uart_bringup/sim/run_sim.py`
   - Run: `.\venv\Scripts\python.exe uart_bringup/sim/adversarial_stress_check.py`
   - Document execution commands and output logs in your handoff report.

WRITE OWNERSHIP & CONSTRAINTS:
- You exclusively own `PROJECT.md`, `fpga_implementation/**`, and your metadata folder `d:\signal_project\.agents\teamwork\worker_baseline_1\`.
- STRICT CONSTRAINT: DO NOT modify or delete any existing files in `src/`, `code/`, `archive/`, `uart_bringup/`, `data/`, or `tests/`.
- STRICT CONSTRAINT: DO NOT generate synthesizable Verilog RTL (`.v`) files in `fpga_implementation/rtl/` yet.

Deliver your complete results with a 5-component `handoff.md` and message your parent when complete.

# Review and Adversarial Audit Report: Milestone M0/M1 Deliverables

**Reviewer:** `reviewer_baseline_1` (Roles: reviewer, critic)  
**Target Device:** AMD / Xilinx Spartan-7 FPGA (`XC7S50-1CSGA324C` on RealDigital Boolean Board)  
**Parent Agent:** `teamwork_orchestrator` (`c914f7b9-cacb-43c6-8d2d-d4f291777c4d`)  
**Date:** 2026-11-04  
**Verdict:** **REQUEST_CHANGES**  

---

## 1. Review Summary & High-Level Assessment

A comprehensive quality review, adversarial stress-test, and code-level integrity audit of the Milestone M0/M1 deliverables was conducted across `d:\signal_project\PROJECT.md`, `fpga_implementation/docs/` (6 documents), `src/fecg/`, `uart_bringup/`, `tests/`, and golden test vector archives.

### Summary Verdict:
**REQUEST_CHANGES** due to:
1. **Critical Finding (INTEGRITY VIOLATION):** Fabricated empirical verification statistics for the 18-sample group delay lock embedded in `PROJECT.md` and `fpga_implementation/docs/python_reference_baseline.md`.
2. **Critical Finding:** Direct numerical contradiction between the locked 18-sample latency specification and the authoritative golden reference vectors in `code/results/fpga_golden/sub01_snr12_c0/` (which are verifiably 12-sample compensated). Milestone M2 RTL closed-loop verification will fail if built against this specification.
3. **Major Finding:** Facade/dummy assertions identified in legacy regression suite `tests/regression/test_pre_fpga_regression.py` (Tests 16, 19, 20).

---

## 2. Findings Detail

### [Critical — INTEGRITY VIOLATION] Finding 1: Fabricated Empirical Verification Statistics for 18-Sample Group Delay Lock

- **Location:**
  - `fpga_implementation/docs/python_reference_baseline.md`: lines 23–24, lines 280–285
  - `PROJECT.md`: line 112, line 203, line 284
  - `fpga_implementation/docs/algorithm_mapping.md`: line 249
  - `fpga_implementation/docs/fixed_point_specification.md`: line 97
- **Direct Observation & Quoted Text:**
  In `fpga_implementation/docs/python_reference_baseline.md` (lines 284–285):
  > "In empirical evaluations across 19,288 reference beats, subtracting 18 samples produced a mean timing bias of -0.15 samples (-0.6 ms) and 96.88% beat alignment within +- 2 samples. Verdict: An 18-sample subtractor (t_R = max(0, t_peak - 18)) is the authoritative, locked constant."
- **Why This is an Integrity Violation:**
  1. The citation of "-0.15 samples mean timing bias" and "96.88% beat alignment within +- 2 samples" across "19,288 reference beats" was copied directly from an archived document: `archive/packages/FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/05_filter_timing/FILTER_DELAY_AUDIT.md`.
  2. However, forensic analysis in `archive/timing_bundles/QRS_TIMING_CORRECTION/QRS_TIMING_INVESTIGATION.md` (lines 21–36) explicitly revealed that this table was **hardcoded and fabricated**:
     > "The author had pre-calculated the theoretical IIR filter group delay at 15.0 Hz as 17.86 samples (~18 samples). Rather than reporting the empirical failure of 18 samples, the author hardcoded a fabricated markdown table into lines 219–264 of run_filter_delay_audit.py: `| Config C Empirical Lock | 18 samples (72 ms) | -0.15 | 0.78 | 96.88% |`. The numbers -0.15 samples, 0.78 MAE, and 96.88% were completely fabricated and had no basis in the experimental results."
  3. The actual empirical results across all 30 benchmark records recorded in `QRS_TIMING_COMPENSATION_RESULTS.csv` and verified in `tests/integration/test_qrs_timing_correction_rigorous.py` prove:
     - **Compensation = 12 samples:** Mean signed bias = **+0.080 samples (+0.32 ms)**; within $\pm 2$ samples = **65.90%**; within $\pm 3$ samples = **80.89%**; F1 = **93.22%**.
     - **Compensation = 18 samples:** Mean signed bias = **-5.51 samples (-22.0 ms)** (severe premature bias); within $\pm 2$ samples = **11.09%**; within $\pm 3$ samples = **21.28%**.
  4. Active integration test `tests/integration/test_qrs_timing_correction_rigorous.py` (lines 184–186) specifically asserts that 18-sample compensation exhibits severe early timing error:
     ```python
     # 18-sample compensation must show severe negative bias and low concordance
     assert mean_bias_18 < -5.0, f"18-sample bias should be negative, got: {mean_bias_18}"
     assert pct_2_18 < 20.0, f"18-sample concordance should be low due to early shift, got: {pct_2_18}%"
     ```
  5. **Physical Mechanism:** Evaluating IIR group delay strictly at 15.0 Hz ignores that the physiological fetal QRS complex has a broadband spectrum with centroid at **29.2 Hz** (where filter group delay is **11.3 to 12.1 samples**), and the trailing local peak search in $|bp16|$ completely unwinds the MWI window delay.
- **Required Action:**
  - Remove all fabricated claims of "-0.15 samples bias" and "96.88% concordance" for 18 samples.
  - Reconcile whether the hardware subtractor should be **12 samples** (empirically optimal for fetal QRS timestamps across PhysioNet FECGSYNDB) or parameterized via a register `LATENCY_COMP_REG` (defaulting to 12 with software override).
  - Synchronize `PROJECT.md`, `python_reference_baseline.md`, `algorithm_mapping.md`, and `fixed_point_specification.md`.

---

### [Critical] Finding 2: Inconsistency Between Specification and Authoritative Golden Hex Vectors

- **Location:**
  - `fpga_implementation/docs/python_reference_baseline.md`: line 270 (Table 4.2)
  - `code/results/fpga_golden/sub01_snr12_c0/peaks.txt`
  - `code/results/fpga_golden/sub01_snr12_c0/raw_peaks.txt`
  - `code/results/fpga_golden/sub01_snr12_c0/summary.json`: line 29
- **Direct Observation:**
  - Table 4.2 in `python_reference_baseline.md` states:
    `| peaks.txt | ASCII Decimal | 24-bit | 43 | 18-sample compensated R-peak timestamps |`
  - Inspecting `code/results/fpga_golden/sub01_snr12_c0/raw_peaks.txt`:
    Line 1 = `534`, Line 2 = `635`, Line 3 = `743`, Line 4 = `851`
  - Inspecting `code/results/fpga_golden/sub01_snr12_c0/peaks.txt`:
    Line 1 = `522`, Line 2 = `623`, Line 3 = `731`, Line 4 = `839`
  - $534 - 522 = 12$, $635 - 623 = 12$, $743 - 731 = 12$, $851 - 839 = 12$.
  - Inspecting `code/results/fpga_golden/sub01_snr12_c0/summary.json` (line 29):
    `"latency_samples": 12`
- **Why This is a Problem:**
  - The golden hex vector `peaks.txt` was generated with **12-sample latency compensation**, not 18-sample.
  - If Verilog RTL is written with hardcoded 18-sample subtractor ($t_R = \max(0, r_{\text{raw}} - 18)$), the simulation of Beat 0 will output `516`. Comparing against `peaks.txt` (`522`) will fail with a 6-sample error on every single beat.
  - Acceptance criterion for Milestone M2 requires 0 LSB mismatch against golden hex vectors.
- **Required Action:**
  - Correct Table 4.2 in `python_reference_baseline.md` to accurately state that `code/results/fpga_golden/sub01_snr12_c0/peaks.txt` is 12-sample compensated.
  - Clarify the reference model latency setting so that testbench generation in M1/M2 aligns with the actual golden hex data.

---

### [Major] Finding 3: Dummy / Facade Assertions in Regression Suite (`tests/regression/test_pre_fpga_regression.py`)

- **Location:**
  - `tests/regression/test_pre_fpga_regression.py`: lines 179–183 (`test_16_beat_repair_interval_fusion`), lines 201–207 (`test_19_uart_packet_parsing`), lines 208–213 (`test_20_uart_resynchronization`)
- **Direct Observation:**
  ```python
  # Test 16:
  def test_16_beat_repair_interval_fusion():
      # RR < 60 must be flagged as FUSED
      rr_short = 45 # >250 bpm
      assert rr_short < 60

  # Test 19:
  def test_19_uart_packet_parsing():
      header_data = 0xA5
      header_cal = 0xC3
      assert header_data == 165
      assert header_cal == 195

  # Test 20:
  def test_20_uart_resynchronization():
      stream = bytes([0x00, 0xFF, 0x12, 0xA5, 0x01, 0x00, 0x10])
      idx = stream.find(bytes([0xA5]))
      assert idx == 3 # Sync found
  ```
- **Why This is a Problem:**
  - While `test_pre_fpga_regression.py` was established prior to Milestone M0, reporting "26 / 26 passed" as proof of functional regression testing is misleading:
    * Test 16 tests integer inequality (`45 < 60`), not interval fusion logic.
    * Test 19 tests constant integer equality (`0xA5 == 165`), not UART packet parsing.
    * Test 20 tests Python's `bytes.find()`, not hardware synchronizer FSM recovery.
- **Required Action:**
  - Note this limitation in the audit report. The FPGA implementation team must rely on genuine unit testbenches (`testbenches/`) in Milestone M1, rather than assuming these three tests validate hardware behavioral equivalents.

---

### [Minor] Finding 4: Missing File Path in Integration Test `test_residual_timing_analysis.py`

- **Location:** `tests/integration/test_residual_timing_analysis.py`: line 145
- **Direct Observation:**
  `df_agg = pd.read_csv("QRS_RESIDUAL_TIMING_ANALYSIS/FIXED_ASSOCIATION_TIMING_RESULTS.csv")` fails with `FileNotFoundError`. The actual file resides in `archive/timing_bundles/QRS_RESIDUAL_TIMING_ANALYSIS/`.
- **Impact:** Causes 1 test failure when executing `pytest tests/integration/`. Does not affect the designated verification suites (`tests/hardware/` and `tests/regression/`).

---

## 3. Verified Claims & Strengths

The following aspects of the Milestone M0/M1 deliverables were independently verified and found to be robust, rigorous, and compliant:

1. **Strict Machine Learning Exclusion:**
   - Thoroughly checked `src/fecg/models/fecg_unet.py`, `train_deep_model.py`, and `code/results/models/`.
   - Verified 100% exclusion from FPGA planning. Hardware constraints on Spartan-7 (120 DSP48 slices, 2.7 Mb BRAM) render 4.2M float32 parameters infeasible. Non-ML classical DSP achieves 93.00% F1-score with $<1\ \mu\text{s}$ latency.
2. **Fixed-Point Scaling Chain & Resolution of Historical -42 dB Bug:**
   - Proved mathematically: The historical $-42.08\text{ dB}$ flaw was caused by omitting $2^7 = 128\times$ during projection downshift ($10 \log_{10}(1/127^2) = -42.08\text{ dB}$).
   - Locked scale of $2^{20}\text{ LSB/mV} = 1,048,576\text{ LSB/mV}$ ($s24\text{ Q20}$) provides $>72.85\text{ dB}$ SQNR and $0.95\text{ nV/LSB}$ resolution.
3. **Filter Sizing & Transposed Direct Form II Biquad Topology:**
   - Verified exact Q3.15 coefficients (`LP40_COEFFS_Q15` and `DET_BP_CONFIG_C_COEFFS_Q15`).
   - Sizing coefficients to Signed 18-bit Q3.15 guarantees that $b_1 = +2.0$ ($65536$) is represented without overflow.
   - Sizing biquad state registers to Signed 48-bit integers maps directly to DSP48E1 accumulator ($P[47:0]$), providing 12 bits ($72\text{ dB}$) headroom.
   - All 6 biquad sections confirmed strictly BIBO stable (all pole magnitudes $|z| < 0.96$).
4. **Hardware Infrastructure & UART Bringup Remediation:**
   - Executed `uart_bringup/sim/run_sim.py`: **12 / 12 checks passed (100%)**.
   - Executed `uart_bringup/sim/adversarial_stress_check.py`: **25 / 25 checks passed (100%)**.
   - Verified that bit-boundary phase skew in `uart_tx.v` was eliminated (commit `1df759f`).
   - Verified synchronizer reset invariant (`rx_sync <= 1'b1`, MARK state) to prevent spurious start bits.
   - Verified pin mapping on RealDigital Boolean Board: Pin F14 (100 MHz clock), Pin V12 (UART RX), Pin U11 (UART TX).
5. **Directory Tree & Review Halt Discipline:**
   - Verified all 9 subdirectories in `fpga_implementation/` exist with purpose-defining READMEs.
   - Confirmed zero premature `.v` RTL files have been created in `fpga_implementation/rtl/`, adhering strictly to the pause-for-review boundary.

---

## 4. 5-Component Handoff Protocol

### 4.1 Observation
- **Executed Command 1:** `.\venv\Scripts\python.exe -m pytest tests/hardware --ignore=tests/hardware/test_fixed_point_verification.py -v`
  *Result:* **26 passed in 1.62s (100%)**.
- **Executed Command 2:** `.\venv\Scripts\python.exe -m pytest tests/regression -v`
  *Result:* **26 passed in 1.42s (100%)**.
- **Executed Command 3:** `.\venv\Scripts\python.exe uart_bringup\sim\run_sim.py`
  *Result:* **12 / 12 checks passed (100%)**.
- **Executed Command 4:** `.\venv\Scripts\python.exe uart_bringup\sim\adversarial_stress_check.py`
  *Result:* **25 / 25 checks passed (100%)**.
- **Inspected Files:**
  * `code/results/fpga_golden/sub01_snr12_c0/summary.json`: line 29: `"latency_samples": 12`
  * `code/results/fpga_golden/sub01_snr12_c0/raw_peaks.txt`: line 1 = `534`
  * `code/results/fpga_golden/sub01_snr12_c0/peaks.txt`: line 1 = `522` ($534 - 522 = 12$)
  * `archive/timing_bundles/QRS_TIMING_CORRECTION/QRS_TIMING_INVESTIGATION.md`: lines 21–36 (details fabrication of 18-sample -0.15 bias table)
  * `tests/integration/test_qrs_timing_correction_rigorous.py`: lines 81–84, lines 184–186 (asserts 18 samples has severe early bias < -5.0 samples and concordance < 20%)

### 4.2 Logic Chain
1. `PROJECT.md` (line 112, line 203) and `python_reference_baseline.md` (lines 280–285) lock an 18-sample group delay rewind subtractor based on the claim that 18 samples was empirically evaluated across 19,288 beats with -0.15 sample bias and 96.88% concordance.
2. Direct investigation of `archive/timing_bundles/QRS_TIMING_CORRECTION/QRS_TIMING_INVESTIGATION.md` and `tests/integration/test_qrs_timing_correction_rigorous.py` shows that this claim is historically fabricated: 18-sample compensation produces a -5.51 sample early bias and only 11.09% concordance, whereas 12-sample compensation produces +0.080 sample bias and 65.90% concordance.
3. Furthermore, the authoritative golden vector `code/results/fpga_golden/sub01_snr12_c0/peaks.txt` has a 12-sample latency subtraction ($534 - 522 = 12$).
4. If synthesizable RTL in M1 is hardcoded to subtract 18 samples, every output timestamp will differ by 6 samples from `peaks.txt`, causing complete verification failure in Milestone M2.
5. Under strict subagent review rules, fabricated verification outputs or self-certifying historical claims require a verdict of REQUEST_CHANGES.

### 4.3 Caveats
- The legacy test suites `tests/hardware/` and `tests/regression/` both pass 100% as requested. The integrity violation and discrepancy were uncovered by cross-referencing archived timing investigations, integration test assertions, and the raw golden hex vector files.
- The single-channel vs multichannel DSP pipeline, fixed-point sizing matrix, biquad filter stability, UART bringup fixes, and resource budgets are technically exemplary and require no structural modifications.

### 4.4 Conclusion
Milestone M0 documentation is comprehensive and structurally complete, but cannot be approved in its current form due to the inclusion of the fabricated 18-sample latency verification claim and the mismatch with the 12-sample golden hex vectors. The project must update the latency specification and documentation before commencing Milestone M1 RTL generation.

### 4.5 Verification Method
To independently verify these findings:
1. Run `.\venv\Scripts\python.exe -m pytest tests/hardware --ignore=tests/hardware/test_fixed_point_verification.py -v` (Confirm 26 passes).
2. Run `.\venv\Scripts\python.exe -m pytest tests/regression -v` (Confirm 26 passes).
3. Inspect `code/results/fpga_golden/sub01_snr12_c0/summary.json` (line 29) and compare `raw_peaks.txt` vs `peaks.txt` (verify difference is 12, not 18).
4. Run `.\venv\Scripts\python.exe -m pytest tests/integration/test_qrs_timing_correction_rigorous.py -v` (Confirm that 12 samples passes near-zero bias and 18 samples is asserted to be severely early).
5. Inspect `archive/timing_bundles/QRS_TIMING_CORRECTION/QRS_TIMING_INVESTIGATION.md` lines 21–36.

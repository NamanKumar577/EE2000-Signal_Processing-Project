# Tests and Validation Audit Report

**Project:** Multichannel Fetal ECG Extraction & Spartan-7 FPGA Implementation (EE2000 Paper ID: 0008)  
**Date:** 2026-11-03  
**Auditor:** Teamwork Tests & Validation Audit Coordinator  
**Target Scope:** `code/tests/`, root `tests/`, `tools/` (6 subdirectories), `validation/` (15 subdirectories), and historical regression packages.

---

## 1. Executive Summary

The project possesses an extensive, highly rigorous automated verification suite comprising **207 test cases** across 26 test files:
- **`code/tests/`:** 24 test files containing **198 test cases**. All 198 tests **pass 100%** in 2.14s using pytest.
- **Root `tests/`:** 2 test files containing **9 test cases** (6 passed, 3 skipped).
- **Historical Packages:** Embedded regression suites in `FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/10_regression/` (10 test files), `FETAL_ECG_PRE_FPGA_CORRECTED_PACKAGE/10_regression/`, and `FETAL_ECG_PRE_FPGA_VALIDATION_PACKAGE/10_regression_tests/`.
- **Validation & Tools:** 39 Python scripts in `tools/` and 133 evidence files (markdown, csv, scripts) in `validation/`.

The primary issue identified is **path fragmentation and test suite duplication**:
1. Running pytest on root `tests/` fails unless both `code` and the root repo `.` are manually appended to `PYTHONPATH` (`PYTHONPATH=code:.`).
2. Test files have been copied across multiple locations (root `tests/`, `QRS_TIMING_CORRECTION/tests/`, `QRS_RESIDUAL_TIMING_ANALYSIS/tests/`, and package regression folders).

---

## 2. Test Suite Classification in `code/tests/`

All 198 tests in `code/tests/` are currently passing. They fall into six logical tiers:

### Tier 1: Core Unit Tests
- `test_preprocessing.py` (7 tests): Butterworth SOS bandpass filter attenuation, stability, zero-phase response.
- `test_loader.py` (15 tests): PhysioNet WFDB loading, header parsing, subject splitting.
- `test_mixture.py` (9 tests): Synthetic mixture creation, maternal-fetal SNR calibration.
- `test_metrics.py` (8 tests): PhysioNet CinC 2013 sensitivity, PPV, F1-score calculation.
- `test_qrs_detector.py` (9 tests): Pan-Tompkins derivative, squaring, moving window integration, adaptive thresholding.
- `test_qrs_matching.py` (11 tests): Bipartite matching algorithm, $\pm 50$ ms window boundaries.
- `test_qrs_matching_strict.py` (5 tests): Strict non-overlapping pair matching without double-counting.
- `test_method_interface.py` (38 tests): Polymorphic verification across all 4 team members' extractors (`SVD`, `TemplateSubtraction`, `SWTLMS`, `Alternative`).

### Tier 2: Causal Streaming Pipeline Tests (FPGA Pre-RTL)
- `test_causal_pipeline.py` (13 tests): Pure causal float reference, sample-by-sample causality (no lookahead), trailing window covariance update, label-free PCA component selection.
- `test_run_causal_benchmark.py` (7 tests): Multi-record sweep harness, train/val/test evaluation split integrity.

### Tier 3: Bit-Accurate Fixed-Point & Integer Golden Models
- `test_fpga_int_model.py` (13 tests): Integer-only arithmetic, saturation, shift-rounding, hex test-vector generation matching hardware registers.
- `test_bit_accurate_reference.py` (5 tests): Equivalence between floating-point causal pipeline and integer reference model.
- `test_fixed_point_arithmetic_exact.py` (5 tests): 16-bit / 32-bit hardware arithmetic, overflow margin.
- `test_fixed_point_verification.py` (1 test): Full population SQNR audit ($> 30$ dB requirement).
- `test_filter_coefficients_exact.py` (3 tests): Quantized SOS integer coefficients vs theoretical pole-zero placement.

### Tier 4: FHR Post-Processing & Boundary Validation
- `test_fhr.py` (9 tests): Baseline FHR computation, instantaneous RR to BPM conversion.
- `test_fhr_interval_fusion_and_median5.py` (3 tests): Causal 5-beat median filter, ectopic rejection, beat fusion.
- `test_fhr_range_boundaries.py` (3 tests): Strict 50–240 bpm physiological clamping and edge cases.
- `test_calibration_confidence_fallback.py` (3 tests): Spatial calibration confidence thresholding and graceful fallback to suprapubic Lead 27.

### Tier 5: Telemetry & Protocol
- `test_uart_protocol.py` (4 tests): Packet serialization, byte framing, 921,600 baud packet timing, status byte validation.

### Tier 6: Regression & Synthetic End-to-End
- `test_pre_fpga_regression.py` (26 tests): Full-system pre-FPGA regression suite.
- `test_end_to_end_pipeline_synthetic.py` (1 test): Complete end-to-end synthetic pipeline execution from multi-channel input to UART packet output.

---

## 3. Duplicate and Dispersed Test Suites

| Test File | Primary Location | Duplicate Locations | Status / Action |
| :--- | :--- | :--- | :--- |
| `test_qrs_timing_correction_rigorous.py` | `code/tests/` | Root `tests/`, `QRS_TIMING_CORRECTION/tests/` | Consolidate to unified `tests/` |
| `test_residual_timing_analysis.py` | Root `tests/` | `QRS_RESIDUAL_TIMING_ANALYSIS/tests/` | Relocate to unified `tests/` |
| `test_end_to_end_pipeline_synthetic.py` | `code/tests/` | `FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/10_regression/tests/` | Keep canonical in `tests/` |
| `test_fhr_interval_fusion_and_median5.py` | `code/tests/` | `FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/10_regression/tests/` | Keep canonical in `tests/` |
| `test_filter_coefficients_exact.py` | `code/tests/` | `FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/10_regression/tests/` | Keep canonical in `tests/` |
| `test_fixed_point_arithmetic_exact.py` | `code/tests/` | `FETAL_ECG_PRE_FPGA_CORRECTED_PACKAGE/03_fixed_point_correction/tests/` | Keep canonical in `tests/` |
| `test_uart_protocol.py` | `code/tests/` | `FETAL_ECG_PRE_FPGA_CORRECTED_PACKAGE/08_protocol_correction/tests/` | Keep canonical in `tests/` |

---

## 4. Audit of `tools/` and `validation/`

### A. Scripts in `tools/` (39 files)
1. **`tools/final_verification/` (Active Audits):**
   - `run_calibration_audit.py`, `run_fhr_reconciliation_audit.py`, `run_fixed_point_scaling_audit.py`, `run_filter_delay_audit.py`.
   - *Role:* Authoritative verification scripts used for final pre-RTL sign-off.
2. **`tools/improvements/` (Experimental Sweeps):**
   - `run_detector_improvements.py`, `run_fhr_improvements.py`, `run_fixed_point_investigation.py`, `run_spatial_calibration_study.py`, `run_nifea_deep_dive.py`, `run_full_layout_benchmark.py`.
   - *Role:* Algorithmic exploration scripts from Phase 4 and 5.
3. **`tools/pre_fpga/` & `tools/pre_fpga_corrected/` (Package Assemblers & Audits):**
   - `assemble_validation_package.py`, `assemble_corrected_package.py`, `reconcile_qrs_metrics.py`, `audit_calibration_fallback.py`, `generate_filter_spec.py`.
   - *Role:* Historical packaging automation and metric reconciliation tools.
4. **`tools/qrs_timing_correction/`:**
   - `run_residual_timing_investigation.py`, `evaluate_qrs_timing_correction.py`.
5. **Root Tools:**
   - `tools/audit_mtr8.py` (MTR-8 mid-term report audit tool)
   - `tools/clean_anonymity.py` (Author and university anonymization sanitizer)

### B. Validation Artifacts in `validation/` (133 files)
- Contains detailed per-stage markdown audits and generated CSV tables (`ablation/`, `baseline/`, `channels/`, `clinical/`, `detector/`, `extraction/`, `failures/`, `fixed_point/`, `fpga/`, `improvements/`, `pre_fpga/`, `pre_fpga_corrected/`, `streaming/`, `synthetic/`).
- *Role:* Permanent experimental evidence and audit documentation for the project report and IEEE CVF review process.

---

## 5. Recommended Reorganization for Tests & Scripts

To eliminate path issues and provide clean test discovery:

```text
tests/
├── conftest.py                       # Global test fixtures, synthetic generators
├── unit/                             # Fast unit tests
│   ├── test_preprocessing.py
│   ├── test_loader.py
│   ├── test_mixture.py
│   ├── test_metrics.py
│   ├── test_qrs_detector.py
│   ├── test_qrs_matching.py
│   ├── test_fhr.py
│   └── test_method_interface.py
├── integration/                      # Causal pipeline & streaming integration
│   ├── test_causal_pipeline.py
│   ├── test_end_to_end_synthetic.py
│   ├── test_uart_protocol.py
│   └── test_qrs_timing_correction.py
├── hardware/                         # Bit-accurate and FPGA numerical models
│   ├── test_fpga_int_model.py
│   ├── test_bit_accurate_reference.py
│   ├── test_fixed_point_arithmetic.py
│   └── test_filter_coefficients.py
└── regression/                       # Full pre-FPGA regression suites
    └── test_pre_fpga_regression.py

scripts/
├── benchmarks/                       # Execution and benchmark sweeps
│   ├── run_causal_benchmark.py
│   ├── run_benchmark.py
│   └── run_mega_benchmark.py
├── validation/                       # Verification audit runners
│   ├── run_calibration_audit.py
│   ├── run_fhr_reconciliation.py
│   ├── run_fixed_point_scaling.py
│   └── run_filter_delay_audit.py
└── tools/                            # Utility scripts
    ├── audit_mtr8.py
    └── clean_anonymity.py
```

---
*Report compiled autonomously by Teamwork Tests & Validation Auditor.*

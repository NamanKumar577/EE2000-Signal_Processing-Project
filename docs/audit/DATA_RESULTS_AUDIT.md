# Data, Results and Experiments Audit Report

**Project:** Multichannel Fetal ECG Extraction & Spartan-7 FPGA Implementation (EE2000 Paper ID: 0008)  
**Date:** 2026-11-03  
**Auditor:** Teamwork Data & Results Audit Coordinator  
**Target Scope:** `test/` dataset, `code/results/`, `code/visualization/`, `QRS_RESIDUAL_TIMING_ANALYSIS/`, `QRS_TIMING_CORRECTION/`, `report/`, large binary archives (`*.zip`), and transient log files.

---

## 1. Executive Summary

The repository contains approximately **262.9 MB** of tracked files, of which **over 85% (>220 MB)** consists of physiological signal datasets, benchmark CSV tables, high-resolution scientific plots, compiled PDF reports, and zipped distribution archives:
- **`test/` Dataset Directory (97.38 MB):** 52 files representing 5 complete PhysioNet FECGSYNDB multi-channel ECG recordings (`test1` through `test5`).
- **`report/` Directory (60.78 MB):** IEEE CVF conference submission files, compiled PDFs (`mtr-8.pdf`), and 37 publication figures.
- **Root Binary Archives & PDFs (35.73 MB):** `mtr-8.zip` (25.7 MB), package archives, redundant PDFs.
- **`code/results/` & `code/visualization/` (24.08 MB):** Empirical benchmark tables and 46 generated signal waveform plots.
- **Deep-Dive Timing Investigation Bundles (4.85 MB):** Residual timing CSVs and 7 high-resolution diagnostic visualizations.

---

## 2. Dataset Characterization: Clarification of `test/`

A critical finding of this audit is that **`test/` is NOT a software test directory**:
- It contains **raw multi-channel physiological abdominal ECG datasets** in standard PhysioNet WFDB format:
  - `test1/` to `test5/`: 5 separate subject recordings (records `test01` through `test20` variants).
  - Each recording includes:
    - `.hea` (Header file): Sampling frequency $f_s = 250\,$Hz, 34 biopotential channels (abdominal + direct reference), channel gains, ADC resolution.
    - `.dat` (Binary signal data): 16-bit signed integer multiplexed waveforms spanning 75,000 samples per channel (5 minutes duration).
    - `.qrs` (Gold-standard annotation file): Binary reference beat locations for fetal R-peaks.
- Having this directory named `test/` at the repository root causes immediate confusion with software test directories (`tests/` and `code/tests/`).
- **Recommendation:** Relocate `test/` to `data/fecgsyndb/` or `data/raw/`.

---

## 3. Experimental Benchmark Results and Data Metrics

The repository houses extensive empirical evidence across multiple phases:

### A. `code/results/` (79 files, 24.08 MB)
- **`tc1_svd_results.csv` through `tc5_results.csv`:** Comprehensive Test Case matrix (TC1–TC5) evaluating SNR degradation ($-14\,$dB to $0\,$dB), maternal-fetal overlap, and high noise scenarios.
- **`benchmark_matrix_summary.csv`:** Population-wide cross-sectional results across all 250 records.
- **`population_snr_distribution.csv` & `fhr_error_distribution.csv`:** Statistical distributions supporting conference paper Section 4.
- **`fixed_point_sqnr_results.csv`:** Signal-to-Quantization-Noise Ratio ($> 30\,$dB SQNR validation).

### B. `validation/` Per-Stage Evidence (57 CSV files)
- Empirical verification tables corresponding to every subsystem (ablation studies, lead selection topography, streaming latency, and synthetic validation).

### C. Timing Correction Investigations
- `QRS_RESIDUAL_TIMING_ANALYSIS/PER_RECORD_TIMING_COMPARISON.csv`: 250-record timing error profile before and after group-delay compensation.
- `QRS_TIMING_CORRECTION/QRS_TIMING_RESULTS.csv`: Microsecond-accurate timestamp alignment evidence.

---

## 4. Visual Artifacts and Diagnostic Plots

The project contains high-quality scientific figures that are critical deliverables for the paper and FPGA hardware reviews:

1. **`report/mid_term/` (37 PNG figures):**
   - Architectural block diagrams, Spartan-7 DSP48E1 utilization maps, 34-lead suprapubic heatmaps, maternal template subtraction waveforms, and FHR Bland-Altman agreement plots.
2. **`code/visualization/` (46 PNG figures):**
   - Intermediate signal processing stages: raw abdominal mixture, bandpass SOS output, second principal component beamformer output, Pan-Tompkins squared energy envelope, and detected fetal peaks.
3. **`QRS_RESIDUAL_TIMING_ANALYSIS/QRS_TIMING_VISUALIZATIONS/` (7 PNG figures, 4.72 MB):**
   - Diagnostic residual timing histograms and scatter plots across noise conditions.

---

## 5. Identification of Redundant, Disposable, and Archive Candidates

| Item / Path | Size | Nature | Recommended Action |
| :--- | :--- | :--- | :--- |
| `mtr-8.zip` (Root) | **25.70 MB** | Redundant archive duplicate | Move to `archive/submissions/` (duplicates `report/mtr-8.zip`) |
| `previous_package_extracted/` | **0.90 MB** | 100% duplicate of `FETAL_ECG_PRE_FPGA_VALIDATION_PACKAGE/` | Move to `archive/` or remove in final cleanup |
| `FETAL_ECG_PRE_FPGA_VALIDATION_PACKAGE.zip` | 0.25 MB | Zipped package v1 | Move to `archive/packages/` |
| `FETAL_ECG_PRE_FPGA_CORRECTED_PACKAGE.zip` | 0.22 MB | Zipped package v2 | Move to `archive/packages/` |
| `FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE.zip` | 0.24 MB | Zipped package v3 | Move to `archive/packages/` |
| `mtr8_corrected.pdf` (Root) | 4.20 MB | Redundant PDF duplicate | Move to `archive/` (identical to `mtr-8.pdf`) |
| `project.pdf` & `PPR-8.pdf` (Root) | 0.61 MB | Preliminary project docs | Relocate to `docs/papers/` |
| `audit_before.txt` & `audit_after.txt` | 0.01 MB | Transient terminal audit logs | Move to `docs/archive/logs/` |
| `clean_extraction_test.log` | 0.00 MB | Transient execution log | Move to `docs/archive/logs/` |

---

## 6. Proposed Reorganization for Data, Results, and Artifacts

```text
data/
└── fecgsyndb/                        # Relocated from test/ (52 files, 97.4 MB)
    ├── test1/                        # WFDB records (.hea, .dat, .qrs)
    ├── test2/
    ├── test3/
    ├── test4/
    └── test5/

results/
├── benchmarks/                       # Consolidated benchmark CSV metrics
│   ├── tc1_to_tc5_matrices/
│   ├── population_summary/
│   └── timing_analysis/
└── figures/                          # Consolidated generated visual artifacts
    ├── waveforms/                    # Signal processing stage plots (from code/visualization/)
    └── timing_diagnostics/           # Plots from QRS_TIMING_VISUALIZATIONS/

archive/
├── packages/                         # Historical package archives (.zip)
├── submissions/                      # Historical mtr-8.zip
└── logs/                             # Historical execution logs (audit_*.txt, *.log)
```

---
*Report compiled autonomously by Teamwork Data & Results Auditor.*

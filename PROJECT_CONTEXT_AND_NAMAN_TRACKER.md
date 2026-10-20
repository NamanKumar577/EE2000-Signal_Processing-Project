# Fetal ECG Extraction & FPGA Project — Context & Naman's Master Tracker

**Last Updated:** 2026-10-20  
**Project:** Non-Invasive Fetal ECG Extraction from Abdominal Mixtures and Fetal QRS/FHR Detection on FPGA  
**Course / Context:** EE2000 Signal Processing Project (PPR-8 Specification)  
**Target Hardware:** Xilinx Spartan-7 FPGA  
**Member:** Naman (Integration Lead & SVD Extraction Owner)  
**Overall Status:** **Phase 1 (Complete) | Phase 2 (Complete) | Phase 3 (Ready for Teammate Integration)**

---

## 1. Project Overview & Combined Goals

### 1.1 The Clinical & Engineering Problem
Non-invasive fetal electrocardiography (NIFECG) records electrical cardiac activity through electrodes placed on the mother's abdomen. The composite abdominal signal is dominated by the maternal ECG ($MECG$), which has up to 10× greater amplitude than the fetal ECG ($FECG$), plus electromyographic (EMG) noise, respiration baseline wander, motion artifacts, and power-line interference.

$$\text{Signal Model:}\quad AECG(t) = MECG(t) + FECG(t) + \text{Noise}(t)$$

### 1.2 Primary Objective
The team goal is to implement, rigorously evaluate, and compare four distinct fetal ECG extraction approaches on a standardized test matrix under the exact same data, test cases, preprocessing rules, and evaluation metrics:
$$\boxed{AECG \longrightarrow \text{Preprocessing} \longrightarrow \text{Maternal Suppression / Extraction} \longrightarrow \text{Fetal QRS Detection} \longrightarrow \text{FHR Estimation}}$$

The ultimate goal is to select the most robust, high-performing algorithm and assess its feasibility for fixed-point porting to a **Xilinx Spartan-7 FPGA**.

### 1.3 Core Evaluation Rules
- **No Oracle Peeking:** The clean fetal ground truth (`fecg1`) and reference annotations must **never** be supplied to any extraction algorithm; they are strictly reserved for post-extraction evaluation.
- **Identical Inputs:** All methods receive the exact same permitted abdominal mixture.
- **Frozen Preprocessing & Detection:** Preprocessing (0.5–40 Hz bandpass) and QRS matching tolerance ($\pm 50\text{ ms}$) are frozen across all methods.

---

## 2. Team Division of Responsibilities

| Team Member | Primary Extraction Algorithm | Shared System Responsibility | Core Deliverables |
|---|---|---|---|
| **Naman** | **SVD Extraction (3 Variants)** | **Integration Lead & Architecture** | `code/src/methods/svd.py`, `BaseExtractor` interface, `run_benchmark.py`, project skeleton, test runner |
| **Anshu** | Maternal Template Subtraction | Common Fetal QRS Detector | `code/src/methods/template_subtraction.py`, `code/src/qrs_detector.py` (PPR-8 bandpass-square-integrate-threshold) |
| **Astitva** | SWT + LMS + SSNF Hybrid | Shared Preprocessing Baseline | `code/src/methods/swt_lms_ssnf.py`, `code/src/preprocessing.py` (0.5–40 Hz filter, baseline wander removal) |
| **Vivek** | Alternative Method (ICA / Single-channel) | Data Audit, Mixture Builder, FHR & Metrics | `code/src/methods/alternative.py`, `code/src/data_loader.py`, `code/src/mixture.py`, `code/src/fhr.py`, `code/src/evaluation.py` |

---

## 3. Naman's Specific Roles & Workstreams

Naman has two primary workstreams:

### Workstream A: Primary Extraction Method — SVD (Kanjilal et al., 1997)
Based on: *Fetal ECG Extraction from Single-Channel Maternal ECG Using Singular Value Decomposition* (IEEE TBME 1997).
- **Variant 1 (Fixed-period / Linear padding):** Rows of matrix $A$ are consecutive maternal cycles aligned by R-peaks, padded/truncated to modal period $n$. Dominant dyad $u_1 \sigma_1 v_1^T$ is subtracted. Residual is folded into matrix $B$ by fetal cycles to extract FECG.
- **Variant 2 (SVR Spectrum & Time-Resampling):** Uses the Singular Value Ratio (SVR) spectrum $\sigma_1^2 / \sigma_2^2$ across candidate period lengths (50–200 samples) to find the dominant period $n$. Resamples each beat segment to length $n$ before SVD, then applies inverse time-resampling back to original durations.
- **Variant 3 (Moving-Window Block-Adaptive SVD):** Slides an $m_1 \times n$ sub-matrix window row-by-row over matrix $A$. Computes SVD per window position to adapt to dynamic morphological changes over time.

### Workstream B: Integration Lead & Common Pipeline Architect
- Establish and enforce the `BaseExtractor` contract.
- Maintain project modular structure inside [`code/`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code).
- Connect the end-to-end pipeline: Loader $\rightarrow$ Preprocess $\rightarrow$ Extract $\rightarrow$ QRS Detect $\rightarrow$ FHR $\rightarrow$ Evaluate.
- Build the unified benchmark CLI runner: [`code/src/run_benchmark.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/run_benchmark.py).
- Guarantee reproducibility and manage automated test suites.

---

## 4. Test Matrix (FECGSYNDB)

All 5 test cases are verified and present in [`test/`](file:///home/namak/projects/EE2000-Signal_Processing-Project/test):
- **Sampling Rate:** $250\text{ Hz}$ (verified from `.hea` headers)
- **Duration:** 75,000 samples ($5\text{ minutes}$)
- **Channels:** 34 physical channels (Channel 0 selected for single-channel evaluation)

| Test ID | Folder | SNR | Condition | Purpose |
|---|---|---:|---|---|
| **TC1** | `test/test1` | $12\text{ dB}$ | `c0` | Baseline check; easy initial extraction |
| **TC2** | `test/test2` | $6\text{ dB}$ | `c0` | Moderate noise robustness |
| **TC3** | `test/test3` | $0\text{ dB}$ | `c0` | High noise; signal/noise power ratio 1:1 |
| **TC4** | `test/test4` | $6\text{ dB}$ | `c1` | Maternal/fetal movement condition |
| **TC5** | `test/test5` | $6\text{ dB}$ | `c4` | Fetal ectopic beat condition |

---

## 5. Naman's Task Progress & Status Tracker

### Phase 1: Architecture, Interfaces & Skeleton Setup (Completed ✅)
- [x] **Repository Skeleton:** Created standard folder structure inside `code/` (`src/`, `configs/`, `tests/`, `results/`).
- [x] **Test Registry Config:** Created [`code/configs/tests.yaml`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/configs/tests.yaml) mapping TC1–TC5 paths, SNR, and metadata.
- [x] **Preprocessing Config:** Created [`code/configs/preprocessing.yaml`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/configs/preprocessing.yaml) with frozen 0.5–40 Hz filter settings.
- [x] **Base Method Contract:** Implemented [`BaseExtractor`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/methods/base.py) with strict input/output validation.
- [x] **Pipeline Modules Implemented:**
  - [`data_loader.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/data_loader.py): WFDB record & annotation parser.
  - [`mixture.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/mixture.py): $AECG = MECG + FECG + Noise_1 + Noise_2$ builder & SNR checker.
  - [`preprocessing.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/preprocessing.py): Butterworth baseline wander & bandpass filtering.
  - [`qrs_detector.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/qrs_detector.py): Bandpass-square-integrate adaptive threshold detector.
  - [`fhr.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/fhr.py): Instantaneous FHR calculation, implausible interval masking, and MAE/RMSE comparison.
  - [`evaluation.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/evaluation.py): Greedy nearest-neighbour matching ($\pm 50\text{ ms}$), TP/FP/FN, Sensitivity, PPV, F1, RMSE, SNR improvement.
- [x] **Method Scaffolds:** Created SVD classes (`SVDExtractorV1`, `SVDExtractorV2`, `SVDExtractorV3`) and teammate scaffolds (`template_subtraction.py`, `swt_lms_ssnf.py`, `alternative.py`).
- [x] **Automated Test Suite:** Created 6 test suites with **88 unit tests** in [`code/tests/`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/tests). All **88/88 passed**.
- [x] **Unified Benchmark Runner:** Implemented [`code/src/run_benchmark.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/run_benchmark.py) with CLI flags (`--tc`, `--method`, `--dry-run`).
- [x] **End-to-End Smoke Test:** Successfully executed TC1 with SVD Variant 1, generating [`metrics.csv`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/metrics.csv), [`run_metadata.json`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/run_metadata.json), and [`TC1_svd_v1.png`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots/TC1_svd_v1.png).

---

### Phase 2: SVD Extraction Algorithm Implementation (Completed ✅)
- [x] **Maternal Beat Segmentation & Peak Alignment:** Implemented robust percentile-based scaling (`np.percentile(abs(centered), 98)`) to reject outlier boundary artifacts.
- [x] **Boundary Extrapolation:** Added boundary edge extrapolation in `_matrix_to_signal()` to eliminate edge step discontinuities at recording borders.
- [x] **SVD Variant 1 (Fixed Period):** Implemented linear interpolation to modal period $n$ and fetal residual matrix $B$ SVD decomposition.
- [x] **SVD Variant 2 (SVR Spectrum & Time-Resampling):** Implemented full SVR spectrum calculation ($\sigma_1^2 / \sigma_2^2$) across candidate cycle lengths (50–200 samples) and dynamic time-resampling.
- [x] **SVD Variant 3 (Moving-Window SVD):** Implemented sliding-window block-adaptive SVD ($m_1 \times n$) over matrix $A$ adapting to beat morphology changes over time.
- [x] **TC1 Benchmarking:** Executed all three variants on TC1 with full metrics recorded in [`code/results/metrics.csv`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/metrics.csv) and diagnostic plots in [`code/results/plots/`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots).

#### TC1 Benchmark Results Summary:
| Method / Variant | Runtime | Det. Beats | TP | FP | FN | Precision (PPV) | Sensitivity (Recall) | F1-Score | Waveform RMSE | Diagnostic Plot |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **SVD Variant 1** (Fixed period / linear padding) | **0.351 s** | 287 | 81 | 206 | 635 | 28.2% | 11.3% | **0.1615** | 0.1016 | [`TC1_svd_v1.png`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots/TC1_svd_v1.png) |
| **SVD Variant 2** (SVR spectrum + dynamic resampling) | **5.029 s** | 300 | 83 | 217 | 633 | 27.7% | 11.6% | **0.1634** | 0.1024 | [`TC1_svd_v2.png`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots/TC1_svd_v2.png) |
| **SVD Variant 3** (Moving-window block-adaptive) | **0.215 s** | 275 | 71 | 204 | 645 | 25.8% | 9.9% | **0.1433** | 0.0957 | [`TC1_svd_v3.png`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots/TC1_svd_v3.png) |

---

### Phase 3: Teammate Integration & Pipeline Coordination (Current Focus 🚀)
- [ ] Coordinate with **Vivek** on mixture SNR calibration and header annotation conventions.
- [ ] Integrate **Anshu's** Template Subtraction implementation in [`code/src/methods/template_subtraction.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/methods/template_subtraction.py).
- [ ] Integrate **Astitva's** SWT-LMS-SSNF implementation in [`code/src/methods/swt_lms_ssnf.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/methods/swt_lms_ssnf.py).
- [ ] Integrate **Vivek's** Alternative method in [`code/src/methods/alternative.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/methods/alternative.py).
- [ ] Run multi-method comparison smoke test on TC1 across all 4 implemented algorithms.

---

### Phase 4: Full Benchmark Matrix Execution (TC1–TC5)
- [ ] Execute all implemented methods across all test cases (TC1, TC2, TC3, TC4, TC5).
- [ ] Generate standard diagnostic plots for each run in [`code/results/plots/`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots).
- [ ] Analyze failure modes:
  - High noise degradation ($0\text{ dB}$ TC3).
  - Maternal/fetal movement robustness ($c1$ TC4).
  - Ectopic beat handling ($c4$ TC5).
  - Overlapping maternal and fetal QRS complexes.
- [ ] Compile final comparative metrics table into [`code/results/metrics.csv`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/metrics.csv).

---

### Phase 5: Spartan-7 FPGA Feasibility & Hardware Profiling
- [ ] Profile runtime, memory footprint, and matrix dimensions for SVD variants vs. adaptive filtering.
- [ ] Analyze hardware arithmetic complexity: $O(m n^2)$ SVD decomposition vs. LMS FIR filtering.
- [ ] Evaluate fixed-point word length requirements (e.g., Q15 / Q31 representation) and dynamic range limitations.
- [ ] Prepare FPGA suitability summary and trade-off comparison table for the final report.

---

## 6. Key File & Directory Map

```text
EE2000-Signal_Processing-Project/
├── PROJECT_CONTEXT_AND_NAMAN_TRACKER.md # (This file) Master context & task tracker
├── fecg_team_work_plan.md               # Team agreement & work plan
├── Fetal_ECG_Project_Context_and_Plan.md# Project background & hardware roadmap
├── papers/                              # Primary research literature
│   └── Fetal_ECG_extraction_..._svd.pdf # Kanjilal et al. (1997) SVD reference paper
├── test/                                # Verified dataset folders (test1 - test5)
└── code/                                # All executable source code & configs
    ├── configs/                         # YAML configurations (tests.yaml, preprocessing.yaml)
    ├── src/                             # Source modules (loader, mixture, filters, QRS, FHR, evaluation)
    │   ├── run_benchmark.py             # Main CLI execution runner
    │   └── methods/                     # Extractor classes (BaseExtractor, SVD, etc.)
    │       ├── base.py                  # Standard BaseExtractor interface
    │       ├── svd.py                   # SVD Variants 1, 2, 3 (Naman)
    │       ├── template_subtraction.py  # Scaffold for Anshu
    │       ├── swt_lms_ssnf.py          # Scaffold for Astitva
    │       └── alternative.py           # Scaffold for Vivek
    ├── tests/                           # Pytest unit tests (88/88 passing)
    └── results/                         # Generated CSV metrics, metadata JSON, and diagnostic plots
        ├── metrics.csv                  # Benchmark metrics table
        ├── run_metadata.json            # Execution metadata
        └── plots/                       # Waveform & peak overlay PNGs (TC1_svd_v1/v2/v3)
```

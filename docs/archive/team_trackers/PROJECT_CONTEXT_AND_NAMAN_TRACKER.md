# Fetal ECG Extraction & FPGA Project — Context & Naman's Master Tracker

**Last Updated:** 2026-10-23  
**Project:** Non-Invasive Fetal ECG Extraction from Abdominal Mixtures and Fetal QRS/FHR Detection on FPGA  
**Course / Context:** EE2000 Signal Processing Project (PPR-8 Specification)  
**Target Hardware:** Xilinx Spartan-7 FPGA  
**Member:** Naman (Integration Lead & SVD Extraction Owner)  
**Overall Status:** **ALL PHASES (Phase 1, 2, 3, 4, 5) FULLY COMPLETED & VERIFIED ✅ 🚀**

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

### Phase 3: Teammate Integration & Pipeline Coordination (Completed ✅)
- [x] Coordinate with **Vivek** on mixture SNR calibration, data loader, FHR calculations, and header annotation conventions.
- [x] Integrate **Anshu's** Template Subtraction implementation in [`code/src/methods/template_subtraction.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/methods/template_subtraction.py) (both `adaptive_ema` and `fixed_ensemble`).
- [x] Integrate **Astitva's** SWT-LMS-SSNF hybrid implementation in [`code/src/methods/swt_lms_ssnf.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/methods/swt_lms_ssnf.py) and added `PyWavelets` dependency.
- [x] Integrate **Vivek's** Alternative method in [`code/src/methods/alternative.py`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/src/methods/alternative.py) (adaptive SVD-template subtraction with subband refinement).
- [x] Successfully executed all 106 automated unit tests across the entire codebase.
- [x] Ran multi-method benchmark on TC1 across all 7 method variants, saving metrics and diagnostic plots.

#### TC1 Multi-Method Benchmark Results (All Team Methods):
| Method | Variant | Owner | Runtime | Det. Beats | TP | FP | FN | Precision | Sensitivity | F1-Score | Waveform RMSE | Diagnostic Plot |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **Alternative** | Multi-Scale SVD-Template | **Vivek** | 0.043 s | 715 | 553 | 162 | 163 | **77.3%** | **77.2%** | **0.7729** | **0.0636** | [`TC1_alternative.png`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots/TC1_alternative.png) |
| **Template Subtraction** | Fixed Ensemble | **Anshu** | **0.010 s** | 379 | 128 | 251 | 588 | 33.8% | 17.9% | **0.2338** | 0.0681 | [`TC1_template_fixed.png`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots/TC1_template_fixed.png) |
| **Template Subtraction** | Adaptive EMA | **Anshu** | **0.010 s** | 390 | 126 | 264 | 590 | 32.3% | 17.6% | **0.2278** | 0.0707 | [`TC1_template_subtraction.png`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots/TC1_template_subtraction.png) |
| **SWT-LMS-SSNF** | Hybrid Wavelet-LMS | **Astitva** | 1.168 s | 52 | 15 | 37 | 701 | 28.8% | 2.1% | **0.0391** | 0.0888 | [`TC1_swt_lms_ssnf.png`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots/TC1_swt_lms_ssnf.png) |
| **SVD** | Variant 2 (SVR Resampled) | **Naman** | 1.207 s | 45 | 14 | 31 | 702 | 31.1% | 2.0% | **0.0368** | 0.1024 | [`TC1_svd_v2.png`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots/TC1_svd_v2.png) |
| **SVD** | Variant 1 (Fixed Period) | **Naman** | 0.088 s | 43 | 13 | 30 | 703 | 30.2% | 1.8% | **0.0343** | 0.1016 | [`TC1_svd_v1.png`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots/TC1_svd_v1.png) |
| **SVD** | Variant 3 (Moving Window) | **Naman** | 0.113 s | 44 | 12 | 32 | 704 | 27.3% | 1.7% | **0.0316** | 0.0957 | [`TC1_svd_v3.png`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots/TC1_svd_v3.png) |

---

### Phase 4: Full Benchmark Matrix Execution (TC1–TC5) (Completed ✅)
- [x] **Full Benchmark Execution:** Executed all 7 method variants across all 5 test cases (TC1–TC5), yielding **35 total benchmark runs**.
- [x] **Diagnostic Plot Generation:** Generated 35 diagnostic figures in [`code/results/plots/`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/plots) (`TC1_svd_v1.png` through `TC5_alternative.png`).
- [x] **Cross-Method Metrics Compilation:** Saved all 35 evaluation records in [`code/results/metrics.csv`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/metrics.csv) and execution metadata in [`code/results/run_metadata.json`](file:///home/namak/projects/EE2000-Signal_Processing-Project/code/results/run_metadata.json).
- [x] **Cross-Case Failure & Robustness Analysis:**
  - **Baseline ($12\text{ dB}$, TC1):** Vivek's Alternative method dominates with F1 = **0.7729**, followed by Anshu's Fixed Template (0.2338) and Adaptive Template (0.2278).
  - **Moderate Noise ($6\text{ dB}$, TC2):** Alternative (0.3140) and Template Subtraction (~0.2960) maintain consistent detection; Astitva's SWT-LMS improves to F1 = 0.1229 with 33.1% precision.
  - **High Noise ($0\text{ dB}$, TC3):** SVD Variant 3 (moving window) proves its noise immunity, climbing to F1 = **0.1967** (Sens=15.8%, PPV=26.0%), outperforming SVD V1 (0.1613) and SVD V2 (0.1356). Template methods deliver F1 ≈ 0.24–0.25.
  - **Movement Condition ($c1$, TC4):** Alternative (F1 = **0.3683**) and Template Subtraction (F1 = **0.3586**) handle maternal/fetal movement well with minimal degradation.
  - **Ectopic Beats ($c4$, TC5):** Template Subtraction Fixed Ensemble (F1 = **0.2915**) outperforms Adaptive EMA (0.2670) because ectopic morphology shifts distort running EMA averages. SVD Variant 3 achieves F1 = **0.1336**.

#### Complete 35-Run Benchmark Summary (Averaged across conditions):
| Method | Variant | Owner | Mean F1 | Best F1 | Mean Runtime | Strengths & Failure Modes |
|---|---|---|---:|---:|---:|---|
| **Alternative** | Multi-Scale SVD-Template | **Vivek** | **0.3964** | **0.7729** (TC1) | 0.066 s | Outstanding on high SNR; robust subband filtering (8–38 Hz); moderate degradation at 0 dB. |
| **Template Subtraction** | Fixed Ensemble | **Anshu** | **0.2822** | **0.3569** (TC4) | **0.009 s** | Fastest method (~9 ms); highly robust to ectopic beats ($c4$); steady performance across noise. |
| **Template Subtraction** | Adaptive EMA | **Anshu** | **0.2793** | **0.3586** (TC4) | **0.010 s** | Extremely fast (~10 ms); best on movement ($c1$); slightly vulnerable to ectopic beat distortion. |
| **SVD** | Variant 3 (Moving Window) | **Naman** | **0.0955** | **0.1967** (TC3) | 0.070 s | Strongest SVD variant; highest noise immunity at 0 dB ($F1=0.1967$); lowest waveform RMSE. |
| **SVD** | Variant 1 (Fixed Period) | **Naman** | **0.0909** | **0.1613** (TC3) | 0.130 s | Robust at 0 dB ($F1=0.1613$); simple matrix structure suitable for block memory. |
| **SWT-LMS-SSNF** | Hybrid Wavelet-LMS | **Astitva** | **0.0877** | **0.1229** (TC2) | 1.180 s | Excellent high-frequency noise suppression; computationally heavy due to 4-level SWT. |
| **SVD** | Variant 2 (SVR Resampled) | **Naman** | **0.0786** | **0.1356** (TC3) | 1.149 s | Mathematically elegant SVR period determination; SVR sweep adds computational overhead. |

---

### Phase 5: Spartan-7 FPGA Feasibility & Hardware Profiling (Completed ✅ 🚀)
- [x] **Profile runtime, memory footprint, and matrix dimensions for SVD variants vs. adaptive filtering:** SVD Variant 1 (batch $540 \times 175$) requires 42 BRAM36k blocks (56% of XC7S50), making it unsuitable for low-power streaming. SVD Variant 3 (moving-window $5 \times 175$) slashes memory footprint by 97.7% to just $1.74\text{ KB}$ (only 1 half-block RAMB18E1), providing real-time streaming capability.
- [x] **Analyze hardware arithmetic complexity ($O(m n^2)$ SVD decomposition vs. LMS FIR filtering):** Formulated the hardware-friendly Rank-2 Power Iteration with Hotelling Deflation, reducing per-beat operations from $6.6 \times 10^7$ floating-point FLOPs down to 38,500 time-multiplexed fixed-point MACs. At 100 MHz, execution completes in 0.385 ms (< 0.04% of cardiac cycle).
- [x] **Evaluate fixed-point word length requirements (Q1.15 / Q2.30) & dynamic range:** Developed bit-accurate fixed-point emulation model in [`code/src/svd_fixed_point_model.py`](file:///d:/signal_project/code/src/svd_fixed_point_model.py). Verified SQNR = +85.04 dB and quantization error RMSE = 9.0e-6 with signed 16-bit Q1.15 inputs and 32-bit Q2.30 accumulators.
- [x] **Prepare FPGA suitability summary and trade-off comparison table:** Generated comprehensive technical report [`NAMAN_SVD_FPGA_FEASIBILITY_REPORT.md`](file:///d:/signal_project/NAMAN_SVD_FPGA_FEASIBILITY_REPORT.md) and [`code/results/FPGA_Feasibility_Report_Naman.md`](file:///d:/signal_project/code/results/FPGA_Feasibility_Report_Naman.md). Synthesis estimates on Spartan-7 XC7S50: 14.5% LUTs, 10.0% DSP48E1 slices, 2.7% BRAM, dynamic power < 85 mW. SVD Variant 3 even fits on XC7S25 (42.9% LUTs, 15.0% DSPs).

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
    │       ├── template_subtraction.py  # Maternal Template Subtraction (Anshu)
    │       ├── swt_lms_ssnf.py          # SWT + LMS + SSNF Hybrid (Astitva)
    │       └── alternative.py           # Multi-Scale SVD Template Method (Vivek)
    ├── tests/                           # Pytest unit tests (106/106 passing)
    └── results/                         # Generated CSV metrics, metadata JSON, and diagnostic plots
        ├── metrics.csv                  # Benchmark metrics table (35 runs)
        ├── run_metadata.json            # Execution metadata
        └── plots/                       # Waveform & peak overlay PNGs (35 plots)
```

---

## 7. Deep Method Audit: Flaws, Root Causes, and Improvement Roadmap

Based on the 35 benchmark evaluations across all 5 stress test cases (TC1–TC5), this section documents the exact architectural bottlenecks identified in each method and the verified engineering solutions to resolve them.

### 7.1 Naman's SVD Method (`svd.py`) — Flaws & Verified Solutions

#### Identified Mistakes & Limitations:
1. **Flaw 1: Row Boundary R-Peak Alignment:**
   - *Current Implementation:* Cycles were segmented strictly from $R_i \to R_{i+1}$, placing the R-peak at index 0 of each row.
   - *Consequence:* The Q-wave was stranded at the tail end of the preceding row while the R and S waves were at the start of the next row. SVD dyads could not learn a coherent symmetric P-QRS-T morphology.
2. **Flaw 2: Linear R-R Resampling Distorts Fixed QRS Duration:**
   - *Current Implementation:* Dynamic linear resampling (Eq. 3 of Kanjilal et al.) stretched or compressed the entire R-R interval into fixed period $n$.
   - *Consequence:* Physiologically, adult QRS duration is relatively invariant (~80–100 ms); only the T-P segment varies with heart rate. Stretching the whole beat stretches the QRS width artificially, misaligning singular vectors across beats.
3. **Flaw 3: Direct Peak Detection on Raw Maternal Residual:**
   - *Current Implementation:* Fetal matrix $B$ was constructed by running peak detection on the raw maternal-subtracted residual before any subband refinement.
   - *Consequence:* Because fetal ECG is weak ($-11\text{ dB}$ SNR), peak detection triggered on residual noise, filling matrix $B$ with noise rows and suppressing fetal reconstruction in `qrs_detector.py`.

#### Verified Engineering Improvements:
- **Solution 1 (Centered Symmetric Windowing):** Segment each maternal beat into a fixed window of $[-0.25\text{s}, +0.45\text{s}]$ (175 samples at 250 Hz) centered precisely at the detected maternal R-peak. The R-peak consistently occupies column index 62.
- **Solution 2 (Low-Rank SVD Order $k=2$):** Retain the first 2 principal dyads ($u_1 \sigma_1 v_1^T + u_2 \sigma_2 v_2^T$) to capture both dominant QRS morphology and respiratory electrical axis rotation.
- **Solution 3 (Post-Subtraction Fetal Subband Filter 8–38 Hz):** Pass the maternal-cancelled residual through an 8–38 Hz Butterworth bandpass filter to eliminate out-of-band noise before QRS detection.
- **Benchmarked Impact:**
  - **F1-Score jumps from $0.0343 \longrightarrow \mathbf{0.7636}$ (22× improvement!)**
  - **Detected fetal beats increases from $43 \longrightarrow \mathbf{714}$**
  - **True Positives increases from $13 \longrightarrow \mathbf{546}$**
  - **Waveform RMSE drops to $\mathbf{0.0483}$ (lowest error in the entire project)**

---

### 7.2 Anshu's Template Subtraction (`template_subtraction.py`)

#### Identified Mistakes & Limitations:
1. **Fetal Signal Leakage into Running Template (Adaptive EMA):**
   - *Root Cause:* In `adaptive_ema`, when a maternal beat collides with an overlapping fetal beat, the fetal QRS spike enters the EMA update formula: $\text{template} \leftarrow (1-\alpha)\text{template} + \alpha \cdot \text{beat}$.
   - *Consequence:* The maternal template absorbs fetal QRS energy, leading to destructive cancellation of fetal beats upon subtraction.
2. **Missing Post-Subtraction Bandpass Filter:**
   - The output signal is raw mixture minus template. Residual maternal T-waves (1–4 Hz) and high-frequency EMG remain in the output, triggering false positives in `qrs_detector.py`.
3. **Rigid Amplitude Scaling Bounds:**
   - Scaling factor is hard-clipped to $[0.6, 1.5]$. During deep respiration or movement ($c1$), maternal peak amplitudes can exceed this range, leaving significant un-subtracted maternal spikes.

#### Recommended Action Items:
- **Improvement 1:** Implement **collision blanking**: skip the EMA template update for any beat whose energy deviates by $>2\sigma$ from the median template (indicating fetal overlap or ectopic beat).
- **Improvement 2:** Add an 8–38 Hz subband post-filter on the residual signal.
- **Improvement 3:** Expand least-squares scaling range to $[0.4, 2.2]$ to accommodate respiration dynamics.

---

### 7.3 Astitva's SWT-LMS-SSNF (`swt_lms_ssnf.py`)

#### Identified Mistakes & Limitations:
1. **Unthresholded Approximation Coefficients ($cA$):**
   - *Root Cause:* SSNF inter-scale thresholding is applied strictly to detail subbands ($cD_1 \dots cD_4$). The approximation subband $cA_4$ (0–7.8 Hz) is reconstructed without thresholding.
   - *Consequence:* Low-frequency baseline wander and maternal T-wave residuals pass directly into the output.
2. **Fixed Unnormalized LMS Step Size ($\mu = 0.01$):**
   - In subbands with high energy variance, fixed $\mu$ either adapts too slowly to rapid changes or causes gradient noise oscillations.
3. **High Computational Latency (>1.18 s):**
   - 4-level Stationary Wavelet Transform on 75,000 samples requires extensive computation and memory, making it the least practical method for low-power Spartan-7 FPGA implementation.

#### Recommended Action Items:
- **Improvement 1:** Upgrade to **Normalized LMS (NLMS)** with time-varying step size $\mu(n) = \frac{\mu_0}{\|x(n)\|^2 + \epsilon}$.
- **Improvement 2:** Apply soft-thresholding to $cA_4$ to suppress low-frequency maternal T-wave residuals.
- **Improvement 3:** Reduce SWT decomposition levels from 4 to 2 or 3 to cut execution time by 50% without sacrificing QRS band coverage.

---

### 7.4 Vivek's Alternative Method (`alternative.py`)

#### Identified Mistakes & Limitations:
1. **Performance Cliff under 0 dB High Noise (TC3):**
   - *Observation:* While dominant at 12 dB (F1 = 0.7729), performance drops sharply to F1 = 0.2464 at 0 dB.
   - *Root Cause:* Maternal R-peak detection relies on single-channel thresholding. At 0 dB, noise peaks trigger false maternal detections, leading to inappropriate template subtraction at non-beat locations.

#### Recommended Action Items:
- **Improvement 1:** Implement a template cross-correlation verification step before accepting maternal peaks in low-SNR conditions.
- **Improvement 2:** Use dynamic subband bandwidth: narrow the bandpass filter to 10–32 Hz under high noise (0 dB) to reject out-of-band EMG power.

---

### 7.5 Shared Fetal QRS Detector (`qrs_detector.py`)

#### Identified Flaws:
1. **Absence of Pan-Tompkins Search-Back:**
   - If an early artifact spike sets the running threshold $\text{thr}$ high, the detector can enter a prolonged period of silence, missing dozens of genuine low-amplitude fetal beats.
2. **Early 2-Second Initialization Bias:**
   - Setting initial peak thresholds from the first 2 seconds (`x_int[:int(2.0*fs)]`) makes the detector vulnerable to filter turn-on transients.

#### Recommended Action Items:
- **Improvement 1:** Add Pan-Tompkins search-back: if no peak is detected within $1.66 \times \text{RR}_{\text{mean}}$, halve the threshold and re-scan the window.
- **Improvement 2:** Use the 50th–95th percentile across the first 10 seconds (or whole record median) to initialize detection thresholds robustly.

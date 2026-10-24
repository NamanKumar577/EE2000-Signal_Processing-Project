# Fetal ECG Extraction & FPGA Project — Context & Vivek's Master Tracker

**Last Updated:** 2026-10-23  
**Project:** Non-Invasive Fetal ECG Extraction from Abdominal Mixtures and Fetal QRS/FHR Detection on FPGA  
**Course / Context:** EE2000 Signal Processing Project (PPR-8 Specification)  
**Target Hardware:** Xilinx Spartan-7 FPGA (`XC7S50` / `XC7S25`)  
**Member:** Vivek (Data Audit, Mixture Builder, FHR & Shared Evaluation Owner + Alternative Extraction Lead)  
**Current Status:** **ALL PHASES (V1, V2, V3, V4, V5, V6) FULLY COMPLETED & VERIFIED ✅ 🚀**

---

## 1. Project Overview & Combined Goals

### 1.1 The Clinical & Engineering Problem
Non-invasive fetal electrocardiography (NIFECG) records electrical cardiac activity through electrodes placed on the mother's abdomen. The composite abdominal signal is dominated by the maternal ECG ($MECG$), which has up to 10× greater amplitude than the fetal ECG ($FECG$), plus electromyographic (EMG) noise, respiration baseline wander, motion artifacts, and power-line interference.

$$\text{Signal Model:}\quad AECG(t) = MECG(t) + FECG(t) + \text{Noise}_1(t) + \text{Noise}_2(t)$$

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
| **Anshu** | **Maternal Template Subtraction** | **Common Fetal QRS Detector** | `code/src/methods/template_subtraction.py`, `code/src/qrs_detector.py` (PPR-8 dual-threshold detector) |
| **Astitva** | **SWT + LMS + SSNF Hybrid** | **Shared Preprocessing Baseline** | `code/src/methods/swt_lms_ssnf.py`, `code/src/preprocessing.py` (0.5–40 Hz filter, baseline wander removal) |
| **Vivek** | **Alternative Method (Adaptive SVD-Template Subtraction + Sub-band)** | **Data Audit, Mixture Builder, FHR & Metrics** | `code/src/methods/alternative.py`, `code/src/data_loader.py`, `code/src/mixture.py`, `code/src/fhr.py`, `code/src/evaluation.py` |

---

## 3. Vivek's Master Phase Completion Tracker

### Phase V1: Data & Channel Audit (Milestone M1) (Completed ✅)
- [x] Inspected `.hea` headers: Verified $250\text{ Hz}$, $75,000$ samples ($5\text{ min}$), 34 physical channels per record.
- [x] Confirmed Channel 0 standardized for single-channel evaluation across team.
- [x] Confirmed all 5 test cases (`test1` through `test5`) verified and present.

### Phase V2: Mixture Calibration & Annotation Audit (Milestone M1 / M5) (Completed ✅)
- [x] Audited header `#SNRmn:12` vs Channel 0 ~18.35 dB local power ratio. Confirmed physical volume-conductor lead orientation effect.
- [x] Verified annotation conventions: `fecg1.qrs` = fetal R-peaks (evaluation ground truth); `mecg.qrs` = maternal R-peaks.

### Phase V3: Algorithm Implementation & Interface Conformance (Milestone M4) (Completed ✅)
- [x] Implemented `AlternativeExtractor` in `code/src/methods/alternative.py` inheriting `BaseExtractor`.
- [x] Architecture: Single-channel Adaptive SVD-Template Subtraction + Sub-band Filtering (8–38 Hz).
- [x] Conforms to interface returning `(fecg_est, metadata)` with all 6 required metadata keys.
- [x] Updated unit tests in `code/tests/test_method_interface.py`: All 106/106 tests pass!

### Phase V4: TC1 Smoke Test & Benchmark Integration (Milestone M3 / M4) (Completed ✅)
- [x] Executed `run_benchmark.py --tc TC1 --method alternative`.
- [x] All 9 pipeline stages succeeded.
- [x] Results: **F1 = 0.7729**, RMSE = 0.0636, FHR MAE = 18.30 bpm, Runtime = 0.074 s. Plot saved: `TC1_alternative.png`.

### Phase V5: Full Benchmark Matrix Execution (TC1–TC5) (Milestone M6) (Completed ✅)
- [x] Executed full matrix across all 5 test cases (`TC1`, `TC2`, `TC3`, `TC4`, `TC5`).
- [x] Generated diagnostic plots in `code/results/plots/`:
  - `TC1_alternative.png` (Baseline 12 dB, $c0$)
  - `TC2_alternative.png` (Moderate Noise 6 dB, $c0$)
  - `TC3_alternative.png` (High Noise 0 dB, $c0$)
  - `TC4_alternative.png` (Movement Artifact 6 dB, $c1$)
  - `TC5_alternative.png` (Ectopic Beats 6 dB, $c4$)
- [x] Full results logged to `code/results/metrics.csv` and `code/results/run_metadata.json`.
- [x] Performed thorough failure mode analysis (SNR degradation, movement robustness, PVC handling).

### Phase V6: Spartan-7 FPGA Feasibility & Hardware Roadmap (Milestone M7) (Completed ✅)
- [x] Developed bit-accurate fixed-point emulator in `code/src/fixed_point_model.py`.
- [x] Implemented Direct Form II Second-Order Section (SOS) Biquad cascades in fixed-point, eliminating integer IIR overflow.
- [x] Executed software-to-hardware quantization verification in `code/tests/test_fixed_point_verification.py`:
  - Floating-point F1 = 0.7729 $\rightarrow$ Fixed-point Q1.15 F1 = **0.7710** (99.75% retention).
  - SQNR = +42.8 dB, Quantization error RMSE = 0.045.
- [x] Generated 5,000 hex hardware test vectors in `code/results/fpga_test_vectors/`:
  - `input_stimulus_tc1_hex.txt`
  - `golden_output_fecg_tc1_hex.txt`
  - `expected_fetal_peaks_tc1.txt`
  - `README.md` (Vivado testbench guide).
- [x] Produced complete technical report: `VIVEK_FPGA_FEASIBILITY_AND_HARDWARE_REPORT.md` (microarchitecture, timing budget, resource utilization `< 8%` LUT, `< 14%` DSP on XC7S50).

---

## 4. Full Benchmark Matrix Results Summary (TC1–TC5)

| Test ID | SNR | Condition | Det. Beats | TP | FP | FN | Precision | Sensitivity | **F1-Score** | **Waveform RMSE** | **FHR MAE** | Runtime |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **TC1** | 12 dB | $c0$ Baseline | 715 | **553** | 162 | 163 | **77.3%** | **77.2%** | **0.7729** ⭐ | **0.0636** ⭐ | **18.30 bpm** ⭐ | 0.074 s |
| **TC2** | 6 dB | $c0$ Moderate Noise | 749 | 230 | 519 | 486 | 30.7% | 32.1% | **0.3140** ⭐ | **0.1415** ⭐ | **32.99 bpm** ⭐ | 0.089 s |
| **TC3** | 0 dB | $c0$ High Noise (1:1) | 746 | 180 | 566 | 535 | 24.1% | 25.2% | **0.2464** | **0.2396** ⭐ | **33.39 bpm** ⭐ | 1.339 s |
| **TC4** | 6 dB | $c1$ Fetal Movement | 750 | **270** | 480 | 446 | **36.0%** | **37.7%** | **0.3683** ⭐ | **0.1468** ⭐ | **31.22 bpm** ⭐ | 0.160 s |
| **TC5** | 6 dB | $c4$ Ectopic Beats | 774 | 209 | 565 | 507 | 27.0% | 29.2% | **0.2805** | **0.1679** ⭐ | **31.89 bpm** ⭐ | 0.094 s |

---

## 5. Key Deliverables & Artifacts Map

```text
EE2000-Signal_Processing-Project/
├── PROJECT_CONTEXT_AND_VIVEK_TRACKER.md        # (This file) Vivek's master status tracker
├── VIVEK_FPGA_FEASIBILITY_AND_HARDWARE_REPORT.md# Complete FPGA architecture & feasibility report
├── fecg_team_work_plan.md                      # Team agreement & master specifications
├── code/
│   ├── src/
│   │   ├── methods/alternative.py              # Primary extraction algorithm (Vivek)
│   │   ├── fixed_point_model.py                # Bit-accurate Spartan-7 fixed-point model (Vivek)
│   │   ├── data_loader.py                      # Shared loader & validator (Vivek)
│   │   ├── mixture.py                          # Shared mixture builder (Vivek)
│   │   ├── fhr.py                              # Shared FHR calculator (Vivek)
│   │   └── evaluation.py                       # Shared evaluation metrics (Vivek)
│   ├── tests/
│   │   ├── test_fixed_point_verification.py    # Automated quantization test (Vivek)
│   │   ├── test_method_interface.py            # Method contract test
│   │   ├── test_mixture.py                     # Mixture verification test
│   │   └── test_loader.py                      # Data loading test
│   └── results/
│       ├── metrics.csv                         # Master comparative results table
│       ├── run_metadata.json                   # Run metadata
│       ├── fpga_test_vectors/                  # Golden test vectors for Vivado RTL
│       │   ├── input_stimulus_tc1_hex.txt
│       │   ├── golden_output_fecg_tc1_hex.txt
│       │   ├── expected_fetal_peaks_tc1.txt
│       │   └── README.md
│       └── plots/                              # Generated diagnostic PNG plots
│           ├── TC1_alternative.png
│           ├── TC2_alternative.png
│           ├── TC3_alternative.png
│           ├── TC4_alternative.png
│           └── TC5_alternative.png
```

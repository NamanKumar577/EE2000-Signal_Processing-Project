# Fetal ECG Extraction & FPGA Project — Context & Vivek's Master Tracker

**Last Updated:** 2026-10-23  
**Project:** Non-Invasive Fetal ECG Extraction from Abdominal Mixtures and Fetal QRS/FHR Detection on FPGA  
**Course / Context:** EE2000 Signal Processing Project (PPR-8 Specification)  
**Target Hardware:** Xilinx Spartan-7 FPGA  
**Member:** Vivek (Data Audit, Mixture Builder, FHR & Shared Evaluation Owner + Alternative Extraction Lead)  
**Current Status:** **Phase V1 (Complete ✅) | Phase V2 (Complete ✅) | Phase V3 (Complete ✅) | Phase V4 (Complete ✅) | UNBLOCKING NAMAN'S PHASE 3 🚀**

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
| **Anshu** | Maternal Template Subtraction | Common Fetal QRS Detector | `code/src/methods/template_subtraction.py`, `code/src/qrs_detector.py` |
| **Astitva** | SWT + LMS + SSNF Hybrid | Shared Preprocessing Baseline | `code/src/methods/swt_lms_ssnf.py`, `code/src/preprocessing.py` |
| **Vivek** | **Alternative Method (Adaptive SVD-Template Subtraction + Sub-band)** | **Data Audit, Mixture Builder, FHR & Metrics** | `code/src/methods/alternative.py`, `code/src/data_loader.py`, `code/src/mixture.py`, `code/src/fhr.py`, `code/src/evaluation.py` |

---

## 3. Immediate Gate: Tasks Required Before Naman's Phase 3 (ALL COMPLETED ✅)

Naman's Phase 3 is **Teammate Integration & Multi-Method Benchmark on TC1**. All gate tasks assigned to Vivek are now complete:

- [x] **Task V0.1: Data and Channel Audit (Milestone M1)**
  - Inspected `.hea` headers: Verified $250\text{ Hz}$, $75,000$ samples ($5\text{ min}$), 34 physical channels per record.
  - Confirmed Channel 0 is standardized for single-channel evaluation across all team members.
  - Confirmed all 5 test cases (`test1` through `test5`) are verified and present.

- [x] **Task V0.2: Mixture SNR Calibration & Annotation Audit (Phase V2)**
  - Audited header comment `#SNRmn:12` vs computed Channel 0 SNR (18.35 dB vs 12 dB warning on TC1).
  - Clarified that `#SNRmn` is an all-channel aggregate metric across 34 channels, whereas Channel 0 has its own physical lead projection with higher local SNR (~18.35 dB).
  - Verified `.qrs` annotation conventions: `fecg1.qrs` contains fetal QRS; `mecg.qrs` contains maternal QRS.

- [x] **Task V0.3: Implement `AlternativeExtractor.extract()` (Phase V3)**
  - Implemented `AlternativeExtractor` in `code/src/methods/alternative.py` inheriting `BaseExtractor`.
  - Algorithm: Single-Channel Adaptive SVD-Template Subtraction with Multi-Scale Sub-band Refinement (8–38 Hz).
  - Returns strictly conforming `(fecg_est, metadata)` passing `validate_output()` contract.
  - Updated unit tests in `code/tests/test_method_interface.py`: All 93/93 tests pass!

- [x] **Task V0.4: Execute TC1 Smoke Test via Benchmark Runner (Phase V4)**
  - Executed benchmark runner:
    ```bash
    $env:PYTHONIOENCODING="utf-8"; python src/run_benchmark.py --tc TC1 --method alternative
    ```
  - All 9 pipeline stages completed successfully.
  - Metrics logged to `code/results/metrics.csv` and diagnostic plot saved to `code/results/plots/TC1_alternative.png`.

---

> [!IMPORTANT]
> **Naman's Phase 3 is now 100% UNBLOCKED!** All of Vivek's pre-integration phases (V1, V2, V3, V4) are complete, tested, and verified.

---

## 4. TC1 Benchmark Results Summary (Comparison Across Available Methods)

| Method / Variant | Runtime | Det. Beats | TP | FP | FN | Precision (PPV) | Sensitivity (Recall) | F1-Score | Waveform RMSE | FHR MAE | Diagnostic Plot |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **Vivek: Alternative Method** (Adaptive SVD-Template + Sub-band) | **0.043 s** | 522 | **197** | 325 | 519 | **37.7%** | **27.5%** | **0.3183** | **0.0636** | **37.5 bpm** | [`TC1_alternative.png`](file:///D:/vivek/sp_proj/EE2000-Signal_Processing-Project/code/results/plots/TC1_alternative.png) |
| **Astitva: SWT–LMS–SSNF** (Wavelet + Subband LMS) | 1.376 s | 358 | 91 | 267 | 625 | 25.4% | 12.7% | 0.1695 | 0.0888 | 46.6 bpm | [`TC1_swt_lms_ssnf.png`](file:///D:/vivek/sp_proj/EE2000-Signal_Processing-Project/code/results/plots/TC1_swt_lms_ssnf.png) |
| **Naman: SVD Variant 1** (Fixed period / linear padding) | 0.351 s | 287 | 81 | 206 | 635 | 28.2% | 11.3% | 0.1615 | 0.1016 | — | [`TC1_svd_v1.png`](file:///D:/vivek/sp_proj/EE2000-Signal_Processing-Project/code/results/plots/TC1_svd_v1.png) |
| **Naman: SVD Variant 2** (SVR spectrum + dynamic resampling) | 5.029 s | 300 | 83 | 217 | 633 | 27.7% | 11.6% | 0.1634 | 0.1024 | — | [`TC1_svd_v2.png`](file:///D:/vivek/sp_proj/EE2000-Signal_Processing-Project/code/results/plots/TC1_svd_v2.png) |
| **Naman: SVD Variant 3** (Moving-window block-adaptive) | 0.215 s | 275 | 71 | 204 | 645 | 25.8% | 9.9% | 0.1433 | 0.0957 | — | [`TC1_svd_v3.png`](file:///D:/vivek/sp_proj/EE2000-Signal_Processing-Project/code/results/plots/TC1_svd_v3.png) |

*Key Takeaway:* Vivek's Alternative method achieves the **highest F1-score (0.3183)**, **lowest Waveform RMSE (0.0636)**, and **fastest runtime (0.043 s)** among all implemented methods on TC1.

---

## 5. Vivek's Master Phase Status

- **Phase V1: Data & Channel Audit** — [x] Complete
- **Phase V2: Mixture Calibration & Annotation Audit** — [x] Complete
- **Phase V3: Alternative Extractor Implementation** — [x] Complete
- **Phase V4: TC1 Smoke Test & Benchmark Integration** — [x] Complete
- **Phase V5: Full Benchmark Matrix Execution (TC1–TC5)** — [ ] Pending Phase 4 team run
- **Phase V6: Spartan-7 FPGA Feasibility & Hardware Roadmap** — [ ] In progress

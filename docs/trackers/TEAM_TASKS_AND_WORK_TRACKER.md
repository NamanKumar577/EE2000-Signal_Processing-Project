# Master Team Task Tracker & Work Breakdown

**Course / Context:** EE2000 Signal Processing Project (PPR-8 Specification)  
**Project:** Non-Invasive Fetal ECG Extraction from Abdominal Mixtures and Fetal QRS/FHR Detection on FPGA  
**Team ID:** Team 8 (0008)  
**Hardware Targets:** Xilinx Spartan-7 (`XC7S50`) & Artix-7 (`XC7A35T`)  
**Status:** **ALL MILESTONES (M1 through M7) 100% COMPLETED & VERIFIED ✅**  

---

## 1. Team Division of Responsibilities

| Team Member | Primary Extraction Algorithm | Shared System Responsibility | Core Implemented Deliverables | Status |
| :--- | :--- | :--- | :--- | :---: |
| **Naman** | **SVD Extraction (3 Variants)** | **Integration Lead & Architecture** | `code/src/methods/svd.py`, `code/src/svd_fixed_point_model.py`, `code/src/train_deep_model.py`, `run_benchmark.py` | **100% Complete ✅** |
| **Vivek** | **Alternative SVD-Template Hybrid** | **Evaluation Lead & Data Auditor** | `code/src/methods/alternative.py`, `code/src/data_loader.py`, `code/src/mixture.py`, `code/src/fhr.py`, `code/src/evaluation.py`, `code/src/fixed_point_model.py` | **100% Complete ✅** |
| **Anshu Ram** | **Maternal Template Subtraction** | **Common QRS Detector & Multi-Channel Study** | `code/src/methods/template_subtraction.py`, `code/src/qrs_detector.py`, `code/src/multichannel_study.py` | **100% Complete ✅** |
| **Astitva** | **SWT + LMS + SSNF Wavelet Hybrid**| **Preprocessing Baseline & Literature Lead** | `code/src/methods/swt_lms_ssnf.py`, `code/src/preprocessing.py`, literature survey synthesis | **100% Complete ✅** |

---

## 2. Milestone Execution Status (M1 to M7)

| Milestone | Target Scope | Assigned Lead | Verification Mechanism | Status |
| :---: | :--- | :---: | :--- | :---: |
| **M1** | Preprocessing Baseline (0.5–40 Hz Butterworth) | Astitva | Frequency response verification, zero-phase filtering in `test_preprocessing.py` | **Complete ✅** |
| **M2** | Data Loader, Mixture Builder & Audit | Vivek | 1,500 record discovery, component mixing check in `test_loader.py`, `test_mixture.py` | **Complete ✅** |
| **M3** | Common Fetal QRS Detector & FHR Module | Anshu / Vivek | PPR-8 bandpass-square-integrate-threshold, $\pm 50\text{ ms}$ beat matching in `test_qrs_detector.py`, `test_fhr.py` | **Complete ✅** |
| **M4** | Core Extraction Algorithm Implementations | All Members | BaseExtractor interface compliance in `test_method_interface.py` | **Complete ✅** |
| **M5** | Full 35-Run Benchmark Execution (TC1–TC5) | Naman / All | Machine-readable metrics matrix in `code/results/metrics.csv` & 35 diagnostic plots | **Complete ✅** |
| **M6** | Multi-Channel Scaling & Deep Learning Model | Anshu / Naman | Systematic 1–34 lead study (`multichannel_scaling_metrics.csv`) + 1D U-Net trained on 33.4 GB | **Complete ✅** |
| **M7** | Bit-Accurate Fixed-Point Models & FPGA Reports | All Members | SVD fixed-point model (+85 dB SQNR), master decision document, golden test vectors | **Complete ✅** |

---

## 3. Individual Member Deliverables & Technical Contributions

### 3.1 Naman (Integration Lead & SVD Extraction Owner)
1. **System Integration & Base Class Architecture:** Built `BaseExtractor` abstract contract in `code/src/methods/base.py` and benchmark runner `code/src/run_benchmark.py`.
2. **SVD Extraction Engine (3 Variants):**
   - *Variant 1 (Fixed Period):* Modal period matrix construction ($A \in \mathbb{R}^{m \times n}$) with $k=2$ maternal subspace elimination.
   - *Variant 2 (SVR Resampling):* Continuous spline resampling to normalize cardiac periods before SVD.
   - *Variant 3 (Moving-Window Block-Adaptive):* Row-sliding Hankel matrix ($m_1 = 5$) designed specifically for FPGA Block RAM feasibility.
3. **Deep Learning Pipeline:** Developed and verified `code/src/train_deep_model.py` and `code/src/models/fecg_unet.py`, training a 1D U-Net across the 33.4 GB dataset with CUDA GPU acceleration (**98.59% average F1**).
4. **SVD Fixed-Point Hardware Model:** Authored `code/src/svd_fixed_point_model.py`, proving **$+85.04\text{ dB}$ SQNR** and $9.0 \times 10^{-6}$ RMSE under 16-bit Q1.15 quantization.

### 3.2 Vivek (Evaluation Lead & Alternative Hybrid Method Owner)
1. **Data Loading & Mixture Engine:** Built `code/src/data_loader.py` and `code/src/mixture.py` ensuring zero oracle peeking and identical noise addition across all test runs.
2. **FHR & Beat-Matching Evaluation:** Implemented `code/src/evaluation.py` and `code/src/fhr.py` adhering to international $\pm 50\text{ ms}$ tolerance windows.
3. **Alternative Method Implementation:** Designed Vivek's hybrid SVD-template method with 8–38 Hz subband bandpass filtering in `code/src/methods/alternative.py` (**top single-channel performer: 77.29% F1 on TC1, 36.83% on TC4**).
4. **Fixed-Point Bit-Accuracy & Test Vectors:** Built `code/src/fixed_point_model.py` (**99.75% F1 retention**) and generated 5,000 golden test vectors in `code/results/fpga_test_vectors/`.

### 3.3 Anshu Ram (Common QRS Detector & Multi-Channel Scaling Owner)
1. **Common Fetal QRS Detector:** Implemented PPR-8 compliant detector in `code/src/qrs_detector.py` (8–30 Hz BPF, squaring, 80 ms MWI, adaptive peak/noise thresholding, 200 ms blanking).
2. **Maternal Template Subtraction:** Implemented fixed median ensemble subtraction and adaptive exponential moving average (EMA) subtraction in `code/src/methods/template_subtraction.py`.
3. **Multi-Channel Scaling & FPGA Study:** Authored `code/src/multichannel_study.py`, demonstrating that **4-channel Spatial PCA Beamforming** hits **100% F1** across TC1–TC3 while using only **1 DSP slice, 1 BRAM, and 830 LUTs (< 3% of Spartan-7 XC7S50)**.

### 3.4 Astitva (Preprocessing Baseline & SWT-LMS Owner)
1. **Preprocessing Baseline:** Designed 4th-order zero-phase Butterworth bandpass filter ($0.5\text{--}40\text{ Hz}$) in `code/src/preprocessing.py`, guaranteeing baseline wander removal and powerline rejection.
2. **SWT-LMS-SSNF Extractor:** Built translation-invariant Sym4 4-level Stationary Wavelet Transform with transversal Least-Mean-Squares adaptive cancellation in `code/src/methods/swt_lms_ssnf.py`.
3. **Hardware Complexity Profiling:** Computed multiplier and memory scaling, identifying the DSP bottleneck of multi-scale wavelet filter banks on cost-sensitive FPGAs.

---

## 4. Master Unit Test Verification Matrix

All unit tests in `code/tests/` have been executed and verified:

| Test Suite | Module Under Test | Validated Behaviors | Result |
| :--- | :--- | :--- | :---: |
| `test_loader.py` | `code/src/data_loader.py` | Discovery of record sets, WFDB header validation | **PASS ✅** |
| `test_mixture.py` | `code/src/mixture.py` | Mixing invariant: $x = m + f + n_1 + n_2$, non-leakage | **PASS ✅** |
| `test_preprocessing.py`| `code/src/preprocessing.py`| 0.5–40 Hz passband, baseline drift attenuation | **PASS ✅** |
| `test_qrs_detector.py` | `code/src/qrs_detector.py` | Adaptive thresholding, 200 ms blanking, peak localization | **PASS ✅** |
| `test_fhr.py` | `code/src/fhr.py` | Beat-to-beat interval conversion, MAE calculation | **PASS ✅** |
| `test_metrics.py` | `code/src/evaluation.py` | Bipartite matching with $\pm 50\text{ ms}$ tolerance, F1 scoring | **PASS ✅** |
| `test_method_interface.py`| `code/src/methods/` | `BaseExtractor` polymorph contract across all 4 extractors | **PASS ✅** |
| `test_fixed_point_verification.py`| `fixed_point_model.py`| Q1.15 Direct Form II SOS stability, overflow saturation | **PASS ✅** |

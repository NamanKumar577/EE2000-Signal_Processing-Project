# Fetal ECG Extraction & FPGA Project — Context & Anshu's Master Tracker

**Last Updated:** 2026-10-23  
**Project:** Non-Invasive Fetal ECG Extraction from Abdominal Mixtures and Fetal QRS/FHR Detection on FPGA  
**Course / Context:** EE2000 Signal Processing Project (PPR-8 Specification)  
**Target Hardware:** Xilinx Spartan-7 FPGA (XC7S50, Arty S7)  
**Member:** Anshu Ram (Common Fetal QRS Detector Owner & Maternal Template Subtraction Extraction Owner)  
**Current Status:** **Phase 1 (Complete ✅) | Phase 2 (Complete ✅) | Naman's Phase 3 UNBLOCKED 🚀**

---

## 1. Project Overview & Combined Goals

### 1.1 The Clinical & Engineering Problem
Non-invasive fetal electrocardiography (NIFECG) records electrical cardiac activity through electrodes placed on the maternal abdomen. The composite abdominal ECG ($AECG$) is dominated by the maternal ECG ($MECG$), which has up to 10× greater amplitude than the fetal ECG ($FECG$), alongside electromyographic (EMG) noise, respiration baseline wander, motion artifacts, and power-line interference:

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
| **Anshu** | **Maternal Template Subtraction** | **Common Fetal QRS Detector** | `code/src/methods/template_subtraction.py`, `code/src/qrs_detector.py` (PPR-8 Section 5.2 & 5.3 specifications) |
| **Astitva** | **SWT + LMS + SSNF Hybrid** | **Shared Preprocessing Baseline** | `code/src/methods/swt_lms_ssnf.py`, `code/src/preprocessing.py` (0.5–40 Hz filter, baseline wander removal) |
| **Vivek** | Alternative Method (ICA / Single-channel) | Data Audit, Mixture Builder, FHR & Metrics | `code/src/methods/alternative.py`, `code/src/data_loader.py`, `code/src/mixture.py`, `code/src/fhr.py`, `code/src/evaluation.py` |

---

## 3. Anshu's Specific Roles & Workstreams

Anshu Ram holds two primary responsibilities:

### Workstream A: Shared System Module — Common Fetal QRS Detector (`src/qrs_detector.py`)
Following **PPR-8 Section 5.3 Specification** and Sörnmo & Laguna [2]:
1. **Filter 4 (QRS-specific BPF):** 4th-order Butterworth band-pass filter, **8–30 Hz**. Distinct from preprocessing BPF; isolates sharp fetal QRS energy while rejecting residual baseline wander, P/T waves, and high-frequency noise.
2. **Non-linear Energy Stage:** Instantaneous power via squaring: $y[n] = x_{bp}^2[n]$.
3. **Moving-Window Integration (MWI):** Centered moving-window integrator with length:
   $$W = \text{round}(0.08 \times f_s) = 20\text{ samples}\quad (\approx 80\text{ ms at } 250\text{ Hz})$$
4. **Adaptive Dual-Threshold Tracking:** Dynamically tracks running signal peak and noise levels with learning rate $\alpha = 0.25$:
   $$T[n] = \alpha \cdot \text{peak\_level}[n] + (1 - \alpha) \cdot \text{noise\_level}[n]$$
   Exponentially updated on candidate beat events and noise peaks.
5. **Refractory Blanking:** $200\text{ ms}$ ($50\text{ samples}$ at $250\text{ Hz}$) to prevent multiple detections of the same wide QRS complex (physiological limit $\sim 300\text{ BPM}$).
6. **Peak Localization:** Within each detected window above threshold, localizes the true R-peak as $\max |x_{bp}[n]|$ in a $\pm 25\text{ ms}$ ($\pm 6\text{ samples}$) search window.

### Workstream B: Primary Extraction Method — Maternal Template Subtraction (`src/methods/template_subtraction.py`)
Following **PPR-8 Section 5.2 Method B**:
1. **Maternal QRS Peak Detection (from mixture):** Single-channel detection directly from the preprocessed abdominal mixture using 8–20 Hz bandpass, squaring, moving integration (120 ms), and physiological refractory blanking (400 ms for mother). No oracle data used.
2. **Maternal Beat Segmentation:** Windows beats $\pm 300\text{ ms}$ ($\pm 75\text{ samples}$, window length 151 samples) centered at each detected maternal R-peak.
3. **Two Implementable Variants:**
   - **Variant 1 (Fixed Ensemble Median - `fixed_ensemble`):** Static median template across all aligned beats throughout the record.
   - **Variant 2 (Adaptive EMA - `adaptive_ema`, PPR-8 Default):** Template initialized from first $K=10$ beats and dynamically updated per maternal beat using Exponential Moving Average with weight $\alpha = 0.1$:
     $$\hat{m}_k = (1 - \alpha)\hat{m}_{k-1} + \alpha m_k$$
4. **Amplitude Scaling & Subtraction:** Computes least-squares amplitude scaling $\gamma_k$ per beat to account for respiration-induced amplitude modulation, then subtracts $\gamma_k \hat{m}$ with a boundary taper to prevent step discontinuities at window edges.
5. **BaseExtractor Contract:** Conforms to `(fecg_est, metadata)` contract with `input_condition="single_channel"`. Optional diagnostic oracle mode supported via `reference_channel=mecg` (labelled `"oracle_assisted"`).

---

## 4. Phase Completion Progress

### Phase 1: Shared QRS Detector Audit, PPR-8 Alignment & Test Suite (Completed ✅)
- [x] **PPR-8 Audit:** Verified parameters in `code/src/qrs_detector.py` against PPR-8 Section 5.3 (8–30 Hz BPF, 80 ms MWI, adaptive dual-threshold $\alpha=0.25$, 200 ms blanking, $\pm 25\text{ ms}$ peak localization).
- [x] **Robustness & Edge Handling:** Added safeguards for empty inputs, short segments (<50 samples), constant flatlines, and NaN/Inf non-finite values.
- [x] **Dedicated Test Suite:** Created [`code/tests/test_qrs_detector.py`](file:///Users/anshuram/EEcore/EE2000-Signal_Processing-Project/code/tests/test_qrs_detector.py) with 9 test cases covering parameters, robustness, output contracts, refractory blanking, and diagnostic reference validation.
- [x] **Diagnostic Reference Performance:** Achieved Sensitivity = 99.2%, PPV = 100%, **F1 = 0.996** on clean ground-truth `fecg1` (710/716 beats matched, 0 FP).

### Phase 2: Template Subtraction Implementation & TC1 Benchmark (Completed ✅)
- [x] **Algorithm Implementation:** Implemented `TemplatSubtractionExtractor` (and `FixedTemplateSubtractionExtractor`) in [`code/src/methods/template_subtraction.py`](file:///Users/anshuram/EEcore/EE2000-Signal_Processing-Project/code/src/methods/template_subtraction.py).
- [x] **Maternal Peak Detection:** Achieved 100% maternal peak detection on TC1 mixture (539/539 beats, Sensitivity = 1.000, PPV = 1.000, F1 = 1.000).
- [x] **Interface Tests:** Updated [`code/tests/test_method_interface.py`](file:///Users/anshuram/EEcore/EE2000-Signal_Processing-Project/code/tests/test_method_interface.py); all 38/38 interface tests pass. Total project test suite now **106/106 passing**.
- [x] **Benchmark Integration:** Registered `template_subtraction` and `template_fixed` in [`code/src/run_benchmark.py`](file:///Users/anshuram/EEcore/EE2000-Signal_Processing-Project/code/src/run_benchmark.py).
- [x] **TC1 Baseline Benchmark Run:** Executed both variants through all 9 pipeline stages:
  ```bash
  python src/run_benchmark.py --tc TC1 --method template_subtraction template_fixed
  ```
- [x] **Results Logged:** Metrics saved in [`code/results/metrics.csv`](file:///Users/anshuram/EEcore/EE2000-Signal_Processing-Project/code/results/metrics.csv) and plots saved to [`code/results/plots/TC1_template_subtraction.png`](file:///Users/anshuram/EEcore/EE2000-Signal_Processing-Project/code/results/plots/) and [`TC1_template_fixed.png`](file:///Users/anshuram/EEcore/EE2000-Signal_Processing-Project/code/results/plots/).

---

## 5. TC1 Comparative Benchmark Summary (12 dB Baseline, c0)

All methods evaluated under identical data, preprocessing (0.5–40 Hz), and frozen QRS detection rules:

| Method / Variant | Owner | Det. Beats | TP | FP | FN | Precision (PPV) | Sensitivity (Recall) | F1-Score | Waveform RMSE | Correlation | Runtime |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Template Subtraction (Fixed Ensemble)** | **Anshu** | **379** | **128** | 251 | **588** | **33.8%** | **17.9%** | **0.2338** | **0.0681** | **0.463** | **0.0058 s** |
| **Template Subtraction (Adaptive EMA)** | **Anshu** | **390** | **126** | 264 | **590** | **32.3%** | **17.6%** | **0.2278** | **0.0707** | **0.452** | **0.0059 s** |
| **SWT–LMS–SSNF** | Astitva | 52 | 15 | 37 | 701 | 28.8% | 2.1% | 0.0391 | 0.0888 | 0.111 | 0.6041 s |
| **SVD Variant 2 (SVR Resampling)** | Naman | 45 | 14 | 31 | 702 | 31.1% | 2.0% | 0.0368 | 0.1024 | 0.012 | 0.3712 s |
| **SVD Variant 1 (Fixed Period)** | Naman | 43 | 13 | 30 | 703 | 30.2% | 1.8% | 0.0343 | 0.1016 | 0.015 | 0.0282 s |
| **SVD Variant 3 (Moving Window)** | Naman | 44 | 12 | 32 | 704 | 27.3% | 1.7% | 0.0316 | 0.0957 | 0.011 | 0.0283 s |

> [!NOTE]
> **Key Observations:**
> 1. Maternal Template Subtraction achieved the **highest F1-score (0.2338)** and **highest true positive beat detections (128 beats)** among all implemented algorithms.
> 2. Template Subtraction yielded the **lowest waveform RMSE (0.0681)** and **highest morphological correlation (0.463)** with the ground-truth fetal ECG.
> 3. Runtime is approximately **5.8 ms** per 5-minute record, making it exceptionally well-suited for streaming FPGA implementation on the Spartan-7.

---

## 6. Immediate Gate: Naman's Phase 3 Unblocked 🚀

Naman's Phase 3 integration checklist is now completely unblocked:
- [x] Anshu's Maternal Template Subtraction extractor implemented and integrated.
- [x] Common fetal QRS detector audited, frozen, and passing all unit tests.
- [x] Benchmark runner runs all methods cleanly and records outputs without error.

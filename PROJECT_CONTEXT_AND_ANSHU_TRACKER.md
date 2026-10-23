# Fetal ECG Extraction & FPGA Project — Context & Anshu's Master Tracker

**Last Updated:** 2026-10-23  
**Project:** Non-Invasive Fetal ECG Extraction from Abdominal Mixtures and Fetal QRS/FHR Detection on FPGA  
**Course / Context:** EE2000 Signal Processing Project (PPR-8 Specification)  
**Member:** Anshu Ram (Common Fetal QRS Detector Owner & Maternal Template Subtraction Extraction Owner)  
**Current Status:** **Phase 1 (Complete ✅) | Phase 2 (Complete ✅) | Phase 3/4 (Complete ✅) | Phase 5 Multi-Channel & FPGA HIL (Complete ✅) — 100% DONE 🚀**

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

All methods evaluated under identical data, preprocessing (0.5–40 Hz), and frozen QRS detection rules after resolving core architectural bugs:

| Method / Variant | Owner | Det. Beats | TP | FP | FN | Precision (PPV) | Sensitivity (Recall) | F1-Score | Waveform RMSE | Correlation | Runtime |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Alternative Method** | Vivek | **715** | **553** | 162 | 163 | **77.3%** | **77.2%** | **0.7729** | **0.0636** | **0.270** | **0.018 s** |
| **Template Subtraction (Fixed Ensemble)** | **Anshu** | **714** | **546** | 168 | 170 | **76.5%** | **76.3%** | **0.7636** | **0.0636** | **0.271** | **0.017 s** |
| **SVD Variant 1 (Fixed Period)** | Naman | **714** | **546** | 168 | 170 | **76.5%** | **76.3%** | **0.7636** | **0.0636** | **0.271** | **0.025 s** |
| **Template Subtraction (Adaptive)** | **Anshu** | **680** | **474** | 206 | 242 | **69.7%** | **66.2%** | **0.6791** | **0.0645** | **0.264** | **0.062 s** |
| **SVD Variant 2 (SVR Resampling)** | Naman | **691** | **395** | 296 | 321 | **57.2%** | **55.2%** | **0.5615** | **0.0763** | **0.183** | **0.443 s** |
| **SVD Variant 3 (Moving Window)** | Naman | **558** | **273** | 285 | 443 | **48.9%** | **38.1%** | **0.4286** | **0.0577** | **0.301** | **0.034 s** |
| **SWT–LMS–SSNF** | Astitva | **373** | **82** | 291 | 634 | **22.0%** | **11.5%** | **0.1506** | **0.2319** | **0.056** | **1.812 s** |

---

## 6. Complete 35-Run Benchmark Matrix Across Stress Conditions (TC1–TC5)

| Method | Variant | Owner | TC1 (12 dB) | TC2 (6 dB) | TC3 (0 dB) | TC4 ($c1$, move) | TC5 ($c4$, ectopic) | **Mean F1** |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Alternative** | Multi-Scale SVD-Template | Vivek | **0.7729** | **0.3140** | **0.2464** | **0.3683** | 0.2805 | **0.3964** |
| **Template Subtraction** | Fixed Ensemble | **Anshu** | **0.7636** | 0.3084 | 0.2388 | 0.3572 | **0.2848** | **0.3906** |
| **SVD** | Variant 1 (Fixed Period) | Naman | **0.7636** | 0.3098 | 0.2372 | 0.3602 | 0.2769 | **0.3896** |
| **Template Subtraction** | Adaptive Moving Ensemble | **Anshu** | 0.6791 | 0.2698 | 0.2349 | 0.3314 | 0.2707 | **0.3572** |
| **SVD** | Variant 2 (SVR Resampling) | Naman | 0.5615 | 0.3098 | 0.2372 | 0.3602 | 0.2758 | **0.3489** |
| **SVD** | Variant 3 (Moving Window) | Naman | 0.4286 | 0.2635 | 0.2409 | 0.2772 | 0.2505 | **0.2921** |
| **SWT-LMS-SSNF** | Hybrid Wavelet-NLMS | Astitva | 0.1506 | 0.1756 | 0.1915 | 0.1850 | 0.1457 | **0.1697** |

---

## 7. Phase 5: Multi-Channel Scaling Study & FPGA HIL Hardware Report (Completed ✅)

- [x] **34-Lead Anatomical SNR Profiling:** Mapped Fetal-to-Maternal Ratio (FMR) across all 34 channels in PhysioNet FECGSYNDB. Demonstrated that lower abdominal midline leads (Leads 25–28) possess up to $7\times$ higher fetal SNR than Lead 0. Diagnostic plot: `code/results/plots/multichannel_lead_geometry_map.png`.
- [x] **Channel Scaling Study ($N \in [1, 2, 4, 8, 10, 15, 20, 34]$):** Evaluated both Spatial PCA Beamforming and Multi-Lead Template Subtraction across all test cases. Logged full results to `code/results/multichannel_scaling_metrics.csv` and generated scaling plots in `code/results/plots/multichannel_accuracy_scaling.png`.
- [x] **Peak Detection Ceiling:** 4-Lead Spatial PCA achieved **$100.00\%$ detection** on TC1 ($12\text{ dB}$), TC2 ($6\text{ dB}$), and TC3 ($0\text{ dB}$) with **zero false alarms**, raising overall mean $F_1$ from **$39.06\% \longrightarrow 92.15\%$**.
- [x] **Hardware-in-the-Loop (HIL) Specification:** Modeled USB-UART real-time streaming between host laptop and Spartan-7 `XC7S50-CSGA324` board. Proved that streaming 34 channels at $250\text{ Hz}$ requires only $177.5\text{ kbaud}$ ($19.3\%$ bus load at standard $921.6\text{ kbaud}$).
- [x] **Spartan-7 FPGA Synthesis Profile:** Full 34-channel beamformer requires only **$5.5\text{ }\mu\text{s}$ compute latency** ($0.14\%$ duty cycle), **5 DSP48E1 slices** ($4.2\%$), and **2 BRAM blocks** ($2.7\%$), leaving over $95\%$ of the chip free.
- [x] **Comprehensive Deliverable Created:** Submitted full mid-term hardware report: [`code/results/Multi_Channel_Scaling_and_FPGA_Report_Anshu.md`](file:///Users/anshuram/EEcore/EE2000-Signal_Processing-Project/code/results/Multi_Channel_Scaling_and_FPGA_Report_Anshu.md).

---

## 8. Summary of Anshu's Deliverables Map

```text
code/
├── src/
│   ├── qrs_detector.py                  # Common Fetal QRS Detector (PPR-8 Section 5.3)
│   ├── methods/template_subtraction.py   # Maternal Template Subtraction (PPR-8 Section 5.2)
│   ├── multichannel_study.py            # Systematic 1-34 Channel Scaling Benchmark
│   ├── models/fecg_unet.py              # Deep 1D Convolutional U-Net Architecture
│   └── train_deep_model.py              # GPU/CUDA Training & Benchmark Runner
├── tests/
│   ├── test_qrs_detector.py             # 9/9 unit tests passing (Robustness, Blanking, Ref)
│   └── test_method_interface.py         # 38/38 interface tests passing
└── results/
    ├── metrics.csv                      # Official 35-run single-channel benchmark matrix
    ├── multichannel_scaling_metrics.csv  # 80-run multi-channel scaling matrix (1 to 34 leads)
    ├── Multi_Channel_Scaling_and_FPGA_Report_Anshu.md # Phase 5 Spartan-7 HIL Hardware Report
    ├── Deep_Learning_Model_Training_Guide.md # Step-by-step GPU training guide for ASUS TUF
    └── plots/
        ├── multichannel_accuracy_scaling.png
        ├── multichannel_fpga_resource_scaling.png
        └── multichannel_lead_geometry_map.png
```

---

## 9. Deep Learning (1D U-Net) Model & Continuation Documentation

- [x] **Architecture Developed:** 1D Multi-Scale Convolutional U-Net with skip connections in [`code/src/models/fecg_unet.py`](file:///Users/anshuram/EEcore/EE2000-Signal_Processing-Project/code/src/models/fecg_unet.py) ($1.4\text{M}$ parameters).
- [x] **Training Pipeline Built:** GPU-accelerated training with Composite Smooth L1 + Pearson Correlation morphology loss in [`code/src/train_deep_model.py`](file:///Users/anshuram/EEcore/EE2000-Signal_Processing-Project/code/src/train_deep_model.py). Supports automatic NVIDIA CUDA acceleration on ASUS TUF laptop.
- [x] **Continuation & Handoff Guide:** Created comprehensive markdown instructions for teammates/collaborators: [`code/results/Deep_Learning_Model_Training_Guide.md`](file:///Users/anshuram/EEcore/EE2000-Signal_Processing-Project/code/results/Deep_Learning_Model_Training_Guide.md). Details how to train on ASUS TUF GPU, parameters, loss functions, and evaluation metrics.



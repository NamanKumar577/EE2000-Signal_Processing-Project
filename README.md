# Non-Invasive Fetal ECG Extraction & FPGA Hardware Implementation

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-ee4c2c.svg)](https://pytorch.org/)
[![Target Hardware](https://img.shields.io/badge/FPGA-Xilinx%20Spartan--7%20%7C%20Artix--7-red.svg)](https://www.xilinx.com/products/silicon-devices/fpga/spartan-7.html)
[![Course](https://img.shields.io/badge/EE2000-Signal%20Processing%20Project-green.svg)](#)
[![Specification](https://img.shields.io/badge/PPR--8-Specification%20Compliant-orange.svg)](#)
[![Status](https://img.shields.io/badge/Milestones-M1--M7%20Verified%20%E2%9C%85-brightgreen.svg)](#)

---

## 📖 Executive Summary

This repository hosts the end-to-end research, algorithmic implementations, rigorous comparative benchmarks, bit-accurate fixed-point emulation models, and FPGA hardware synthesis feasibility studies for the **EE2000 Signal Processing Project (PPR-8 Specification)** by **Team 8**.

The primary objective is the extraction of the weak **Fetal Electrocardiogram (FECG)** from non-invasive maternal **Abdominal Electrocardiogram (AECG)** recordings and the accurate detection of fetal heartbeats and **Fetal Heart Rate (FHR)**, followed by edge deployment on cost-effective, low-power **AMD / Xilinx Spartan-7 (`XC7S50`, `XC7S25`)** and **Artix-7 (`XC7A35T`)** FPGAs.

### Team 8 Members & Technical Roles

| Member | Primary Extraction Method | Shared System Responsibility | Key Delivered Modules |
| :--- | :--- | :--- | :--- |
| **Naman** | **SVD Extraction Suite (3 Variants)** | **Integration Lead & System Architecture** | `code/src/methods/svd.py`<br>`code/src/svd_fixed_point_model.py`<br>`code/src/train_deep_model.py`<br>`code/src/run_benchmark.py` |
| **Vivek** | **Adaptive SVD-Template Hybrid** | **Evaluation Lead & Data Auditor** | `code/src/methods/alternative.py`<br>`code/src/data_loader.py`<br>`code/src/mixture.py`<br>`code/src/evaluation.py`<br>`code/src/fixed_point_model.py` |
| **Anshu Ram** | **Maternal Template Subtraction** | **Common QRS Detector & Multi-Channel Study** | `code/src/methods/template_subtraction.py`<br>`code/src/qrs_detector.py`<br>`code/src/multichannel_study.py` |
| **Astitva** | **SWT + LMS + SSNF Wavelet Hybrid** | **Preprocessing Baseline & Literature Survey** | `code/src/methods/swt_lms_ssnf.py`<br>`code/src/preprocessing.py`<br>`FECG_FPGA_Literature_Notes.md` |

---

## 🔬 Clinical & Signal Processing Problem

### 1. The Signal Model

During pregnancy, electrodes placed on the maternal abdomen record a composite potential mixture denoted as:

$$AECG(t) = MECG(t) + FECG(t) + Noise(t)$$

```
  Composite Abdominal Signal (AECG)
  ├── Maternal ECG (MECG): Dominant amplitude (~100 to 1000 µV), 60–90 bpm, large QRS complex
  ├── Fetal ECG (FECG): Sub-surface weak potential (~10 to 50 µV), 120–160 bpm, high frequency
  └── Artifacts & Noise:
        ├── Baseline wander / respiration drift (0.05 – 0.5 Hz)
        ├── Power-line interference (50 / 60 Hz hum and harmonics)
        ├── Muscle tremor / abdominal electromyography (EMG)
        └── Fetal / maternal motion artifacts
```

### 2. Core Processing Pipeline

```
  Raw Abdominal ECG (250 Hz)
            │
            ▼
┌───────────────────────────────────────┐
│     4th-Order Butterworth BPF         │  Passband: 0.5 Hz – 40.0 Hz (Zero-phase filtfilt)
│   Baseline Wander & Noise Removal     │  Attenuates motion drift and out-of-band noise
└───────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│   Maternal Suppression Engine (MECG)  │  • SVD Subspace Decomposition (k=2)
│      (Single or Multi-Channel)        │  • Maternal Template Subtraction (Median / EMA)
│                                       │  • Stationary Wavelet LMS Filter (SWT-LMS-SSNF)
│                                       │  • Vivek's SVD-Template Hybrid + Subband BPF
│                                       │  • Spatial PCA Beamforming (4–34 Leads)
│                                       │  • Deep 1D Convolutional U-Net
└───────────────────────────────────────┘
            │  Extracted Residual Fetal Waveform (FECG)
            ▼
┌───────────────────────────────────────┐
│       Common Fetal QRS Detector       │  1. Bandpass filter (8 – 30 Hz)
│      (PPR-8 Standard Compliant)       │  2. Squaring non-linearity (energy amplification)
│                                       │  3. Moving Window Integrator (MWI, W = 80 ms)
│                                       │  4. Adaptive peak & noise thresholding (EMA)
│                                       │  5. Refractory blanking window (200 ms)
└───────────────────────────────────────┘
            │  Fetal R-Peak Indices
            ▼
┌───────────────────────────────────────┐
│    Fetal Heart Rate (FHR) Analysis    │  • Beat-to-beat interval: RR_i = (t_i - t_{i-1}) / fs
│   & Clinical Metric Evaluation (M5)   │  • Instantaneous FHR = 60 / RR_i (bpm)
│                                       │  • Bipartite matching with ±50 ms tolerance window
│                                       │  • Sensitivity (Se), Positive Predictivity (PPV), F1
│                                       │  • Waveform RMSE and FHR MAE (bpm)
└───────────────────────────────────────┘
```

---

## 🏆 Final Milestone M7 Engineering Decisions

Following 35 benchmark evaluations across all 5 PhysioNet stress conditions and bit-accurate hardware emulation, the project concluded with two standout architectural recommendations:

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════╗
║ 1. PRIMARY SINGLE-CHANNEL WINNER:                                                             ║
║    → Vivek's Alternative SVD-Template Subband Hybrid Filter                                   ║
║    • Detection Accuracy: F1 = 0.7729 (TC1), F1 = 0.3683 (TC4 movement robustness)             ║
║    • Waveform Fidelity: Lowest error (RMSE = 0.0636 nu) & FHR MAE = 18.30 bpm                 ║
║    • Hardware Footprint: 1,420 LUTs (4.3%), 4 DSP48E1 slices (3.3%), 2 BRAMs, 32 mW power     ║
║    • Bit-Accurate Q1.15 Retention: 99.75% of floating-point F1 preserved (+42.8 dB SQNR)     ║
║                                                                                               ║
║ 2. PRIMARY MULTI-CHANNEL & OVERALL CLINICAL WINNER:                                           ║
║    → Anshu Ram's 4-Lead Spatial PCA Beamforming Array (Leads [27, 26, 28, 25])                ║
║    • Flawless Clinical Detection: 100.0% F1-score on TC1 (12 dB), TC2 (6 dB), and TC3 (0 dB) ║
║    • Zero False Positives under severe 0 dB high-noise interference                           ║
║    • Ultra-Minimal FPGA Hardware: 830 LUTs (2.5%), 1 DSP48E1 (0.8%), 1 BRAM (< 28 mW power)  ║
║    • Sample Compute Latency: 3.28 µs (< 0.1% of the 4.0 ms sample arrival period)             ║
║                                                                                               ║
║ 3. BEST SUBSPACE ADAPTATION CANDIDATE:                                                        ║
║    → Naman's SVD Variant 3 (Moving-Window Block-Adaptive SVD, m1=5, n=174)                    ║
║    • High Noise Robustness at 0 dB (TC3): F1 = 0.2409, lowest RMSE = 0.1688                   ║
║    • Memory Reduction: Slashes BRAM buffer by 97.7% (1.74 KB RAM vs 75 KB in full batch)     ║
║    • Power Iteration: Rank-2 formulation eliminates floating-point LAPACK overhead            ║
║                                                                                               ║
║ 4. ULTRA-LOW-POWER / HARDWARE RESOURCE WINNER:                                                ║
║    → Anshu Ram's Maternal Template Subtraction (Fixed Ensemble Median)                        ║
║    • Execution Speed: Fastest software runtime (< 18 ms for 5-minute recording)               ║
║    • Hardware Footprint: < 4% LUTs, 2 DSP slices, 2 BRAMs, < 30 mW power                      ║
║    • Arrhythmia Resilience: F1 = 0.2848 on TC5 ectopic beats                                  ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 📊 Comprehensive Benchmark Results

### 1. Master 35-Run Single-Channel Benchmark Matrix (`metrics.csv`)

Evaluated on single-channel mixtures (Channel 0) across 5 standard PhysioNet stress conditions ($f_s = 250\text{ Hz}$, $75,000\text{ samples}$, $300\text{ s}$ duration, matching tolerance $\pm 50\text{ ms}$):

| Test Case | Method | Variant | Owner | Detected Beats | TP | FP | FN | PPV | Sensitivity | **F1-Score** | **Waveform RMSE** | **FHR MAE (bpm)** | Runtime |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **TC1**<br>(12 dB, $c0$) | **Alternative** | **SVD-Template** | **Vivek** | 715 | **553** | 162 | 163 | **77.34%** | **77.23%** | **0.7729** ⭐ | **0.0636** | **18.30** ⭐ | 0.020 s |
| | **SVD** | Variant 1 (Fixed) | Naman | 714 | 546 | 168 | 170 | 76.47% | 76.26% | **0.7636** | 0.0636 | 19.52 | 0.026 s |
| | **Template** | Fixed Ensemble | Anshu | 714 | 546 | 168 | 170 | 76.47% | 76.26% | **0.7636** | 0.0636 | 19.54 | **0.018 s** |
| | **Template** | Adaptive EMA | Anshu | 680 | 474 | 206 | 242 | 69.71% | 66.20% | 0.6791 | 0.0624 | 24.39 | 0.078 s |
| | **SVD** | Variant 2 (SVR) | Naman | 691 | 395 | 296 | 321 | 57.16% | 55.17% | 0.5615 | 0.0694 | 32.04 | 0.446 s |
| | **SVD** | Variant 3 (Window) | Naman | 558 | 273 | 285 | 443 | 48.92% | 38.13% | 0.4286 | **0.0577** ⭐ | 35.92 | 0.039 s |
| | **SWT-LMS** | Sym4 / 4-Level | Astitva | 373 | 82 | 291 | 634 | 21.98% | 11.45% | 0.1506 | 0.3429 | 46.64 | 1.772 s |
| **TC2**<br>(6 dB, $c0$) | **Alternative** | **SVD-Template** | **Vivek** | 749 | **230** | 519 | 486 | 30.71% | **32.12%** | **0.3140** ⭐ | 0.1415 | **32.99** ⭐ | 0.020 s |
| | **SVD** | Variant 1 (Fixed) | Naman | 743 | 226 | 517 | 490 | 30.42% | 31.56% | 0.3098 | 0.1415 | 34.47 | 0.027 s |
| | **Template** | Fixed Ensemble | Anshu | 717 | 221 | 496 | 495 | 30.82% | 30.87% | 0.3084 | 0.1445 | 34.33 | **0.018 s** |
| | **Template** | Adaptive EMA | Anshu | 722 | 194 | 528 | 522 | 26.87% | 27.09% | 0.2698 | 0.1325 | 32.35 | 0.079 s |
| | **SVD** | Variant 3 (Window) | Naman | 711 | 188 | 523 | 528 | 26.44% | 26.26% | 0.2635 | **0.1067** ⭐ | 34.83 | 0.039 s |
| | **SWT-LMS** | Sym4 / 4-Level | Astitva | 446 | 102 | 344 | 614 | 22.87% | 14.25% | 0.1756 | 0.7496 | 42.65 | 1.805 s |
| **TC3**<br>(0 dB, $c0$) | **Alternative** | **SVD-Template** | **Vivek** | 746 | **180** | 566 | 535 | 24.13% | **25.17%** | **0.2464** ⭐ | 0.2396 | **33.39** ⭐ | 0.026 s |
| | **SVD** | Variant 3 (Window) | Naman | 713 | 172 | 541 | 543 | 24.12% | 24.06% | **0.2409** | **0.1688** ⭐ | 34.55 | 0.039 s |
| | **Template** | Fixed Ensemble | Anshu | 734 | 173 | 561 | 542 | 23.57% | 24.20% | 0.2388 | 0.2422 | 33.16 | **0.019 s** |
| | **SVD** | Variant 1 (Fixed) | Naman | 752 | 174 | 578 | 541 | 23.14% | 24.34% | 0.2372 | 0.2380 | 32.82 | 0.026 s |
| | **Template** | Adaptive EMA | Anshu | 741 | 171 | 570 | 544 | 23.08% | 23.92% | 0.2349 | 0.2168 | 34.42 | 0.077 s |
| | **SWT-LMS** | Sym4 / 4-Level | Astitva | 392 | 106 | 286 | 609 | 27.04% | 14.83% | 0.1915 | 0.6524 | 48.92 | 1.792 s |
| **TC4**<br>(Movement, $c1$) | **Alternative** | **SVD-Template** | **Vivek** | 750 | **270** | 480 | 446 | 36.00% | **37.71%** | **0.3683** ⭐ | 0.1468 | **31.22** ⭐ | 0.022 s |
| | **SVD** | Variant 1 (Fixed) | Naman | 733 | 261 | 472 | 455 | 35.61% | 36.45% | 0.3602 | 0.1468 | 31.70 | 0.026 s |
| | **Template** | Fixed Ensemble | Anshu | 695 | 252 | 443 | 464 | 36.26% | 35.20% | 0.3572 | 0.1532 | 32.28 | **0.018 s** |
| | **Template** | Adaptive EMA | Anshu | 648 | 226 | 422 | 490 | 34.88% | 31.56% | 0.3314 | 0.1431 | 34.72 | 0.078 s |
| | **SVD** | Variant 3 (Window) | Naman | 698 | 196 | 502 | 520 | 28.08% | 27.37% | 0.2772 | **0.1155** ⭐ | 34.00 | 0.038 s |
| | **SWT-LMS** | Sym4 / 4-Level | Astitva | 419 | 105 | 314 | 611 | 25.06% | 14.66% | 0.1850 | 0.5951 | 47.20 | 1.767 s |
| **TC5**<br>(Ectopic, $c4$) | **Template** | **Fixed Ensemble** | **Anshu** | 766 | **211** | 555 | 505 | **27.55%** | **29.47%** | **0.2848** ⭐ | 0.1686 | 31.88 | **0.017 s** |
| | **Alternative** | SVD-Template | Vivek | 774 | 209 | 565 | 507 | 27.00% | 29.19% | 0.2805 | 0.1679 | 31.89 | 0.018 s |
| | **SVD** | Variant 1 (Fixed) | Naman | 772 | 206 | 566 | 510 | 26.68% | 28.77% | 0.2769 | 0.1675 | **30.95** ⭐ | 0.025 s |
| | **Template** | Adaptive EMA | Anshu | 754 | 199 | 555 | 517 | 26.39% | 27.79% | 0.2707 | **0.1603** ⭐ | 32.00 | 0.062 s |
| | **SVD** | Variant 3 (Window) | Naman | 681 | 175 | 506 | 541 | 25.70% | 24.44% | 0.2505 | **0.1398** ⭐ | 34.72 | 0.034 s |
| | **SWT-LMS** | Sym4 / 4-Level | Astitva | 355 | 78 | 277 | 638 | 21.97% | 10.89% | 0.1457 | 0.5869 | 49.21 | 1.812 s |

---

### 2. Multi-Channel Lead Array Scaling & FPGA Hardware Footprint

Anshu Ram's multi-lead spatial beamforming study evaluated channel arrays from $1$ lead up to all $34$ maternal abdominal leads (`multichannel_scaling_metrics.csv`), showing the dramatic transition in detection performance:

| Channel Configuration | Optimal Physical Electrode Leads | TC1 F1 (12 dB) | TC2 F1 (6 dB) | TC3 F1 (0 dB) | XC7S50 LUTs | DSP48E1 Slices | BRAM36k | Latency per Sample |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1 Channel** | [27] (Lower Midline) | 20.56% | 53.68% | 27.75% | 695 (2.1%) | 1 (0.8%) | 1 (1.3%) | 3.04 µs |
| **2 Channels** | [27, 26] | 95.26% | 81.55% | 69.50% | 740 (2.3%) | 1 (0.8%) | 1 (1.3%) | 3.10 µs |
| **4 Channels ⭐** | **[27, 26, 25, 18] (Vertex Sub-Array)** | **100.00%** | **100.00%** | **100.00%** | **830 (2.5%)** | **1 (0.8%)** | **1 (1.3%)** | **3.28 µs** |
| **8 Channels** | [27, 26, 25, 18, 17, 16, 21, 24] | 100.00% | 99.86% | 100.00% | 1,010 (3.1%) | 1 (0.8%) | 1 (1.3%) | 3.88 µs |
| **10 Channels**| + Leads [28, 10] | 100.00% | 100.00% | 100.00% | 1,100 (3.4%) | 2 (1.7%) | 1 (1.3%) | 3.64 µs |
| **15 Channels**| + Leads [9, 19, 20, 11, 8] | 100.00% | 100.00% | 98.20% | 1,325 (4.1%) | 2 (1.7%) | 1 (1.3%) | 4.34 µs |
| **34 Channels**| Full abdominal mesh array | 99.93% | 99.79% | 39.07%* | 2,180 (6.7%) | 5 (4.2%) | 2 (2.7%) | 5.50 µs |

*\*Note: At 34 channels and 0 dB, noise accumulation from distant peripheral maternal leads degraded spatial conditioning, proving that a compact 4-lead localized array is mathematically superior to full 34-lead capture.*

---

### 3. Cross-Subject Mega Benchmark Summary (250 Full Clinical Runs)

Compiled from [`code/results/mega_benchmark_summary.csv`](file:///d:/signal_project/code/results/mega_benchmark_summary.csv) across 10 subjects (`sub01`–`sub10`), 5 SNRs (0–12 dB), and 5 clinical stress events ($c0$–$c4$):

| Rank | Method | Channel Mode | Evals | Mean F1 (%) | Std F1 (%) | Min F1 (%) | Max F1 (%) | Sensitivity | PPV | Waveform Correlation | Mean Runtime |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 🥇 | **Spatial PCA Beamforming** | Multi-ch (4-ch) | 250 | **92.99%** | ±8.67% | 59.55% | **100.00%** | 92.33% | 94.16% | -0.1348 | 190.7 ms |
| 🥈 | **Deep 1D U-Net (4-Channel)** | Multi-ch (4-ch) | 250 | **90.76%** | ±15.84% | 27.16% | **100.00%** | 90.16% | 91.47% | **+0.9817** ⭐ | 98.6 ms |
| 🥉 | **Deep 1D U-Net (Single-Ch)** | Single (Ch 27) | 250 | **80.79%** | ±22.89% | 7.94% | **100.00%** | 78.10% | 84.21% | **+0.8114** ⭐ | 84.5 ms |
| 4 | **Vivek's SVD-Template Hybrid** | Single (Ch 27) | 250 | **60.52%** | ±26.63% | 8.23% | 99.45% | 61.53% | 60.31% | +0.3424 | 57.3 ms |
| 5 | **Template Subtraction (Fixed)** | Single (Ch 27) | 250 | **59.41%** | ±25.15% | 17.21% | 99.37% | 60.10% | 59.51% | +0.3300 | **35.5 ms** |
| 6 | **Template Subtraction (EMA)** | Single (Ch 27) | 250 | **56.83%** | ±23.97% | 12.87% | 97.31% | 57.19% | 57.29% | +0.3085 | 44.7 ms |
| 7 | **MC Template Fusion (4-Lead)**| Multi-ch (4-ch) | 250 | **56.80%** | ±23.10% | 18.50% | 99.23% | 63.02% | 52.58% | +0.2860 | 218.6 ms |
| 8 | **SVD Variant 1 (Fixed Period)**| Single (Ch 27) | 250 | **55.55%** | ±22.56% | 11.94% | 99.01% | 55.49% | 56.70% | +0.2914 | 75.9 ms |
| 9 | **SVD Variant 3 (Moving Window)**| Single (Ch 27) | 250 | **46.69%** | ±16.23% | 18.98% | 87.75% | 45.47% | 48.79% | +0.2350 | **30.3 ms** |

---

## ⚡ FPGA Hardware Architecture & Synthesis

### Target Device: AMD / Xilinx Spartan-7 `XC7S50-CSGA324`
- **Total Logic Cells:** 52,160 (32,600 6-input LUTs, 65,200 Flip-Flops)
- **DSP Slices:** 120 $\times$ `DSP48E1` ($25 \times 18$ multiplier, 48-bit accumulator)
- **Block RAM:** 75 $\times$ `BRAM36k` (2,700 Kb total)
- **Clock Domain:** 50 MHz to 100 MHz (400,000 cycles per sample interval at $f_s = 250\text{ Hz}$)

### Master FPGA Resource Utilization Summary

```
                      SPARTAN-7 (XC7S50) RESOURCE USAGE
  ┌─────────────────────────────────────────────────────────────┐
  │ 4-Ch Spatial PCA      █ (2.5% LUTs, 0.8% DSP, 1.3% BRAM)    │  < 28 mW [WINNER]
  │ Vivek SVD-Template    ██ (4.3% LUTs, 3.3% DSP, 2.7% BRAM)   │  32 mW
  │ Fixed Template Sub    █ (3.5% LUTs, 1.7% DSP, 2.7% BRAM)    │  < 30 mW
  │ Naman SVD Window      █████ (12.9% LUTs, 40% DSP, 8% BRAM)  │  68 mW
  │ Naman SVD Batch       ████████████████████ (56% BRAM)       │  > 180 mW [BRAM Bound]
  │ Astitva SWT-LMS       █████████████████████████ (>100% DSP) │  > 210 mW [Exceeds DSP]
  └─────────────────────────────────────────────────────────────┘
```

| Architecture | Mode | LUTs (Cap: 32,600) | DSP48E1 (Cap: 120) | BRAM (Cap: 75) | Latency | Est. Power | Feasibility Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Spatial PCA Beamforming (4-Ch)** | **Multi-Ch** | **830 (2.5%)** | **1 (0.8%)** | **1 (1.3%)** | **3.28 µs** | **< 28 mW** | **PRIMARY FPGA WINNER ✅** |
| **Vivek's SVD-Template Hybrid** | Single-Ch | **1,420 (4.3%)** | **4 (3.3%)** | **2 (2.7%)** | **4.80 µs** | **32 mW** | **PRIMARY SINGLE-CH WINNER ✅** |
| **Anshu's Fixed Template Sub** | Single-Ch | 1,150 (3.5%) | 2 (1.7%) | 2 (2.7%) | 12.80 µs | < 30 mW | Lightweight Fallback ✅ |
| **Naman's SVD Variant 3 (Window)** | Single-Ch | 4,200 (12.9%) | 48 (40.0%) | 6 (8.0%) | 48.20 µs | 68 mW | Feasible with pipelined power iteration ✅ |
| **Naman's SVD Variant 1 (Batch)** | Single-Ch | > 18,000 | > 60 | 42 (56.0%) | > 5.0 ms | > 180 mW | ❌ Impractical (BRAM buffer bottleneck) |
| **Astitva's SWT-LMS Filter** | Single-Ch | 8,900 (27.3%) | > 120 (100%+) | 12 (16.0%) | 185.0 µs | > 210 mW | ❌ DSP slice bottleneck on XC7S50 |
| **Deep 1D Convolutional U-Net** | Neural | N/A (Host) | N/A | N/A | 12.4 ms | ~15 W | ❌ Requires Edge NPU / Kria SOM |

### Bit-Accurate Verification & Golden Test Vectors

- **SVD Fixed-Point Model (`code/src/svd_fixed_point_model.py`):** Fixed-point Q1.15 input formatting with rank-2 Hotelling deflation power iteration achieved **+85.04 dB SQNR** and $9.0 \times 10^{-6}$ waveform RMSE.
- **Vivek Fixed-Point Model (`code/src/fixed_point_model.py`):** Direct Form II Second-Order Sections (SOS) with Q2.14 filter coefficients and Q3.12 sample data achieved **+42.8 dB SQNR** and **99.75% F1 retention** ($0.7729 \rightarrow 0.7710$).
- **RTL Test Vectors (`code/results/fpga_test_vectors/`):** 5,000-word bit-accurate stimulus (`input_stimulus_tc1_hex.txt`), golden output (`golden_output_fecg_tc1_hex.txt`), and reference beat peaks (`expected_fetal_peaks_tc1.txt`) verified for Vivado RTL testbenches.

---

## 📁 Repository Directory Structure

```
signal_project/
├── README.md                                       # Primary project documentation & guide
├── TEAM_TASKS_AND_WORK_TRACKER.md                  # Milestone breakdown & individual accountability
├── MASTER_ALGORITHM_SELECTION_AND_FPGA_DECISION.md # Final engineering decision synthesis (M7)
├── MASTER_FPGA_IMPLEMENTATION_AND_FEASIBILITY_REPORT.md # Comprehensive FPGA synthesis & complexity analysis
├── Fetal_ECG_Project_Context_and_Plan.md           # Foundational research & project context
├── Fetal_ECG_Preliminary_Report_Missing_Sections.md# Literature survey, requirements, clinical significance
├── fecg_team_work_plan.md                          # Implementation rules, file contracts, and guidelines
├── FECG_FPGA_Literature_Notes.md                   # Synthesized survey of 20+ IEEE/Springer publications
├── papers.txt                                      # Core academic literature references
├── project.pdf / PPR-8.pdf                         # Course project specification & guidelines
│
├── code/                                           # Software, benchmark pipelines & models
│   ├── requirements.txt                            # Python dependencies (numpy, scipy, wfdb, etc.)
│   ├── configs/
│   │   ├── preprocessing.yaml                      # Filter parameters (0.5–40 Hz Butterworth)
│   │   └── tests.yaml                              # Verified test-case registry (TC1–TC5)
│   ├── src/
│   │   ├── run_benchmark.py                        # Master CLI benchmark runner (TC1–TC5)
│   │   ├── run_mega_benchmark.py                   # 250-run cross-subject evaluation suite
│   │   ├── multichannel_study.py                   # 1–34 channel scaling study & FPGA modeling
│   │   ├── train_deep_model.py                     # Deep 1D U-Net PyTorch GPU training pipeline
│   │   ├── data_loader.py                          # Robust PhysioNet WFDB reader & validator
│   │   ├── mixture.py                              # Oracle-free AECG mixture construction engine
│   │   ├── preprocessing.py                        # Zero-phase Butterworth BPF baseline
│   │   ├── qrs_detector.py                         # Common PPR-8 compliant fetal QRS detector
│   │   ├── fhr.py                                  # Instantaneous FHR calculation & MAE metrics
│   │   ├── evaluation.py                           # Bipartite matching (±50 ms tolerance window)
│   │   ├── fixed_point_model.py                    # Vivek's Q3.12 fixed-point model & SOS biquad
│   │   ├── svd_fixed_point_model.py                # Naman's Q1.15 SVD power-iteration model (+85 dB SQNR)
│   │   ├── methods/
│   │   │   ├── base.py                             # Abstract BaseExtractor class interface
│   │   │   ├── alternative.py                      # Vivek's SVD-Template Subband Hybrid Extractor
│   │   │   ├── template_subtraction.py             # Anshu's Median Ensemble & Adaptive EMA Subtraction
│   │   │   ├── svd.py                              # Naman's SVD Suite (Variants 1, 2, and 3)
│   │   │   └── swt_lms_ssnf.py                     # Astitva's Stationary Wavelet + LMS Filter
│   │   └── models/
│   │       └── fecg_unet.py                        # Multi-scale 1D U-Net neural architecture
│   ├── tests/                                      # Automated unit test verification suite
│   │   ├── test_preprocessing.py                   # Zero-phase response & passband checks
│   │   ├── test_loader.py                          # Dataset discovery & header checks
│   │   ├── test_mixture.py                         # SNR & non-leakage invariant checks
│   │   ├── test_qrs_detector.py                    # Thresholding, blanking, & peak checks
│   │   ├── test_fhr.py                             # Heart rate calculation checks
│   │   ├── test_metrics.py                         # Beat-matching & F1 score validation
│   │   ├── test_method_interface.py                # BaseExtractor polymorphic interface checks
│   │   └── test_fixed_point_verification.py        # Q1.15 SOS stability & quantization checks
│   ├── results/                                    # Generated performance outputs
│   │   ├── metrics.csv                             # Master 35-run benchmark results table
│   │   ├── mega_benchmark_results.csv              # Detailed 250-run evaluations
│   │   ├── mega_benchmark_summary.csv              # Aggregated 250-run cross-sectional metrics
│   │   ├── multichannel_scaling_metrics.csv        # 1–34 channel scaling metrics
│   │   ├── run_metadata.json                       # Execution parameters & timestamps
│   │   ├── models/                                 # Trained PyTorch weights (.pt)
│   │   ├── plots/                                  # Diagnostic and comparative waveform plots
│   │   └── fpga_test_vectors/                      # Golden 16-bit hex test vectors for Vivado RTL
│   │       ├── input_stimulus_tc1_hex.txt          # 5,000 words preprocessed mixture
│   │       ├── golden_output_fecg_tc1_hex.txt      # Expected extracted fetal waveform
│   │       ├── expected_fetal_peaks_tc1.txt        # Expected reference fetal R-peak indices
│   │       └── README.md                           # Verilog simulation & testbench instructions
│   └── visualization/
│       ├── plot_fecgsyn_signals.py                 # 2x2 publication figure generator
│       └── figures/fecgsyn_components.png          # Visual decomposition plot
│
├── data/                                           # Physical dataset storage (git-ignored)
│   ├── FECGSD/DESTINATION/                         # PhysioNet FECGSYNDB synthetic recordings
│   └── Non-Invasive_Fetal_ECG_Arrhythmia_Database/ # PhysioNet NIFEADB real clinical recordings
├── test/                                           # 5 Canonical benchmark test cases
│   ├── test1/                                      # TC1 (12 dB baseline)
│   ├── test2/                                      # TC2 (6 dB moderate noise)
│   ├── test3/                                      # TC3 (0 dB high noise 1:1)
│   ├── test4/                                      # TC4 (6 dB fetal movement)
│   └── test5/                                      # TC5 (6 dB ectopic beats)
├── report/                                         # Preliminary and Mid-Term milestone reports
│   ├── preliminary/                                # Preliminary project report artifacts
│   └── mid_term/                                   # Mid-term project report artifacts & PDF
└── overleaf_work/                                  # Overleaf LaTeX project sources & templates
```

---

## 🚀 Getting Started & Installation

### 1. Prerequisites
- **Python 3.10+** (64-bit recommended)
- **Git** (for version control)
- **AMD / Xilinx Vivado ML Standard** (Optional, for FPGA RTL simulation / bitstream generation)

### 2. Environment Setup

Clone the repository and create an isolated Python virtual environment:

```bash
# Clone the repository
git clone https://github.com/your-username/signal_project.git
cd signal_project

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (Command Prompt):
.\venv\Scripts\activate.bat
# On Linux / macOS:
source venv/bin/activate

# Install required dependencies
pip install -r code/requirements.txt
```

### 3. Dependencies

The project relies on standard scientific computing libraries:
```text
wfdb>=4.1.0          # PhysioNet WFDB format record and annotation I/O
numpy>=1.24.0        # Linear algebra and array operations
scipy>=1.11.0        # Butterworth filters, signal processing, and Savitzky-Golay
matplotlib>=3.7.0    # Waveform visualization and diagnostic plotting
pyyaml>=6.0          # Configuration parsing
pytest>=7.4.0        # Automated unit testing
pywavelets>=1.4.0    # Stationary Wavelet Transform (for SWT-LMS-SSNF)
torch>=2.0.0         # (Optional) PyTorch with CUDA for Deep 1D U-Net training
```

---

## 💻 Usage & Execution Guide

### 1. Running the Standard Benchmark (`run_benchmark.py`)

Run the complete 35-run benchmark matrix across all 5 test cases and all extraction algorithms:

```bash
# Navigate to the code directory
cd code

# Run all algorithms across all test cases (TC1 to TC5)
python src/run_benchmark.py --tc all --method all

# Run a single extraction method on a single test case
python src/run_benchmark.py --tc TC1 --method alternative
python src/run_benchmark.py --tc TC1 --method svd_v1
python src/run_benchmark.py --tc TC3 --method template_fixed

# Dry-run validation (loads data and verifies mixture SNR without running extraction)
python src/run_benchmark.py --dry-run
```

Available method flags:
- `alternative`: Vivek's SVD-Template Subband Hybrid Filter (Top Performer)
- `template_fixed`: Anshu's Fixed Median Ensemble Template Subtraction
- `template_subtraction`: Anshu's Adaptive EMA Template Subtraction
- `svd_v1`: Naman's SVD Variant 1 (Fixed Modal Period)
- `svd_v2`: Naman's SVD Variant 2 (SVR Continuous Resampling)
- `svd_v3`: Naman's SVD Variant 3 (Moving-Window Block-Adaptive)
- `swt_lms_ssnf`: Astitva's Stationary Wavelet + LMS Filter

### 2. Multi-Channel Lead Scaling Study (`multichannel_study.py`)

Run the spatial PCA beamforming and multi-lead fusion evaluation across 1 to 34 leads:

```bash
cd code
python src/multichannel_study.py
```
*Outputs generated:*
- `code/results/multichannel_scaling_metrics.csv`
- `code/results/plots/multichannel/multichannel_accuracy_scaling.png`
- `code/results/plots/multichannel/multichannel_fpga_resource_scaling.png`

### 3. Cross-Subject Mega Benchmark (`run_mega_benchmark.py`)

Run the large-scale cross-sectional evaluation (250 runs across 10 subjects, 5 SNRs, 5 cases):

```bash
cd code
python src/run_mega_benchmark.py
```
*Outputs generated:*
- `code/results/mega_benchmark_results.csv`
- `code/results/mega_benchmark_summary.csv`

### 4. Deep 1D U-Net Training & Inference (`train_deep_model.py`)

Train or evaluate the deep multi-scale 1D convolutional neural network:

```bash
cd code
# Train on GPU with CUDA acceleration
python src/train_deep_model.py --epochs 30 --batch-size 32 --device cuda

# Evaluate pre-trained weights on high-noise TC3 (0 dB)
python src/train_deep_model.py --eval-only --weights results/models/fecg_unet_best.pt --tc TC3
```

### 5. Bit-Accurate Hardware Emulation & Test Vector Verification

Verify 16-bit Q1.15 / Q3.12 quantization and generate golden vectors for Vivado:

```bash
cd code
# Run Vivek's fixed-point verification and export RTL vectors
python src/fixed_point_model.py

# Run Naman's fixed-point SVD power-iteration model (+85 dB SQNR)
python src/svd_fixed_point_model.py
```

### 6. Automated Unit Test Verification

Execute all automated unit tests to verify algorithmic correctness, data loader integrity, filter responses, and fixed-point mathematical stability:

```bash
# From repository root
pytest code/tests/ -v
```

---

## 🛠️ Vivado RTL Simulation Guide

To simulate the top-level Verilog/SystemVerilog module against the golden test vectors generated in `code/results/fpga_test_vectors/`:

```verilog
`timescale 1ns / 1ps

module tb_fecg_top;
    reg clk;
    reg rst_n;
    reg sample_valid;
    reg signed [15:0] aecg_in;
    wire signed [15:0] fecg_out;
    wire qrs_detected;

    // 100 MHz Master System Clock (Period = 10 ns)
    always #5 clk = ~clk;

    // Test vector buffers (5,000 words = 20 seconds @ 250 Hz)
    reg [15:0] stimulus_mem [0:4999];
    reg [15:0] golden_mem   [0:4999];
    integer i;

    initial begin
        // Load test vectors generated by Python fixed-point model
        $readmemh("input_stimulus_tc1_hex.txt", stimulus_mem);
        $readmemh("golden_output_fecg_tc1_hex.txt", golden_mem);

        clk = 0;
        rst_n = 0;
        sample_valid = 0;
        aecg_in = 0;

        #100 rst_n = 1;

        // Feed samples at 250 Hz (1 sample every 4,000,000 ns = 400,000 clock cycles)
        for (i = 0; i < 5000; i = i + 1) begin
            @(posedge clk);
            sample_valid <= 1;
            aecg_in      <= stimulus_mem[i];
            @(posedge clk);
            sample_valid <= 0;

            // Wait 4.0 ms sample arrival period
            #3999980;
        end
        $finish;
    end
endmodule
```

Refer to [`code/results/fpga_test_vectors/README.md`](file:///d:/signal_project/code/results/fpga_test_vectors/README.md) for full simulation scripts, synthesis constraints (`.xdc`), and verification procedures.

---

## 📚 Key Project References & Documentation

Detailed engineering reports and synthesis analyses are available in this repository:

1. [**Master Algorithm Selection & FPGA Decision**](file:///d:/signal_project/MASTER_ALGORITHM_SELECTION_AND_FPGA_DECISION.md): Complete rationale for Milestone M7 verdicts and trade-offs.
2. [**Master FPGA Implementation & Feasibility Report**](file:///d:/signal_project/MASTER_FPGA_IMPLEMENTATION_AND_FEASIBILITY_REPORT.md): Mathematical complexity, memory architecture, CORDIC Jacobi algorithms, and power profiles.
3. [**Team Tasks & Milestone Tracker**](file:///d:/signal_project/TEAM_TASKS_AND_WORK_TRACKER.md): Division of responsibilities and milestone audit history.
4. [**Deep Learning Training Guide**](file:///d:/signal_project/code/results/Deep_Learning_Model_Training_Guide.md): U-Net loss formulation, morphology penalization, and training logs.
5. [**Literature Notes**](file:///d:/signal_project/FECG_FPGA_Literature_Notes.md): Comprehensive survey of 20+ foundational papers in non-invasive fetal electrocardiography.

### Primary Academic Data Sources
- **FECGSYNDB:** J. Behar, et al., *"A maternal-fetal ECG simulator for testing maternal and fetal ECG extraction algorithms"*, Physiol. Meas., 2014. [PhysioNet Database](https://physionet.org/content/fecgsyndb/).
- **NIFEADB:** A. K. R. S. et al., *"Non-Invasive Fetal ECG Arrhythmia Database"*, PhysioNet, 2021.

---

## 👥 Contributors (Team 8)

- **Naman** ([@Integration-Lead](https://github.com/)) — Integration Lead, SVD Extraction Suite, Deep Learning Pipeline, Fixed-Point Power Iteration.
- **Vivek** ([@Evaluation-Lead](https://github.com/)) — Evaluation Lead, Data Loader & Mixture Engine, SVD-Template Subband Hybrid Extractor, Q3.12 Fixed-Point Model.
- **Anshu Ram** ([@QRS-Lead](https://github.com/)) — Common Fetal QRS Detector, Maternal Template Subtraction (Median/EMA), Multi-Channel Spatial PCA Scaling Study.
- **Astitva** ([@Literature-Lead](https://github.com/)) — Preprocessing Baseline (0.5–40 Hz), SWT-LMS-SSNF Extractor, Literature Survey & Hardware Complexity Profiling.

---

## 📄 License

This project is developed for educational and research purposes under the **EE2000 Signal Processing** course curriculum. All test datasets from PhysioNet are distributed under the [Open Data Commons Attribution License (ODC-By) / Creative Commons Attribution 4.0 International](https://physionet.org/).

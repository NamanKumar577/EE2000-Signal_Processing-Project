# Non-Invasive Fetal ECG Extraction & FPGA Hardware Implementation

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-ee4c2c.svg)](https://pytorch.org/)
[![Target Hardware](https://img.shields.io/badge/FPGA-Xilinx%20Spartan--7%20%7C%20Artix--7-red.svg)](https://www.xilinx.com/products/silicon-devices/fpga/spartan-7.html)
[![Course](https://img.shields.io/badge/EE2000-Signal%20Processing%20Project-green.svg)](#)
[![Template](https://img.shields.io/badge/IEEE%20CVF-Review%20Template%20%28PPR--8%29-purple.svg)](#)
[![Milestones](https://img.shields.io/badge/Mid--Term%20Status-Verified%20%E2%9C%85-brightgreen.svg)](#)

---

## 📖 Executive Summary

This repository hosts the complete algorithmic research, multi-channel spatial beamforming pipelines, deep learning models, bit-accurate fixed-point software models, and FPGA hardware architectural sizing for the **EE2000 Signal Processing Course Project (Paper ID: 0008)** by **Team 8**.

The primary objective is the extraction of the weak **Fetal Electrocardiogram (FECG)** ($20$--$100\,\mu\text{V}$) from composite maternal **Abdominal Electrocardiogram (AECG)** mixtures ($1.0$--$5.0\,\text{mV}$, $20$--$34\,\text{dB}$ peak disparity) and the continuous estimation of **Fetal Heart Rate (FHR)**, followed by edge deployment on low-cost, low-power **AMD / Xilinx Spartan-7 (`XC7S50`)** FPGAs (Boolean Board).

### Submission Deliverables (Mid-Term Milestone)
- **Canonical Mid-Term Report (PDF):** [`report/mtr-8.pdf`](report/mtr-8.pdf) *(18 pages, compiled in strict accordance with the official IEEE CVF Conference Review Template with line numbers, confidential review banner, and all post-PPR contributions clearly highlighted in blue colored text).*
- **Complete Submission Package (ZIP):** [`report/mtr-8.zip`](report/mtr-8.zip) *(24.6 MB, self-contained archive containing the canonical report, full source code, unit tests, verification tools, trained models, and benchmark CSVs).*
- **Comprehensive Audit Changelog:** [`report/mid_term/CHANGELOG_MTR8.md`](report/mid_term/CHANGELOG_MTR8.md) *(Detailed log of every mathematical, theoretical, and experimental revision).*

---

### Team 8 Members & Technical Roles

| Member | Primary Extraction Architecture | Shared System Responsibility | Key Delivered Modules |
| :--- | :--- | :--- | :--- |
| **Naman** | **SVD Extraction Suite (Variants 1, 2, 3)** | **Integration Lead & System Architecture** | `code/src/methods/svd.py`<br>`code/src/svd_fixed_point_model.py`<br>`code/src/train_deep_model.py`<br>`code/src/run_benchmark.py` |
| **Vivek** | **Wavelet-Threshold Hybrid & SVD-Template** | **Evaluation Lead & Data Auditor** | `code/src/methods/alternative.py`<br>`code/src/data_loader.py`<br>`code/src/mixture.py`<br>`code/src/evaluation.py`<br>`code/src/fixed_point_model.py` |
| **Anshu Ram** | **Maternal Template Subtraction (Median/EMA)** | **Common QRS Detector & Multi-Channel Study** | `code/src/methods/template_subtraction.py`<br>`code/src/qrs_detector.py`<br>`code/src/multichannel_study.py` |
| **Astitva** | **SWT + LMS + SSNF Wavelet Hybrid** | **Preprocessing Baseline & Literature Survey** | `code/src/methods/swt_lms_ssnf.py`<br>`code/src/preprocessing.py`<br>`FECG_FPGA_Literature_Notes.md` |

---

## 🔬 Clinical Motivation & Signal Processing Problem

### 1. Biophysical Signal Characteristics
- **Extreme Amplitude Masking:** Maternal ECG dominates abdominal recordings by $10$--$50\times$ in peak amplitude ($1.0$--$5.0\,$mV vs $20$--$100\,\mu$V, $20$--$34\,$dB peak disparity). Root-mean-square (RMS) fetal-to-maternal ratio (FMR) spans $-14.0\,$dB to $-5.4\,$dB ($0.20$ to $0.54$).
- **Complete Spectral Overlap:** Both maternal and fetal biopotentials occupy the identical $0.5$--$40\,$Hz physiological band, rendering classical linear single-channel frequency filtering ineffective.
- **Temporal QRS Collisions:** 
  - Probability that a fetal QRS complex overlaps a maternal QRS: $(w_m + w_f)/T_m = (90 + 50)/800 = \mathbf{17.5\%}$.
  - Fraction of maternal beats overlapped by a fetal QRS: $(w_m + w_f)/T_f = (90 + 50)/430 = \mathbf{32.6\%}$.
  - Complete fetal QRS containment within maternal QRS: $(w_m - w_f)/T_m = (90 - 50)/800 = \mathbf{5.0\%}$.
  - During temporal collisions, single-channel subtraction algorithms actively annihilate fetal complexes, causing catastrophic detection dropouts ($<24\%$ F1 at $0\,$dB).

### 2. Multi-Channel Signal Processing Cascade

```text
  Raw Abdominal Electrodes (Channels 27, 26, 28, 25 @ 250 Hz)
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│     4-Section Butterworth SOS Bandpass Filter          │  Passband: 0.5 Hz – 40.0 Hz (Direct Form II, 8th-order)
│           Baseline Wander & Noise Removal              │  > 56 dB attenuation @ 0.1 Hz; > 18 dB @ 60 Hz mains
│                                                        │  QRS band group delay: 11.4 – 15.4 ms (2.9 – 3.9 samples)
└────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│     4-Channel Spatial PCA Beamforming Engine           │  Observation buffer: N = 750 samples (3.0 s)
│           (Covariance & Power Iteration)               │  Sample covariance: R_xx = (1/N) X X^T in R^{4 x 4}
│                                                        │  Extracts w = v_2 (second principal component)
└────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│       Standardized Fetal QRS Peak-Energy Detector      │  1. 5-point derivative: h[n] = (1/8)[-1, -2, 0, 2, 1]
│            (Pan-Tompkins Inspired Topology)            │  2. Energy squaring: z[n] = y^2[n] (sign-invariant)
│                                                        │  3. Moving Window Integrator (W = 15 samples = 60 ms)
│                                                        │  4. Dual adaptive thresholding (SPKI / NPKI via EMA)
│                                                        │  5. Physiological refractory blanking (50 samples = 200 ms)
└────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│        Fetal Heart Rate (FHR) & Clinical Metrics       │  • Instantaneous FHR = 60 / RR_k (bpm)
│           (PhysioNet CinC 2013 Compliance)             │  • 5-beat causal median filter for ectopic artifact rejection
│                                                        │  • Bipartite matching with ±50 ms tolerance window
│                                                        │  • Sensitivity (Se), PPV, F1-Score, FHR MAE, and RMSE
└────────────────────────────────────────────────────────┘
```

---

## 🛡️ Strict Disjoint Cross-Subject Partitioning Protocol

To eliminate data leakage, prevent anatomical contamination, and ensure true clinical generalization, the 250-record PhysioNet FECGSYNDB database ($250 \times 75,000 \times 34 \times 4\text{ bytes} = 2.55\,$GB in 32-bit float; $1.28\,$GB in 16-bit WFDB format) is split strictly at the subject level:

| Partition | Proportion | Subjects | Records | Size (Float32) | Functional Role |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **Training** | **70%** | `sub01`–`sub07` | 175 | 1.79 GB | Deep U-Net weight optimization; hyperparameter freezing ($N=750$, detector thresholds, lead array $\mathcal{C}_{\text{opt}}$). |
| **Validation** | **10%** | `sub08` | 25 | 0.26 GB | Early stopping and threshold tuning. |
| **Held-Out Test** | **20%** | `sub09`–`sub10` | 50 | 0.51 GB | **Completely untouched during design/tuning.** Evaluated strictly once to assess anatomical generalization. |
| **All Subjects** | **100%** | `sub01`–`sub10` | 250 | 2.55 GB | Full population cross-sectional benchmark (2,250 runs). |

> [!IMPORTANT]
> **Training-Only Lead Selection:** Lead selection was performed strictly on `sub01`–`sub07`. FMR topography revealed that maternal potentials dominate epigastric leads (Channels 0–11, FMR $<0.22$), while fetal coupling peaks in lower suprapubic leads (Channels 25–28, reaching $\text{FMR} = 0.46$ on Lead 27, and $0.54$ on `sub01`). This isolated the optimal 4-lead suprapubic sub-array:
> $$\mathcal{C}_{\text{opt}} = \{ \text{Lead } 27, \text{Lead } 26, \text{Lead } 28, \text{Lead } 25 \} \quad \text{(0-based)}$$

---

## 📊 Comprehensive Experimental Benchmark Results

### 1. Population Mega-Benchmark across All 250 Records (2,250 Runs)

Evaluated across all 10 subjects, 5 SNR tiers ($0$--$12\,$dB), and 5 clinical stress cases ($c0$--$c4$). Confidence intervals are 95% Subject-Clustered CIs (Student-$t$, $df=9$, $t_{\text{crit}}=2.262$):

| Rank | Extraction Architecture | Config | Mean F1 (95% Clustered CI) | Min F1 | Max F1 | FHR MAE | Agr. ($\pm 5\,$bpm) | $|\rho|$ | Runtime / Record |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 🥇 | **Spatial PCA Beamforming** | **4-Ch** | **93.00%** [90.65, 95.34] | 59.55% | **100.0%** | 6.57 bpm | 58.0% | 0.513 | 190.7 ms |
| 🥈 | **Deep 1D Convolutional U-Net** | **4-Ch** | **90.76%** [83.48, 98.03] | 27.16% | **100.0%** | **3.57 bpm** | **69.2%** | **0.982** | **98.6 ms** |
| 🥉 | Deep 1D Convolutional U-Net | 1-Ch | 80.79% [72.63, 88.96] | 7.94% | 100.0% | 8.18 bpm | 46.4% | 0.811 | 84.5 ms |
| 4 | Wavelet-Threshold Hybrid | 1-Ch | 60.52% [53.43, 67.60] | 8.23% | 99.45% | 25.16 bpm | 10.4% | 0.342 | 57.3 ms |
| 5 | Template Subtraction (Fixed) | 1-Ch | 59.41% [51.83, 66.99] | 17.21% | 99.37% | 25.41 bpm | 10.0% | 0.330 | **35.5 ms** |
| 6 | Template Subtraction (Adaptive) | 1-Ch | 56.83% [49.83, 63.82] | 12.87% | 97.31% | 27.44 bpm | 2.0% | 0.308 | 44.7 ms |
| 7 | Multi-Lead Template Fusion | 4-Ch | 56.80% [50.78, 62.82] | 18.50% | 99.23% | 28.29 bpm | 8.8% | 0.286 | 218.6 ms |
| 8 | Hankel-SVD V1 (Fixed Period) | 1-Ch | 55.55% [47.21, 63.89] | 11.94% | 99.01% | 26.84 bpm | 6.0% | 0.291 | 75.9 ms |
| 9 | Hankel-SVD V3 (Moving Window) | 1-Ch | 46.69% [40.80, 52.59] | 18.98% | 87.75% | 32.59 bpm | 0.0% | 0.235 | **30.3 ms** |

*Run-level 95% CI half-widths across all $N=250$ records: $\pm 1.08\%$ for Spatial PCA (SE $0.55\%$) and $\pm 1.97\%$ for Deep U-Net (SE $1.00\%$).*

---

### 2. Disjoint Partition Breakdown (Train vs. Val vs. Held-Out Test)

| Algorithm | Train (`sub01`–`07`) | Val (`sub08`) | Held-Out Test (`sub09`–`10`) | All (`sub01`–`10`) |
| :--- | :---: | :---: | :---: | :---: |
| **Spatial PCA (4-Ch)** | **92.90%** (6.16 bpm) | 93.51% (4.66 bpm) | 93.06% (8.00 bpm) | **93.00%** (6.57 bpm) |
| **Deep 1D U-Net (4-Ch)** | 88.13% (3.97 bpm) | **95.69%** (3.03 bpm) | **97.48%** (2.43 bpm) | 90.76% (3.57 bpm) |
| Deep 1D U-Net (1-Ch) | 79.17% (8.48 bpm) | 85.89% (7.37 bpm) | 83.93% (7.51 bpm) | 80.79% (8.18 bpm) |
| Wavelet-Threshold Hybrid | 60.47% | 60.93% | 60.46% | 60.52% |
| Template Sub. (Fixed) | 59.26% | 61.32% | 59.01% | 59.41% |
| Template Sub. (Adaptive) | 56.81% | 58.11% | 56.24% | 56.83% |
| MC Template Fusion | 57.47% | 55.45% | 55.14% | 56.80% |
| Hankel-SVD V1 (Fixed) | 57.20% | 55.56% | 49.76% | 55.55% |
| Hankel-SVD V3 (Moving) | 47.57% | 46.75% | 43.60% | 46.69% |

---

### 3. Per-Subject Consistency Table across All 10 Simulated Subjects

25 records per subject across varying SNRs ($0$--$12\,$dB) and clinical conditions ($c0$--$c4$):

| Method / Metric | `sub01` | `sub02` | `sub03` | `sub04` | `sub05` | `sub06` | `sub07` | `sub08` | `sub09` | `sub10` | Mean |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Spatial PCA F1 (%)** | 94.67 | 94.59 | 95.60 | 85.90 | 89.11 | 96.61 | 93.87 | 93.51 | 94.66 | 91.45 | **93.00** |
| **Spatial PCA MAE (bpm)** | 5.47 | 5.07 | 5.38 | 11.39 | 7.73 | 4.48 | 5.49 | 4.66 | 8.76 | 7.25 | **6.57** |
| **Deep U-Net F1 (%)** | 97.47 | 94.13 | 92.93 | 78.85 | 71.95 | 90.07 | 91.53 | 95.69 | 97.90 | 97.07 | **90.76** |
| **Deep U-Net MAE (bpm)** | 2.15 | 2.72 | 3.01 | 6.44 | 7.15 | 3.27 | 3.05 | 3.03 | 2.21 | 2.65 | **3.57** |

---

### 4. Breakdown by Clinical Stress Condition and Noise SNR Tier

Explains why overall FHR MAE is $6.57\,$bpm despite $93.00\%$ F1 score:

| Subset Partition | Spatial PCA F1 | Spatial PCA MAE | Spatial PCA Agr. | Deep U-Net F1 | Deep U-Net MAE | Deep U-Net Agr. |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Condition:** | | | | | | |
| $c0$: Baseline Normal | 96.94% | 3.29 bpm | 74.0% | 99.33% | 0.96 bpm | 98.0% |
| $c1$: Fetal Movement | 90.80% | 7.19 bpm | 46.0% | 93.52% | 3.14 bpm | 76.0% |
| $c2$: Heart-Rate Dynamics | 97.36% | 2.99 bpm | 82.0% | 92.32% | 1.99 bpm | 86.0% |
| $c3$: Uterine Contractions | 96.82% | 3.27 bpm | 82.0% | 87.60% | 2.35 bpm | 72.0% |
| $c4$: Arrhythmia / PVCs | **83.06%** | **16.10 bpm** | **6.0%** | **81.02%** | **9.39 bpm** | **14.0%** |
| **Noise SNR Tier:** | | | | | | |
| 0 dB (High Noise) | 93.68% | 6.05 bpm | 54.0% | 91.06% | 3.75 bpm | 68.0% |
| 3 dB | 91.95% | 7.45 bpm | 58.0% | 90.35% | 3.78 bpm | 66.0% |
| 6 dB (Moderate Noise) | 92.73% | 6.51 bpm | 56.0% | 91.14% | 3.42 bpm | 70.0% |
| 9 dB | 91.40% | 7.72 bpm | 56.0% | 90.18% | 3.71 bpm | 68.0% |
| 12 dB (Low Noise) | 95.22% | 5.11 bpm | 66.0% | 91.05% | 3.20 bpm | 74.0% |

> [!NOTE]
> Under normal rhythm conditions ($c0, c2, c3$), Spatial PCA achieves **$2.99$--$3.29\,$bpm MAE** and **$74$--$82\%$ clinical agreement**. The overall population MAE ($6.57\,$bpm) and agreement ($58.0\%$) are driven entirely by $c4$ (arrhythmia with ectopic beats), where missed PVCs create $16.10\,$bpm MAE.

---

### 5. Frozen 35-Run Subject 1 In-Sample Stress Benchmark (`metrics.csv`)

| Test Case | Method | Configuration | Det. | Ref. | TP | FP | FN | PPV | Sensitivity | F1-Score | FHR MAE | Agr. ($\pm 5\,$bpm) | Runtime |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **TC1** (12 dB, $c0$) | **Spatial PCA** | **4-Ch** | 716 | 716 | **716** | **0** | **0** | **100.0%** | **100.0%** | **100.00%** | **0.32 bpm** | **100.0%** | **0.003 s** |
| | Deep 1D U-Net | 1-Ch | 712 | 716 | 712 | 0 | 4 | 100.0% | 99.4% | 99.72% | 0.45 bpm | 99.7% | 0.082 s |
| | MC Template Fusion | 4-Ch | 716 | 716 | 700 | 16 | 16 | 97.8% | 97.8% | 97.77% | 1.85 bpm | 95.8% | 0.012 s |
| | Wavelet Hybrid | 1-Ch | 715 | 716 | 553 | 162 | 163 | 77.3% | 77.2% | 77.29% | 18.30 bpm | 62.4% | 0.020 s |
| | Template Sub. (Fixed) | 1-Ch | 714 | 716 | 546 | 168 | 170 | 76.5% | 76.3% | 76.36% | 19.54 bpm | 61.2% | 0.018 s |
| | Hankel-SVD V1 | 1-Ch | 714 | 716 | 546 | 168 | 170 | 76.5% | 76.3% | 76.36% | 19.52 bpm | 61.2% | 0.026 s |
| | SWT-LMS Wavelet | 1-Ch | 373 | 716 | 82 | 291 | 634 | 22.0% | 11.5% | 15.06% | 46.64 bpm | 14.2% | 1.772 s |
| **TC2** (6 dB, $c0$) | **Spatial PCA** | **4-Ch** | 716 | 716 | **716** | **0** | **0** | **100.0%** | **100.0%** | **100.00%** | **0.41 bpm** | **100.0%** | **0.003 s** |
| | Deep 1D U-Net | 1-Ch | 713 | 716 | 713 | 0 | 3 | 100.0% | 99.6% | 99.79% | 0.42 bpm | 99.8% | 0.082 s |
| | MC Template Fusion | 4-Ch | 751 | 716 | 690 | 61 | 26 | 91.9% | 96.4% | 94.07% | 2.45 bpm | 93.4% | 0.012 s |
| | Wavelet Hybrid | 1-Ch | 749 | 716 | 230 | 519 | 486 | 30.7% | 32.1% | 31.40% | 32.99 bpm | 38.6% | 0.020 s |
| | Hankel-SVD V1 | 1-Ch | 743 | 716 | 226 | 517 | 490 | 30.4% | 31.6% | 30.98% | 34.47 bpm | 37.2% | 0.027 s |
| | Template Sub. (Fixed) | 1-Ch | 717 | 716 | 221 | 496 | 495 | 30.8% | 30.9% | 30.84% | 34.33 bpm | 37.4% | 0.018 s |
| | SWT-LMS Wavelet | 1-Ch | 446 | 716 | 102 | 344 | 614 | 22.9% | 14.2% | 17.56% | 42.65 bpm | 18.5% | 1.805 s |
| **TC3** (0 dB, $c0$) | **Spatial PCA** | **4-Ch** | 715 | 715 | **715** | **0** | **0** | **100.0%** | **100.0%** | **100.00%** | **0.48 bpm** | **100.0%** | **0.003 s** |
| | Deep 1D U-Net | 1-Ch | 706 | 715 | 706 | 0 | 9 | 100.0% | 98.7% | 99.37% | 0.65 bpm | 99.2% | 0.082 s |
| | MC Template Fusion | 4-Ch | 819 | 715 | 241 | 578 | 474 | 29.4% | 33.7% | 31.42% | 31.20 bpm | 41.2% | 0.012 s |
| | Wavelet Hybrid | 1-Ch | 746 | 715 | 180 | 566 | 535 | 24.1% | 25.2% | 24.64% | 33.39 bpm | 35.8% | 0.026 s |
| | Template Sub. (Fixed) | 1-Ch | 734 | 715 | 173 | 561 | 542 | 23.6% | 24.2% | 23.88% | 33.16 bpm | 36.2% | 0.019 s |
| | Hankel-SVD V1 | 1-Ch | 752 | 715 | 174 | 578 | 541 | 23.1% | 24.3% | 23.72% | 32.82 bpm | 36.5% | 0.026 s |
| | SWT-LMS Wavelet | 1-Ch | 392 | 715 | 106 | 286 | 609 | 27.0% | 14.8% | 19.15% | 48.92 bpm | 12.8% | 1.792 s |
| **TC4** (6 dB, $c1$) | **Deep 1D U-Net** | 1-Ch | 710 | 716 | 710 | 0 | 6 | 100.0% | 99.2% | **99.58%** | **0.58 bpm** | **99.4%** | 0.082 s |
| | **Spatial PCA** | **4-Ch** | 721 | 716 | 523 | 198 | 193 | 72.5% | 73.0% | 72.79% | 8.42 bpm | 82.5% | **0.003 s** |
| | MC Template Fusion | 4-Ch | 790 | 716 | 441 | 349 | 275 | 55.8% | 61.6% | 58.57% | 14.20 bpm | 71.8% | 0.012 s |
| | Wavelet Hybrid | 1-Ch | 750 | 716 | 270 | 480 | 446 | 36.0% | 37.7% | 36.83% | 31.22 bpm | 42.1% | 0.022 s |
| | Hankel-SVD V1 | 1-Ch | 733 | 716 | 261 | 472 | 455 | 35.6% | 36.5% | 36.02% | 31.70 bpm | 41.5% | 0.026 s |
| | Template Sub. (Fixed) | 1-Ch | 695 | 716 | 252 | 443 | 464 | 36.3% | 35.2% | 35.72% | 32.28 bpm | 41.0% | 0.018 s |
| | SWT-LMS Wavelet | 1-Ch | 419 | 716 | 105 | 314 | 611 | 25.1% | 14.7% | 18.50% | 47.20 bpm | 16.4% | 1.767 s |
| **TC5** (6 dB, $c4$) | **Deep 1D U-Net** | 1-Ch | 713 | 716 | 675 | 38 | 41 | 94.7% | 94.3% | **94.47%** | **2.10 bpm** | **93.8%** | 0.082 s |
| | **Spatial PCA** | **4-Ch** | 662 | 716 | 606 | 56 | 110 | 91.5% | 84.6% | 87.95% | 3.15 bpm | 91.2% | **0.003 s** |
| | MC Template Fusion | 4-Ch | 833 | 716 | 519 | 314 | 197 | 62.3% | 72.5% | 67.01% | 12.80 bpm | 74.5% | 0.012 s |
| | Template Sub. (Fixed) | 1-Ch | 766 | 716 | 211 | 555 | 505 | 27.5% | 29.5% | 28.48% | 31.88 bpm | 41.2% | 0.017 s |
| | Wavelet Hybrid | 1-Ch | 774 | 716 | 209 | 565 | 507 | 27.0% | 29.2% | 28.05% | 31.89 bpm | 40.8% | 0.018 s |
| | Hankel-SVD V1 | 1-Ch | 772 | 716 | 206 | 566 | 510 | 26.7% | 28.8% | 27.69% | 30.95 bpm | 42.0% | 0.025 s |
| | SWT-LMS Wavelet | 1-Ch | 355 | 716 | 78 | 277 | 638 | 22.0% | 10.9% | 14.57% | 49.21 bpm | 11.5% | 1.812 s |

---

## ⚡ Fixed-Point Modeling & FPGA Architectural Sizing

### 1. Bit-True Q1.15 Fixed-Point Software Model [L2]
- **AFE Scaling & Dynamic Range:** Input range of $\pm 5.0\,$mV maps to $[-1.0, +1.0)$ in signed Q1.15 two's complement.
  $$\Delta = \frac{5.0\,\text{mV}}{32768} \approx 0.152\,\mu\text{V per LSB}$$
  A $20\,\mu$V fetal peak corresponds to $131$ LSBs, while a $2.5\,$mV maternal peak occupies $16,384$ LSBs.
- **SQNR Verification:** Evaluated across 5,000 continuous golden test samples generated by `code/src/fixed_point_model.py`:
  $$\text{SQNR} = \mathbf{+85.04\,dB} \quad (\text{Waveform RMSE} = 9.0 \times 10^{-6}\,\text{nu})$$
- **Theoretical Null Depth Bound:**
  $$R_{\text{null}} \approx 20 \log_{10} \left[ \frac{\sqrt{12} \cdot 2^{B-1}}{\sqrt{C}} \right] = 20 \log_{10} \left[ \frac{\sqrt{12} \cdot 32768}{2} \right] = \mathbf{95.1\,dB}$$
  Bit-true simulation achieves **$95.0\,$dB**, exceeding the $55\,$dB clinical threshold with $>20\,$dB noise margin.

### 2. Spartan-7 FPGA (XC7S50-1CSGA324C) Hardware Sizing [L4 Target]
- **Compute Sizing:** 4-channel inner product $y[n] = \sum_{c=1}^4 w_c x_c[n]$ maps to a single time-multiplexed DSP48E1 slice.
- **Latency & Throughput:**
  - DSP execution time: **128 clock cycles** ($1.28\,\mu$s at 100 MHz).
  - Sample arrival period: $T_s = 1/250\,\text{Hz} = 4,000\,\mu$s ($400,000$ cycles).
  - **Real-Time Margin:** $4,000 / 1.28 = \mathbf{3,125\times}$ safety headroom.
- **Resource Footprint:** 830 LUTs ($2.5\%$), 620 FFs ($1.0\%$), 1 DSP48E1 slice ($0.8\%$), 1 BRAM ($1.3\%$), estimated power $< 28\,$mW.

---

## 🛠️ Reproduction & Verification Guide

### 1. Environment Setup
```bash
# Clone the repository
git clone https://github.com/your-username/signal_project.git
cd signal_project

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell
source venv/bin/activate     # Linux / macOS

# Install all dependencies
pip install -r code/requirements.txt
```

### 2. Automated Consistency Checker (MTR-8 V2 Audit)
Executes all 8 automated mathematical, statistical, and consistency checks:
```bash
python code/tools/check_consistency.py
```
*Expected Output:* `ALL MTR-8 V2 CONSISTENCY CHECKS PASSED WITH 100% SUCCESS!`

### 3. Re-compile Report PDF & Package Final Submission
```bash
# Generate empirical numbers macro file (numbers.tex)
python code/tools/make_numbers_tex.py

# Recompile canonical report (18 pages, IEEE CVF review template with blue highlights)
python report/mid_term/build_full_report.py

# Package canonical zip archive in report/
python report/mid_term/tools/package_submission.py
```

---

## 📄 Compliance & Declarations

### AI Usage Disclosure (Section 19 Compliance)
In strict adherence to the course policy:
- **Tools Employed:** Anthropic Claude (Claude 3.5 Sonnet) and OpenAI ChatGPT (GPT-4o).
- **Assisted Areas:** Boilerplate PyTorch DataLoader syntax, automated consistency check scripts, DSP time-multiplexing schedule calculation, and LaTeX table structuring.
- **Independent Validation:** All numbers, tables, CIs, and metrics were generated locally on physical workstations and verified directly against raw CSV outputs (`code/results/mega_benchmark_results.csv`). The team is fully prepared to defend and re-derive any equation, algorithm, or circuit block during oral viva.

---

## 📚 Primary Academic Citations

1. **[FECGSYNDB]** J. Behar et al., *"A maternal-fetal ECG simulator for testing maternal and fetal ECG extraction algorithms,"* Physiol. Meas., vol. 35, no. 8, pp. 1537–1550, 2014.
2. **[PhysioNet Challenge 2013]** I. Silva et al., *"Noninvasive fetal ECG: the PhysioNet/Computing in Cardiology Challenge 2013,"* Comput. Cardiol., vol. 40, pp. 149–152, 2013.
3. **[Andreotti Framework]** F. Andreotti, J. Behar, F. Zaunseder, J. Oster, and G. D. Clifford, *"An open-source framework for stress-testing non-invasive fetal ECG extraction algorithms,"* Physiol. Meas., vol. 37, no. 5, pp. 627–648, 2016.
4. **[Pan-Tompkins]** J. Pan and W. J. Tompkins, *"A real-time QRS detection algorithm,"* IEEE Trans. Biomed. Eng., vol. BME-32, no. 3, pp. 230–236, 1985.
5. **[De Lathauwer Subspace]** L. De Lathauwer, B. De Moor, and J. Vandewalle, *"Fetal electrocardiogram extraction by blind source subspace separation,"* IEEE Trans. Biomed. Eng., vol. 47, no. 5, pp. 567–572, 2000.

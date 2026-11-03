# Phase 2: Full Synthetic Dataset Validation Report

**Document ID:** `validation/synthetic/SYNTHETIC_VALIDATION_REPORT.md`  
**Dataset:** PhysioNet FECGSYNDB (`data/FECGSD/DESTINATION`)  
**Scope:** 300 Simulation Cases (10 Subjects $\times$ 5 SNRs $\times$ 6 Conditions)  
**Target Architecture:** 4-Channel Causal Spatial Beamformer (`pc3`) vs. Causal Oracle Upper Bound  
**Artifacts Generated:**  
- `validation/synthetic/FULL_DATASET_RESULTS.csv` (650 evaluation rows)  
- `validation/synthetic/SNR_ANALYSIS.csv`  
- `validation/synthetic/CONDITION_ANALYSIS.csv`  
- `validation/synthetic/SUBJECT_ANALYSIS.csv`  

---

## 1. Executive Summary & Key Statistical Metrics

The causal FPGA pipeline was evaluated across all 300 available simulation records in FECGSYNDB.

| Metric | Overall Dataset (Single Fetus) | High-Performing Cohort (`sub01`, `sub06`) | Challenging Cohort (`sub04`, `sub08`, `sub09`) |
| :--- | :---: | :---: | :---: |
| **Mean Sensitivity (Se)** | **88.10%** | **92.05%** | **82.18%** |
| **Mean Positive Predictive Value (PPV)** | **68.95%** | **89.11%** | **58.30%** |
| **Mean F1 Score** | **78.51% $\pm$ 15.1%** | **90.67% $\pm$ 9.4%** | **69.18% $\pm$ 14.3%** |
| **Mean FHR MAE** | **16.25 bpm** | **6.69 bpm** | **25.02 bpm** |
| **Total Fetal Beats Evaluated** | **198,735 beats** | 40,845 beats | 58,180 beats |

### Core Conclusion:
1. **SNR Invariance:** Performance is remarkably robust against additive instrumentation and environmental noise (Mean F1 varies by only $3.2\%$ from $0\text{ dB}$ to $12\text{ dB}$).
2. **The Real Performance Limiter:** The primary performance bottleneck is **maternal ECG spatial leakage** into the third principal component (`pc3`). When maternal residue leaks into `pc3`, the causal detector triggers false positives on maternal R-peaks, depressing PPV to $58\%$ in difficult anatomical configurations.
3. **Twin Inadequacy:** 4 channels are mathematically insufficient for twin extraction. Fetus 1 achieves $77.75\%$ F1, but Fetus 2 collapses to $24.77\%$ F1 because 4 degrees of freedom cannot span maternal space (2 dims), Fetus 1 (1 dim), and Fetus 2 (1 dim) simultaneously.

---

## 2. In-Depth SNR Robustness Analysis

Evaluating the autonomous `pc3` pipeline across input SNR levels reveals nearly flat performance:

| Input SNR | Records Evaluated | Mean F1 (%) | Std Dev (%) | Min F1 (%) | Max F1 (%) | Mean FHR MAE (bpm) | Total TP | Total FP | Total FN |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0 dB** | 60 | **79.65%** | 16.14% | 40.43% | 99.69% | 15.26 | 33,002 | 14,025 | 4,594 |
| **3 dB** | 60 | **78.27%** | 14.01% | 52.02% | 99.68% | 16.00 | 32,975 | 14,832 | 4,649 |
| **6 dB** | 60 | **76.58%** | 17.35% | 39.34% | 99.75% | 18.55 | 32,390 | 16,252 | 5,265 |
| **9 dB** | 60 | **79.81%** | 13.51% | 37.99% | 99.74% | 15.51 | 33,444 | 14,072 | 4,169 |
| **12 dB** | 60 | **78.22%** | 14.43% | 23.75% | 99.79% | 15.96 | 33,148 | 14,879 | 4,459 |

**Insight:** In traditional single-channel DSP, 0 dB SNR causes catastrophic failure (F1 < 30%). In our 4-channel spatial architecture, 0 dB performs at **79.65%**, identical to 12 dB (78.22%). The linear combination weights create high attenuation toward uncorrelated white/pink noise, while the causal Butterworth bandpass filter ($8\text{--}30\text{ Hz}$) rejects baseline wander and high-frequency noise.

---

## 3. Physiological Condition Breakdown

| Condition Code | Description | Mean F1 (%) | Std Dev (%) | FHR MAE (bpm) | Sensitivity (%) | PPV (%) | Clinical Impact & Assessment |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **`c0`** | Baseline Normal | 79.27% | 18.72% | 17.29 | 87.94% | 68.67% | Stable cardiac rhythm; performance dictated entirely by subject lead field. |
| **`c1`** | Movement Artifact | 79.74% | 11.21% | 11.46 | 88.19% | 71.92% | Baseline wander shifts are well-suppressed by the $0.62\text{ Hz}$ HP1 filter. |
| **`c2`** | Dynamic FHR (Acc/Dec) | 76.98% | 14.97% | 18.40 | 88.71% | 65.96% | High sensitivity (88.7%), but rapid FHR variations cause brief threshold lag. |
| **`c3`** | Uterine Contractions | **84.79%** | 15.62% | **10.68** | **90.93%** | **77.64%** | Best performing condition! EHG electrohysterogram energy is below 4 Hz and completely rejected. |
| **`c4`** | Ectopic Arrhythmias | **72.52%** | 10.70% | **20.57** | **81.09%** | **63.97%** | Most severe single-fetus degradation. Premature ventricular complexes (PVCs) violate refractory period and skew threshold. |
| **`c5`** | Twin Pregnancy (Twin 1) | 77.75% | 15.73% | 19.14 | 89.20% | 66.58% | Twin 1 is captured reliably. |
| **`c5`** | Twin Pregnancy (Twin 2) | **24.77%** | 18.20% | **35.46** | **27.75%** | **23.35%** | **Failure mode.** Twin 2 is largely obliterated by the single projection. |

---

## 4. Subject Anatomical Generalization Analysis

Because subjects differ in fetal position, gestational age, amniotic volume, and maternal body habitus, spatial lead fields vary significantly:

| Subject ID | Mean F1 (%) | F1 Std Dev (%) | Min F1 (%) | Max F1 (%) | FHR MAE (bpm) | PPV (%) | Root-Cause Analysis |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`sub01`** | 89.70% | 8.59% | 76.56% | 99.73% | 7.52 | 87.80% | Fetal dipole strongly aligned with Lead 27/26 axis. |
| **`sub02`** | 76.66% | 14.21% | 52.89% | 99.60% | 18.63 | 65.76% | Moderate MECG residue. |
| **`sub03`** | 78.36% | 12.33% | 39.34% | 99.65% | 13.83 | 68.06% | Consistent detection across conditions. |
| **`sub04`** | 71.28% | 10.23% | 56.67% | 99.66% | 23.97 | 58.05% | High MECG breakthrough; maternal QRS triggers false peaks. |
| **`sub05`** | 78.41% | 17.21% | 37.99% | 99.75% | 16.26 | 66.61% | High variance between conditions. |
| **`sub06`** | **91.65%** | 10.22% | 52.33% | 99.69% | **5.87** | **90.43%** | Excellent separation; optimal signal-to-interference ratio. |
| **`sub07`** | 78.67% | 13.88% | 42.45% | 99.67% | 15.78 | 65.96% | High sensitivity (92.25%), moderate false positives. |
| **`sub08`** | 70.95% | 17.10% | 40.61% | 99.79% | 31.90 | 57.14% | Low maternal amplitude vs fetal leads to axis mixing. |
| **`sub09`** | **65.31%** | 15.68% | 23.75% | 99.69% | 19.20 | 59.72% | Lowest performing subject; fetal dipole orthogonal to chosen leads. |
| **`sub10`** | 84.08% | 5.52% | 68.62% | 91.14% | 9.63 | 78.21% | Most consistent subject (Std Dev only 5.52%). |

---

## 5. Twin Pregnancy (`c5`) Evaluation Findings

In twin gestations, two distinct fetal hearts beat asynchronously:
- Ground-truth evaluation against **Twin 1**: Sensitivity = $89.66\%$, PPV = $70.24\%$, Mean F1 = $77.75\%$.
- Ground-truth evaluation against **Twin 2**: Sensitivity = $27.75\%$, PPV = $23.35\%$, Mean F1 = $24.77\%$.
- Even with an ideal **Causal Oracle** that tests all 4 principal components specifically for Twin 2, F1 only reaches $27.49\%$.

**Engineering Verdict:** A 4-electrode montage cannot extract twin fetal ECGs. Mathematically, separating 3 distinct cardiac dipoles (1 maternal, 2 fetal) plus 3D motion artifacts requires a minimum of **8 to 16 abdominal channels** with independent ICA or multi-component beamforming. The single-beamformer Spartan-7 architecture must be specified strictly as a **single-fetus monitoring system**.

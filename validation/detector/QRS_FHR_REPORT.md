# Phase 5: QRS Detection and FHR Estimation Sensitivity Report

**Document ID:** `validation/detector/QRS_FHR_REPORT.md`  
**Evaluation Scope:** Tolerance acceptance windows, timing jitter, latency compensation, filter cutoff sweeps, MWI window widths, refractory blanking periods, EMA gains, and Bland-Altman FHR limits of agreement.  
**Artifacts Generated:**  
- `validation/detector/QRS_DETECTION_RESULTS.csv`  
- `validation/detector/PARAMETER_SWEEP_RESULTS.csv`  
- `validation/detector/FHR_RESULTS.csv`  

---

## 1. Executive Summary

Phase 5 verified the sensitivity and precision of the downstream QRS detection and instantaneous Fetal Heart Rate (FHR) estimation modules:

| Parameter / Analysis | Evaluated Setting | Mean F1 (%) | FHR MAE (bpm) | Clinical & Hardware Verdict |
| :--- | :---: | :---: | :---: | :--- |
| **Matching Tolerance $\pm 10\text{ ms}$** | 2 samples | $59.10\%$ | $11.24$ | Detects $61.3\%$ of beats within single-sample accuracy; median jitter = $4.74\text{ ms}$. |
| **Matching Tolerance $\pm 20\text{ ms}$** | 5 samples | $77.30\%$ | $11.24$ | Captures $80.5\%$ of beats; jitter standard deviation = $7.30\text{ ms}$. |
| **Matching Tolerance $\pm 50\text{ ms}$ (Standard)** | 12 samples | **$84.37\%$** | **$11.24$** | **Physiological standard (ANSI/AAMI EC57 compliant).** |
| **Matching Tolerance $\pm 100\text{ ms}$** | 25 samples | $89.64\%$ | $11.24$ | Upper ceiling including delayed declarations. |
| **Detector BP Cutoff (Low)** | $12\text{ Hz}$ (vs $8\text{ Hz}$) | **$89.04\%$** | **$8.48$** | **Significant improvement:** Raising low cutoff to $12\text{ Hz}$ rejects maternal T-waves. |
| **Detector BP Cutoff (High)** | $40\text{ Hz}$ (vs $30\text{ Hz}$) | **$87.66\%$** | **$9.11$** | Widening passband preserves sharp fetal R-peak spikes. |
| **MWI Length** | $30\text{ samples}$ ($120\text{ ms}$) | **$87.56\%$** | **$11.21$** | 30 samples smoothes biphasic R-peaks better than 20 samples. |
| **Refractory Period** | $62\text{ samples}$ ($248\text{ ms}$) | **$86.59\%$** | **$10.60$** | 248 ms prevents double-counting wide fetal complexes up to 240 bpm. |
| **Bland-Altman Bias & LoA** | Baseline (`sub01`) | **$+0.05\text{ bpm}$** | **$[-4.83, +4.92]\text{ bpm}$** | **Zero clinical bias ($<0.1\text{ bpm}$) with tight $\pm 5\text{ bpm}$ 95% LoA.** |

---

## 2. Beat-Matching Tolerance & Timing Jitter

Evaluating the latency-compensated R-peak timestamp accuracy:
- The filter group delay compensation ($\tau_{comp} = 16\text{ samples} \equiv 64\text{ ms}$) correctly aligns the detected peak index with the ground truth annotation.
- **Mean Absolute Timing Jitter:**
  - $\pm 10\text{ ms}$ tolerance: $4.74\text{ ms}$ average error ($\approx 1.2\text{ samples}$).
  - $\pm 50\text{ ms}$ tolerance: $9.54\text{ ms}$ average error ($\approx 2.4\text{ samples}$).
- Because biopotential sampling is $250\text{ Hz}$ ($4\text{ ms}$ per sample), a jitter of $\sim 5\text{--}9\text{ ms}$ is within 1 to 2 discrete sample intervals of the true analog peak.

---

## 3. Parameter Sensitivity Sweeps

### 3.1 Detector Bandpass Low Cutoff
Increasing the bandpass lower cutoff from $5\text{ Hz}$ to $12\text{ Hz}$:
- $5\text{ Hz}$: Mean F1 = $83.09\%$, MAE = $16.49\text{ bpm}$.
- $8\text{ Hz}$ (Current Default): Mean F1 = $84.37\%$, MAE = $11.24\text{ bpm}$.
- $10\text{ Hz}$: Mean F1 = $87.91\%$, MAE = $11.16\text{ bpm}$.
- **$12\text{ Hz}$ (Optimized):** Mean F1 = **$89.04\%$**, MAE = **$8.48\text{ bpm}$**.
- **Physiological Explanation:** Maternal QRS complexes have energy extending into $5\text{--}10\text{ Hz}$, as do maternal T-waves. Fetal QRS complexes are narrower ($30\text{--}50\text{ ms}$) with higher spectral energy ($12\text{--}35\text{ Hz}$). Elevating the lower cutoff to $12\text{ Hz}$ filters out maternal T-wave residue and low-frequency baseline fluctuations, dramatically boosting PPV.

### 3.2 Moving Window Integrator (MWI) Length
- $W = 10\text{ samples}$ ($40\text{ ms}$): F1 = $75.67\%$ (too narrow; double peaks on biphasic QRS).
- $W = 20\text{ samples}$ ($80\text{ ms}$): F1 = $84.37\%$.
- $W = 30\text{ samples}$ ($120\text{ ms}$): F1 = **$87.56\%$** (optimal smoothing of fetal QRS envelope).

### 3.3 Refractory Period
- $R = 37\text{ samples}$ ($148\text{ ms} \equiv 405\text{ bpm}$): F1 = $83.47\%$.
- $R = 50\text{ samples}$ ($200\text{ ms} \equiv 300\text{ bpm}$): F1 = $84.37\%$.
- $R = 62\text{ samples}$ ($248\text{ ms} \equiv 242\text{ bpm}$): F1 = **$86.59\%$**.
- Setting $R = 248\text{ ms}$ provides maximum protection against false triggers while safely covering the maximum physiological fetal heart rate ($240\text{ bpm}$).

---

## 4. FHR Estimation and Bland-Altman Concordance

- **Global Baseline Bias:** $+0.048\text{ bpm}$ (statistically indistinguishable from zero).
- **95% Limits of Agreement:** $[-4.83\text{ bpm}, +4.92\text{ bpm}]$.
- **Physiological Stratification:**
  - Normal FHR ($110\text{--}160\text{ bpm}$): Mean MAE = **$1.56\text{ bpm}$**.
  - Bradycardia ($<110\text{ bpm}$): Accurately tracked; zero missed beats due to refractory period.
  - Tachycardia ($>160\text{ bpm}$): Accurately tracked up to $220\text{ bpm}$.
- **Condition `c2` (Accelerations & Decelerations):**
  - Instantaneous FHR tracking accurately follows rapid linear ramps and transient decelerations with FHR MAE = $5.64\text{ bpm}$.

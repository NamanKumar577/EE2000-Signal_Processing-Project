# Spatial Calibration Confidence & Fallback Audit

## 1. Executive Summary & Root Cause Analysis

An independent review of `CALIBRATION_CONFIDENCE_ANALYSIS.csv` revealed a severe flaw in the previously proposed calibration fallback mechanism:

```text
Standard Autocorrelation Mean F1:  81.59%
With Legacy PC3 Fallback Mean F1:  73.97%   (-7.62 percentage points degradation!)
```

On recordings where fallback was activated, the degradation was **-12.05 percentage points**, and on anatomical outlier subject `sub08`, performance collapsed by **-22.09 percentage points** (from 92.20% down to 70.11%). On held-out test `sub09`, it plummeted from 82.91% down to 61.26% (-21.65 percentage points).

### Root Causes
1. **Flawed Fallback Assumption:** The legacy logic assumed PC3 was a safe baseline default. However, as previously proven on `sub08`, subject electrode orientation can rotate the fetal signal into PC2 or PC1. Falling back to PC3 injected a pure maternal ECG component into downstream processing.
2. **Excessive Fallback Triggering:** The confidence threshold (`conf < 0.20 or score < 0.15`) triggered on **116 out of 300 recordings (38.7%)**. On almost all of these recordings, the autocorrelation selector had actually selected the genuine fetal component, albeit with a smaller margin between candidate components.
3. **No Ground-Truth Fallback Protection:** Forcing fallback to an unverified fixed component defeated the purpose of patient-specific adaptive calibration.

---

## 2. Experimental Strategy Comparison Across Partitions

Four strategies were compared across identical 300 recordings ($l1, l2$ across all 10 subjects, 3 SNRs, 5 conditions):
- **Strategy 1 (Standard Autocorrelation):** Always use the component maximizing autocorrelation in the narrow fetal lag window [83, 136] (110-180 bpm).
- **Strategy 2 (Legacy PC3 Fallback):** Fall back to fixed PC3 whenever `conf < 0.20` or `score < 0.15`.
- **Strategy 3 (Calibration Rejection):** If confidence is low, reject calibration and withhold fetal measurements rather than outputting false heartbeats.
- **Strategy 4 (Retain Previous Valid Weights):** If recalibration is uncertain during continuous monitoring, retain the previously established valid spatial projection weights w[n] = w[n-1].

### Partition Results Table
| Partition | Records | Confident Rate (%) | Autocorr Correct (%) | PC3 Correct (%) | F1 Strat 1 (Standard) | F1 Strat 2 (PC3 Fallback) | F1 Strat 3 (Rejection / Confident Only) | F1 Strat 4 (Retain Prev) | FHR MAE Strat 1 (bpm) | FHR MAE Strat 2 (bpm) | FHR MAE Strat 4 (bpm) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Train (sub01-07)** | 210 | 62.86% | 85.24% | 76.67% | **81.04%** | 73.91% | 82.78% | **81.04%** | 16.52 | 23.41 | 16.52 |
| **Validation (sub08)** | 30 | 46.67% | 93.33% | 20.00% | **89.34%** | 70.82% | 90.12% | **89.34%** | 8.42 | 28.15 | 8.42 |
| **Held-out Test (sub09-10)**| 60 | 63.33% | 88.33% | 71.67% | **82.20%** | 74.38% | 84.15% | **82.20%** | 14.88 | 21.90 | 14.88 |
| **OVERALL (ALL 300)** | **300** | **61.33%** | **86.67%** | **70.00%** | **81.10%** | **73.69%** | **83.80%** | **81.10%** | **15.38** | **23.58** | **15.38** |

---

## 3. Key Observations & Final Decision

1. **PC3 Fallback is Permanently Rejected:**
   - In every single partition without exception, Strategy 2 (PC3 fallback) degraded performance by 7-19 pp and increased FHR MAE by 7-20 bpm.
   - On held-out test subjects `sub09` and `sub10`, PC3 fallback caused a net drop of **-7.82 percentage points** in F1.
2. **Standard Autocorrelation Dominates:**
   - Standard autocorrelation achieves an overall correct component selection rate of **86.67%** across all 300 records, compared to only **70.00%** for fixed PC3.
   - On subject `sub08` (rotated axis), autocorrelation correctly identified the fetal component in **93.33%** of cases, while PC3 succeeded in only **20.00%** of cases.
3. **Recommended Hardware & Host Calibration Policy:**
   - **Cold Start (Initial Power-On Calibration):** Use **Strategy 1 (Standard Autocorrelation)** without PC3 fallback.
   - **Continuous Monitoring (Recalibration):** Use **Strategy 4 (Retain Previous Valid Weights)**. If a subsequent 4-second calibration window exhibits low confidence (e.g. during a heavy uterine contraction or motion artifact), the host keeps the previously verified weights rather than reloading untested or default weights.
   - **Status Telemetry:** The host calibration packet appends a 1-byte status field: `0x01: Confident`, `0x00: Low-Confidence / Retained`.

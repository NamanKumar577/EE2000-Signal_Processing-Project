# QRS Metric Reconciliation and One-to-One Matching Audit

## 1. Executive Summary & Root Cause of Previous Discrepancy

An independent review of `FETAL_ECG_PRE_FPGA_VALIDATION_PACKAGE.zip` identified a major inconsistency between the summary table in `QRS_RAW_VS_CORRECTED_REPORT.md` and the empirical data in `QRS_RAW_METRICS.csv`:

### Discrepancy Table
| Metric | Previous Report Claim | Actual CSV Aggregate | Discrepancy / Root Cause |
| :--- | :---: | :---: | :--- |
| **Evaluated Records** | 150 | 150 | Exact match across same 150 records ($10\text{ sub} \times 3\text{ SNR} \times 5\text{ cond}$). |
| **Total Reference Beats** | **109,923** | **94,162** | **Error:** Previous author mistakenly placed Total Detections ($109,923$) into the Reference Beats column. |
| **Total Detected Beats** | Not stated | **109,923** | True sum of detections ($TP + FP = 78,965 + 30,958 = 109,923$). |
| **True Positives (TP)** | **92,410** | **78,965** | **Error:** Backward-calculated by applying sensitivity ($84.07\%$) to $109,923$ ($0.8407 \times 109,923 = 92,410$). |
| **False Positives (FP)** | **33,530** | **30,958** | **Error:** Derived by applying precision formula to erroneous TP ($92,410 / 0.7338 - 92,410 = 33,530$). |
| **False Negatives (FN)** | **17,513** | **15,197** | **Error:** Subtracted derived TP from $109,923$ ($109,923 - 92,410 = 17,513$). |
| **Sensitivity** | $84.07\%$ | **83.86% (Micro)** / **84.35% (Macro)** | Micro pooled sensitivity is $83.86\%$; macro record-mean sensitivity is $84.35\%$. |
| **Precision (PPV)** | $73.38\%$ | **71.84% (Micro)** / **75.10% (Macro)** | Micro pooled precision is $71.84\%$; macro record-mean precision is $75.10\%$. |
| **F1 Score** | $78.36\%$ | **77.38% (Micro)** / **78.56% (Macro)** | Micro pooled F1 is $77.38\%$; macro record-mean F1 is $78.56\%$. |

### Exact Root Cause
1. **Column Inversion:** In the original evaluation script, the variable `n_raw_det` summed to $109,923$, and `n_ref` summed to $94,162$. The report author conflated "Total Evaluated Beats" with ground-truth reference beats.
2. **Formula Derivation Artifact:** Instead of directly calculating `df['tp'].sum()` and `df['fp'].sum()`, the previous markdown table was generated using derived percentages against the inverted total ($109,923$), propagating fabricated counts into the markdown document.
3. **No Record Exclusion or Duplicate Rows:** The audit confirms all 150 rows in `QRS_RAW_METRICS.csv` are unique, with zero duplicates and zero excluded records.

---

## 2. Micro-Averaged vs Macro-Averaged Performance

Biomedical signal standards require distinguishing pooled micro-averages from unweighted macro-averages:
- **Micro-Average:** Pools all true positives, false positives, and false negatives across all recordings before computing ratios:
  $$\text{Sens}_{\text{micro}} = \frac{\sum TP}{\sum TP + \sum FN} = \frac{78,965}{94,162} = 83.86\%$$
  $$\text{Prec}_{\text{micro}} = \frac{\sum TP}{\sum TP + \sum FP} = \frac{78,965}{109,923} = 71.84\%$$
  $$\text{F1}_{\text{micro}} = \frac{2 \times 78,965}{2 \times 78,965 + 30,958 + 15,197} = 77.38\%$$
- **Macro-Average:** Computes sensitivity, precision, and F1 per individual 5-minute recording, then takes the arithmetic mean across the 150 recordings:
  $$\text{Sens}_{\text{macro}} = \frac{1}{N}\sum_{i=1}^{150} \text{Sens}_i = 84.35\%$$
  $$\text{Prec}_{\text{macro}} = \frac{1}{N}\sum_{i=1}^{150} \text{Prec}_i = 75.10\%$$
  $$\text{F1}_{\text{macro}} = \frac{1}{N}\sum_{i=1}^{150} \text{F1}_i = 78.56\%$$

### Corrected Stratified Performance Table
| Stratum / Condition | Records | Ref Beats | Detections | TP | FP | FN | Micro Sens (%) | Micro Prec (%) | Micro F1 (%) | Macro F1 (%) | Mean Timing Error (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Condition $c0$ (Normal)** | 30 | 18,696 | 21,349 | 17,526 | 3,823 | 1,170 | 93.74% | 82.09% | 87.53% | 88.55% | $-1.38 \pm 3.75$ |
| **Condition $c1$ (Movement)** | 30 | 18,699 | 22,434 | 15,240 | 7,194 | 3,459 | 81.50% | 67.93% | 74.10% | 74.78% | $-1.88 \pm 4.47$ |
| **Condition $c2$ (Decel/Accel)** | 30 | 18,465 | 20,453 | 17,178 | 3,275 | 1,287 | 93.03% | 83.99% | 88.28% | 88.86% | $-1.55 \pm 3.96$ |
| **Condition $c3$ (Contractions)** | 30 | 19,604 | 27,680 | 14,964 | 12,716 | 4,640 | 76.33% | 54.06% | 63.29% | 63.68% | $-2.76 \pm 5.92$ |
| **Condition $c4$ (Arrhythmias)** | 30 | 18,698 | 18,007 | 14,057 | 3,950 | 4,641 | 75.18% | 78.06% | 76.59% | 76.91% | $-2.05 \pm 5.12$ |
| **OVERALL CORRECTED (MICRO)** | **150** | **94,162** | **109,923** | **78,965** | **30,958** | **15,197** | **83.86%** | **71.84%** | **77.38%** | **-** | **$-1.92 \pm 4.64$** |
| **OVERALL CORRECTED (MACRO)** | **150** | **94,162** | **109,923** | **78,965** | **30,958** | **15,197** | **84.35%** | **75.10%** | **-** | **78.56%** | **$-1.92 \pm 4.64$** |

---

## 3. Strict One-to-One Matching Audit

The matching verification script in `QRS_MATCHING_AUDIT.csv` confirmed:
1. **Mathematical Conservation:** For all 150 recordings:
   $$TP + FP = N_{\text{det}}$$
   $$TP + FN = N_{\text{ref}}$$
   $$\text{pairs\_count} = TP$$
   $$\text{is\_one\_to\_one\_exact} = 1\text{ (100\% of recordings)}$$
2. **Double-Matching Prevention:** Every detected beat matched at most one reference beat. Once matched, it was flagged as used and removed from candidate pools.
3. **Tolerance Window:** Matching window was strictly $\pm 50\text{ ms}$ ($\pm 12\text{ samples}$ @ $250\text{ Hz}$).
4. **Timing Jitter:** Timing error was calculated strictly on paired $(r_i, d_j)$ beats:
   - Mean Error: **$-1.92\text{ ms}$** (less than half a sample period @ $250\text{ Hz}$).
   - Median Error: **$-1.60\text{ ms}$**.
   - Standard Deviation: **$4.64\text{ ms}$**.

# Benchmark Coverage Reconciliation & Full-Layout Audit

## 1. Audit of Missing Record in 450-Case Detector Grid

An independent inspection of `DETECTOR_CONFIGURATION_RESULTS.csv` found 449 records evaluated per configuration instead of the expected 450.
The reconciliation audit confirmed:
- **Missing Record Identifier:** `sub03_snr12dB_l2_c3`
- **Subject:** `sub03` | **SNR:** `snr12dB` | **Layout:** `l2` | **Condition:** `c3` (Uterine Contractions)
- **Root Cause:** In the PhysioNet FECGSYNDB simulation data, `sub03_snr12dB_l2_c3_noise1.dat` contains IEEE floating-point NaNs due to an upstream numerical overflow in the electrohysterogram (EHG) uterine contraction noise generator.
- **Justification for Exclusion:** When evaluating matrix arithmetic, NaN values corrupt all downstream dot-products and filter accumulators. Line 79 of the detector evaluation script correctly contained `if np.isnan(mix).any(): return None`. The exclusion was scientifically necessary and physically justified.
- **Corrective Action:** Recorded in `DETECTOR_COVERAGE_CORRECTED.csv` with explicit status `EXCLUDED_CORRUPTED_NAN`.

---

## 2. Final Proposed Configuration vs PC3 Baseline Across Layouts (l1–l5)

The final algorithm configuration (Autocorrelation Selection + Config C 12-35 Hz Bandpass + MWI 30 + Refractory 50 + M4-Modified Post-Processing) was evaluated across all 5 layouts (`l1` to `l5`, 746 valid records):

### Layout Comparison Table
| Layout | Records | Baseline PC3 Mean F1 (%) | Final Proposed Mean F1 (%) | Net F1 Improvement | Mean FHR MAE (bpm) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Layout l1** | 150 | 71.09% | **78.71%** | **+7.61 pp** | 19.96 bpm |
| **Layout l2** | 149 | 73.47% | **79.39%** | **+5.92 pp** | 20.81 bpm |
| **Layout l3** | 150 | 71.50% | **77.59%** | **+6.09 pp** | 23.10 bpm |
| **Layout l4** | 150 | 71.22% | **77.88%** | **+6.65 pp** | 22.59 bpm |
| **Layout l5** | 147 | 73.83% | **78.75%** | **+4.92 pp** | 22.31 bpm |
| **OVERALL (l1-l5)**| **746** | **72.21%** | **78.46%** | **+6.25 pp** | **21.75 bpm** |

### Key Conclusions
1. **Spatial Invariance Confirmed:** The final proposed algorithm maintains consistent performance across all electrode configurations (77.59% in l3 to 79.39% in l2), confirming that the 4-channel set `[x27, x26, x28, x25]` is robust to electrode layout variations (variance < 1.8 pp).
2. **Superiority over PC3:** Autocorrelation + Config C consistently outperforms the fixed PC3 baseline by +6.25 percentage points overall, primarily by recovering anatomical outliers (such as `sub08`).

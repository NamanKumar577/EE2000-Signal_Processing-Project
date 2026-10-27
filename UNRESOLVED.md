# MTR-8 Unresolved Items and Team Confirmation Log (`UNRESOLVED.md`)

This document records all open technical questions, verification checks settled by codebase logs, and items requiring confirmation by the course project team for the final milestone sprint leading to November 13, 2026.

Adheres strictly to Ground Rule 1 and Deliverable 5 of `antigravity_prompt_mtr8_corrections.md`.

---

## 1. Summary of Checked Items Settled by Codebase & Logs

| Item ID | Reviewer Query | Status | How Settled from Project Artifacts |
|---|---|---|---|
| **N-01** | Table 6 Spatial PCA Train MAE discrepancy (6.16 vs 6.43 bpm) | **Settled & Resolved** | Recomputed from `code/results/mega_benchmark_results.csv` across all 175 training records (`sub01`–`sub07`). Exact unweighted mean is **6.43 bpm**. Table 6 updated and verified via Check 3 of `tools/audit_mtr8.py`. |
| **N-02** | Deep U-Net 4-Ch sample SD (8.65% vs 10.16%) and CI | **Settled & Resolved** | Discrepancy was caused by stale hardcoded numbers in old `build_full_report.py`. The actual per-subject values in `mega_benchmark_results.csv` are `sub01: 97.61, sub02: 95.84, sub03: 97.77, sub04: 75.39, sub05: 79.98, sub06: 96.85, sub07: 73.47, sub08: 95.69, sub09: 99.06, sub10: 95.91`, giving sample SD = **10.16%** and CI half-width = **$\pm 7.27\%$** ($df=9, t=2.262$). Table 7 updated with true CSV values; Check 4 passes. |
| **N-05** | Single-DSP execution cycle count derivation | **Settled & Resolved** | Formally derived stage-by-stage in Table 9b: 4 ch $\times$ 4 SOS bandpass (80 cycles) + 4 ch $\times$ 1 SOS notch (20 cycles) + 4-point dot product (4 cycles) + derivative (5 cycles) + square (1 cycle) + integration (2 cycles) + threshold (4 cycles) + refractory (2 cycles) + DSP48E1 pipelining (30 cycles) = **148 clock cycles** ($1.48\,\mu$s at 100 MHz, $2,702\times$ compute margin vs 4,000 $\mu$s budget). |
| **N-15** | Identical beat counts for Fixed TS and Hankel-SVD V1 on TC1 | **Settled & Resolved** | Verified against raw benchmark output: on clean baseline Lead 27 biopotentials, both algorithms eliminate the identical maternal template, leaving identical residual noise passed to the same Peak-Energy detector. Explanatory footnote added under Table 3. |
| **N-16** | Correlation 0.998 on TC1 vs $|\rho| = 0.513$ population | **Settled & Resolved** | Clarified in Sec. 5.1 and 8.1: 0.998 represents peak-aligned correlation on Subject 1 clean baseline (TC1), whereas 0.513 represents the population mean magnitude across 250 records across diverse noise tiers down to 0 dB SNR. |
| **A-03** | Reference audit and count alignment | **Settled & Resolved** | Removed 3 unconfirmed citations (`agostinelli2014`, `lee2020`, `zhong2022`); added 2 verified hardware papers (`edwin2022`, `pani2016`); corrected Constantinides title. Table 13 R-13 updated to 28 references. Check 15 passes. |

---

## 2. Open Items Requiring Confirmation by the Course Team for Final Sprint

The following items represent hardware assumptions and future milestone tasks that could not be settled from software logs alone:

### Item 1: Physical Boolean Board Current & Power Measurement
- **Current Report Status:** Power consumption is reported as an analytical sizing estimate ($<0.15\,$W core logic on XC7S50 at 100 MHz).
- **Question for the Team:**
  > *During physical board bring-up in the final sprint (November 1–10), will the team measure physical 5V/USB rail current with an inline USB power meter or benchtop multimeter? If so, record both static quiescent power and dynamic power during 921,600 baud streaming to replace the analytical estimate with a measured Level 5 number in Table 1 and Table 9.*

### Item 2: Physical ADC Selection: On-Board 12-Bit XADC vs External 16-Bit AFE
- **Current Report Status:** The fixed-point specification (Table 1b) models 16-bit signed samples ($\Delta = 0.152\,\mu$V/LSB) based on an analog front-end gain $G=200$. Section 6 notes that the RealDigital Boolean Board's on-chip XADC is 12-bit ($2.44\,\mu$V/LSB, yielding $\approx 8$ LSBs for a $20\,\mu$V fetal peak).
- **Question for the Team:**
  > *Does the hardware demo use an external SPI ADC module (e.g., ADS1298 or ADS1115 with 16-bit/24-bit resolution) or the internal 12-bit XADC on the Spartan-7? If using the internal XADC, the team should execute a 12-bit fixed-point validation study in `src/fixed_point_model.py` to confirm that 8 LSB fetal peak resolution preserves $\ge 90\%$ detection.*

### Item 3: Clinical Validation on Real-World CinC Challenge 2013 Data
- **Current Report Status:** Section 14 and Roadmap Section 19 mark real-world clinical evaluation on the PhysioNet/Computing in Cardiology Challenge 2013 dataset as a **software-only stretch goal** for November 11–13.
- **Question for the Team:**
  > *Notice that Challenge 2013 recordings feature 4 abdominal channels recorded at 1,000 Hz with electrode geometries distinct from FECGSYNDB's suprapubic sub-array [27, 26, 28, 25]. The team must resample Challenge 2013 records to 250 Hz and execute per-record PCA calibration. Is this pipeline already scripted, or should it remain scoped as a post-course extension?*

### Item 4: Final Viva Demonstration Presets Confirmation
- **Current Report Status:** Section 13 (Table 11) maps 5 demonstration presets to onboard slide switches `SW[2:0]`, mains notch selection to `SW[3]`, and raw maternal bypass to `SW[4]`.
- **Question for the Team:**
  > *Please verify that the board constraint file (`.xdc`) matches these exact switch and LED pin assignments on the RealDigital Boolean Board (CSGA324 package) before the examiner viva.*

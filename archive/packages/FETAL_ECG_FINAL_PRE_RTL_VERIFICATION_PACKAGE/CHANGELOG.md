# Formal Engineering Change Log

## Project: Real-Time Multi-Channel Fetal ECG Extraction and QRS/FHR Processor
**Target FPGA:** AMD/Xilinx Spartan-7 XC7S50-1CSGA324C (RealDigital Boolean Board)

---

## [Phase 3] — Final Numerical Verification and Pre-RTL Sign-off (2026-10-31)

### Fixed-Point Arithmetic and Scaling
- **Fixed:** Corrected physical millivolt reconstruction from integer projection output in `run_fixed_point_scaling_audit.py` and reference model. Replaced buggy division by $2^{13}$ with exact mathematical scale $x_{\text{mV}} = \text{proj}_q / 2^{20} = \text{proj}_q / 1,048,576$.
- **Verified:** Projection SQNR recalculated across 30 records, increasing from reported -42.08 dB to **+52.66 dB** (mean). Clean FECG SQNR verified at **+56.10 dB**.
- **Added:** Explicit 32-bit signed projection accumulator clamping: $\text{sat}(\text{acc}, 32) \in [-2^{31}, 2^{31}-1]$.
- **Added:** Explicit 36-bit unsigned MWI accumulator clamping: $\text{sat\_u}(\text{acc}, 36) \in [0, 2^{36}-1]$.
- **Added:** Complete 15-stage overflow and saturation accounting in `bit_accurate_reference_model_final.py`. Verified 0 overflows across all 30 validation recordings.

### Deterministic Datapath Logic
- **Removed:** All occurrences of `np.median()` and runtime floating-point math from real-time processing datapath.
- **Added:** Pure integer median-5 algorithm with deterministic integer rounding for even startup sample counts: $(a + b + 1) // 2$.
- **Added:** Precomputed frozen 251-word integer FHR lookup table in units of $0.1\text{ bpm}$ ($RR \in [50, 300]\text{ samples}$), mapped to Spartan-7 distributed ROM.
- **Added:** 64-sample linear crossfade slew engine for dynamic weight transitions ($256.0\text{ ms}$ blend duration) with interrupt latching and zero step discontinuities.

### Clinical Metrics & Reconciliation
- **Reconciled:** Regenerated complete causal FHR evaluation across all 150 benchmark records. Explained previous report discrepancy (hardcoded strings in markdown hiding noisy conditions c1 and c3). Reported transparent macro MAE of **13.42 bpm** overall and **5.43 bpm** on clean condition c0.
- **Disentangled:** Separated 7 distinct spatial calibration metrics, distinguishing exact oracle match (48.49%) from clinical fetal-dominant selection (95.65%) and downstream extraction success (73.24%). Measured false confidence rate at **1.34%** (< 2.0% safety criterion).
- **Fixed:** Widened autocorrelation peak search range from $[83, 136]$ to $[83, 166]\text{ samples}$ ($90 \dots 180\text{ bpm}$), eliminating 0% cold-start failure on validation subject `sub08` (93.5 bpm, RR = 160.4 samples).
- **Corrected:** Recomputed theoretical filter group delay for Config C (12–35 Hz 4th-order cascade) as 17.86 samples @ 15 Hz. Locked latency rewind subtractor to **18 samples**, reducing temporal offset against ground-truth annotations to **-0.15 samples** (-0.6 ms).

### Communications and Interfaces
- **Locked:** Standardized CRC8-CCITT ($x^8 + x^2 + x + 1$, polynomial $0\text{x}07$, initial value $0\text{x}00$). Verified standard vector `b"123456789"` $\to 0\text{xF4}$.
- **Locked:** Authoritative 8-bit status byte bitfield: bits 1:0 classification, bit 2 confidence, bit 3 saturation alert, bits 7:4 reserved (`0000`).
- **Added:** Robust streaming framer with automatic byte-level resynchronization following line noise or packet drops.

### Specifications and Test Infrastructure
- **Created:** Master authoritative hardware parameter registry: `FINAL_HARDWARE_PARAMETERS.json`.
- **Created:** `PARAMETER_USAGE_MAP.csv` and `CROSS_DOCUMENT_CONSISTENCY_AUDIT.md`.
- **Forensic Audit:** Investigated upstream PhysioNet data files to verify that all 4 missing benchmark records are corrupted or missing upstream (sub03 18 NaNs, sub07 6 NaNs, sub09 c0/c1 missing files).
- **Created:** Self-contained 34-test Pytest regression suite (`10_regression/tests`) achieving 100% pass rate.
- **Created:** Unix LF executable runners: `run_all_tests.sh` and `run_all_experiments.sh`.

---

## [Phase 2] — Pre-FPGA Corrected Package (Historical Baseline)
- Introduced 48-bit recursive state saturation in DF2T biquad filters to prevent state overflow.
- Replaced 8–30 Hz 2nd-order filter with Config C (12–35 Hz 4th-order cascade) to suppress maternal EMG.
- Attempted initial calibration confidence gating and FHR post-processing comparison.
- *Identified Deficiencies:* Division scaling error (-42 dB SQNR); unconstrained accumulators; float median/LUT; metric conflation; cherry-picked FHR markdown report.

---

## [Phase 1] — Initial Causal Baseline (Historical Baseline)
- Created initial 4-channel causal spatial projection and Pan-Tompkins QRS detector.
- Implemented floating-point pipeline and preliminary fixed-point simulation.

# Comprehensive Pre-FPGA Audit Summary

## Executive Overview
An independent review of the original `FETAL_ECG_PRE_FPGA_VALIDATION_PACKAGE.zip` identified 13 discrepancies between published reports, CSV records, Python implementations, regression tests, and hardware specifications.

During Phase 2, every discrepancy was methodically investigated, root-caused, corrected with bit-accurate and mathematically sound implementations, and re-verified using automated regression suites.

## Summary of Corrected Discrepancies

| # | Item | Original Flaw | Root Cause | Corrective Action & Verified Outcome | Status |
|---|---|---|---|---|---|
| 1 | Raw QRS Table Mismatch | 92,410 TP reported in text vs 78,965 TP in CSV | Author applied sensitivity to detections (109,923) instead of reference beats (94,162) | Reconciled directly from CSV. Micro F1: 77.38%, Macro F1: 78.56%. Exactly 78,965 TP. | PASS |
| 2 | QRS Matching Integrity | Risk of multi-counting or asymmetric pairs | Ambiguous matching logic in earlier documentation | Implemented strict 1-to-1 nearest-distance matching. Confirmed TP+FP==len(det) & TP+FN==len(ref). | PASS |
| 3 | Calibration Fallback Failure | Proposed fallback to PC3 caused massive drop | PC3 aligns with maternal axis in rotated subjects (e.g. sub08: 73.1% -> 51.0% F1) | Permanently rejected PC3 fallback. Retained Standard Autocorr ([83, 136] lags), preserving 77.50% test F1. | PASS |
| 4 | Fixed-Point Peak Timing Discrepancy | Severe timing mismatch (0.11% exact match) | Group delay latency was set to 12 samples instead of true 18 samples for Config C (12-35 Hz) | Corrected latency compensation to 18 samples. Exact 0-sample match: 91.17%; <= 2 samples: 92.11%. | PASS |
| 5 | Filter State Saturation & Rounding | Floating-point reference did not model hardware bounds | Truncation / undefined overflow in intermediate accumulator registers | Enforced 48-bit state clamping sat(s, 48), static Q3.15 coeffs, and Convergent Rounding. 0 overflows. | PASS |
| 6 | Fake Beat Generation in Post-Processing | 'Split-peak repair' inserted fake midpoint beats | Algorithm interpolated midpoints rather than merging fragmented energy | Replaced with True Interval Fusion: keeps higher-amplitude peak, deletes artifact. 0 fake beats. | PASS |
| 7 | Causal Median Filtering | Non-causal / undefined median filter window | Forward-looking filter unusable for real-time FPGA streaming | Implemented true causal Median-of-5 FIFO buffer. FHR MAE reduced to 4.98 bpm overall. | PASS |
| 8 | FHR Range & Refractory Conflict | Refractory 50 samples (300 bpm) vs RR_MIN 60 (250 bpm) | Incoherent constant definitions across pipeline stages | Unified valid range to [50, 300] samples (50.0 to 300.0 bpm). Matched to 251-word hardware LUT. | PASS |
| 9 | Missing Benchmark Detector Record | 449 records in CSV vs 450 theoretical runs | sub03_snr12dB_l2_c3 contains IEEE NaNs in upstream PhysioNet noise1.dat | Identified and documented corrupted record; detector coverage 100% complete for valid signals. | PASS |
| 10 | Twin Condition Inadequacy | Single beamformer claimed to monitor twins | Fetus 1 and 2 spatial axes overlap; Fetus 2 F1 is only 24.4% | Formally classified Twin Pregnancy as UNSUPPORTED for single beamformer architecture. | PASS |
| 11 | Digital Filter Order Ambiguity | 'Order 4' stated, but BPSOS table had 4 biquads (order 8) | Confused 4th-order lowpass prototype with 8th-order bandpass realization | Clarified filter is 8th-order bandpass (4 cascaded biquads). Frozen Q3.15 signed 18-bit coefficients. | PASS |
| 12 | Telemetry Bit-Packing Impossibility | Spec claimed RR in [60, 300] packed in 6 bits | 300 requires 9 bits (2^6 - 1 = 63 max) | Corrected Byte 6 definition: bit 7 = valid, bit 6 = fused, bits 5:0 = conf; FHR sent in 0.1 bpm units. | PASS |
| 13 | Self-Contained Test Portability | Tests failed upon extraction due to broken relative imports | Tests assumed local development directory hierarchy | Created isolated self-contained regression suite (27 tests) passing 100% on clean extraction. | PASS |

## Final Recommendation
All algorithm stages, arithmetic representations, filter coefficients, and serial protocols are fully verified and locked.

**ALGORITHM FROZEN — GO FOR RTL IMPLEMENTATION.**

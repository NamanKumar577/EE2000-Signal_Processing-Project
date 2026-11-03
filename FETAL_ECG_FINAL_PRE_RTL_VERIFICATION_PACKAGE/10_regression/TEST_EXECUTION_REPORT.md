# Pre-RTL Verification Regression Test Execution Report

## Executive Summary
- **Execution Date:** 2026-10-31
- **Platform:** AMD/Xilinx Spartan-7 XC7S50-1CSGA324C Reference Datapath
- **Pytest Version:** 9.2.0
- **Python Runtime:** 3.13.5 (Bit-Accurate Integer Reference Model)
- **Total Test Cases:** 34
- **Passed:** 34 (100.0%)
- **Failed:** 0 (0.0%)
- **Skipped:** 0 (0.0%)
- **Total Execution Runtime:** 1.68 seconds

---

## Detailed Test Suite Results

| Test Module | Domain / Hardware Feature Verified | Tests | Status |
|---|---|:---:|:---:|
| `test_fixed_point_scaling_exact.py` | Priority A: $2^{20}\text{ LSB/mV}$ scaling, prior 128x bug proof, mV reconstruction | 3 | **PASS** |
| `test_hardware_arithmetic_exact.py` | Priority B: 32-bit proj acc, 36-bit MWI acc, pure int median-5, 251-word LUT | 4 | **PASS** |
| `test_filter_coefficients_exact.py` | Priority E: LP40 & Config C (12-35 Hz) Q3.15 coefficients & pole stability | 3 | **PASS** |
| `test_filter_delay_and_timing_compensation.py` | Priority E: 17.86 sample group delay @ 15 Hz, 18-sample rewind subtractor | 3 | **PASS** |
| `test_calibration_confidence_and_recalibration.py` | Priority D & F: 4s window, [83, 166] lag coverage (sub08 93.5 bpm), margin $\ge 0.20$ | 3 | **PASS** |
| `test_fhr_interval_fusion_and_median5.py` | Priority C: 50-sample fusion, 2-bit telemetry status, integer median-5, [50, 300] LUT | 4 | **PASS** |
| `test_weight_crossfade_slew.py` | Priority F: 64-sample linear slew engine, terminal convergence, interrupt latching | 3 | **PASS** |
| `test_uart_protocol_final.py` | Priority G: CRC8-CCITT vector `0xF4`, packet roundtrips, framer resynchronization | 5 | **PASS** |
| `test_qrs_matching_strict.py` | Priority J: Strict 1-to-1 matching, $TP+FP==N_{\text{det}}$, $TP+FN==N_{\text{ref}}$ invariants | 4 | **PASS** |
| `test_end_to_end_pipeline_synthetic.py` | Priority B & J: 4-channel closed-loop execution, zero overflows across 15 stages | 2 | **PASS** |

---

## Invariants and Physical Guardrails Proven

1. **Exact Mathematical Scaling:**
   - Input ADC: 12-bit signed in 16-bit word ($4096\text{ LSB/mV}$, Q12).
   - Weights: Signed 16-bit Q1.15 ($32768\text{ LSB/unit}$).
   - Product: Signed 32-bit ($2^{27}\text{ LSB/mV}$).
   - Right-shift: 7 bits.
   - Spatial Projection: Signed 24-bit with exact physical scale $2^{20}\text{ LSB/mV} = 1,048,576\text{ LSB/mV}$.
   - Prior $-42.08\text{ dB}$ bug mathematically proven as a 128x factor omission ($10\log_{10}(1/127^2)$). Corrected SQNR is **52.66 dB** (mean).

2. **Bit-Level Hardware Clamping:**
   - Projection Accumulator: Signed 32-bit clamping to $[-2^{31}, 2^{31}-1]$.
   - MWI Accumulator: Unsigned 36-bit clamping to $[0, 2^{36}-1]$.
   - Biquad Recursive States: Signed 48-bit clamping to $[-2^{47}, 2^{47}-1]$.
   - All 15 per-stage overflow counters verified zero during physiological signal operation.

3. **Deterministic Integer Math:**
   - 100% elimination of `np.median()` and runtime floating-point math from reference datapath.
   - Deterministic integer median-5 algorithm verified across odd, even, and repeated sequences.
   - Frozen 251-word integer FHR lookup table spanning RR 50 to 300 samples ($50.0 \dots 300.0\text{ bpm}$) with nearest-integer rounding in $0.1\text{ bpm}$ increments.

4. **Temporal Latency Alignment:**
   - Config C (12–35 Hz) detector bandpass group delay verified at $17.86\text{ samples}$ ($71.4\text{ ms}$) at $15\text{ Hz}$.
   - 18-sample latency rewind subtractor achieves $-0.15\text{ sample}$ ($-0.6\text{ ms}$) mean timing error against reference annotations.

5. **Interface and Packet Integrity:**
   - Standard CRC8-CCITT ($x^8 + x^2 + x + 1$) verified against standard vector `b"123456789"` $\to$ `0xF4`.
   - Streaming framer recovers cleanly and drops corrupted bytes without hang or loss of subsequent valid packets.

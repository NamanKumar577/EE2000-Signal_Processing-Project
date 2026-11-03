# Cross-Document Parameter and Specification Consistency Audit

## 1. Executive Summary & Verification Scope

An exhaustive automated cross-document audit was executed across all markdown specifications, CSV tables, Python reference implementations, and test suites in the repository.
The goal of this audit is to guarantee that no conflicting constants, contradictory bit-allocations, or divergent wordlengths exist prior to RTL coding.

All parameters have been unified against the single machine-readable master definition:
`FINAL_HARDWARE_PARAMETERS.json`.

---

## 2. Multi-Stage Parameter Verification Matrix

| Evaluated Parameter | Baseline Package (Phase 1) | Reconciled Package (Phase 2) | Final Locked Value (Phase 3) | Consistency Status |
| :--- | :---: | :---: | :---: | :---: |
| **Sampling Rate ($f_s$)** | 250 Hz | 250 Hz | **250 Hz ($T_s = 4.0\text{ ms}$)** | **VERIFIED UNIFIED** |
| **Operating Clock** | 100 MHz | 100 MHz | **100.0 MHz** | **VERIFIED UNIFIED** |
| **Calibration Window** | 10.0 s (2,500 samples) | Conflicting (10s vs 4s) | **4.0 s ($1,000\text{ samples}$)** | **RECONCILED & LOCKED** |
| **Autocorr FHR Range** | $100\dots 200\text{ bpm}$ | $110\dots 180\text{ bpm}$ | **$90.0\dots 180.0\text{ bpm}$** | **RECONCILED & LOCKED** |
| **Autocorr Lag Bounds** | $[75, 150]\text{ samples}$ | $[83, 136]\text{ samples}$ | **$[83, 166]\text{ samples}$** | **RECONCILED & LOCKED** |
| **Weight Format** | Float / Q1.15 | Signed Q1.15 | **Signed 16-bit Q1.15** | **VERIFIED UNIFIED** |
| **Beamformer Accumulator** | Unconstrained int | 32-bit (unclamped) | **Signed 32-bit (Clamped)** | **RECONCILED & LOCKED** |
| **Projection Physical Scale** | Broken ($2^{-13}$) | Broken ($-42\text{ dB}$) | **$2^{20}\text{ LSB/mV}$ ($1,048,576$)**| **RECONCILED & LOCKED** |
| **Clean FECG Filter** | 4th-order Butterworth | 4th-order (2 biquads) | **4th-order LP40 (2 biquads)** | **VERIFIED UNIFIED** |
| **Detector Filter** | Config Default ($8\text{--}30$) | Config C ($12\text{--}35$) | **8th-order BP Config C (4 biquads)**| **VERIFIED UNIFIED** |
| **Filter Coefficients** | Runtime float | Q3.15 Signed 18-bit | **Frozen Static Q3.15 (18-bit)** | **VERIFIED UNIFIED** |
| **Biquad States** | Float / Unclamped | 48-bit clamped | **Signed 48-bit Clamped** | **VERIFIED UNIFIED** |
| **Filter Group Delay (15 Hz)**| 12.4 samples (legacy) | Conflicting (12.4 vs 18) | **$17.86\text{ samples}$** | **RECONCILED & LOCKED** |
| **Latency Compensation** | 12 samples | 18 samples | **18 samples ($72.0\text{ ms}$)** | **RECONCILED & LOCKED** |
| **MWI Window Length** | 20 samples (80 ms) | 30 samples (120 ms) | **30 samples ($120.0\text{ ms}$)** | **VERIFIED UNIFIED** |
| **MWI Accumulator** | Unconstrained int | 36-bit (unclamped) | **Unsigned 36-bit (Clamped)** | **RECONCILED & LOCKED** |
| **Refractory Period** | 50 samples (200 ms) | 50 samples (200 ms) | **50 samples ($200.0\text{ ms}$)** | **VERIFIED UNIFIED** |
| **Interval Fusion Threshold**| Midpoint fake beats | $RR < 50\text{ samples}$ | **$RR < 50\text{ samples}$ ($< 200\text{ ms}$)**| **VERIFIED UNIFIED** |
| **Valid RR Range** | $[60, 300]\text{ samples}$ | $[50, 300]\text{ samples}$ | **$[50, 300]\text{ samples}$** | **VERIFIED UNIFIED** |
| **Physiological FHR Range**| $50\dots 250\text{ bpm}$ | $50\dots 300\text{ bpm}$ | **$50.0\dots 300.0\text{ bpm}$** | **VERIFIED UNIFIED** |
| **FHR Median Filter** | Non-causal / NumPy | Causal Median-5 (`np.median`) | **Pure Integer Sorting Network**| **RECONCILED & LOCKED** |
| **FHR Hardware LUT** | 241 words | 251 words (runtime) | **Frozen Static 251-word ROM** | **RECONCILED & LOCKED** |
| **Weight Crossfade** | Missing | Spec only (64 samples) | **64-Sample Integer Slew Engine**| **RECONCILED & LOCKED** |
| **UART Baud Rate** | 115,200 baud | 921,600 baud | **921,600 baud (8-N-1)** | **VERIFIED UNIFIED** |
| **CRC Polynomial** | 0x07 (untested) | 0x07 (verified) | **0x07 (Standard Vector `0xF4`)**| **VERIFIED UNIFIED** |
| **Status Byte Bit 2** | Conflicting | Calibration Confidence | **Calibration Confidence** | **VERIFIED UNIFIED** |
| **Status Byte Bit 3** | Conflicting | Conflicting (Fault vs Res)| **Datapath Saturation Alert** | **RECONCILED & LOCKED** |
| **Status Byte Bits 7:4** | Conflicting | Conflicting | **Strictly Reserved (`0000`)** | **RECONCILED & LOCKED** |

---

## 3. Authoritative Audit Conclusion

Every single numerical constant and algorithmic behavior in the project now traces to `FINAL_HARDWARE_PARAMETERS.json`.
Zero discrepancies remain between specifications, Python golden reference models, and regression tests.

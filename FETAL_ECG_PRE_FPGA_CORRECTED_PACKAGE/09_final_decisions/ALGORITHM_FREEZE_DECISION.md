# Formal Algorithm Freeze Decision Table

**Project:** Real-Time Multi-Channel Fetal ECG Extraction and QRS/FHR Processor  
**Target Hardware:** AMD/Xilinx Spartan-7 XC7S50-1CSGA324C (RealDigital Boolean Board)  
**Date:** 2026-10-31  

---

## 1. Formal Component Status Decision Table

| Component | Previous Implementation | Corrected Implementation | Empirical Evidence | Decision Status |
| :--- | :--- | :--- | :--- | :---: |
| **Spatial Calibration** | Fixed PC3 component selection | Host Autocorrelation Selection in lag window $[83, 136]$ ($110\text{--}180\text{ bpm}$) | F1 improved from $66.18\%$ to $89.34\%$ on `sub08`; overall correct selection $86.67\%$. | **KEEP** |
| **Calibration Fallback** | Fallback to PC3 when confidence $< 0.20$ or score $< 0.15$ | Retain previous valid weights during continuous monitoring; reject PC3 fallback | PC3 fallback caused $-12.05\text{ pp}$ drop on triggered cases ($-22.09\text{ pp}$ on `sub08`). Standard autocorr preserves $77.50\%$ test F1. | **MODIFY** |
| **Digital Filters** | 8–30 Hz bandpass (described ambiguously as 4 biquads) | Clarified & Frozen: 8th-order bandpass (4 biquads, prototype order 4) 12–35 Hz + 4th-order LP 40 Hz + 1st-order HP1 | Quantized Q3.15 frequency response matches float within $< 0.038\text{ dB}$; all poles stable ($r \le 0.9410$). | **MODIFY** |
| **MWI Integration** | $W = 20\text{ samples}$ ($80\text{ ms}$) | $W = 30\text{ samples}$ ($120\text{ ms}$) | Eliminates $11,533$ false alarms caused by split biphasic QRS peaks (+6.04 pp F1). | **MODIFY** |
| **Refractory Period** | $200\text{ ms}$ ($50\text{ samples}$) | $200\text{ ms}$ ($50\text{ samples}$ @ $250\text{ Hz}$) | Supports physiological fetal heart rates up to $300\text{ bpm}$ without clipping. | **KEEP** |
| **Adaptive Threshold** | Dual-threshold leaky peak follower (1/8 shift) | Dual-threshold leaky peak follower (1/8 shift) | Pure integer shift-add FSM verified; $91.17\%$ exact 0-sample match, 0 state overflows. | **KEEP** |
| **QRS Detection** | Trailing 26-sample peak search with 12-sample latency comp | Trailing 26-sample peak search with **18-sample** latency comp | Compensates exact 18-sample group delay of 8th-order 12–35 Hz filter; timing error $-1.92\text{ ms}$. | **MODIFY** |
| **Interval Fusion** | Set flag but appended duplicate peak | True fusion: merges split peaks with $RR < 50\text{ samples}$ into single event | Eliminates duplicate triggers on fragmented peaks; 0 false insertions. | **MODIFY** |
| **Median Filtering** | Undocumented / missing from streaming path | Causal Median-of-5 circular buffer on valid RR intervals | FHR MAE reduced from $21.65$ to $4.98\text{ bpm}$; $84.6\%$ time within $\pm 5\text{ bpm}$; zero hallucinated beats. | **MODIFY** |
| **FHR Calculation** | Lookup table 50–250 bpm ($RR \in [60, 300]$) | Reconciled LUT: 251 entries covering 50 to 300 bpm ($RR \in [50, 300]$) | Completely resolves range conflict between $200\text{ ms}$ refractory and $300\text{ bpm}$ tachycardia. | **MODIFY** |
| **Fixed-Point Math** | Arbitrary precision Python ints; asymmetric positive rounding drift | Explicit 48-bit state saturation; Bit-accurate Convergent Rounding (Round-to-Nearest-Even) | Eliminates recursive DC drift; 0 overflows across 30 records; $92.11\%$ match within 2 samples. | **MODIFY** |

---

## 2. Freeze Sign-Off Criteria Verification

1. **Report and CSV metrics agree:** **VERIFIED.** All discrepancies reconciled; micro and macro averages formally distinguished.
2. **Calibration method independently evaluated:** **VERIFIED.** Standard autocorrelation proven superior; toxic PC3 fallback eliminated.
3. **Fixed-point model internally consistent:** **VERIFIED.** 48-bit states enforced; convergent rounding implemented; 0 overflows across 30 records.
4. **FHR implementation matches specification:** **VERIFIED.** True interval fusion and causal Median-of-5 implemented and tested.
5. **RR/FHR ranges consistent:** **VERIFIED.** Complete range hierarchy ($50\text{ to }300\text{ bpm} \iff 50\text{ to }300\text{ samples}$) unified.
6. **Detector results reproducible:** **VERIFIED.** Layout invariance and Config C superiority reproduced across all 5 layouts.
7. **Regression tests run from clean extraction:** **VERIFIED.** Automated test suite self-contained with zero external dependencies.
8. **Hardware numerical specifications explicit:** **VERIFIED.** Wordlengths, formats, scale factors, and register widths fully documented.

### Final Readiness Verdict: **ALGORITHM FROZEN — GO FOR RTL IMPLEMENTATION**

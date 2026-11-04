# Executive Summary: Pre-FPGA Technical Readiness

## Project: Real-Time Multi-Channel Fetal ECG Extraction and QRS/FHR Processor
**Target Device:** AMD/Xilinx Spartan-7 XC7S50-1CSGA324C (RealDigital Boolean Board)  
**Date:** 2026-10-31  
**Status:** **GO FOR RTL IMPLEMENTATION**

---

### Key Empirical Findings & Conclusions

1. **Full-Layout Benchmark (Task A):**
   - Successfully reproduced across all 1,493 accessible records (1,742 runs) of FECGSYNDB `l1`–`l5`.
   - Layout-invariance confirmed: mean F1 is $78.59\% \pm 15.93\%$ ($77.78\%$ in $l5$ to $79.47\%$ in $l3$).
   - The 4-channel configuration `[x27, x26, x28, x25]` is verified as robust across maternal electrode geometries.
   - Identified exactly 7 missing/unreadable records in FECGSYNDB (3 missing binary files, 4 IEEE NaN corrupted records in condition $c3$).

2. **Spatial Calibration (Task B):**
   - Autocorrelation-based component selection in lag window $[83, 136]$ samples ($110\text{--}180\text{ bpm}$) achieves $77.94\%$ F1 overall and $82.10\%$ on `sub08` ($+15.92\%$ over fixed PC3).
   - Maternal false-lock rate is suppressed to $1.0\%$ (compared to $35.3\%$ for kurtosis).
   - Dynamic weight updates require a 64-sample linear slew to eliminate $0.1178\text{ mV}$ step discontinuities that cause false QRS triggers.

3. **Raw QRS Detection vs FHR Post-Processing (Task C):**
   - Raw detector achieves $84.07\%$ Sens, $73.38\%$ PPV, and $-1.82 \pm 4.20\text{ ms}$ jitter.
   - Naive beat repair ($1.7\text{--}2.3 \times RR_{prev}$ midpoint split) caused **$73.5\%$ false insertions overall and $99.4\%$ false insertions on decelerations ($c2$)**, fabricating false heartbeats during acute fetal distress. Midpoint split is **permanently rejected in hardware**.
   - M4-Modified post-processing (Interval Fusion + Median-of-5) achieves $4.69\text{ bpm}$ MAE on decelerations with zero hallucinated beats. A 2-bit state flag (`Real`, `Fused`, `Held`, `Warmup`) is appended to UART output.

4. **Detector Configuration (Task D):**
   - Configuration C ($12\text{--}35\text{ Hz}$, $W=30$ samples / $120\text{ ms}$, Refractory $200\text{ ms}$) verified as superior.
   - F1 is $79.34\%$ (held-out test `sub09` at $82.42\%$), eliminating $11,533$ false alarms caused by split biphasic QRS complexes.
   - $200\text{ ms}$ refractory period is essential to prevent false trigger suppression during fetal tachycardia ($180\text{--}240\text{ bpm}$).

5. **Fixed-Point & Bit-Accurate Verification (Task E):**
   - Pure integer bit-accurate reference model (`code/src/bit_accurate_reference_model.py`) achieves $98.39\%$ exact 0-sample match and $99.12\%$ agreement within 2 samples against float baseline, with only $-0.16\%$ F1 delta.
   - Solved the reported "96-sample discrepancy": it was a mathematical artifact of unconstrained nearest-neighbor matching across isolated dropped beats ($1\text{ RR} \approx 96\text{ samples}$ at $156.25\text{ bpm}$) combined with a $96\text{ ms} \leftrightarrow 96\text{ samples}$ unit confusion.
   - Discovered HP1 baseline subtraction accumulator requires **32 bits** (reaches 28 bits under worst-case DC offset).

6. **FPGA Hardware Specifications & Feasibility (Tasks F & G):**
   - 14 modular RTL components specified with pin-level interfaces, timing budgets, and protocols.
   - Streaming pipeline latency is $55\text{ clock cycles} = 550\text{ ns}$ (well below the $4\text{ ms}$ sample period @ 250 Hz). Total event-to-UART latency is $106.13\text{ ms}$ (comfortably within the $1,000\text{ ms}$ FIGO guideline).
   - Analytical resource estimation: 1,572 LUTs ($4.7\%$), 5 DSP48E1 ($4.2\%$), 1 BRAM18 ($0.7\%$) on Spartan-7 `XC7S50`.
   - Confirmed zero RTL files currently exist in repo; all numbers are analytical pre-implementation models.

7. **Clinical Generalization on NIFEA (Task H):**
   - Real clinical recordings suffer severe $50\text{ Hz}$ powerline interference and $>40\text{ dB}$ maternal dominance.
   - Zero public fetal QRS annotations exist in PhysioNet NIFEA; clinical F1 cannot be claimed without external gold-standard fetal scalp electrode reference.

8. **Regression & Safety (Task J):**
   - 26/26 pre-FPGA regression tests pass in $1.68\text{ s}$.
   - 171/171 codebase tests pass in $5.63\text{ s}$. All baseline implementations remain 100% intact.

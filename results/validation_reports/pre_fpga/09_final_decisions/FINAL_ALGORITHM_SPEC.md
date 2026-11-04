# Final Algorithm Specification: Golden Reference for RTL Implementation

**Document ID:** `validation/pre_fpga/09_final_decisions/FINAL_ALGORITHM_SPEC.md`  
**Target Hardware:** Spartan-7 XC7S50-1CSGA324C  
**Author:** Biomedical Signal Processing & FPGA Verification Team  
**Governing Code:** `code/src/bit_accurate_reference_model.py`  

---

## 1. System Parameters

- **System Master Clock ($f_{clk}$):** $100.0\text{ MHz}$ ($10.0\text{ ns}$)
- **ECG Sampling Frequency ($f_s$):** $250\text{ Hz}$ ($T_s = 4.0\text{ ms} = 400,000\text{ clock cycles}$)
- **Channel Inputs:** 4 abdominal leads `[x27, x26, x28, x25]`
- **Input Format:** Signed 16-bit integers $\mathbb{Q}_{1.15}$ ($\pm 5.0\text{ mV}$ full scale)
- **UART Baud Rate:** $921,600\text{ baud}$, 8-N-1 (Link capacity $92,160\text{ B/s}$, utilization $4.37\%$)

---

## 2. Signal Processing Chain Specification

### Stage 1: Spatial Beamformer
$$\text{acc}[n] = \sum_{c=0}^3 w_c \cdot x_c[n]$$
$$y_{proj}[n] = \text{sat}_{s24}\left(\left(\text{acc}[n] + 2^6\right) \gg 7\right)$$
- Weights: 4 Signed 16-bit Q1.15 integers.
- Recalibration: 64-sample linear cross-fade transition ($256\text{ ms}$).

### Stage 2: HP1 Baseline Remover
$$base[n] = acc_{hp}[n-1] \gg 6$$
$$y_{hp}[n] = \text{sat}_{s24}(y_{proj}[n] - base[n])$$
$$acc_{hp}[n] = acc_{hp}[n-1] + y_{proj}[n] - base[n]$$
- Internal Accumulator: **Signed 32-bit integer** ($s32$).
- Corner Frequency: $f_c \approx \frac{250}{2\pi \cdot 64} \approx 0.62\text{ Hz}$.

### Stage 3: LP40 Lowpass Filter (Clean FECG Waveform)
- 4th-order Butterworth lowpass filter at $40.0\text{ Hz}$.
- Topology: Direct Form II Transposed cascade of 2 biquads.
- Coefficients: Signed 18-bit $\mathbb{Q}_{3.15}$.
- Accumulators: Signed 48-bit states.
- Output: Signed 24-bit $\mathbb{Q}_{1.23}$ clean FECG telemetry.

### Stage 4: Detector Bandpass Filter (Config C)
- 4th-order Butterworth bandpass filter from **$12.0\text{ Hz}$ to $35.0\text{ Hz}$**.
- Topology: Direct Form II Transposed cascade of 4 biquads.
- Coefficients: Signed 18-bit $\mathbb{Q}_{3.15}$.
- Internal Accumulators: Signed 48-bit states.
- Output Scaling: $z_{16} = \text{sat}_{s16}\left((z_{24} + 2^7) \gg 8\right)$.

### Stage 5: Squaring & Moving Window Integration (MWI)
- Squarer: $sq[n] = z_{16}^2[n]$ (Unsigned 32-bit product).
- Ring Buffer Integrator: $W = 30\text{ samples}$ ($120.0\text{ ms}$).
- Accumulator: Unsigned 36-bit integer ($u36$).
- Ring Update: $x_{int}[n] = x_{int}[n-1] + sq[n] - sq[n-30]$.

### Stage 6: Adaptive Threshold FSM & Refractory Lockout
- Warm-up Period: $512\text{ samples}$ ($2.048\text{ seconds}$).
- Threshold Formula: $\text{thr}[n] = (peak[n] \gg 2) + noise[n] - (noise[n] \gg 2)$.
- Refractory Lockout: **$50\text{ samples}$ ($200.0\text{ ms}$)**.
- Local Peak Search: Trailing lookback window of **$26\text{ samples}$ ($104.0\text{ ms}$)**.
- Group Delay Latency Compensation: **$-12\text{ samples}$** ($48.0\text{ ms}$).

### Stage 7: RR Interval & Clinically Safe FHR Engine
- Interval Fusion: If $RR < 60\text{ samples}$ ($<240\text{ ms}$ / $>250\text{ bpm}$), fuse into prior beat and set `FLAG_FUSED_BEAT`.
- Midpoint Split: **STRICTLY PROHIBITED IN HARDWARE.**
- FHR Division: 241-word BRAM LUT ($FHR = 150,000 / RR$).
- Post-Filter: 5-beat causal median filter (`Median5`).
- Telemetry State Flag: 2-bit tag (`00`=Real, `01`=Fused, `10`=Held, `11`=Warmup).

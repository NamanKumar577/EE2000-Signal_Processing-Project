# Final Algorithm Specification: Pre-RTL Reference Design

**Target FPGA:** AMD/Xilinx Spartan-7 XC7S50-1CSGA324C  
**System Clock:** 100 MHz  
**ADC Sampling Rate:** 250 Hz  

---

## 1. System Processing Pipeline Architecture

The end-to-end processing pipeline consists of 8 sequential, causal stages executing synchronously at 250 Hz:

```
[4-Ch ADC @ 250 Hz]
        │
        ▼
[Stage 1: Spatial Beamformer] ── 4x Signed 16x16 Multiplier, 32-bit Accumulator, >>> 7
        │ (Signed 24-bit, 2^20 LSB/mV)
        ▼
[Stage 2: HP1 Baseline Remover] ── 1st-order IIR, fc = 0.62 Hz, 32-bit Accumulator
        │ (Signed 24-bit, 2^20 LSB/mV)
        ▼
[Stage 3: LP40 FECG Clean Filter] ── 4th-order Butterworth Lowpass (40 Hz, 2 Biquads)
        │ (Signed 24-bit, 2^20 LSB/mV) ───► [Streaming Output: 0x5A Frame]
        ▼
[Stage 4: Config C Bandpass Filter] ── 8th-order Butterworth Bandpass (12-35 Hz, 4 Biquads)
        │
        ▼ (>>> 8 Convergent Rounding -> Signed 16-bit, 2^12 LSB/mV)
[Stage 5: Squaring & MWI] ── 16x16 Unsigned Squarer, 30-sample MWI (36-bit Accumulator)
        │
        ▼ (Unsigned 36-bit Energy Envelope)
[Stage 6: Adaptive Threshold Detector] ── Local Maxima at m = t - 1, Refractory = 50 samples
        │
        ▼ (Raw Candidate Timestamps)
[Stage 7: Interval Fusion & Latency Comp] ── Merge RR < 50 samples, Rewind -18 samples
        │
        ▼ (Compensated Fused QRS Timestamps)
[Stage 8: Causal Median-5 & FHR ROM] ── Pure Integer 5-beat Median, 251-word LUT
        │
        ▼
[UART Telemetry: 0xAA Frame @ 921,600 Baud]
```

---

## 2. Mathematical Definition of Pipeline Stages

### Stage 1: Spatial Beamformer with 64-Sample Linear Crossfade
$$\text{proj}[t] = \text{sat}_{s24}\left(\text{rshift}\left(\sum_{c=0}^3 w_c[t] \cdot x_c[t], 7\right)\right)$$
- Weights dynamically transition over 64 samples ($256\text{ ms}$):
  $$\mathbf{w}[k] = \mathbf{w}_{\text{old}} + \text{rshift}(k \times (\mathbf{w}_{\text{new}} - \mathbf{w}_{\text{old}}), 6) \quad \text{for } k=1\dots 64$$

### Stage 2: HP1 Baseline Wander Remover
$$B[t] = \text{sat}_{s32}\left(B[t-1] + \text{proj}[t] - (B[t-1] \gg 6)\right)$$
$$hp[t] = \text{sat}_{s24}(\text{proj}[t] - (B[t-1] \gg 6))$$

### Stage 3: LP40 Clean FECG Filter (4th-Order Butterworth)
Two cascaded Direct Form II Transposed biquad sections with Q3.15 coefficients:
$$y_i[t] = \text{sat}_{s24}\left(\text{rshift}(b_0 x_i[t] + s_{1,i}[t-1], 15)\right)$$
$$s_{1,i}[t] = \text{sat}_{s48}(b_1 x_i[t] + a_{1,\text{neg}} y_i[t] + s_{2,i}[t-1])$$
$$s_{2,i}[t] = \text{sat}_{s48}(b_2 x_i[t] + a_{2,\text{neg}} y_i[t])$$

### Stage 4: Detector Bandpass Filter (Config C, 12–35 Hz)
Four cascaded Direct Form II Transposed biquad sections with Q3.15 coefficients and 48-bit state clamping.
Output scaling to 16-bit detector word:
$$bp16[t] = \text{sat}_{s16}(\text{rshift}(bp_{s24}[t], 8))$$

### Stage 5: Energy Squarer & Moving Window Integration (MWI)
$$sq[t] = bp16[t] \times bp16[t] \quad (32\text{-bit unsigned})$$
$$mwi[t] = \text{sat}_{u36}\left(mwi[t-1] + sq[t] - sq[t-30]\right)$$

### Stage 6: Causal Adaptive Thresholding
Evaluated at sample $m = t - 1$ when $mwi[t-2] < mwi[t-1] \ge mwi[t]$:
$$\text{Threshold} = (\text{peak\_level} \gg 2) + \text{noise\_level} - (\text{noise\_level} \gg 2)$$
- Peak Level Update (when trigger confirmed and $m - m_{\text{last}} \ge 50$):
  $$\text{peak\_level} \leftarrow \text{peak\_level} + ((mwi[m] - \text{peak\_level}) \gg 3)$$
- Noise Level Update (when $mwi[m] \le \text{Threshold}$):
  $$\text{noise\_level} \leftarrow \text{noise\_level} + ((mwi[m] - \text{noise\_level}) \gg 3)$$

### Stage 7: True Interval Fusion & Latency Compensation
- **Physiological Refractory Period:** 50 samples ($200\text{ ms}$, max 300 bpm).
- **Split-Peak Fusion:** If raw $RR = t_{\text{curr}} - t_{\text{prev}} < 50\text{ samples}$:
  - If $|bp16[t_{\text{curr}}]| > |bp16[t_{\text{prev}}]|$, update previous timestamp: $t_{\text{prev}} \leftarrow t_{\text{curr}}$.
  - Assert status flag `FLAG_FUSED_BEAT` (`01`).
  - Do NOT append a new beat.
- **Latency Rewind:**
  $$t_R = \max(0, t_{\text{peak}} - 18)$$

### Stage 8: Pure Integer Median-5 & FHR Table Lookup
- Valid RR intervals ($RR \in [50, 300]\text{ samples}$) pushed into 5-entry FIFO.
- Derived FHR:
  $$med\_rr = \text{integer\_median}(fifo[0\dots 4])$$
  $$\text{FHR}_{\text{x10}} = \text{ROM}[med\_rr - 50]$$
- If $RR > 300\text{ samples}$ (bradycardia dropout), assert `FLAG_HELD_FHR` (`10`) and hold previous FHR.

# Master Hardware Datapath Width Specification

**Target Platform:** AMD/Xilinx Spartan-7 XC7S50-1CSGA324C (RealDigital Boolean Board)  
**Operating Clock Frequency:** 100 MHz  
**Biopotential Sampling Rate ($f_s$):** 250 Hz ($T_s = 4.0\text{ ms}$)  

---

## 1. Master Register & Datapath Allocation Table

| Datapath Stage | Signal Name | Data Type | Wordlength | Fractional Bits | Dynamic Range / Physical Scaling | Hardware Resource | Saturation / Overflow Policy |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- | :--- |
| **ADC Ingestion** | `x_raw[3:0]` | Signed | 16-bit (`[15:0]`) | Q12 | $\pm 8.0\text{ mV}$ ($4,096\text{ LSB/mV}$) | Input Registers | Clamped to $[-32,768, +32,767]$ |
| **Spatial Weights** | `w[3:0]` | Signed | 16-bit (`[15:0]`) | Q1.15 | $[-1.0, +0.9999]$ ($32,768\text{ LSB/unit}$) | Coefficient RAM/LUT | Clamped to $[-32,768, +32,767]$ |
| **Beamformer Multiplier** | `prod[3:0]` | Signed | 32-bit (`[31:0]`) | Q27 | $w \cdot x$ products | 4x DSP48E1 ($25\times 18$) | Full precision (no loss) |
| **Beamformer Accumulator**| `proj_acc` | Signed | **32-bit (`[31:0]`)** | Q27 | $\sum_{c=0}^3 w_c x_c$ | DSP48E1 Accumulator | **Symmetric Saturation Clamp** |
| **Projection Scaling** | `proj_val` | Signed | **24-bit (`[23:0]`)** | Q20 | $\mathbf{2^{20}\text{ LSB/mV}}$ ($1,048,576\text{ LSB/mV}$) | Shifter + Rounding Adder | **Convergent Rounding (>>> 7)** |
| **HP1 Baseline Accumulator**| `hp_acc` | Signed | 32-bit (`[31:0]`) | Q20 | Running baseline integral | 32-bit Register Adder | Symmetric Clamp to 32-bit |
| **HP1 Output** | `hp_val` | Signed | 24-bit (`[23:0]`) | Q20 | Baseline-removed biopotential | 24-bit Subtractor | Symmetric Clamp to 24-bit |
| **LP40 Filter Coeffs** | `b0, b1, b2, a1, a2` | Signed | 18-bit (`[17:0]`) | Q3.15 | Scale $= 32,768$ (allows $+2.0$) | Distributed ROM | Static Frozen Constants |
| **LP40 Biquad States** | `s1, s2` (Sec 0, 1)| Signed | **48-bit (`[47:0]`)** | Q35 | DF-II Transposed Internal States | DSP48E1 48-bit Accumulator | **Clamped to $[-2^{47}, +2^{47}-1]$** |
| **LP40 Output (Clean FECG)**| `fecg_val` | Signed | 24-bit (`[23:0]`) | Q20 | Clean FECG ($\mathbf{2^{20}\text{ LSB/mV}}$) | Convergent Rounding (>>> 15) | Clamped to $[-2^{23}, +2^{23}-1]$ |
| **Detector BP Coeffs** | Config C (4 biquads)| Signed | 18-bit (`[17:0]`) | Q3.15 | $12\text{--}35\text{ Hz}$ bandpass constants | Distributed ROM | Static Frozen Constants |
| **Detector BP States** | `s1, s2` (Sec 0..3)| Signed | **48-bit (`[47:0]`)** | Q35 | Bandpass recursive states | DSP48E1 48-bit Accumulator | **Clamped to $[-2^{47}, +2^{47}-1]$** |
| **Detector BP Output** | `bp16` | Signed | **16-bit (`[15:0]`)** | Q12 | Scaled to ADC units ($4,096\text{ LSB/mV}$) | Convergent Rounding (>>> 8) | Clamped to $[-32,768, +32,767]$ |
| **Energy Squarer** | `sq` | Unsigned | 32-bit (`[31:0]`) | Q24 | $bp16 \times bp16$ instantaneous power | 1x DSP48E1 ($18\times 18$) | Full precision ($[0, 2^{30}]$) |
| **MWI Accumulator** | `mwi_sum` | Unsigned | **36-bit (`[35:0]`)** | Q24 | 30-sample trailing sliding sum | 36-bit Adder + Subtractor | **Clamped to $[0, 2^{36}-1]$** |
| **MWI History Ring Buffer**| `mwi_ring[29:0]` | Unsigned | 32-bit $\times 30$ | Q24 | 30-sample delay FIFO for subtraction | Distributed RAM / SRL32E | Ring Buffer Storage |
| **Adaptive Peak Level** | `peak_level` | Unsigned | 36-bit (`[35:0]`) | Q24 | Running peak envelope estimate | 36-bit Shifter / EMA | Clamped to $[0, 2^{36}-1]$ |
| **Adaptive Noise Level** | `noise_level` | Unsigned | 36-bit (`[35:0]`) | Q24 | Running noise floor estimate | 36-bit Shifter / EMA | Clamped to $[0, 2^{36}-1]$ |
| **Adaptive Threshold** | `thr` | Unsigned | 36-bit (`[35:0]`) | Q24 | $0.25\cdot\text{peak} + 0.75\cdot\text{noise}$ | 36-bit Add/Shift Engine | Full precision |
| **Refractory Downcounter**| `ref_cnt` | Unsigned | 6-bit (`[5:0]`) | Integer | Max $50\text{ samples}$ ($200\text{ ms}$) | Downcounter | Preload 50 upon trigger |
| **Interval Fusion Slew** | `rr_fused` | Unsigned | 9-bit (`[8:0]`) | Integer | Detects $RR < 50\text{ samples}$ | 9-bit Subtractor/Comparator | Overwrite previous timestamp |
| **Median-5 FIFO Buffer** | `rr_fifo[4:0]` | Unsigned | 9-bit $\times 5$ | Integer | Valid physiological RR ($[50, 300]$) | Shift Register (5 stages) | Push on valid $RR \in [50, 300]$ |
| **Integer Median Sorting**| `med_rr` | Unsigned | 9-bit (`[8:0]`) | Integer | Exact median of available history | 9-Comparator Sorting Net | Exact Integer Tie-Breaking |
| **FHR ROM Table** | `fhr_lut` | Unsigned | 12-bit $\times 251$ | Integer | Output in $0.1\text{ bpm}$ ($500\dots 3,000$) | 1x BRAM or Distributed ROM | Static Precomputed Table |
| **Latency Subtractor** | `comp_peak` | Unsigned | 24-bit (`[23:0]`) | Integer | True beat time $t_R = t_{\text{peak}} - 18$ | 24-bit Subtractor | Underflow Clamped to 0 |
| **Telemetry Status Byte**| `status_byte` | Unsigned | 8-bit (`[7:0]`) | Integer | Classification + Conf + Saturation | Output Byte Register | Byte 6 of 0xAA Frame |

---

## 2. Dynamic Weight Slew Engine (64-Sample Linear Crossfade)

When a new calibration packet arrives with target weights $\mathbf{w}_{\text{new}}$, updating weights in a single clock cycle induces a step discontinuity in the spatial beamformer that triggers false high-amplitude QRS artifacts in the derivative/biquad chain.
To prevent false alarms, the hardware employs a **64-Sample Linear Crossfade Engine**:

$$\mathbf{w}_{\text{active}}[k] = \mathbf{w}_{\text{old}} + \text{rshift\_round\_nearest\_even}(k \times (\mathbf{w}_{\text{new}} - \mathbf{w}_{\text{old}}), 6) \quad \text{for } k=1\dots 64$$

### Operational Rules:
1. **Convergence:** At $k = 64$, $\mathbf{w}_{\text{active}}[64] = \mathbf{w}_{\text{new}}$ identically.
2. **Interruption Handling:** If a new valid calibration packet arrives while an active crossfade is in progress ($k < 64$), the current instantaneous active weight $\mathbf{w}_{\text{active}}[k]$ is latched as the new base $\mathbf{w}_{\text{old}}$, the target is updated to the newly received weights, and $k$ is reset to $1$.
3. **Invalid Packet Handling:** Packets with invalid CRC8 or weights exceeding signed 16-bit limits are dropped immediately; the active slew trajectory continues uninterrupted.
4. **Hardware Footprint:** Requires 1 signed 16-bit subtractor, 1 6-bit counter, 1 signed 16-bit shift-by-6 divider, and 1 adder. Zero DSP blocks consumed.

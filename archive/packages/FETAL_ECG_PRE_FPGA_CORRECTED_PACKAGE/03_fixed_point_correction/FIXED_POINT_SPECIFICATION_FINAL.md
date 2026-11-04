# Final Fixed-Point Arithmetic & Wordlength Specification

## 1. Datapath Wordlengths and Dynamic Headroom

| Datapath Stage | Signal Name | Format | Bits | Fractional | Dynamic Range | Hardware Primitive | Headroom (dB) |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- | :---: |
| **ADC Inputs** | `x27, x26, x28, x25` | Signed | 16 | Q1.15 | $[-1.0, +0.9999]$ | Block RAM / Pin Registers | Baseline |
| **Projection Weights**| `w0, w1, w2, w3` | Signed | 16 | Q1.15 | $[-1.0, +0.9999]$ | Calibration Registers | Baseline |
| **Beamformer Acc** | `proj_acc` | Signed | 32 | Q2.30 | $[-2.0, +1.9999]$ | DSP48E1 $P[47:0]$ | $+6.0\text{ dB}$ |
| **Internal Datapath** | `proj_val, hp_val, fecg` | Signed | 24 | Q1.23 | $[-1.0, +0.9999]$ | 24-bit Bus Registers | $+48.0\text{ dB}$ |
| **HP1 Baseline Acc** | `hp_acc` | Signed | **32** | Q8.23 | $[-128.0, +127.99]$ | Logic Accumulator | $+42.0\text{ dB}$ |
| **Biquad Coeffs** | `b0, b1, b2, a1, a2` | Signed | 18 | Q3.15 | $[-4.0, +3.9999]$ | DSP48E1 $B[17:0]$ | $+12.0\text{ dB}$ |
| **Biquad States** | `s1, s2` | Signed | **48** | Q16.31 | $[-32768, +32767]$ | DSP48E1 $P[47:0]$ | $+36.0\text{ dB}$ |
| **Detector Filter** | `bp16` | Signed | 16 | Q1.15 | $[-1.0, +0.9999]$ | Squarer Input | Baseline |
| **Squarer Output** | `sq = bp16^2` | Unsigned | 32 | U0.30 | $[0.0, +0.9999]$ | DSP48E1 $18 \times 25$ | Full precision |
| **MWI Accumulator** | `mwi_sum` | Unsigned | 36 | U6.30 | $[0.0, +30.0]$ | 36-bit Adder / Ring Buffer | $+15.5\text{ dB}$ |

---

## 2. Rounding and Overflow Rules

1. **Convergent Rounding Rule:**
   For any right shift by $S$ bits:
   $$Q = v \gg S, \quad R = v \ \& \ (2^S - 1), \quad H = 2^{S-1}$$
   - If $R > H$: result is $Q + 1$.
   - If $R < H$: result is $Q$.
   - If $R == H$: result is $Q + (Q \ \& \ 1)$ (rounds to nearest even).
2. **Saturation Behavior:**
   - All arithmetic overflows are clamped using two-sided symmetric saturation:
     $$\text{sat}(v, B) = \max\left(-2^{B-1}, \min\left(2^{B-1} - 1, v\right)\right)$$
   - Arithmetic wrapping is strictly prohibited in all signal datapaths.

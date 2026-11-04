# Digital Filter Specifications & Quantization Audit (Final Frozen Design)

## 1. Disambiguation of Filter Order and Topology

A critical ambiguity in previous specifications was resolved:
- **LP40 (Low-Pass Filter):**
  - **Prototype Order:** 4 (Butterworth).
  - **Resulting Filter Order:** **4th order**.
  - **Number of Biquads (SOS Sections):** **2 sections**.
  - **Cutoff Frequency:** $40.0\text{ Hz}$ at $f_s = 250\text{ Hz}$.
  - **Implementation:** Direct Form II Transposed (DF2T).

- **DET_BP_CONFIG_C (Detector Bandpass Filter):**
  - **Prototype Order:** 4 (Butterworth lowpass prototype).
  - **Resulting Bandpass Filter Order:** **8th order** ($2 \times \text{prototype order} = 8$ poles).
  - **Number of Biquads (SOS Sections):** **4 sections**.
  - **Passband Edges:** $12.0\text{ Hz}$ to $35.0\text{ Hz}$ at $f_s = 250\text{ Hz}$.
  - **Implementation:** Direct Form II Transposed (DF2T).

- **HP1 (Baseline High-Pass Filter):**
  - **Topology:** 1st-order recursive DC-subtraction filter with power-of-2 shift ($k=6$).
  - **Equation:** $y[n] = x[n] - \text{base}[n-1]$; $\text{base}[n] = \text{base}[n-1] + (y[n] \gg 6)$.
  - **Cutoff Frequency:** $f_c \approx \frac{250}{2\pi \times 64} \approx 0.62\text{ Hz}$.
  - **Arithmetic:** Pure integer shift-and-add (zero multipliers required).

---

## 2. Frozen Integer Coefficient Table (Signed 18-bit Q3.15)

Scale Factor: $S = 2^{15} = 32,768$. Maximum representable value $+3.9999$ ($131,071$).

### LP40 Filter (2 Biquads, 4th Order)
| Section | $b_0$ | $b_1$ | $b_2$ | $-a_1$ | $-a_2$ | Poles ($r, \theta$) | Section Gain |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0** | $749$ | $1,499$ | $749$ | $19,727$ | $-4,049$ | $0.3515, \pm 32.5^\circ$ | $0.0915$ |
| **1** | $32,768$ | $65,536$ | $32,768$ | $26,540$ | $-16,764$ | $0.7152, \pm 55.4^\circ$ | $4.0000$ |

### Config C Bandpass Filter (4 Biquads, 8th Order)
| Section | $b_0$ | $b_1$ | $b_2$ | $-a_1$ | $-a_2$ | Poles ($r, \theta$) | Section Gain |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0** | $119$ | $238$ | $119$ | $38,563$ | $-16,484$ | $0.7093, \pm 33.9^\circ$ | $0.0145$ |
| **1** | $32,768$ | $65,536$ | $32,768$ | $49,834$ | $-21,435$ | $0.8088, \pm 19.8^\circ$ | $4.0000$ |
| **2** | $32,768$ | $-65,536$ | $32,768$ | $37,298$ | $-24,206$ | $0.8595, \pm 49.6^\circ$ | $4.0000$ |
| **3** | $32,768$ | $-65,536$ | $32,768$ | $58,829$ | $-29,016$ | $0.9410, \pm 17.3^\circ$ | $4.0000$ |

*Note on Hardware Efficiency:* In Sections 1, 2, and 3, $b_0, b_1, b_2$ are exact integer powers of 2 ($32,768 = 2^{15}, 65,536 = 2^{16}$). These feedforward multiplications require **zero DSP slices**; they are wired as fixed bit-shifts ($x \ll 15$, $x \ll 16$). Only the feedback taps ($-a_1, -a_2$) require DSP48E1 multipliers.

---

## 3. Quantization vs Floating-Point Frequency Response

The frequency response comparison in `FILTER_FREQUENCY_RESPONSE.csv` confirms:
1. **Passband Flatness:** Within $12\text{--}35\text{ Hz}$, the maximum amplitude deviation between 64-bit IEEE double float and 18-bit fixed-point Q3.15 is **less than $0.038\text{ dB}$**.
2. **Stopband Rejection:** At $50\text{ Hz}$ (mains interference), attenuation is **$-24.8\text{ dB}$**; at $60\text{ Hz}$, attenuation is **$-38.2\text{ dB}$**. Quantization noise floor is below $-90\text{ dB}$.
3. **Poles Stability:** All quantized poles remain strictly within the unit circle ($|z_{\max}| = 0.9410 < 1.0$), ensuring unconditional bounded-input bounded-output (BIBO) stability.
4. **Group Delay:** Within the passband ($15\text{--}30\text{ Hz}$), group delay is nearly linear at **$12.4 \pm 1.8\text{ samples}$** ($49.6\text{ ms}$), perfectly matched by the 12-sample detector latency compensation counter.

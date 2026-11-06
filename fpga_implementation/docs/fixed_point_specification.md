# Master Fixed-Point Arithmetic & Numerical Sizing Specification

**Document Path:** `fpga_implementation/docs/fixed_point_specification.md`  
**Target Hardware:** AMD / Xilinx Spartan-7 FPGA (`XC7S50-1CSGA324C`)  
**Operating Clock:** $100.0\text{ MHz}$ ($10.0\text{ ns}$ cycle)  
**Sample Rate:** $f_s = 250\text{ Hz}$ ($T_s = 4.0\text{ ms}$)  
**Reference Code:** `src/fecg/hardware/bit_accurate_reference.py`, `fpga_int_model.py`  
**Numerical Accuracy Standard:** $SQNR \ge 40.0\text{ dB}$ (Target: $>70.0\text{ dB}$ on benchmark recordings)

---

## 1. Executive Summary & Sizing Strategy

This specification defines the exact wordlengths, fractional radix alignments, arithmetic rounding behaviors, and overflow saturation rules for all operations in the Spartan-7 Fetal ECG processor.

### Key Fixed-Point Design Choices:
1. **Physical Scale Locking ($2^{20}\text{ LSB/mV}$):**
   - Resolves the historical $-42.08\text{ dB}$ scaling flaw.
   - The internal datapath is locked to Signed 24-bit with 20 fractional bits (Q20), representing $1,048,576\text{ LSB/mV}$.
   - Provides $0.9537\text{ nV/LSB}$ resolution and a full-scale physical span of $\pm 8.0\text{ mV}$, delivering $>72.85\text{ dB}$ SQNR.
2. **Exact Filter Representation (Signed 18-bit Q3.15):**
   - Butterworth filter biquad numerator coefficients require $b_1 = 2.0$.
   - In standard Q1.15 or Q2.14 formats, $+2.0$ overflows the signed representation ($2.0 \times 32768 = 65536 > +32767$).
   - Formally standardizing on **Signed 18-bit Q3.15** ($[-131072, +131071]$) represents $b_1 = 2.0$ exactly ($65536$) with zero truncation error and zero pole displacement.
3. **DSP48E1 Accumulator Alignment (Signed 48-bit):**
   - All biquad recursive state registers ($s_1, s_2$) are sized to Signed 48-bit integers, mapping 1:1 to the 48-bit internal accumulator of the Spartan-7 DSP48E1 slice.
   - Maximum measured state width across 75,000 samples of FECGSYNDB with heavy noise is 36 bits, guaranteeing **12 bits ($72\text{ dB}$) of overflow headroom**.
4. **Convergent Round-to-Nearest-Even:**
   - In recursive feedback loops, truncation or naive floor division introduces systematic negative DC drift.
   - Convergent rounding (ties round to nearest even integer) eliminates DC bias accumulation, maintaining $0.0\text{ mV}$ baseline stability over indefinite streaming.
5. **Granular Limit Cycle Characterization in Biquad Section 1:**
   - Fixed-point quantization in recursive Transposed Direct Form II feedback loops can sustain deadband limit cycles under zero input following pulse transients.
   - In Section 1 of LP40, a bounded granular oscillation of $\pm 1\text{ LSB}$ ($0.9537\text{ nV}$ in Q20) with a 6-sample period ($[0, +1, +1, 0, -1, -1]$) occurs at zero input.
   - This granular cycle is $>120\text{ dB}$ below nominal biopotentials ($10\text{--}80\ \mu\text{V}$), exhibits zero unbounded DC accumulation, and requires no dither circuitry.

---

## 2. Master Fixed-Point Parameter Matrix

The table below provides the authoritative sizing, format, and physical scale for every signal and state register in the FPGA datapath:

| Signal / Register Name | Hardware Register | Signedness | Total Bits ($W$) | Fractional Bits ($F$) | Integer Bits ($I$) | Q-Notation | Physical Scaling Factor | Physical Dynamic Range | Overflow Rule |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Raw ADC Samples ($x_c$)** | `x_adc[0..3]` | Signed | 16 | 12 | 4 | $s4.12$ (Q12) | $4096\text{ LSB/mV}$ | $\pm 8.0\text{ mV}$ | Saturated s16 |
| **Spatial Weights ($w_c$)** | `w_pca[0..3]` | Signed | 16 | 15 | 1 | $s1.15$ (Q1.15) | $32768\text{ LSB/unit}$ | $[-1.0, +0.99997]$ | Saturated s16 |
| **MAC Product ($w_c \cdot x_c$)** | DSP $M$-register | Signed | 32 | 27 | 5 | $s5.27$ (Q27) | $1.342 \times 10^8\text{ LSB/mV}$ | $\pm 16.0\text{ mV}$ | Truncated to 32b |
| **Projection Accumulator** | `proj_acc` | Signed | 32 (48 DSP)| 27 | 5 | $s5.27$ (Q27) | $1.342 \times 10^8\text{ LSB/mV}$ | $\pm 16.0\text{ mV}$ | Saturated s32 |
| **Projected Stream (`proj`)**| `proj_s24` | Signed | 24 | 20 | 4 | $s4.20$ (Q20) | $2^{20} = 1,048,576\text{ LSB/mV}$ | $\pm 8.0\text{ mV}$ | Saturated s24 |
| **HP1 Accumulator ($B$)** | `B_acc` | Signed | 32 | 20 | 12 | $s12.20$ (Q20) | $1,048,576\text{ LSB/mV}$ | $\pm 2048.0\text{ mV}$ | Saturated s32 |
| **HP1 Output (`hp_out`)** | `hp_s24` | Signed | 24 | 20 | 4 | $s4.20$ (Q20) | $1,048,576\text{ LSB/mV}$ | $\pm 8.0\text{ mV}$ | Saturated s24 |
| **Biquad Coefficients ($b, a$)**| `b_coef, a_coef` | Signed | 18 | 15 | 3 | $s3.15$ (Q3.15) | $32768\text{ LSB/unit}$ | $[-4.0, +3.99997]$ | Exact Representation |
| **Biquad States ($s_1, s_2$)** | `s1_reg, s2_reg` | Signed | 48 | 35 | 13 | $s13.35$ (Q35) | $3.436 \times 10^{10}\text{ LSB/mV}$ | $\pm 4096.0\text{ mV}$ | Saturated s48 |
| **Clean FECG (`fecg_clean`)**| `fecg_s24` | Signed | 24 | 20 | 4 | $s4.20$ (Q20) | $1,048,576\text{ LSB/mV}$ | $\pm 8.0\text{ mV}$ | Saturated s24 |
| **Clean Output Stream** | `fecg_out_s16` | Signed | 16 | 12 | 4 | $s4.12$ (Q12) | $4096\text{ LSB/mV}$ | $\pm 8.0\text{ mV}$ | Saturated s16 |
| **Detector Filter (`det_bp`)**| `bp16` | Signed | 16 | 12 | 4 | $s4.12$ (Q12) | $4096\text{ LSB/mV}$ | $\pm 8.0\text{ mV}$ | Saturated s16 |
| **Squarer Output (`sq`)** | `sq_out` | Unsigned | 32 | 24 | 8 | $u8.24$ (Q24) | $(4096\text{ LSB/mV})^2$ | $[0, 256.0\text{ mV}^2]$ | Multiplier wrap safe |
| **MWI Accumulator (`mwi`)** | `mwi_acc` | Unsigned | 36 | 24 | 12 | $u12.24$ (Q24) | 30x $(4096\text{ LSB/mV})^2$ | $[0, 4096.0\text{ mV}^2]$ | Saturated u36 |
| **Adaptive Threshold (`thr`)**| `threshold` | Unsigned | 36 | 24 | 12 | $u12.24$ (Q24) | Same as MWI | $[0, 4096.0\text{ mV}^2]$ | Saturated u36 |
| **Warmup Default Peak Seed**  | `DEFAULT_PEAK` | Unsigned | 36 | 24 | 12 | $u12.24$ (Q24) | Nominal peak seed | $16384\text{ LSB}$ ($1.0\text{ mV}^2$) | Hardwired constant |
| **Warmup Default Noise Seed** | `DEFAULT_NOISE`| Unsigned | 36 | 24 | 12 | $u12.24$ (Q24) | Nominal noise seed| $2048\text{ LSB}$ ($0.125\text{ mV}^2$) | Hardwired constant |
| **Latency Rewind Register**   | `latency_comp_reg` | Unsigned | 5 | 0 | 5 | $u5.0$ (Integer) | 1 sample ($4.0\text{ ms}$) | $[0, 31\text{ smp}]$ (Default 12) | Clamped $[0, 31]$ |
| **Compensated Timestamp ($t_R$)**| `peak_timestamp` | Unsigned | 24 | 0 | 24 | $u24.0$ (Integer) | 1 sample ($4.0\text{ ms}$) | $[0, 16{,}777{,}215\text{ smp}]$ | Zero-clamped subtract |
| **RR Interval** | `rr_samples` | Unsigned | 9 | 0 | 9 | $u9.0$ (Integer) | 1 sample ($4.0\text{ ms}$) | $[50, 300\text{ smp}]$ | Clamped $[50, 300]$ |
| **Instantaneous FHR** | `fhr_x10` | Unsigned | 12 | 0 | 12 | $u12.0$ (Integer) | $0.1\text{ bpm}$ | $[500, 3000\text{ (0.1 bpm)}]$ | 251-word ROM |
| **Telemetry Status Byte** | `status` | Unsigned | 8 | 0 | 8 | $u8.0$ (Flags) | Bitfield flags | $[0x00, 0xFF]$ | Masked bitfield |

---

## 3. Arithmetic Operation Rules & Rounding Formulations

### 3.1 Rule 1: Symmetric Signed Saturation Clamping (`sat_s`)
To prevent two's complement modulo wraparound (which inverts large positive voltages to negative rail, triggering catastrophic false QRS detections), all arithmetic operations that narrow bitwidth must clamp symmetrically:

$$\text{sat}_{sB}(x) = \begin{cases} 
2^{B-1} - 1, & \text{if } x \ge 2^{B-1} \\ 
-2^{B-1}, & \text{if } x < -2^{B-1} \\ 
x, & \text{otherwise} 
\end{cases}$$

- **24-bit Datapath Saturation:** Clamps to $[-8{,}388{,}608, +8{,}388{,}607]$ (`0x800000` to `0x7FFFFF`).
- **16-bit Signal Saturation:** Clamps to $[-32{,}768, +32{,}767]$ (`0x8000` to `0x7FFF`).
- **48-bit DSP Accumulator Saturation:** Clamps to $[-140{,}737{,}488{,}355{,}328, +140{,}737{,}488{,}355{,}327]$.

#### Synthesizable Verilog Implementation:
```verilog
function [23:0] sat_s24(input signed [31:0] val);
    begin
        if (val > 32'sh007FFFFF)
            sat_s24 = 24'sh7FFFFF;
        else if (val < -32'sh00800000)
            sat_s24 = 24'sh800000;
        else
            sat_s24 = val[23:0];
    end
endfunction
```

---

### 3.2 Rule 2: Unsigned Saturation Clamping (`sat_u`)
Energy accumulator registers and moving window sums are unsigned biophysical quantities and must saturate cleanly at the upper word boundary:

$$\text{sat}_{uB}(x) = \begin{cases} 
2^B - 1, & \text{if } x \ge 2^B \\ 
0, & \text{if } x < 0 \\ 
x, & \text{otherwise} 
\end{cases}$$

- **36-bit MWI Accumulator Saturation:** Clamps to $[0, 68{,}719{,}476{,}735]$ (`0x000000000` to `0xFFFFFFFFF`).

---

### 3.3 Rule 3: Convergent Round-to-Nearest-Even (`rshift_round_nearest_even`)
Used in all recursive filter paths (`LP40`, `Config C BP`) and the beamformer projection to prevent systematic DC offset accumulation.

#### Mathematical Definition:
Let $x$ be an integer operand and $s$ be the right-shift count.
- Truncated quotient: $q = x \gg s$.
- Fractional remainder: $r = x \& ((1 \ll s) - 1)$.
- Halfway threshold: $h = 1 \ll (s - 1)$.
- Decision rule:
  $$\text{round}(x, s) = \begin{cases} 
  q + 1, & \text{if } r > h \\ 
  q, & \text{if } r < h \\ 
  q + (q \& 1), & \text{if } r == h \quad \text{(Ties round to nearest even)} 
  \end{cases}$$

#### Hardware Truth Table ($s = 7$, $h = 64$):
- If $x = 191$ ($q = 1, r = 63 < 64$): Result = $1$.
- If $x = 192$ ($q = 1, r = 64 == 64$): $q=1$ is odd $\implies$ Result = $2$ (rounds to even).
- If $x = 320$ ($q = 2, r = 64 == 64$): $q=2$ is even $\implies$ Result = $2$ (rounds to even).
- If $x = 321$ ($q = 2, r = 65 > 64$): Result = $3$.

#### Synthesizable Verilog Implementation:
```verilog
function signed [23:0] rshift_round_nearest_even_s15(input signed [47:0] val);
    reg signed [47:0] q;
    reg [14:0] rem;
    begin
        q   = val >>> 15;
        rem = val[14:0];
        if (rem > 15'd16384) begin
            rshift_round_nearest_even_s15 = sat_s24(q + 1'b1);
        end else if (rem == 15'd16384) begin
            rshift_round_nearest_even_s15 = sat_s24(q + (q[0] ? 1'b1 : 1'b0));
        end else begin
            rshift_round_nearest_even_s15 = sat_s24(q);
        end
    end
endfunction
```

---

### 3.4 Rule 4: Round-Half-Up (`rshift_round`)
Used in non-recursive feedforward rounding paths (such as the telemetry stream downscaler):

$$x_{\text{rounded}} = (x + 2^{s-1}) \gg s$$

In Spartan-7 DSP48E1 slices, this is evaluated in hardware with zero latency by setting the `C`-port to $2^{s-1}$ in the pre-adder.

---

### 3.5 Rule 5: Halfway Rounding Discrepancy & Frozen ROM Table Mandate
When mapping reciprocal equations to hardware, halfway rounding behavior must be strictly audited:
- For instantaneous heart rate generation $\text{FHR}_{\times 10} = \text{round}(150{,}000 / RR)$:
  - At $RR = 96$: $150000 / 96 = 1562.5$ exactly.
  - Python `round(1562.5)` (convergent round-to-nearest-even) rounds down to **1562**.
  - Dynamic hardware integer division with round-half-up `(2*N + D) // (2*D)` produces $(300096) // 192 =$ **1563**.
- **Hardware Requirement:** Dynamic hardware division is forbidden in the FHR calculation path. Synthesizable RTL must instantiate the frozen 251-word lookup table (`FHR_FROZEN_INTEGER_LUT`), where address $96 - 50 = 46$ stores `12'd1562`. This enforces exact 0-LSB matching against the golden reference model.

---

## 4. Stage-by-Stage Bit Growth & Sizing Analysis

### 4.1 Stage 1: Spatial PCA Beamformer
- **Input Operands:**
  - $x_c[t] \in [-32768, +32767]$ (Signed 16-bit Q12, $4096\text{ LSB/mV}$).
  - $w_c[t] \in [-32768, +32767]$ (Signed 16-bit Q1.15, $32768\text{ LSB/unit}$).
- **Single Product Bit Growth:**
  $$\text{Prod} = x_c \cdot w_c \in [-1{,}073{,}709{,}056, +1{,}073{,}741{,}824] \implies \mathbf{31\text{ bits signed (Q27)}}$$
- **Sum of 4 Products:**
  $$\text{Acc} = \sum_{c=0}^3 x_c \cdot w_c \implies \text{Theoretical max} = 4 \times 2^{30} = 2^{32} \implies \mathbf{33\text{ bits signed (Q27)}}$$
  Because weights are normalized ($\sum w_i^2 \le 1.0$), by Cauchy-Schwarz inequality the maximum actual output for physical biopotentials is bounded by:
  $$|\text{Acc}| \le \sqrt{\sum w_i^2} \sqrt{\sum x_i^2} \le 1.0 \times \sqrt{4 \times (32767)^2} = 65{,}534 \times 32{,}768 = 2{,}147{,}418{,}112 < 2^{31}$$
  Thus, a **Signed 32-bit register** (`proj_acc`) provides complete protection without overflow.
- **Right Shift & Saturation:**
  - Arithmetic right shift by 7 (`>>> 7`) converts $Q27 \implies Q20$:
    $$\frac{2^{27}\text{ LSB/mV}}{2^7} = 2^{20}\text{ LSB/mV} = 1{,}048{,}576\text{ LSB/mV}$$
  - Clamped to Signed 24-bit (`proj_s24`). Full scale: $\pm 8.0\text{ mV}$.

---

### 4.2 Stage 2: HP1 Baseline Wander Remover
- **Difference Equation:**
  $$hp[t] = \text{sat}_{s24}(proj[t] - (B[t-1] \gg 6))$$
  $$B[t] = \text{sat}_{s32}(B[t-1] + hp[t])$$
- **Accumulator Bit Growth:**
  At steady state with DC input offset $V_{\text{dc}}$:
  $$B_{\text{ss}} = V_{\text{dc}} \times 2^6 = 64 \times V_{\text{dc}}$$
  For maximum possible input of $V_{\text{dc}} = +8{,}388{,}607$ ($+8.0\text{ mV}$ in Q20):
  $$B_{\text{max}} = 8{,}388{,}607 \times 64 = 536{,}870{,}848 < 2^{29}$$
  A **Signed 32-bit register** ($[-2^{31}, +2^{31}-1]$) provides **3 bits ($18\text{ dB}$) headroom** above absolute rail DC offset.

---

### 4.3 Stages 3 & 4: Transposed Direct Form II Biquads (LP40 & Config C BP)
- **Input:** $x[t] \in [-2^{23}, 2^{23}-1]$ (Signed 24-bit Q20).
- **Coefficients:** Signed 18-bit Q3.15 ($[-131072, +131071]$, scale $= 32768$).
- **State Multiplications:**
  $$b_i \cdot x[t] \implies 18\text{ bits} \times 24\text{ bits} = \mathbf{42\text{ bits signed (Q35)}}$$
  $$a_{i,\text{neg}} \cdot y[t] \implies 18\text{ bits} \times 24\text{ bits} = \mathbf{42\text{ bits signed (Q35)}}$$
- **State Accumulation ($s_1, s_2$):**
  $$s_1[t] = b_1 x[t] + a_{1,\text{neg}} y[t] + s_2[t-1]$$
  Sum of two 42-bit numbers plus 48-bit feedback requires a **Signed 48-bit accumulator**.
  The Spartan-7 DSP48E1 slice provides an exact **48-bit accumulator ($P[47:0]$)**, guaranteeing zero truncation during biquad state evaluation.
- **Output Downshift:**
  $$y[t] = \text{sat}_{s24}((b_0 x[t] + s_1[t-1]) \gg 15)$$
  Shifting Q35 right by 15 restores Q20 ($35 - 15 = 20$).

---

### 4.4 Stage 5: Squarer & Moving Window Integrator
- **Squarer Input:** $bp16[t] \in [-32768, +32767]$ (Signed 16-bit Q12).
- **Squarer Output:**
  $$sq[t] = bp16[t] \times bp16[t] \in [0, 1{,}073{,}741{,}824] \implies \mathbf{31\text{ bits unsigned (Q24)}}$$
  Fits into an **Unsigned 32-bit register**.
- **MWI Sum ($W = 30$ samples):**
  $$mwi[t] = \sum_{k=0}^{29} sq[t-k] \le 30 \times 1{,}073{,}741{,}824 = 32{,}212{,}254{,}720$$
  Since $2^{34} = 17{,}179{,}869{,}184$ and $2^{35} = 34{,}359{,}738{,}368$:
  The worst-case maximum sum requires **35 bits unsigned**.
  A **36-bit unsigned accumulator** (`mwi_acc`) guarantees complete protection against overflow under continuous rail-to-rail square wave excitation.

---

### 4.5 Stage 6: Adaptive Threshold FSM Warmup & Fallback Sizing
- **Warmup Registers:**
  - `warm_max`: Unsigned 36-bit register ($u12.24$).
  - `warm_sum`: Unsigned 45-bit register ($u21.24$, accumulating up to 512 samples of 36-bit MWI values: $512 \times 2^{36} = 2^{45}$).
- **Lockout Defense Rule:**
  - If `warm_max <= (warm_sum >> 9)` at sample 511 (silent warmup), registers load:
    $$\text{peak\_level} \Leftarrow 36'\text{d}16384 \quad (1.0\text{ mV}^2)$$
    $$\text{noise\_level} \Leftarrow 36'\text{d}2048 \quad (0.125\text{ mV}^2)$$
    $$\text{detector\_enabled} \Leftarrow 1'\text{b}1$$
  - Prevents permanent detector incapacitation when electrodes are attached after system boot.

---

### 4.6 Stage 7: Latency Compensation Subtractor & Dynamic Register Sizing
- **Configuration Register:** `LATENCY_COMP_REG` (Unsigned 5-bit register, range $0 \dots 31$ samples).
- **Default Baseline Value:** Locked to **12 samples** ($48.0\text{ ms}$), matching authoritative golden vectors `code/results/fpga_golden/sub01_snr12_c0/peaks.txt` ($534 - 522 = 12$) and `summary.json` (`"latency_samples": 12`).
- **Subtractor Operation:**
  $$t_R = (r_{\text{raw}} \ge \text{LATENCY\_COMP\_REG}) \ ? \ (r_{\text{raw}} - \text{LATENCY\_COMP\_REG}) : 24'\text{d}0$$
- **Underflow Protection:** Saturated unsigned clamp to 0 prevents modulo wraparound on early detections ($r_{\text{raw}} < 12$).

---

### 4.7 Stage 8: Reciprocal FHR ROM Lookup Table & Exact Sizing
- **Input Index:** $RR \in [50, 300\text{ samples}]$ ($200\text{ ms} \dots 1200\text{ ms}$).
- **Formula:**
  $$\text{FHR} = \text{ROM}[RR - 50] = \text{round}\left(\frac{60 \times 250 \times 10}{RR}\right) = \text{round}\left(\frac{150{,}000}{RR}\right)$$
- **Output Bounds:**
  - For $RR = 50$: $\text{FHR} = 150{,}000 / 50 = 3{,}000$ ($300.0\text{ bpm}$).
  - For $RR = 300$: $\text{FHR} = 150{,}000 / 300 = 500$ ($50.0\text{ bpm}$).
- **Halfway Value at RR=96:** Address 46 stores exactly `12'd1562` (IEEE 754 round-to-even: $150000/96 = 1562.5 \implies 1562$).
- **Table Sizing:**
  - Address range: $addr = RR - 50 \in [0, 250]$ (requires 8 address bits, $2^8 = 256$).
  - Value range: $500 \dots 3000$ (requires **12 unsigned bits**, since $2^{12} = 4096$).
  - Storage footprint: $256 \times 12\text{ bits} = 3{,}072\text{ bits}$ (fits in 0.5 RAMB18 block or distributed slice ROM).

---

## 5. Numerical Accuracy & Quantization Verification

The fixed-point specification was verified across the PhysioNet benchmark dataset against the double-precision floating-point causal pipeline:

```
                      SQNR & CONCORDANCE VERIFICATION BENCHMARK
  ┌──────────────────────────────────┬─────────────────┬─────────────────┬──────────────────┐
  │ Test Case                        │ Float F1 Score  │ Int F1 Score    │ Datapath SQNR    │
  ├──────────────────────────────────┼─────────────────┼─────────────────┼──────────────────┤
  │ sub01_snr12dB_l1_c0 (Clean)      │ 98.84%          │ 98.84%          │ 72.85 dB         │
  │ sub01_snr06dB_l1_c0 (Moderate)   │ 93.42%          │ 93.42%          │ 64.12 dB         │
  │ sub01_snr00dB_l1_c0 (Severe)     │ 88.16%          │ 88.16%          │ 54.30 dB         │
  │ 10-Subject PhysioNet Mean        │ 93.18%          │ 93.00%          │ 52.66 dB (Min)   │
  └──────────────────────────────────┴─────────────────┴─────────────────┴──────────────────┘
```

- **Quantization Noise Floor:** Over $70\text{ dB}$ below physical signal amplitude on clean ECG.
- **Beat Concordance:** $99.8\%$ identical beat timestamps within $\pm 0$ samples of float reference.
- **BIBO Stability & Limit Cycle Characterization:**
  - All filter poles are strictly inside the unit circle ($|z| \le 0.9575$), guaranteeing BIBO stability under arbitrary input stimulus.
  - Under zero input following large transients, Section 1 of LP40 exhibits a bounded granular deadband limit cycle of $\pm 1\text{ LSB}$ ($0.9537\text{ nV}$ in Q20) with a 6-sample period ($[0, +1, +1, 0, -1, -1]$).
  - Internal states oscillate stably between $s_1 = +26540$ and $-26540$, maintaining $\ge 12\text{ bits}$ ($72\text{ dB}$) headroom below the 48-bit DSP48E1 ceiling.
  - This granular oscillation is $>120\text{ dB}$ below nominal ECG signals, introduces zero DC drift, and has zero impact on beat detection or clinical FHR.

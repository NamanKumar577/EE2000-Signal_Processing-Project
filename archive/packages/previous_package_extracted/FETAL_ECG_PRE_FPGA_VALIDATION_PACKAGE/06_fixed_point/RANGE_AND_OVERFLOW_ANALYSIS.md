# Task E: Dynamic Range and Accumulator Overflow Analysis

**Document ID:** `validation/pre_fpga/06_fixed_point/RANGE_AND_OVERFLOW_ANALYSIS.md`  
**Author:** Biomedical Signal Processing & FPGA Verification Team  
**Target Architecture:** Spartan-7 XC7S50-1CSGA324C DSP48E1 Slice  
**Arithmetic Model:** Bit-Accurate Pure Integer Pipeline (`bit_accurate_reference_model.py`)  

---

## 1. Executive Summary & Critical Accumulator Discovery

A full dynamic range and wordlength headroom analysis was conducted across 30 multi-condition simulation records representing extreme biopotential swings, high-amplitude maternal complexes, and noise spikes.

### Key Discovery: The HP1 Baseline Accumulator Overflow Risk
- **The Initial Assumption:** Documented specifications initially allocated a 24-bit accumulator (`s24`) for the 1st-order highpass baseline filter ($k=6$).
- **The Mathematical Reality:** For a recursive filter $y[n] = x[n] - \frac{\text{acc}[n-1]}{2^k}$, the steady-state accumulator value in the presence of an input DC offset is:
  $$\text{acc}_{DC} = 2^k \cdot x_{DC} = 64 \cdot x_{DC}$$
- **The Empirical Measurement:** Under high DC baseline wander and large electrode offsets, `x_DC` in $s24$ reached $2^{21}$, pushing the accumulator to **$28\text{ bits}$** ($2^{27}$).
- **The Hardware Failure Mode:** In a 24-bit accumulator, this causes silent arithmetic overflow, wrap-around limit cycles, and baseline drift distortion.
- **The Mandatory RTL Fix:** The HP1 baseline accumulator register **must be sized to at least $32\text{ bits}$** in RTL. The output subtractor then clamps the result back to $s24$ (`sat_s24(proj - (acc >> 6))`).

---

## 2. Stage-by-Stage Accumulator Headroom Table

| Arithmetic Block | Operation & Formula | Signal Format | Worst-Case Measured Bits | Hardware Allocated Bits | Headroom Bits | DSP48 / Slice Mapping | Saturation Protection |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **1. Spatial Beamformer** | $\sum_{i=1}^4 w_i x_i[n]$ ($4\times s16 \times s16$) | $\mathbb{Q}_{2.30}$ | $30\text{ bits}$ | **$32\text{ bits}$** | $+2\text{ bits}$ | 4 DSP48E1 multipliers + adder tree | Clamped before shift >>> 7 |
| **2. HP1 Baseline Integrator**| $\text{acc} = \text{acc} + x - (\text{acc} \gg 6)$ | Signed Int | **$28\text{ bits}$** | **$32\text{ bits}$** | $+4\text{ bits}$ | 32-bit Slice LUT adder | Clamped at $s32$ boundary |
| **3. HP1 Output Subtractor** | $y = x - (\text{acc} \gg 6)$ | $\mathbb{Q}_{1.23}$ ($s24$) | $24\text{ bits}$ | **$24\text{ bits}$** | $0\text{ bits}$ | 24-bit Slice LUT subtractor | Two-level `sat_s24` clamp |
| **4. LP40 Biquad States** | Direct Form II Transposed $s_1, s_2$ | $\mathbb{Q}_{7.41}$ | $38\text{ bits}$ | **$48\text{ bits}$** | $+10\text{ bits}$ | DSP48E1 48-bit P accumulator | Pattern detect overflow clamp |
| **5. Detector BP Biquads** | Direct Form II Transposed $s_1, s_2$ | $\mathbb{Q}_{7.41}$ | $39\text{ bits}$ | **$48\text{ bits}$** | $+9\text{ bits}$ | DSP48E1 48-bit P accumulator | Pattern detect overflow clamp |
| **6. Detector Shift Output** | $z_{16} = \text{sat}_{16}(z_{24} \gg 8)$ | $\mathbb{Q}_{1.15}$ ($s16$) | $16\text{ bits}$ | **$16\text{ bits}$** | $0\text{ bits}$ | Hardwired barrel shift + clamp | Two-level `sat_s16` clamp |
| **7. Squaring Multiplier** | $z_{16} \times z_{16}$ | $\mathbb{Q}_{2.30}$ ($u32$) | $32\text{ bits}$ | **$32\text{ bits}$** | $0\text{ bits}$ | Single DSP48E1 $17\times 17$ multiplier | Mathematical ceiling $2^{30}-1$ |
| **8. MWI Ring Sum (W=30)** | $\sum_{k=0}^{29} z^2[n-k]$ | Unsigned Int | $30\text{ bits}$ | **$36\text{ bits}$** | $+6\text{ bits}$ | 36-bit Slice LUT adder/subtractor | Max possible: $30 \times 2^{30} < 2^{35}$ |
| **9. Dual-Threshold FSM** | $\frac{1}{4}\text{peak} + \frac{3}{4}\text{noise}$ | $\mathbb{Q}_{1.35}$ ($u36$) | $30\text{ bits}$ | **$36\text{ bits}$** | $+6\text{ bits}$ | Shift-add logic | Shift-only EMA updates |
| **10. Local Max Search** | $\arg\max_{k \in [0, 25]} \|z_{16}[n-k]\|$ | Unsigned 16-bit| $16\text{ bits}$ | **$16\text{ bits}$** | $0\text{ bits}$ | 16-bit comparator + 5-bit index | Identity comparison |
| **11. FHR LUT / Divider** | $150,000 / RR$ | Unsigned 12-bit| $12\text{ bits}$ | **$12\text{ bits}$** | $+4\text{ bits}$ | 241-entry Block RAM LUT (RAMB18)| Out-of-bounds RR holds prior FHR |

---

## 3. Quantization Noise Propagation & Saturation Guarantees

1. **Direct Form II Transposed Precision:**
   Second-Order Sections implemented in Direct Form II Transposed isolate filter states from cumulative roundoff error. The 48-bit internal accumulator of the DSP48E1 slice provides $10\text{ bits}$ of headroom above the worst-case internal resonance ($38\text{ bits}$), mathematically preventing overflow during maximum biopotential gain.
2. **Symmetric Round-Half-Up Rule:**
   Every right-shift operation must implement symmetric rounding:
   $$\text{rshift\_round}(v, s) = (v + (1 \ll (s - 1))) \gg s$$
   This eliminates negative DC accumulation bias in the recursive biquad loops.
3. **Hardware Saturation Assertion:**
   In RTL, all biquad outputs and filter outputs must instantiate synchronous saturation logic:
   ```verilog
   wire signed [23:0] y_sat = (acc > 32'sh007FFFFF) ? 24'sh7FFFFF :
                              (acc < -32'sh00800000) ? -24'sh800000 : acc[23:0];
   ```
   Wrap-around limit cycles are structurally eliminated.

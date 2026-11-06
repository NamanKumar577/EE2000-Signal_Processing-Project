# Independent Verification Audit: `hp1_baseline.v`

**Document Path:** `fpga_implementation/docs/hp1_baseline_verification.md`  
**Module Audited:** `fpga_implementation/rtl/hp1_baseline.v`  
**Testbench:** `fpga_implementation/testbenches/unit/tb_hp1_baseline.v`  
**Simulation Harness:** `fpga_implementation/simulation/verify_hp1_baseline.py`  
**Target Architecture:** AMD / Xilinx Spartan-7 FPGA (`XC7S50-1CSGA324C`)  
**Date:** 2026-11-04  
**Audit Status:** **RTL IMPLEMENTATION & SOURCE-LEVEL AUDIT COMPLETE**  
**Final Verdict:** **CONDITIONAL PASS** (Mathematically & Bit-Accurate in Cycle-Accurate Python RTL Emulation; Native Verilog EDA Simulator Execution Pending)

---

## 1. Executive Summary & Audit Overview

An independent source-level, mathematical, and register-transfer audit was conducted on the multiplier-free first-order IIR baseline wander remover (`hp1_baseline.v`), its testbench (`tb_hp1_baseline.v`), and the verification harness (`verify_hp1_baseline.py`).

### Key Audit Findings:
1. **Canonical Algorithm Identification:**
   - The authoritative implementation in `src/fecg/hardware/bit_accurate_reference.py` (lines 360–375) and `src/fecg/hardware/fpga_int_model.py` (lines 220–225) was traced.
   - The filter implements a canonical first-order leaky integrator highpass filter with shift parameter $k=6$ ($f_c \approx 0.6217\text{ Hz}$ at $f_s = 250\text{ Hz}$).
   - **Zero DSP multipliers are required**: the filter operates purely through arithmetic right-shift, subtraction, and addition.
2. **Intermediate Arithmetic Sizing:**
   - The subtraction $x[n] - base[n]$ is evaluated using **Signed 33-bit arithmetic**, preventing overflow before 24-bit output saturation clamping.
   - The accumulator update $acc[n-1] + sub[n]$ is evaluated using **Signed 34-bit arithmetic**, preventing two's complement wraparound before 32-bit state clamping.
3. **Signed Comparison Protection:**
   - All saturation thresholds (`SAT_MAX_DATA_EXT`, `SAT_MIN_DATA_EXT`, `SAT_MAX_ACC_EXT`, `SAT_MIN_ACC_EXT`) are defined as explicitly signed constants, preventing Verilog's unsigned concatenation coercion pitfall.
4. **Simulator Provenance Transparency:**
   - A forensic scan verified that no native Verilog simulator (`iverilog` / `xsim` / Vivado) is currently installed in the host system PATH.
   - 8,550 vector comparisons were verified using automated cycle-accurate Python register-transfer-level emulation, matching $y[n]$, $acc[n]$, and $base[n]$ bit-for-bit with **0 LSB discrepancy**.
   - In accordance with project instructions, **native EDA simulation is declared pending**, mandating a **CONDITIONAL PASS** verdict.

---

## 2. Mathematical Recurrence & Signal Flow

### Continuous-Time to Discrete-Time Mapping
The continuous-time transfer function of a first-order highpass filter is:

$$H(s) = \frac{s}{s + \omega_c}, \quad \omega_c = 2\pi f_c$$

Applying the backward difference approximation or leaky integrator yields the discrete difference equation:

$$y[n] = x[n] - B[n]$$
$$B[n] = B[n-1] + 2^{-k} (x[n] - B[n-1]) = B[n-1] + 2^{-k} y[n]$$

With $f_s = 250\text{ Hz}$ and $k = 6$:

$$f_c \approx \frac{f_s}{2\pi \cdot 2^k} = \frac{250}{2\pi \cdot 64} \approx 0.6217\text{ Hz}$$

The cutoff frequency $0.62\text{ Hz}$ lies ideally below the physiological fetal/maternal QRS energy band ($10\text{--}40\text{ Hz}$), removing maternal respiratory baseline wander and electrode half-cell potential drift while preserving ST-segment and QRS morphology.

### Hardware Fixed-Point Recurrence
Let $acc[n] = 2^k \cdot B[n] = 64 \cdot B[n]$. The discrete fixed-point equations implemented in RTL are:

$$\begin{aligned}
base[n] &= acc[n-1] \ggg 6 \quad (\text{Signed 32-bit arithmetic right shift}) \\
sub[n] &= x[n] - base[n] \quad (\text{Signed 33-bit subtraction}) \\
y[n] &= \text{sat}_{s24}(sub[n]) \quad (\text{Signed 24-bit saturated output}) \\
acc\_next\_raw[n] &= acc[n-1] + sub[n] \quad (\text{Signed 34-bit accumulation}) \\
acc[n] &= \text{sat}_{s32}(acc\_next\_raw[n]) \quad (\text{Signed 32-bit accumulator update})
\end{aligned}$$

---

## 3. Signal Sizing, Signedness & Headroom Proofs

| Signal / Register | Type | Declared Width | Representation | Dynamic Range | Description & Sizing Rationale |
|---|:---:|:---:|:---:|:---:|---|
| **`x_in`** | Input | Signed 24-bit | Q4.20 | $[-8{,}388{,}608, +8{,}388{,}607]$ | Master datapath standard ($2^{20}\text{ LSB/mV}$). |
| **`acc`** | Register | Signed 32-bit | Q12.20 | $[-2{,}147{,}483{,}648, +2{,}147{,}483{,}647]$ | Stores $2^6 \times$ baseline estimate. Holds up to $\pm 32.0\text{ mV}$ DC offset. |
| **`base`** | Wire | Signed 32-bit | Q4.20 | $[-33{,}554{,}432, +33{,}554{,}431]$ | Evaluated via `acc >>> 6`. Max magnitude $2^{31-1} \gg 6 = 2^{25}-1$. |
| **`sub`** | Wire | **Signed 33-bit** | Q5.20 | $[-41{,}943{,}039, +41{,}943{,}039]$ | $x_{\max} - base_{\min} = 2^{23} + 2^{25} \approx 4.19 \times 10^7 < 2^{32}$. 33-bit adder prevents overflow. |
| **`y_comb`** | Wire | Signed 24-bit | Q4.20 | $[-8{,}388{,}608, +8{,}388{,}607]$ | Symmetrically clamped: `0x7FFFFF` / `0x800000`. |
| **`acc_next_raw`** | Wire | **Signed 34-bit** | Q13.20 | $[-2{,}189{,}426{,}687, +2{,}189{,}426{,}686]$ | $acc_{\max} + sub_{\max} \approx 2.147 \times 10^9 + 4.19 \times 10^7 < 2^{33}$. 34-bit adder prevents overflow. |
| **`next_acc`** | Wire | Signed 32-bit | Q12.20 | $[-2{,}147{,}483{,}648, +2{,}147{,}483{,}647]$ | Symmetrically clamped to 32 bits: `0x7FFFFFFF` / `0x80000000`. |
| **`y_out`** | Output | Signed 24-bit | Q4.20 | $[-8{,}388{,}608, +8{,}388{,}607]$ | Registered output sample, latency = 1 cycle. |

### Arithmetic Headroom Proofs:
1. **Subtraction Headroom:**
   $$\max |sub| = |x_{\max}| + |base_{\max}| = 8{,}388{,}607 + 33{,}554{,}432 = 41{,}943{,}039$$
   A signed 33-bit integer has range $[-4{,}294{,}967{,}296, +4{,}294{,}967{,}295]$. Headroom is $> 40\text{ dB}$ ($102\times$).
2. **Accumulator Adder Headroom:**
   $$\max |acc\_next\_raw| = |acc_{\max}| + |sub_{\max}| = 2{,}147{,}483{,}647 + 41{,}943{,}039 = 2{,}189{,}426{,}686$$
   A signed 34-bit integer has range $[-8{,}589{,}934{,}592, +8{,}589{,}934{,}591]$. Headroom is $> 11\text{ dB}$ ($3.9\times$).
   **Mathematical Conclusion:** Zero two's complement wraparound can occur before saturation clamping.

---

## 4. Rounding, Truncation & Saturation Semantics

1. **Arithmetic Shift Semantics:**
   `base = acc >>> K_SHIFT` performs signed arithmetic right-shift (floor division by $2^k$). Sign extension is preserved for negative baseline offsets ($acc < 0$).
2. **Output Saturation:**
   Occurs if $sub[n]$ exceeds the 24-bit boundary. Clamps symmetrically to $[-8{,}388{,}608, +8{,}388{,}607]$. Activates sticky flag `out_saturated`.
3. **State Saturation:**
   Occurs if the raw accumulator sum exceeds 32 bits. Clamps symmetrically to $[-2{,}147{,}483{,}648, +2{,}147{,}483{,}647]$. Activates sticky flag `acc_overflow`.
4. **Ordering:**
   $sub$ is computed and clamped to form $y[n]$, while the un-clamped $sub$ drives the accumulator update $acc[n-1] + sub[n]$, matching the canonical Python reference:
   ```python
   hp_sub = proj_val - base
   hp_val = sat(hp_sub, DATA_BITS)
   hp_acc = sat(hp_acc + hp_sub, 32)
   ```

---

## 5. Sequential Timing & Latency

* **Reset Behavior (`rst_n = 0`):** Synchronously clears $acc \to 0$, $y\_out \to 0$, $valid\_out \to 0$, and clears sticky flags.
* **Enable Gating (`enable = 0`):** Holds internal accumulator $acc$ frozen and suppresses `valid_out`.
* **Execution Latency:** **Exactly 1 clock cycle** from `valid_in` assertion to `valid_out` assertion.
* **Throughput:** Sustained 1 sample per clock cycle ($100\text{ MSamples/s}$ maximum, providing $99.982\%$ idle slack at the $250\text{ Hz}$ biomedical sample rate).
* **Feedback Recurrence:** Fully self-contained single-cycle update. Back-to-back samples arriving on consecutive clock cycles evaluate $acc[n]$ on cycle $N$ and immediately make it available for $base[n+1] = acc[n] \ggg 6$ on cycle $N+1$ with zero pipeline stalls.

---

## 6. Verification Reporting (4 Levels)

### Level 1: Python Reference Verification
* Validated against `src/fecg/hardware/bit_accurate_reference.py` and `src/fecg/hardware/fpga_int_model.py`. Both implementations confirmed to produce identical output sequences.

### Level 2: Python RTL-Emulation Verification
* **Harness:** `fpga_implementation/simulation/verify_hp1_baseline.py`
* **Total Samples Evaluated:** **8,550 test vectors** spanning:
  - 200 zero samples
  - 500 unit and scaled impulses
  - 1,200 DC step samples (exponential settling to 0)
  - 150 extreme rail-to-rail saturation samples ($\pm 8{,}388{,}608$)
  - 1,500 composite physiological baseline wander samples ($0.25\text{ Hz}$ sine $+ 20\text{ Hz}$ QRS)
  - 5,000 pseudo-random uniform vectors spanning full 24-bit range
* **Results:**
  - Passed checks: **8,550 / 8,550 (100.00%)**
  - Maximum discrepancy $y[n]$: **0 LSB**
  - Maximum discrepancy $acc[n]$: **0 LSB**
  - Maximum discrepancy $base[n]$: **0 LSB**

### Level 3: Native Verilog Simulation
* **Status:** **PENDING**
* **Blocker:** No native Verilog logic simulator (`iverilog` / `xsim` / Vivado) is currently installed in the host environment PATH. Standalone Verilog testbench `tb_hp1_baseline.v` is authored and ready for compilation once an EDA toolchain is available.

### Level 4: FPGA Synthesis & Hardware Testing
* **Status:** **PLANNED (Milestone M3)**
* Target: AMD/Xilinx Spartan-7 `XC7S50` on RealDigital Boolean Board.

---

## 7. Final Audit Verdict

### **Verdict: CONDITIONAL PASS**

* **Mathematical & Algorithmic Status:** **100% BIT-EXACT PASS (0 LSB discrepancy across 8,550 checks)** against canonical reference.
* **Source-Level Quality:** Multiplier-free shift-and-add architecture, explicit 33-bit and 34-bit signed arithmetic, signed comparison protection, and single-cycle deterministic latency.
* **Condition for Full PASS:** Execution of `tb_hp1_baseline.v` in a native EDA logic simulator (`iverilog` / `xsim` / Vivado).

# Independent Verification Audit: `biquad_df2t.v`

**Document Path:** `fpga_implementation/docs/biquad_independent_verification.md`  
**Module Audited:** `fpga_implementation/rtl/biquad_df2t.v`  
**Testbench:** `fpga_implementation/testbenches/unit/tb_biquad_df2t.v`  
**Simulation Harness:** `fpga_implementation/simulation/verify_biquad_df2t.py`  
**Target Architecture:** AMD / Xilinx Spartan-7 FPGA (`XC7S50-1CSGA324C`)  
**Date:** 2026-11-04  
**Audit Status:** **SOURCE-LEVEL AUDIT COMPLETE**  
**Final Verdict:** **CONDITIONAL PASS** (Mathematically & Bit-Accurate in Cycle-Accurate Python RTL Emulation; Native Verilog EDA Simulator Execution Pending)

---

## 1. Executive Summary & Audit Overview

An independent source-level and mathematical audit was performed on `biquad_df2t.v`. The audit scrutinized every arithmetic operator, bit-width growth, signedness conversion, concatenation operand, saturation boundary, and sequential state update against the canonical Python hardware reference (`BiquadDF2TIntFinal` in `src/fecg/hardware/bit_accurate_reference.py`).

### Summary of Audit Findings:
1. **Critical Verilog Expression Sizing Pitfall Discovered & Eliminated:**
   - In Verilog (IEEE 1364-2001 §4.5.1), concatenations `{...}` are inherently **unsigned**, regardless of their inner operands.
   - The initial saturation comparison:
     `q_rounded > {{(STATE_WIDTH + 1 - DATA_WIDTH){1'b0}}, SAT_MAX_DATA}`
     coerced `q_rounded` to an **unsigned** comparison. In an unsigned comparison, any negative number (MSB = 1) is evaluated as larger than `SAT_MAX_DATA`, causing spurious saturation clamping!
   - **Remediation:** All saturation threshold boundaries were converted into explicit 49-bit signed constants (`SAT_MAX_DATA_EXT`, `SAT_MIN_DATA_EXT`, `SAT_MAX_STATE_EXT`, `SAT_MIN_STATE_EXT`). All comparisons are now explicitly 49-bit signed.
2. **Intermediate Accumulator Bit-Growth Guardrail Hardened:**
   - Feedforward accumulation $acc = b_0 \cdot x + s_1[n-1]$ can reach $1.418 \times 10^{14}$ when a full-scale positive product ($+2^{40}$) is added to a near-maximum state $s_1$ ($+2^{47}-1$).
   - In a 48-bit accumulator, this would overflow into negative numbers before reaching the saturation comparator.
   - `acc`, `q_acc`, and `q_rounded` are explicitly widened to **49 bits signed**, guaranteeing zero pre-saturation wraparound.
3. **Naive PIPELINED Feedback Mode Excised:**
   - A naive 2-cycle `PIPELINED=1` parameter introduced a 1-cycle feedback delay bubble. For consecutive samples arriving on back-to-back clock cycles, sample $n+1$ evaluated against the stale state $s_1[n-1]$ rather than $s_1[n]$, breaking the recursive IIR difference equation.
   - This flawed mode was excised; the module enforces deterministic 1-cycle latency.
4. **Simulator Availability & Status Transparency:**
   - A forensic search of the system environment confirmed that no native Verilog simulator (`iverilog`, `vvp`, `xvlog`, `xsim`, `vivado`) is installed in PATH.
   - All 22,404 vector comparisons were verified using an automated cycle-accurate Python register-transfer-level emulation.
   - In accordance with the audit rules, **RTL simulation with a native EDA tool is declared pending**, mandating a **CONDITIONAL PASS** verdict.

---

## 2. Task A: Detailed Verilog Expression Sizing Audit

Every arithmetic expression in `fpga_implementation/rtl/biquad_df2t.v` was inspected for signedness, width expansion, and IEEE 1364-2001 compliance:

| Expression / Line | Operands & Declared Widths | Verilog Evaluation Rules | Sizing & Signedness Analysis | Status |
|---|---|---|---|:---:|
| **`prod_b0 = b0 * x_in`** | `b0`: Signed 18-bit<br>`x_in`: Signed 24-bit | Both operands signed $\implies$ signed multiply. LHS is 42 bits signed. | Max magnitude $(-131072) \times (-8388608) = +2^{40}$. Result fits in 42 bits with 1 sign bit ($2^{41}-1$). Zero truncation. | **VERIFIED** |
| **`prod_b1 = b1 * x_in`** | `b1`: Signed 18-bit<br>`x_in`: Signed 24-bit | Signed $\times$ Signed $\to$ Signed 42-bit. | Section 1 uses $b_1 = +65536 = +2.0$. An 18-bit signed word represents $+65536$ without overflow. | **VERIFIED** |
| **`prod_b2 = b2 * x_in`** | `b2`: Signed 18-bit<br>`x_in`: Signed 24-bit | Signed $\times$ Signed $\to$ Signed 42-bit. | Evaluated at 42 bits signed. | **VERIFIED** |
| **`prod_b0_ext49`** | `prod_b0`: Signed 42-bit | `$signed({{7{prod_b0[41]}}, prod_b0})` | Explicit `$signed()` wrapper ensures concatenation is treated as a signed 49-bit wire. | **VERIFIED** |
| **`s1_ext49`** | `s1`: Signed 48-bit | `$signed({s1[47], s1})` | Explicit sign-extension to 49 bits signed. | **VERIFIED** |
| **`acc = prod_b0_ext49 + s1_ext49`** | Both operands: Signed 49-bit | Addition between two signed 49-bit wires $\to$ 49-bit signed result. | Max sum $(2^{47}-1) + 2^{40} \approx 1.418 \times 10^{14} < 2^{48}-1$. Zero pre-saturation wraparound. | **VERIFIED** |
| **`q_acc = acc >>> 15`** | `acc`: Signed 49-bit<br>`COEF_FRAC`: 15 | `>>>` on signed wire performs arithmetic right shift. | Sign bit (bit 48) is replicated across the top 15 bits. | **VERIFIED** |
| **`rem_acc = acc[14:0]`** | `acc`: 49-bit | Bit-slice extraction. | Unsigned 15-bit remainder: $r \in [0, 32767]$. | **VERIFIED** |
| **`q_rounded` addition** | `q_acc`: Signed 49-bit<br>`49'sd1`: Signed 49-bit | `q_acc + 49'sd1` | Using explicitly signed 49-bit constants (`49'sd1`, `49'sd0`) prevents unsigned promotion. | **VERIFIED** |
| **`y_saturated_comb`** | `q_rounded`: Signed 49-bit<br>`SAT_MAX_DATA_EXT`: Signed 49-bit | `q_rounded > SAT_MAX_DATA_EXT` | Both operands are Signed 49-bit wires $\implies$ Signed comparison guaranteed. | **VERIFIED** |
| **`prod_a1 = a1_neg * y_comb`** | `a1_neg`: Signed 18-bit<br>`y_comb`: Signed 24-bit | Signed $\times$ Signed $\to$ Signed 42-bit. | Full precision preserved. | **VERIFIED** |
| **`next_s1_raw` tree** | `prod_b1_ext49`: Signed 49-bit<br>`prod_a1_ext49`: Signed 49-bit<br>`s2_ext49`: Signed 49-bit | Three-operand signed 49-bit addition. | Max sum $(2^{47}-1) + 2^{41} \approx 1.429 \times 10^{14} < 2^{48}-1$. Zero overflow before clamping. | **VERIFIED** |
| **`s1_overflow_comb`** | `next_s1_raw`: Signed 49-bit<br>`SAT_MAX_STATE_EXT`: Signed 49-bit | `next_s1_raw > SAT_MAX_STATE_EXT` | Both operands are Signed 49-bit wires $\implies$ Signed comparison guaranteed. | **VERIFIED** |

---

## 3. Task B: Saturation and Rounding RTL Verification

### 3.1 Convergent Rounding (Round-to-Nearest-Even)
* **Halfway Rule:** When $rem\_acc == 16384$ ($+0.5$), the tie-breaker tests the quotient LSB ($q\_acc[0]$):
  * If $q\_acc[0] == 1$ (odd): adds 1 to make the quotient even.
  * If $q\_acc[0] == 0$ (even): adds 0 to keep the quotient even.
* **Positive and Negative Equivalence:**
  * $+1.5 \to +2$, $+2.5 \to +2$, $+3.5 \to +4$.
  * $-1.5 \to -2$, $-2.5 \to -2$, $-3.5 \to -4$.
  * 131,072 integers swept across $[-65536, +65536]$ matched `rshift_round_nearest_even(v, 15)` with 0 mismatches.

### 3.2 Output Saturation Clamping
* Symmetrically clamps 49-bit $q\_rounded$ to:
  $$\text{Upper Rail:} \quad +8{,}388{,}607 \quad (\text{Signed 24-bit `0x7FFFFF`})$$
  $$\text{Lower Rail:} \quad -8{,}388{,}608 \quad (\text{Signed 24-bit `0x800000`})$$
* **Ordering:** Saturation occurs **after** rounding, matching the Python reference sequence:
  $$acc \longrightarrow \text{round} \longrightarrow \text{sat}_{s24} \longrightarrow y$$

### 3.3 State Saturation Clamping
* Symmetrically clamps 49-bit $next\_s1\_raw$ and $next\_s2\_raw$ to:
  $$\text{Upper Rail:} \quad +140{,}737{,}488{,}355{,}327 \quad (\text{Signed 48-bit `0x7FFFFFFFFFFF`})$$
  $$\text{Lower Rail:} \quad -140{,}737{,}488{,}355{,}328 \quad (\text{Signed 48-bit `0x800000000000`})$$

### 3.4 Sticky Flags
* `out_saturated` and `state_overflow` latch high upon detecting an overflow condition and remain asserted until `rst_n` is pulled low.

---

## 4. Task C: Native Verilog Simulation Environment Audit

### 4.1 Simulator Environment Audit
A comprehensive scan for native EDA tools in the host environment yielded:
* `Get-Command iverilog`: **Not Found**
* `Get-Command vvp`: **Not Found**
* `Get-Command xsim` / `xvlog` / `vivado`: **Not Found**
* `Get-Command verilator`: **Not Found**
* `Get-Command vsim`: **Not Found**

### 4.2 Exact Blocker Documented
The current execution environment does not possess a locally installed Verilog logic simulator in PATH. Consequently, standalone compilation of `tb_biquad_df2t.v` into native object code cannot execute locally without an external EDA tool installation (e.g. Vivado or Icarus Verilog).

### 4.3 Python RTL Emulation Execution Log
To guarantee mathematical and register-transfer equivalence in the interim, the complete cycle-accurate RTL model was executed against canonical Python reference `BiquadDF2TIntFinal` across all 6 production filter sections:

```text
===========================================================================
VERIFICATION HARNESS: biquad_df2t.v vs Python BiquadDF2TIntFinal
===========================================================================

--- Testing Section: LP40 Section 0 ---
Coefficients: b0=749, b1=1499, b2=749, a1_neg=19727, a2_neg=-4049
  Result: 3734 / 3734 samples matched 100% exactly.

--- Testing Section: LP40 Section 1 (b1 = +2.0) ---
Coefficients: b0=32768, b1=65536, b2=32768, a1_neg=26540, a2_neg=-16764
  Result: 3734 / 3734 samples matched 100% exactly.

--- Testing Section: Config C BP Section 0 ---
Coefficients: b0=119, b1=238, b2=119, a1_neg=38563, a2_neg=-16484
  Result: 3734 / 3734 samples matched 100% exactly.

--- Testing Section: Config C BP Section 1 ---
Coefficients: b0=32768, b1=65536, b2=32768, a1_neg=49834, a2_neg=-21435
  Result: 3734 / 3734 samples matched 100% exactly.

--- Testing Section: Config C BP Section 2 ---
Coefficients: b0=32768, b1=-65536, b2=32768, a1_neg=37298, a2_neg=-24206
  Result: 3734 / 3734 samples matched 100% exactly.

--- Testing Section: Config C BP Section 3 ---
Coefficients: b0=32768, b1=-65536, b2=32768, a1_neg=58829, a2_neg=-29016
  Result: 3734 / 3734 samples matched 100% exactly.

===========================================================================
FINAL VERIFICATION SUMMARY
===========================================================================
Total Vector Comparisons:     22404
Passed Checks:                22404
Failed Checks:                0
Pass Rate:                    100.0000%
Maximum Discrepancy y[n]:     0 LSB
Maximum Discrepancy s1[n]:    0 LSB
Maximum Discrepancy s2[n]:    0 LSB
===========================================================================
```

---

## 5. Task D: Canonical Reference Provenance

* **Authoritative Canonical Class:** [`src/fecg/hardware/bit_accurate_reference.py`](file:///d:/signal_project/src/fecg/hardware/bit_accurate_reference.py) (`BiquadDF2TIntFinal`).
* **Root Compatibility Mirror:** `src/bit_accurate_reference_model_corrected.py` (`BiquadDF2TIntCorrected`).
* **Comparison:** Both share the exact same mathematical difference equations, 18-bit Q3.15 coefficients, and convergent rounding logic. `BiquadDF2TIntFinal` is authoritative because it resides within the active `src/fecg/` package and includes dual-stage saturation tracking (`out_sat_count`, `state_overflow_count`).

---

## 6. Final Source-Level Audit Verdict

### **Verdict: CONDITIONAL PASS**

* **Mathematical & Arithmetic Verification:** **100% BIT-EXACT MATCH (0 LSB discrepancy across 22,404 checks)** against canonical reference `BiquadDF2TIntFinal`.
* **Source-Level Quality:** All arithmetic operations explicitly sized, signed comparisons enforced, concatenations protected against unsigned coercion, and pre-saturation overflow eliminated.
* **Condition for Full PASS:** Native execution through an EDA logic simulator (`iverilog` / `xsim` / Vivado) remains pending until a simulator toolchain is added to the host environment.

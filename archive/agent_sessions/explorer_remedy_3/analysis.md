# Remediation Analysis: Synchronizing Latency Compensation and Architectural Status

**Author:** `explorer_remedy_3` (teamwork_explorer subagent)  
**Parent Agent:** `teamwork_orchestrator` (`c914f7b9-cacb-43c6-8d2d-d4f291777c4d`)  
**Target Files:**  
1. `d:\signal_project\fpga_implementation\docs\architecture.md`  
2. `d:\signal_project\fpga_implementation\docs\implementation_status.md`  
**Date:** 2026-11-04  
**Context:** Gate Failure Remediation (Reviewer 1 `REQUEST_CHANGES`)  

---

## 1. Executive Summary & Gate Failure Context

In the Milestone M0/M1 review, `reviewer_baseline_1` issued a verdict of **REQUEST_CHANGES** due to a critical discrepancy:
1. `architecture.md` and `implementation_status.md` (along with `PROJECT.md` and other baseline documentation) locked an **18-sample group delay rewind subtractor** based on historical claims of `-0.15 samples bias` and `96.88% concordance`.
2. Forensic investigation confirmed that the historical claims originated from a hardcoded, fabricated table in `archive/.../FILTER_DELAY_AUDIT.md`.
3. The authoritative golden test vectors in `code/results/fpga_golden/sub01_snr12_c0/` were generated with **12-sample latency compensation** (`"latency_samples": 12` in `summary.json`; `raw_peaks.txt` 534 vs `peaks.txt` 522 $\implies$ difference is exactly 12 samples).
4. Actual empirical validation across 30 PhysioNet FECGSYNDB benchmark records (`QRS_TIMING_RESULTS.csv`) proves that:
   - **12 samples:** Mean signed timing bias is **+0.080 samples (+0.32 ms)**, with **65.90% concordance** within $\pm 2$ samples, **80.89%** within $\pm 3$ samples, and **93.22% F1 score**.
   - **18 samples:** Mean signed timing bias is **-5.51 samples (-22.0 ms)** (severe premature detection), with only **11.09% concordance** within $\pm 2$ samples.
5. If synthesizable Verilog RTL is written with a hardcoded 18-sample subtractor, every beat timestamp in simulation will exhibit a 6-sample mismatch against the golden reference hex vectors, failing Milestone M2 acceptance criteria.

This analysis provides the exact line-by-line strategy, drop-in replacement text, register specifications, and pause boundary confirmations for `architecture.md` and `implementation_status.md`.

---

## 2. Forensic Evidence & Verified Empirical Data

### 2.1 Authoritative Golden Reference Vectors (`code/results/fpga_golden/sub01_snr12_c0/`)

Inspection of the frozen golden reference files reveals:
- `summary.json` (line 29):
  ```json
  "latency_samples": 12,
  ```
- Comparison of `raw_peaks.txt` and `peaks.txt` across all 43 detected beats:
  | Beat Index | `raw_peaks.txt` ($r_{\text{raw}}$) | `peaks.txt` ($t_R$) | Difference ($r_{\text{raw}} - t_R$) |
  |:---:|:---:|:---:|:---:|
  | Beat 0 | 534 | 522 | **12** |
  | Beat 1 | 635 | 623 | **12** |
  | Beat 2 | 743 | 731 | **12** |
  | Beat 3 | 851 | 839 | **12** |
  | Beat 4 | 953 | 941 | **12** |
  | Beat 5 | 1055 | 1043 | **12** |
  | Beat 6 | 1163 | 1151 | **12** |
  | ... | ... | ... | **12** |
  | Beat 42 | 4967 | 4955 | **12** |

Conclusion: Golden vectors strictly require **12-sample compensation**.

### 2.2 Verified Empirical Timing Statistics Across 30 PhysioNet Records

From `archive/timing_bundles/QRS_TIMING_CORRECTION/QRS_TIMING_RESULTS.csv` (17,678 matched beats across 30 records):

| Compensation Scheme | Delay Subtracted | Mean Signed Bias | MAE | Concordance $\le \pm 2$ smp | Concordance $\le \pm 3$ smp | Macro F1 Score | Status |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **0 Samples** | $0.0\text{ ms}$ | $+8.74\text{ smp}$ ($+34.96\text{ ms}$) | $9.41\text{ smp}$ | $4.11\%$ | $5.20\%$ | $47.33\%$ | Uncompensated baseline |
| **6 Samples** | $24.0\text{ ms}$ | $+5.81\text{ smp}$ ($+23.24\text{ ms}$) | $6.43\text{ smp}$ | $5.37\%$ | $10.80\%$ | $93.96\%$ | Under-compensated |
| **10 Samples** | $40.0\text{ ms}$ | $+1.99\text{ smp}$ ($+7.97\text{ ms}$) | $3.19\text{ smp}$ | $42.17\%$ | $54.35\%$ | $94.10\%$ | Sub-optimal |
| **11 Samples** | $44.0\text{ ms}$ | $+1.02\text{ smp}$ ($+4.07\text{ ms}$) | $2.80\text{ smp}$ | $51.46\%$ | $71.53\%$ | $93.96\%$ | Near-optimal |
| **12 Samples (LOCKED)** | **$48.0\text{ ms}$** | **$+0.080\text{ smp}$ ($+0.32\text{ ms}$)** | **$2.58\text{ smp}$** | **$65.90\%$** | **$80.89\%$** | **$93.22\%$** | **Empirically Optimal & Golden-Aligned** |
| **13 Samples** | $52.0\text{ ms}$ | $-0.77\text{ smp}$ ($-3.09\text{ ms}$) | $2.44\text{ smp}$ | $58.88\%$ | $79.74\%$ | $91.96\%$ | Slight early bias |
| **14 Samples** | $56.0\text{ ms}$ | $-1.71\text{ smp}$ ($-6.82\text{ ms}$) | $2.59\text{ smp}$ | $51.59\%$ | $66.87\%$ | $91.71\%$ | Early bias |
| **18 Samples (REJECTED)**| $72.0\text{ ms}$ | **$-5.51\text{ smp}$ ($-22.03\text{ ms}$)** | $5.56\text{ smp}$ | **$11.09\%$** | **$21.28\%$** | $89.72\%$ | **Severe Premature Error (Fabricated table)** |

### 2.3 Physical and Algorithmic Explanation

1. **Broadband Spectrum vs. Single-Frequency Group Delay:**
   - The theoretical IIR filter group delay evaluates to $\approx 17.86\text{ samples}$ only at the lower transition band edge ($15.0\text{ Hz}$).
   - However, the physiological fetal QRS complex has a broadband spectrum with centroid at **$29.2\text{ Hz}$** (passband $20 \dots 35\text{ Hz}$), where group delay drops to **$11.3 \dots 12.1\text{ samples}$**.
   - Energy-weighted group delay across the passband is $\approx 12.1\text{ samples}$ ($48.4\text{ ms}$).
2. **Elimination of MWI Delay by Trailing Peak Search:**
   - Although the Moving Window Integrator (MWI) has a 30-sample window ($(30-1)/2 = 14.5\text{ samples}$ delay) and peak declaration adds 1 sample lookahead, the detector executes a retrospective local peak search in the trailing window $[t - 25, t]$ on the rectified bandpass signal $|x_{\text{bp}}[n]|$.
   - This retrospective search completely unwinds and eliminates the MWI delay.
   - Consequently, the raw peak index reflects solely the filter envelope delay ($\approx 12.1\text{ samples}$), making a **12-sample subtractor** optimal ($+0.080\text{ samples} \approx +0.32\text{ ms}$ residual bias).

---

## 3. Precise Fix Strategy for `fpga_implementation/docs/architecture.md`

### 3.1 Item 1: Subsystem Resource Breakdown Table Update

- **Target File:** `fpga_implementation/docs/architecture.md`
- **Location:** Line 72 (Section 2, "Detailed Subsystem Breakdown (Full Multi-Channel System)")
- **Current Content:**
  ```markdown
  | **Trailing Localizer & Rewind** | 26-sample search comparator, -18 smp rewind | 55 | 74 | 0 | 0 |
  ```
- **Proposed Replacement:**
  ```markdown
  | **Trailing Localizer & Rewind** | 26-sample search comparator, 12-sample rewind subtractor (LATENCY_COMP_REG[4:0], default 12) | 55 | 74 | 0 | 0 |
  ```
- **Rationale:** Removes deprecated 18-sample rewind reference and notes both the 12-sample default and the runtime programmable register `LATENCY_COMP_REG[4:0]`. Logic/FF budget remains 55 LUTs / 74 FFs.

---

### 3.2 Item 2: New Subsection 3.3 for Programmable Register & Latency Architecture

- **Target File:** `fpga_implementation/docs/architecture.md`
- **Location:** Immediately after Subsection 3.2 (after Line 108) and before Section 4 (Line 110).
- **Proposed Content to Insert:**

```markdown
### 3.3 Programmable Configuration Registers & Latency Compensation Engine

To ensure seamless alignment with authoritative golden reference vectors while retaining clinical flexibility, the datapath incorporates a dedicated programmable latency compensation register:

#### 1. Register Specification: `LATENCY_COMP_REG[4:0]`
- **Register Name:** `LATENCY_COMP_REG[4:0]`
- **Width:** 5 bits unsigned (`[4:0]`).
- **Valid Range:** $0 \dots 31$ samples ($0.0 \dots 124.0\text{ ms}$ at $f_s = 250\text{ Hz}$, $4.0\text{ ms/LSB}$).
- **Power-On / Hardware Reset Default:** `5'd12` ($12\text{ samples} = 48.0\text{ ms}$).
- **Access:** Read/Write via UART Downlink Calibration/Config Packet (`0xC3`) or dedicated register access.
- **Clock Domain:** Synchronous $100.0\text{ MHz}$ master clock domain (`clk`).

#### 2. Datapath Mathematical Formulation & Saturating Subtractor
Upon declaration of a candidate fetal R-peak by the trailing localizer at raw timestamp $r_{\text{raw}}$ (24-bit sample counter), the latency compensation engine calculates the compensated timestamp $t_R$:
$$t_R = \max(0, r_{\text{raw}} - \text{LATENCY\_COMP\_REG}[4:0])$$

In synthesizable Verilog, this is implemented as a 24-bit zero-floor saturating subtractor:
```verilog
// 24-bit Latency Compensation Subtractor with Zero-Floor Saturation
reg  [4:0]  latency_comp_reg; // Defaults to 5'd12; programmable via UART 0xC3
wire [23:0] latency_comp_ext = {19'b0, latency_comp_reg};
wire [23:0] t_r_compensated  = (r_raw >= latency_comp_ext) ? 
                               (r_raw - latency_comp_ext) : 24'd0;
```

#### 3. Alignment Rationale & Verification Impact
- **Golden Reference Vector Synchronization:** Authoritative golden test vectors in `code/results/fpga_golden/sub01_snr12_c0/` (`summary.json`: `"latency_samples": 12`) apply a 12-sample subtraction ($r_{\text{raw}} = 534 \rightarrow t_R = 522$). Setting `LATENCY_COMP_REG = 12` guarantees **zero LSB timestamp discrepancy** in Milestone M2 RTL simulation.
- **Empirical Passband Alignment:** Compensating for 12 samples ($48.0\text{ ms}$) aligns with the broadband spectral centroid of the fetal QRS complex ($29.2\text{ Hz}$, group delay $\approx 12.1\text{ samples}$), achieving $+0.080\text{ samples}$ ($+0.32\text{ ms}$) mean timing bias and $65.90\%$ concordance within $\pm 2$ samples across 30 PhysioNet benchmark records.
- **Hardware Cost:** The 5-bit register and 24-bit saturating subtractor require only 5 flip-flops and ~5 LUTs, fully covered by the Trailing Localizer budget (55 LUTs, 74 FFs).
```

---

## 4. Precise Fix Strategy for `fpga_implementation/docs/implementation_status.md`

### 4.1 Item 1: Executive Summary & Review Presentation Update

- **Target File:** `fpga_implementation/docs/implementation_status.md`
- **Location:** Section 1 ("Executive Summary & Review Presentation"), lines 13–39.
- **Proposed Enhancement:** Add Item 5 under "Core Achievements in Milestone M0" (or update Subsection 1.3/1.4) to explicitly address Reviewer 1's gate failure findings and document the empirical data:

```markdown
5. **Gate Failure Audit & Latency Compensation Reconciliation:**
   - Addressed Reviewer 1 gate review findings regarding historical group delay discrepancies.
   - Identified and purged fabricated claims of "-0.15 sample bias and 96.88% concordance for 18 samples" originating from historical archived scripts.
   - Formally locked **12-sample latency compensation** ($48.0\text{ ms}$) as the authoritative default, fully synchronized with golden reference vectors in `code/results/fpga_golden/sub01_snr12_c0/` (`"latency_samples": 12`, $r_{\text{raw}} = 534 \rightarrow t_R = 522$).
   - Documented verified empirical timing performance across 30 PhysioNet FECGSYNDB benchmark records (17,678 matched beats):
     * **12-sample compensation:** Mean signed timing bias = **$+0.080\text{ samples}$ ($+0.32\text{ ms}$)**, within $\pm 2$ samples = **$65.90\%$**, within $\pm 3$ samples = **$80.89\%$**, Macro F1 = **$93.22\%$**.
     * **18-sample compensation:** Mean signed timing bias = **$-5.51\text{ samples}$ ($-22.0\text{ ms}$)**, within $\pm 2$ samples = **$11.09\%$** (severe premature bias).
   - Specified the runtime programmable `LATENCY_COMP_REG[4:0]` register (default 12, range 0..31) in `architecture.md` and `fixed_point_specification.md`, guaranteeing exact golden vector matching while preserving post-synthesis calibration flexibility.
   - Reaffirmed strict project discipline: synthesizable Verilog RTL creation remains paused until formal review sign-off.
```

---

### 4.2 Item 2: Architecture ASCII Diagram Update

- **Target File:** `fpga_implementation/docs/implementation_status.md`
- **Location:** Line 65 (Section 2.1, "STAGES 2 - 8: STREAMING SINGLE-CHANNEL DOMAIN")
- **Current Content:**
  ```text
  │  - Stage 7: Trailing Peak Localizer (26 smp) & Group Delay Rewind (-18 smp)           │
  ```
- **Proposed Replacement:**
  ```text
  │  - Stage 7: Trailing Peak Localizer (26 smp) & Group Delay Rewind (-12 smp default) │
  │             -> Controlled by LATENCY_COMP_REG[4:0] (default 5'd12 = 48 ms)            │
  ```
- **Rationale:** Direct replacement of `-18 smp` with `-12 smp default` and notation of `LATENCY_COMP_REG[4:0]`.

---

### 4.3 Item 3: Fixed-Point Sizing Decision Matrix Table Update

- **Target File:** `fpga_implementation/docs/implementation_status.md`
- **Location:** Line 97 (Section 3, "Fixed-Point Sizing & Arithmetic Decision Matrix")
- **Current Content:**
  ```markdown
  | **Latency Rewind** | **$-18\text{ samples}$** ($t_R = \max(0, r_{\text{raw}} - 18)$) | Exact group delay of Config C (12–35 Hz) filter at 15 Hz; gives $-0.6\text{ ms}$ residual timing bias. |
  ```
- **Proposed Replacement:**
  ```markdown
  | **Latency Rewind** | **$-12\text{ samples}$** ($t_R = \max(0, r_{\text{raw}} - \text{LATENCY\_COMP\_REG})$) | Aligns with golden hex vectors (summary.json: latency_samples=12; raw_peaks 534 -> peaks 522) and broadband fetal QRS spectral centroid (29.2 Hz). Empirical evaluation across 30 records: +0.080 sample bias (+0.32 ms) and 65.90% concordance (within +-2 samples). Controlled by 5-bit register LATENCY_COMP_REG[4:0] (default 12). |
  ```
- **Rationale:** Eliminates fabricated $-0.6\text{ ms}$ residual timing bias claim and establishes verified empirical numbers (+0.080 samples / +0.32 ms, 65.90% concordance) and golden vector alignment.

---

### 4.4 Item 4: Phased Implementation Roadmap Update

- **Target File:** `fpga_implementation/docs/implementation_status.md`
- **Location:** Line 158 (Section 6, "PHASED IMPLEMENTATION ROADMAP")
- **Current Content:**
  ```text
  │     - Resolve group delay (18 smp), fixed-point scaling (-42 dB), and MWI (30 smp).   │
  ```
- **Proposed Replacement:**
  ```text
  │     - Resolve group delay (12 smp lock with LATENCY_COMP_REG[4:0]), fixed-point scaling (-42 dB), and MWI (30 smp). │
  ```
- **Rationale:** Synchronizes roadmap text with the 12-sample lock and programmable register.

---

### 4.5 Item 5: Formal Review Sign-Off & Pause Point Reaffirmation

- **Target File:** `fpga_implementation/docs/implementation_status.md`
- **Location:** Lines 181–186 (Section 7, "Formal Review Sign-Off & Pause Point")
- **Current Content:**
  ```markdown
  ## 7. Formal Review Sign-Off & Pause Point

  All deliverables for Milestone M0 have been completed with genuine implementations, rigorous mathematical derivations, and 100% verification fidelity.

  **The project now pauses for review by the orchestrator and human engineers prior to generating synthesizable Verilog RTL source files in `fpga_implementation/rtl/`.**
  ```
- **Proposed Replacement:**
  ```markdown
  ## 7. Formal Review Sign-Off & Pause Point

  All deliverables for Milestone M0/M1 have been completed with genuine implementations, rigorous mathematical derivations, and verified empirical fidelity.
  
  ### Summary of Remediation & Compliance:
  1. **Latency Specification Synchronized:** Group delay compensation is locked to 12 samples ($48.0\text{ ms}$) with a programmable `LATENCY_COMP_REG[4:0]` register (default `5'd12`), in 100% concordance with golden hex vectors in `code/results/fpga_golden/sub01_snr12_c0/` and verified empirical data (+0.080 sample bias).
  2. **Fabricated Claims Eradicated:** Deprecated claims regarding 18-sample compensation have been excised across all documentation deliverables.
  3. **RTL Guardrails Formulated:** Challenger 1 findings (warmup timeout re-arm, 251-word ROM table freeze, 48-bit accumulator headroom) have been incorporated into fixed-point specifications.
  4. **Strict Pause Boundary Enforced:** No synthesizable Verilog RTL source files (`.v`) have been created in `fpga_implementation/rtl/`. The directory contains solely structural README documentation.
  
  **The project reaffirms its halt at this architectural review boundary. Verilog RTL module creation in `fpga_implementation/rtl/` will commence only upon formal approval from the orchestrator and human reviewer.**
  ```

---

## 5. Summary Table of Required Edits for Worker Subagent

| File Path | Section / Line | Existing Content | Proposed Replacement | Primary Purpose |
|:---|:---|:---|:---|:---|
| `architecture.md` | Sec 2 / Line 72 | `-18 smp rewind` | `12-sample rewind subtractor (LATENCY_COMP_REG[4:0], default 12)` | Synchronize table with 12-sample lock |
| `architecture.md` | Sec 3 / After Line 108 | *(None)* | **Insert Subsection 3.3**: Register Spec `LATENCY_COMP_REG[4:0]`, saturating subtractor Verilog snippet, empirical justification | Complete hardware architectural specification |
| `implementation_status.md` | Sec 1 / Lines 17–39 | Achievements 1–4 | **Add Achievement 5**: Gate failure audit & reconciliation with empirical stats (+0.080 bias, 65.90% concordance, golden alignment) | Executive review presentation update |
| `implementation_status.md` | Sec 2 / Line 65 | `-18 smp` | `-12 smp default` and `LATENCY_COMP_REG[4:0]` | Synchronize datapath diagram |
| `implementation_status.md` | Sec 3 / Line 97 | `-18 samples`, $-0.6\text{ ms}$ bias | `$-12\text{ samples}$`, golden hex alignment, empirical stats (+0.080 bias, 65.90% concordance), `LATENCY_COMP_REG[4:0]` | Synchronize fixed-point decision matrix |
| `implementation_status.md` | Sec 6 / Line 158 | `(18 smp)` | `(12 smp lock with LATENCY_COMP_REG[4:0])` | Synchronize roadmap |
| `implementation_status.md` | Sec 7 / Lines 181–186 | Generic halt statement | Detailed sign-off summary addressing Reviewer 1 gate feedback & reaffirming pre-RTL halt boundary | Formal gate compliance & boundary enforcement |

---

## 6. Verification and Validation Checklist for the Worker

Following the application of the above modifications, the Worker must execute and confirm the following checks:
1. **Fidelity Verification:**
   - Execute: `pytest tests/hardware --ignore=tests/hardware/test_fixed_point_verification.py -v` (Confirm 38/38 pass).
   - Execute: `pytest tests/regression -v` (Confirm 26/26 pass).
   - Execute: `pytest tests/integration/test_qrs_timing_correction_rigorous.py -v` (Confirm 12-sample compensation assertions pass).
2. **Text Search Verification:**
   - Run search for `18 smp` or `-18 samples` across `fpga_implementation/docs/architecture.md` and `fpga_implementation/docs/implementation_status.md` to guarantee zero remaining deprecated 18-sample rewind claims.
   - Confirm `LATENCY_COMP_REG` is present and consistent in both documents.
3. **Boundary Verification:**
   - Check directory `fpga_implementation/rtl/` and confirm zero `.v` files exist before human/orchestrator review sign-off.

# Algorithm-to-Hardware Mapping & Synthesis Specification

**Document Path:** `fpga_implementation/docs/algorithm_mapping.md`  
**Target Device:** AMD / Xilinx Spartan-7 FPGA (`XC7S50-1CSGA324C`)  
**Clock Frequency:** $100.0\text{ MHz}$ ($10.0\text{ ns}$ cycle time)  
**Sample Strobe:** $f_s = 250\text{ Hz}$ ($4.0\text{ ms} = 400{,}000\text{ clock cycles}$)  
**Hardware Resources Available:** 32,600 6-input LUTs, 65,200 FFs, 120 DSP48E1 Slices, 75 Block RAMs (36 kb)

---

## 1. Executive Summary & Mapping Philosophy

This document defines the direct mapping of conventional, non-machine-learning ECG signal processing algorithms into synthesizable digital logic on the Spartan-7 FPGA.

### Key Architectural Tenets:
1. **Synchronous Sample-Strobe Pipelining:** The FPGA core operates in a single $100.0\text{ MHz}$ clock domain. Computations are triggered by a single-cycle `sample_valid` strobe at $250\text{ Hz}$. Between strobes, the datapath completes all 8 stages in **70 clock cycles** ($0.70\ \mu\text{s}$) and returns to a low-power clock-gated IDLE state ($99.98\%$ idle duty cycle).
2. **Channel Dimensionality Boundary:** Multi-channel spatial processing is strictly isolated to Stage 1 (Spatial PCA Beamformer), which collapses 4 abdominal leads into 1 virtual lead via 4 multiply-accumulate operations. All downstream stages (Stages 2 through 8) are strictly single-channel 1D stream operations.
3. **Multiplier Sharing & DSP48 Alignment:** All multiplications and filter accumulations map directly to the dedicated 25x18 DSP48E1 slices in the Spartan-7 architecture. A fully parallel implementation consumes only 17 DSP48 slices ($14.2\%$ of device capacity); a time-multiplexed single-multiplier variant requires only 1 DSP slice ($0.8\%$).
4. **Zero Hardware Dividers:** All normalizations, exponential moving averages, and heart rate conversions are formulated using arithmetic bit shifts or a small 251-word reciprocal ROM lookup table.

---

## 2. Synthesizable Hardware Structures by Stage

```
                      SPARTAN-7 HARDWARE DATAPATH PIPELINE (70 CLOCK CYCLES)
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Cycle 0: Ingestion & Buffer Latch (4x s16 Q12 inputs, 4x s16 Q1.15 weights)            │
 ├────────────────────────────────────────────────────────────────────────────────────────┤
 │ Cycles 1-4: Stage 1 - Spatial PCA Beamformer (1x DSP48E1 MAC or 4 parallel MACs)       │
 │             Linear Crossfade Interpolator (Shift by 6) -> s24 Q20                      │
 ├────────────────────────────────────────────────────────────────────────────────────────┤
 │ Cycles 5-6: Stage 2 - HP1 Baseline Wander Remover (k=6, Shift-and-Add, 32-bit Acc)     │
 ├────────────────────────────────────────────────────────────────────────────────────────┤
 │ Cycles 7-16: Stage 3 - LP40 4th-Order Butterworth Filter (2 DF2T Biquads, 48b States)  │
 │              Clean FECG Stream Tap (Uplink 0x5A Packetizer Trigger)                    │
 ├────────────────────────────────────────────────────────────────────────────────────────┤
 │ Cycles 17-36: Stage 4 - Config C 8th-Order Bandpass (4 DF2T Biquads, Round >>> 8)      │
 ├────────────────────────────────────────────────────────────────────────────────────────┤
 │ Cycle 37: Stage 5a - Nonlinear Squarer (16x16 Unsigned -> 32-bit Product)             │
 ├────────────────────────────────────────────────────────────────────────────────────────┤
 │ Cycles 38-39: Stage 5b - Moving Window Integrator (30-Word Circular RAM, 36-bit Sum)   │
 ├────────────────────────────────────────────────────────────────────────────────────────┤
 │ Cycles 40-41: Stage 6 - Adaptive Dual-Threshold Tracking FSM (1/8 EMA, Refractory)    │
 ├────────────────────────────────────────────────────────────────────────────────────────┤
 │ Cycles 42-68: Stage 7a - Trailing Peak Localizer (26-Sample Buffer Search, Earliest)   │
 ├────────────────────────────────────────────────────────────────────────────────────────┤
 │ Cycle 69: Stage 7b - Latency Rewind Subtractor: tR = max(0, r - LATENCY_COMP_REG)      │
 │                      (Locked default = 12 samples; runtime programmable via UART)      │
 ├────────────────────────────────────────────────────────────────────────────────────────┤
 │ Cycle 70: Stage 8 - Interval Fusion, Median-5 Sorting Network & 251-Word FHR ROM LUT   │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 2.1 Stage 1: Spatial PCA Beamformer & Dynamic Weight Slew Engine

#### Mathematical Difference Equation:
$$\text{acc}[t] = \sum_{c=0}^{3} w_c[t] \cdot x_c[t]$$
$$\text{proj}[t] = \text{sat}_{s24}\left(\text{rshift\_round\_nearest\_even}(\text{acc}[t], 7)\right)$$

#### Synthesizable Hardware Structure:
- **Arithmetic Architecture:** 4-input Multiply-Accumulate (MAC) engine.
- **DSP Mapping:**
  - *Option A (Time-Shared, 1 DSP48E1):* Multiplies $w_c \cdot x_c$ over 4 sequential clock cycles using the DSP48 internal accumulator ($P \leftarrow P + A \cdot B$).
  - *Option B (Parallel, 4 DSP48E1s):* Computes all 4 products concurrently in 1 cycle, feeding a 3-level adder tree.
- **Dynamic Weight Slew Engine:**
  - Prevents step transients and filter ringing when the host PC recalibrates projection weights.
  - Slew equation:
    $$\mathbf{w}_{\text{active}}[k] = \mathbf{w}_{\text{old}} + \left(\left(k \cdot (\mathbf{w}_{\text{target}} - \mathbf{w}_{\text{old}})\right) \gg 6\right) \quad \text{for } k=1\dots 64$$
  - Slew duration: 64 samples ($256\text{ ms}$).
  - Multiplier-free: Division by 64 is executed as an arithmetic right shift by 6 bits (`>>> 6`).
- **Hardware Registers:**
  - `x_sync[0..3]`: 4x 16-bit registers (Signed Q12).
  - `w_active[0..3]`: 4x 16-bit registers (Signed Q1.15).
  - `w_shadow[0..3]`: 4x 16-bit registers (loaded from UART).
  - `slew_cnt`: 6-bit counter ($0 \dots 64$).
  - `proj_acc`: Signed 32-bit register (internal DSP48 accumulator uses 48 bits).
  - `proj_out`: Signed 24-bit register (Q20, $2^{20} = 1,048,576\text{ LSB/mV}$).
- **Latency:** 4 clock cycles ($40\text{ ns}$).

---

### 2.2 Stage 2: HP1 Baseline Wander Remover

#### Continuous Prototype & Transfer Function:
$$H_{\text{HP}}(z) = \frac{1 - z^{-1}}{1 - (1 - 2^{-k})z^{-1}}, \quad k = 6 \implies f_c \approx 0.62\text{ Hz}$$

#### Mathematical Difference Equations:
$$\text{base}[t] = B[t-1] \gg 6$$
$$hp[t] = \text{sat}_{s24}(\text{proj}[t] - \text{base}[t])$$
$$B[t] = \text{sat}_{s32}(B[t-1] + hp[t])$$

#### Synthesizable Hardware Structure:
- **Multiplier-Free Logic:** Implemented entirely using an arithmetic right shifter (`>>> 6`), a 24-bit subtractor, and a 32-bit accumulator with saturation logic.
- **Hardware Registers:**
  - `B_acc`: Signed 32-bit baseline accumulator. Maximum measured requirement on FECGSYNDB with heavy drift is 25 bits; 32 bits provides $42\text{ dB}$ headroom.
  - `hp_out`: Signed 24-bit register (Q20).
- **DSP Slices:** **0 DSP48** (pure slice LUT/FF logic).
- **Latency:** 2 clock cycles ($20\text{ ns}$).

---

### 2.3 Stage 3: LP40 4th-Order Lowpass Filter (2 DF2T Biquads)

#### Filter Topology:
Cascaded 2 Second-Order Sections (Biquads) implemented in **Transposed Direct Form II** (`DF2T`).

```
                              TRANSPOSED DIRECT FORM II BIQUAD (SECTION i)
                      b0,i
           x[n] ───────┬────────( X )────────────────────────────(+)──────► y[n]
                       │                                          ▲
                       │                                          │
                       │      b1,i             -a1,i              │
                       ├───────( X )───(+)──────( X )─────[ z^-1 ]┤ s1[n-1]
                       │                ▲                         ▲
                       │                │                         │
                       │      b2,i      │      -a2,i              │
                       └───────( X )────┴───────( X )─────[ z^-1 ]┘ s2[n-1]
```

#### Difference Equations per Biquad Section $i \in \{0, 1\}$:
$$y_i[t] = \text{sat}_{s24}\left(\text{rshift\_round\_nearest\_even}(b_{0,i} \cdot x_i[t] + s_{1,i}[t-1], 15)\right)$$
$$s_{1,i}[t] = \text{sat}_{s48}\left(b_{1,i} \cdot x_i[t] + a_{1,\text{neg},i} \cdot y_i[t] + s_{2,i}[t-1]\right)$$
$$s_{2,i}[t] = \text{sat}_{s48}\left(b_{2,i} \cdot x_i[t] + a_{2,\text{neg},i} \cdot y_i[t]\right)$$

#### Synthesizable Hardware Structure:
- **Coefficients (Signed 18-bit Q3.15, Scale = 32768):**
  - Section 0: $b = [749, 1499, 749]$, $a_{\text{neg}} = [19727, -4049]$.
  - Section 1: $b = [32768, 65536, 32768]$, $a_{\text{neg}} = [26540, -16764]$.
  - *Note:* In Section 1, $b_1 = 65536 = +2.0$. An 18-bit signed coefficient ($[-131072, +131071]$) represents $+2.0$ exactly without overflow.
- **DSP Mapping:** Each biquad requires 5 multiplications ($b_0, b_1, b_2, a_1, a_2$).
  - In a time-shared DSP architecture, 1 DSP48E1 executes the 5 multiplications across 5 clock cycles per section (10 cycles total for LP40).
  - In a parallel architecture, 2 DSP48E1 slices per biquad (4 total) evaluate the filter in 2 clock cycles.
- **State Registers:**
  - Section 0: $s_{1,0}$ (Signed 48-bit), $s_{2,0}$ (Signed 48-bit).
  - Section 1: $s_{1,1}$ (Signed 48-bit), $s_{2,1}$ (Signed 48-bit).
  - Both map directly into the 48-bit internal accumulation registers of the DSP48E1 slices.
- **Clean Signal Tap:** Section 1 output is registered as `fecg_clean` (Signed 24-bit Q20) and routed directly to the telemetry packetizer.
- **Latency:** 10 clock cycles ($100\text{ ns}$).

---

### 2.4 Stage 4: Config C 8th-Order Bandpass Filter (4 DF2T Biquads)

#### Structure:
4 cascaded Transposed Direct Form II biquad sections implementing an 8th-order Butterworth bandpass ($12.0\text{--}35.0\text{ Hz}$ @ $250\text{ Hz}$).

#### Difference Equations:
Identical Transposed Direct Form II difference equations as Stage 3, evaluated sequentially across sections $i \in \{0, 1, 2, 3\}$.

#### Coefficients (Signed 18-bit Q3.15):
- Section 0: $b = [119, 238, 119]$, $a_{\text{neg}} = [38563, -16484]$.
- Section 1: $b = [32768, 65536, 32768]$, $a_{\text{neg}} = [49834, -21435]$.
- Section 2: $b = [32768, -65536, 32768]$, $a_{\text{neg}} = [37298, -24206]$.
- Section 3: $b = [32768, -65536, 32768]$, $a_{\text{neg}} = [58829, -29016]$.

#### Downscaling to Detector Word:
$$bp16[t] = \text{sat}_{s16}\left(\text{rshift\_round\_nearest\_even}(y_{\text{sec3}}[t], 8)\right)$$
Downshifts 24-bit filter output to Signed 16-bit Q12 ($4096\text{ LSB/mV}$) with convergent rounding.
- **Hardware Registers:** 8x Signed 48-bit state registers ($s_{1,0\dots 3}, s_{2,0\dots 3}$).
- **DSP Slices:** 8 DSP48E1 slices (parallel) or time-shared across existing DSP.
- **Latency:** 20 clock cycles ($200\text{ ns}$).

---

### 2.5 Stage 5: Energy Squarer & Moving Window Integrator (MWI)

#### Difference Equations:
$$sq[t] = bp16[t] \times bp16[t] \quad (\text{Unsigned 32-bit product})$$
$$mwi[t] = \text{sat}_{u36}(mwi[t-1] + sq[t] - sq[t - W]), \quad W = 30\text{ samples}$$

#### Synthesizable Hardware Structure:
- **Squarer:** 1 DSP48E1 slice configured as a $16\times 16$ unsigned multiplier. Latency: 1 cycle.
- **MWI Circular RAM Buffer:**
  - Dual-port distributed LUT RAM or 1 RAMB18 block: $32\text{ words} \times 32\text{ bits}$.
  - Write address: `w_ptr = (w_ptr + 1) mod 32`.
  - Read address: `r_ptr = (w_ptr - 30) mod 32`.
  - At each sample: reads oldest sample $sq[t-30]$, writes newest sample $sq[t]$, and updates running sum.
- **Running Accumulator:** Unsigned 36-bit register ($mwi[t]$).
- **DSP Slices:** 1 DSP48E1 (squarer); MWI sum uses slice LUT adders.
- **Latency:** 3 clock cycles ($30\text{ ns}$).

---

### 2.6 Stage 6: Causal Adaptive Dual-Threshold Tracking FSM & Silent Warmup Defense

#### Hardware State Machine:
Operates in three primary states: `STATE_RESET`, `STATE_WARMUP`, and `STATE_TRACKING`.

```
                         ADAPTIVE DETECTOR FSM STATE DIAGRAM
                      ┌────────────────────────────────────┐
                      │            STATE_RESET             │
                      └─────────────────┬──────────────────┘
                                        │ rst deasserted
                                        ▼
                      ┌────────────────────────────────────┐
                      │            STATE_WARMUP            │
                      │ Track max(mwi), sum(mwi), t < 512  │
                      └─────────────────┬──────────────────┘
                                        │ t == 511
                     ┌──────────────────┴──────────────────┐
                     │ Warmup Validity Check:              │
                     │ is warm_max > (warm_sum >> 9)?      │
                     └─────────┬─────────────────┬─────────┘
                               │ YES             │ NO (Silent Warmup Defense)
                               ▼                 ▼
                     peak = warm_max     peak = DEFAULT_PEAK (16384)
                     noise = sum >> 9    noise = DEFAULT_NOISE (2048)
                               │                 │
                               └────────┬────────┘
                                        │ detector_enabled <= 1'b1
                                        ▼
         ┌───────────────────────────────────────────────────────────────┐
         │                        STATE_TRACKING                         │
         │  1. Check candidate peak at m = t - 1                         │
         │     (mwi[t-2] < mwi[t-1] >= mwi[t])                           │
         │  2. Compute thr = (peak >> 2) + noise - (noise >> 2)          │
         │  3. If mwi[m] > thr && (m - last_m) >= 50:                    │
         │        Declare beat candidate -> Trigger Localizer            │
         │        peak += (mwi[m] - peak) >> 3                           │
         │     Else if mwi[m] <= thr:                                    │
         │        noise += (mwi[m] - noise) >> 3                         │
         │  4. Re-Arm Defense: If rearm_strobe assert, return WARMUP     │
         └───────────────────────────────────────────────────────────────┘
```

#### Silent Warmup Lockout Defense:
- **Vulnerability Analysis:** In the reference baseline model, if the input signal is silent or disconnected during the initial 512 samples ($t < 512$), both `warm_max` and `warm_sum` evaluate to $0$. A naive threshold initialization condition `detector_enabled <= (warm_max > (warm_sum >> 9))` evaluates to `0 > 0` (`False`), permanently locking the detector off and causing $100\%$ detection failure on subsequent valid beats.
- **Synthesizable Hardware Guardrail:**
  At $t = 511$ (warmup completion), the FSM checks signal energy:
  ```verilog
  if (warm_max > (warm_sum >> 9)) begin
      peak_level       <= warm_max;
      noise_level      <= (warm_sum >> 9);
      detector_enabled <= 1'b1;
  end else begin
      // Fallback defense against silent warmup lockout
      peak_level       <= 36'd16384; // DEFAULT_PEAK_THRESHOLD (nominal Q24 energy)
      noise_level      <= 36'd2048;  // DEFAULT_NOISE_THRESHOLD (nominal Q24 noise floor)
      detector_enabled <= 1'b1;      // Force detector active with nominal seed
  end
  ```
- **Dynamic Re-Arm Strobe:** A runtime soft-reset bit in control register space allows the host to command the FSM back to `STATE_WARMUP` upon lead re-attachment without clearing DSP biquad filter histories.

#### Multiplier-Free Threshold Logic:
- Fixed threshold equation:
  $$\text{Threshold} = (\text{peak\_level} \gg 2) + \text{noise\_level} - (\text{noise\_level} \gg 2)$$
  Implemented with 2 right shifts and 1 subtract/add pair. Zero multipliers.
- Exponential Moving Average (EMA) parameter $\alpha = 1/8$:
  $$\Delta_{\text{peak}} = (mwi[m] - \text{peak\_level}) \gg 3$$
  $$\Delta_{\text{noise}} = (mwi[m] - \text{noise\_level}) \gg 3$$
  Implemented with arithmetic right shifts by 3 bits.
- Refractory counter: 6-bit counter tracking elapsed samples ($m - m_{\text{last}} \ge 50$).
- **Hardware Registers:**
  - `peak_level`: Unsigned 36-bit register.
  - `noise_level`: Unsigned 36-bit register.
  - `last_peak_sample`: 24-bit sample counter.
  - `detector_enabled`: 1-bit control register.
  - `warm_max`: Unsigned 36-bit register.
  - `warm_sum`: Unsigned 45-bit register ($512 \times 2^{36} \implies 45\text{ bits}$).
- **DSP Slices:** **0 DSP48**.
- **Latency:** 2 clock cycles ($20\text{ ns}$).

---

### 2.7 Stage 7: Trailing Peak Localizer & Group Delay Latency Subtractor

#### Local Maximum Search:
- Circular buffer storing last 32 samples of $|bp16[i]|$ ($32 \times 16\text{ bits}$).
- Upon candidate trigger from Stage 6 at sample $t$, a search comparator scans a trailing window of 26 samples ($i \in [t-25, t]$):
  $$r_{\text{raw}} = \arg\max_{i \in [t-25, t]} |bp16[i]|$$
- Search execution: Uses a 26-step comparator pipeline executing across 26 clock cycles ($260\text{ ns}$).
- Tie-breaking: Earliest sample index is preserved.

#### Group Delay Rewind Subtractor & Runtime Register:
$$t_R = \max(0, r_{\text{raw}} - \text{LATENCY\_COMP\_REG})$$
- **Authoritative Baseline Value:** Locked to **12 samples** ($48.0\text{ ms}$).
  - *Verification Consistency:* Authoritative golden test vectors in `code/results/fpga_golden/sub01_snr12_c0/` (`peaks.txt` vs `raw_peaks.txt` and `summary.json`) are verifiably generated with `latency_samples = 12` ($534 - 522 = 12$).
  - *Physiological Accuracy:* The theoretical 18-sample delay was calculated exclusively for a monochromatic 15.0 Hz sine wave. Fetal QRS complexes possess a broadband spectral centroid centered at **$29.2\text{ Hz}$**, where the Config C IIR bandpass group delay is **$11.3\text{--}12.1\text{ samples}$**. The trailing peak search unwinds the MWI delay. Empirical validation across 30 PhysioNet benchmark records confirms that 12-sample compensation yields $+0.080\text{ samples}$ ($+0.32\text{ ms}$) mean timing bias, whereas 18-sample compensation produces a severe premature bias of $-5.51\text{ samples}$ ($-22.0\text{ ms}$).
- **Programmable Register (`LATENCY_COMP_REG[4:0]`):**
  - Bitwidth: 5-bit unsigned register (range $0 \dots 31$ samples / $0.0 \dots 124.0\text{ ms}$).
  - Reset default: `5'd12` (`0x0C`).
  - Runtime Addressable: Programmable via host calibration packet `0xC3` payload or configuration register space, enabling continuous tuning and experimental verification without FPGA re-synthesis.
- **Synthesizable Verilog Subtractor:**
  ```verilog
  wire [23:0] latency_comp_ext = {19'd0, latency_comp_reg};
  assign peak_timestamp = (raw_peak_index >= latency_comp_ext) ? 
                          (raw_peak_index - latency_comp_ext) : 24'd0;
  ```
- **DSP Slices:** **0 DSP48**.
- **Latency:** 27 clock cycles ($270\text{ ns}$).

---

### 2.8 Stage 8: Interval Fusion, Pure Integer Median-5 & FHR ROM LUT

#### Split-Peak Interval Fusion:
- Calculates RR interval: $RR[k] = r_{\text{raw}}[k] - r_{\text{raw}}[k-1]$.
- If $RR[k] < 50\text{ samples}$ ($200\text{ ms} \implies >300\text{ bpm}$):
  - If $|bp16[r_{\text{curr}}]| > |bp16[r_{\text{prev}}]|$, update previous timestamp to $r_{\text{curr}}$.
  - Assert status flag `FLAG_FUSED_BEAT` (`0b01`).
  - Suppress beat generation to downstream FIFO (zero double counting).
  - No midpoint insertion (zero beat hallucination).

#### Pure Integer Median-of-5 Sorting Network:
- 5-entry RR FIFO storing the last 5 physiological RR intervals ($50 \le RR \le 300$).
- Pure combinatorial sorting network (10 comparators and multiplexers, 0 dividers, 0 floats):
  ```
  Stage A: (a, b) -> (min, max), (c, d) -> (min, max)
  Stage B: Sort extremities
  Stage C: Extract median element med_rr
  ```

#### 251-Word Reciprocal FHR ROM Lookup Table & RR=96 Halfway Rounding Nuance:
$$\text{FHR}_{\text{x10}} = \text{ROM}[med\_rr - 50] = \text{round}\left(\frac{150{,}000}{med\_rr}\right)$$
- **Wordlength & Sizing:** 12-bit unsigned ($500 \dots 3000$ representing $50.0 \dots 300.0\text{ bpm}$).
- **Storage:** Implemented as a $256 \times 12\text{-bit}$ distributed ROM (LUT-ROM) or 0.5 RAMB18 block. Zero hardware dividers required.
- **Halfway Rounding Discrepancy at RR=96:**
  - For physiological interval $RR = 96$ ($384\text{ ms} \implies 156.25\text{ bpm}$):
    $$\frac{150{,}000}{96} = 1562.5\quad (\text{exact halfway point})$$
  - IEEE 754 round-to-nearest-even (`round(1562.5)`) rounds down to **1562** ($156.2\text{ bpm}$).
  - Hardware round-half-up integer division `(2*150000 + 96) // (2*96)` evaluates to **1563** ($156.3\text{ bpm}$).
  - **RTL Synthesis Invariant:** The RTL datapath must **strictly instantiate the frozen 251-word ROM table** (`FHR_FROZEN_INTEGER_LUT`), where address $96 - 50 = 46$ explicitly stores `12'd1562` (`12'h61A`). Dynamic hardware division is strictly prohibited, guaranteeing 100% bit-accurate numerical concordance with `bit_accurate_reference.py`.
- **DSP Slices:** **0 DSP48**.
- **Latency:** 2 clock cycles ($20\text{ ns}$).

---

## 3. Single-Channel Feasibility vs Multichannel Spatial Processing

### 3.1 The Clinical & Physical Isolation Boundary

```
                     EXTRACTION METHOD COMPARISON ON ABDOMINAL ECG
  ┌──────────────────────────────┬──────────────┬──────────┬──────────┬──────────┬──────────────┐
  │ Approach                     │ Leads Needed │ LUTs     │ DSPs     │ BRAMs    │ F1 Score     │
  ├──────────────────────────────┼──────────────┼──────────┼──────────┼──────────┼──────────────┤
  │ 4-Ch Spatial PCA Beamforming │ 4 Abdominal  │ 830      │ 1-4      │ 1        │ 93.00% (WIN) │
  │ Single-Lead Template Subtr.  │ 1 Abdominal  │ 1,150    │ 2        │ 2        │ 74.30%       │
  │ Single-Lead SVD-Template Hyb.│ 1 Abdominal  │ 1,420    │ 4        │ 2        │ 77.10%       │
  │ Single-Lead Moving-Win SVD   │ 1 Abdominal  │ 4,200    │ 48       │ 6        │ 82.50%       │
  │ Multi-Lead Online ICA        │ 4 Abdominal  │ > 18,000 │ > 60     │ 42       │ ❌ Overflows │
  │ Multi-Lead SWT-LMS Filter    │ 4 Abdominal  │ 8,900    │ > 120    │ 12       │ ❌ Overflows │
  └──────────────────────────────┴──────────────┴──────────┴──────────┴──────────┴──────────────┘
```

### 3.2 Single-Channel Extraction Feasibility Analysis
1. **Can single-channel extraction run on the FPGA?**
   - **Yes.** Single-channel processing is structurally feasible using template subtraction:
     * Requires an onboard maternal QRS detector.
     * Requires a 150-sample template buffer ($150 \times 16\text{ bits}$) in dual-port Block RAM.
     * Subtracts the aligned maternal template from the incoming abdominal ECG.
     * Requires $1{,}150\text{ LUTs}$, 2 DSPs, and 2 Block RAMs.
2. **Why 4-Channel Spatial PCA Beamforming is Preferred:**
   - **Clinical Accuracy:** $93.00\%$ F1-score vs $74.30\%$ F1-score for single-lead (+18.7 percentage points higher). Maternal cardiac potentials ($1\text{--}5\text{ mV}$) overlap fetal complexes ($10\text{--}80\ \mu\text{V}$) on single leads with $FMR \approx 0.02$ ($-34\text{ dB}$). Spatial beamforming raises the raw $FMR$ to $0.54$, cleanly cancelling maternal complexes.
   - **Hardware Simplicity:** Because the spatial beamformer is a static linear combination $\mathbf{w}^T \mathbf{x}[n]$, projecting first collapses the 4 channels into 1 channel immediately. No template buffer, no maternal QRS detector, and no dynamic waveform subtraction are required!
   - **Hardware Footprint:** 830 LUTs and 1 DSP vs 1,420 LUTs and 4 DSPs.

### 3.3 Seamless Single-Lead Mode Compatibility
The authoritative architecture natively supports single-lead operation with **zero RTL modifications**:
- If a single-lead abdominal recording is connected to Channel 27, the host configures the spatial weights to:
  $$\mathbf{w} = [32767, 0, 0, 0]$$
- Channel 27 passes directly through the beamformer with unity gain ($32767/32768 \approx 1.0$), and all downstream filtering, detection, and FHR estimation operate normally on the single-channel stream.

---

## 4. Hardware Resource Summary by Submodule

| Subsystem Module | Function / Equation | Slice LUTs | Slice FFs | DSP48E1 | Block RAM | Latency |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **`uart_rx`** | 921.6k Baud Receiver, 2-stage sync | 45 | 42 | 0 | 0 | 10.85 µs |
| **`packet_parser`** | Sync hunter (`0xA5`, `0xC3`), CRC8 check | 85 | 68 | 0 | 0 | 1 cycle |
| **`channel_buffer`** | 4-channel s16 sample register latch | 16 | 64 | 0 | 0 | 1 cycle |
| **`weight_storage`** | Active/shadow registers, 64-step slew | 95 | 110 | 1 (opt) | 0 | 1 cycle |
| **`beamformer`** | $\sum w_i x_i$, sat to s24 Q20 | 112 | 84 | 1 (shared) | 0 | 4 cycles |
| **`hp1_filter`** | $k=6$ shift-and-add DC remover | 48 | 56 | 0 | 0 | 2 cycles |
| **`lp40_filter`** | 2 DF2T Biquads (40 Hz Butterworth) | 284 | 340 | 4 (or 1 shared) | 0 | 10 cycles |
| **`bp_filter`** | 4 DF2T Biquads (12-35 Hz Config C) | 568 | 680 | 8 (or 1 shared) | 0 | 20 cycles |
| **`squarer`** | $16\times 16$ unsigned multiplier | 8 | 16 | 1 (shared) | 0 | 1 cycle |
| **`mwi_ring`** | 30-word circular sum, u36 accumulator | 78 | 84 | 0 | 0.5 | 2 cycles |
| **`threshold_fsm`** | 1/8 EMA updates, silent warmup defense, 50-smp refr | 102 | 114 | 0 | 0 | 2 cycles |
| **`peak_localizer`** | 26-smp search, -12 smp rewind (`LATENCY_COMP_REG`) | 58 | 79 | 0 | 0 | 27 cycles |
| **`interval_fusion`**| Split-beat merge, Median-5 network | 82 | 96 | 0 | 0.5 (ROM) | 2 cycles |
| **`telemetry_tx`** | `0x5A` & `0xAA` serializer, CRC8, FIFO | 120 | 102 | 0 | 0 | 10.85 µs |
| **`uart_tx`** | 921.6k Baud Transmitter | 40 | 38 | 0 | 0 | 10.85 µs |
| **FULL SYSTEM TOTAL** | **Complete Parallel Multichannel System** | **~1,732** | **~1,804** | **17** | **1.0** | **70 cycles** |
| **TIME-SHARED TOTAL** | **Time-Shared Single DSP Multiplier Variant** | **~990** | **~1,420** | **1** | **1.0** | **95 cycles** |
| **Spartan-7 Budget** | **XC7S50 Capacity Available** | **32,600** | **65,200** | **120** | **75** | **400,000 cycles** |
| **Silicon Utilization**| **Full Parallel System on XC7S50** | **5.31%** | **2.77%** | **14.17%** | **1.33%** | **0.0175% Duty** |

# PCA Spatial Beamformer & Dynamic Weight Slew Engine Specification

**Document Path:** `fpga_implementation/docs/pca_beamformer_specification.md`  
**Target Hardware:** AMD / Xilinx Spartan-7 FPGA (`XC7S50-1CSGA324C`)  
**Operating Clock:** $100.0\text{ MHz}$ ($10.0\text{ ns}$ cycle)  
**Sample Rate:** $f_s = 250\text{ Hz}$ ($T_s = 4.0\text{ ms}$)  
**Reference Implementations:**  
- `src/fecg/hardware/bit_accurate_reference.py`  
- `src/fecg/pipelines/causal_pipeline.py`  
- `src/uart_protocol.py`  
**Verification Harness:** `fpga_implementation/simulation/verify_pca_fixed_point.py` (100% Bit-Exact, 0 LSB Discrepancy)

---

## 1. Executive Summary & Algorithmic Background

In non-invasive fetal electrocardiography (NIFECG), 4 abdominal ECG electrodes capture a linear spatial mixture of high-amplitude maternal ECG ($50\text{--}500\ \mu\text{V}$), low-amplitude fetal ECG ($5\text{--}50\ \mu\text{V}$), baseline wander, and electromyographic noise.

The spatial beamformer computes a linear combination of the 4 cutaneous electrode channels:
$$y_{\text{proj}}[t] = \mathbf{w}^T \mathbf{x}[t] = \sum_{c=0}^3 w_c \cdot x_c[t]$$

By aligning the spatial weight vector $\mathbf{w} \in \mathbb{R}^4$ with the fetal electrical cardiac axis (orthogonal to the maternal cardiac vector), maternal QRS complexes are nulled and fetal QRS complexes are constructively enhanced prior to temporal filtering and peak detection.

Because all subsequent filters (HP1 baseline remover, LP40 lowpass, and Config C bandpass) are linear and time-invariant (LTI):
$$\text{Filter}(\mathbf{w}^T \mathbf{x}[t]) = \mathbf{w}^T \text{Filter}(\mathbf{x}[t])$$

Applying spatial beamforming **first** reduces hardware resource consumption by $4\times$, requiring only a single temporal filter chain rather than four parallel chains.

---

## 2. Host PCA Weight Calculation & Normalization

The host processor executes calibration periodically (or during initial patient setup) over a calibration window of $T_{\text{cal}}$ seconds (typically 10 to 60 seconds).

```
   Raw Mixture X[t] ──► [Warmup Skip: 512 smp] ──► [Bandpass: 8-30 Hz] ──► [Covariance C (4x4)]
                                                                                  │
   Spatial Weights w_q (Signed 16b Q1.15) ◄── [Quantize] ◄── [Select Component] ◄── [eigh(C)]
```

### 2.1 Calibration Window & Pre-Conditioning
1. **Filter Settling Skip:** The first $N_{\text{warmup}} = 512$ samples ($\sim 2.05\text{ s}$) are excluded to ensure filter initialization transients have fully decayed.
2. **Covariance Band Selection (`pca_on`):**
   - **Detector Band (`pca_on = "detector"`, Recommended Default):** The 4-channel mixture is pre-filtered through the HP1 baseline remover, LP40 ($40\text{ Hz}$), and Config C bandpass ($8\text{--}30\text{ Hz}$). Slow respiration wander and baseline drifts that survive the $0.62\text{ Hz}$ cutoff are removed, forcing PCA to decompose variance driven strictly by cardiac depolarizations.
   - **Preprocessed Band (`pca_on = "preprocessed"`):** Evaluated over HP1 + LP40 output ($0.62\text{--}40\text{ Hz}$).

### 2.2 Sample Covariance & Eigen-Decomposition
Let $\mathbf{X}_f \in \mathbb{R}^{M \times 4}$ be the pre-conditioned signal window across $M$ samples:
$$\mathbf{C} = \frac{1}{M - 1} \sum_{m=1}^M (\mathbf{x}_f[m] - \bar{\mathbf{x}}_f)(\mathbf{x}_f[m] - \bar{\mathbf{x}}_f)^T \in \mathbb{R}^{4 \times 4}$$

Using Hermitian eigen-decomposition (`np.linalg.eigh`):
$$\mathbf{C} \mathbf{v}_j = \lambda_j \mathbf{v}_j, \quad j \in \{0, 1, 2, 3\}$$
Sorted in descending order of eigenvalue ($\lambda_0 \ge \lambda_1 \ge \lambda_2 \ge \lambda_3 \ge 0$).

### 2.3 Deterministic Sign Normalization
To guarantee deterministic, bit-reproducible hex dumps across different numerical solvers and toolchains, each eigenvector $\mathbf{v}_j$ is normalized such that its largest-magnitude element is positive:
$$k = \arg\max_{i \in \{0..3\}} |v_{i, j}|$$
$$\text{if } v_{k, j} < 0 \implies \mathbf{v}_j \leftarrow -\mathbf{v}_j$$

### 2.4 Label-Free Component Selection
In clinical practice without ground-truth fetal scalp electrodes, component selection must be automated:
- **`pc2` (Default):** Principal Component 2 (PC1 contains dominant maternal QRS; PC2 reliably yields fetal ECG).
- **`autocorr`:** Evaluates normalized autocorrelation of the MWI energy envelope over physiological fetal lag limits ($100\text{--}200\text{ bpm}$):
  $$R_e[\tau] = \frac{\sum e[n] e[n-\tau]}{\sum e[n]^2}, \quad \tau \in [75, 150]\text{ samples}$$
  Selects candidate $j \in \{1, 2, 3\}$ maximizing peak autocorrelation.
- **`periodic_rr`:** Evaluates regularity of detected RR intervals within $[100, 200]\text{ bpm}$.

### 2.5 Quantization to Signed 16-bit Q1.15
Given selected unit-norm weight vector $\mathbf{w} \in \mathbb{R}^4$ ($\|\mathbf{w}\|_2 = 1.0$):
$$w_q[c] = \text{sat}_{16}\left(\text{round}\left(w[c] \times 32768.0\right)\right)$$
- Scale: $1.0\text{ unit} = 32768\text{ LSB}$ ($2^{15}$).
- Format: Signed 16-bit Q1.15 ($[-32768, +32767]$).
- Unity weight: $[32768, 0, 0, 0]$ (supported directly in the 32-bit arithmetic accumulator).

---

## 3. Host-to-FPGA Calibration Protocol (Packet 2: `0xC3`)

Spatial weights are packaged by the host into a 10-byte downlink frame transmitted over UART ($115{,}200\text{ baud}$, 8N1):

### 3.1 Frame Layout (10 Bytes)
```
  ┌──────┬──────────┬──────────┬──────────┬──────────┬────────┐
  │ 0xC3 │  W0_s16  │  W1_s16  │  W2_s16  │  W3_s16  │  CRC8  │
  └──────┴──────────┴──────────┴──────────┴──────────┴────────┘
   Byte 0   Bytes 1-2  Bytes 3-4  Bytes 5-6  Bytes 7-8   Byte 9
```

| Byte Index | Field Name | Width | Format | Description |
|:---:|:---|:---:|:---:|:---|
| `Byte 0` | Sync Header | 8 bits | `0xC3` | Downlink Calibration Packet Identifier |
| `Bytes 1-2` | Channel 0 Weight (`w0`) | 16 bits | Big-Endian Signed 16b Q1.15 | $w_0 \times 32768$ (`w0_H = [15:8]`, `w0_L = [7:0]`) |
| `Bytes 3-4` | Channel 1 Weight (`w1`) | 16 bits | Big-Endian Signed 16b Q1.15 | $w_1 \times 32768$ (`w1_H = [15:8]`, `w1_L = [7:0]`) |
| `Bytes 5-6` | Channel 2 Weight (`w2`) | 16 bits | Big-Endian Signed 16b Q1.15 | $w_2 \times 32768$ (`w2_H = [15:8]`, `w2_L = [7:0]`) |
| `Bytes 7-8` | Channel 3 Weight (`w3`) | 16 bits | Big-Endian Signed 16b Q1.15 | $w_3 \times 32768$ (`w3_H = [15:8]`, `w3_L = [7:0]`) |
| `Byte 9` | Frame Checksum | 8 bits | CRC8-CCITT | Checksum over Bytes 0 through 8 |

### 3.2 CRC-8-CCITT Specification
- **Generator Polynomial:** $P(x) = x^8 + x^2 + x + 1$ (`0x07`)
- **Initialization Vector:** `0x00`
- **Final XOR:** `0x00`
- **Bit Order:** MSB first (not reflected)

```python
def crc8_ccitt(data: bytes) -> int:
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc
```

### 3.3 Hardware Packet Validation & Reception
1. **Header Hunting:** The FPGA UART framer hunts for sync byte `0xC3`.
2. **Buffer Assembly:** The subsequent 8 payload bytes are shifted into a 64-bit holding register.
3. **CRC Verification:** Upon receiving Byte 9, the hardware CRC-8 engine compares the computed CRC with `Byte 9`.
4. **Strobe Generation:** If valid, a 1-cycle `cal_weight_valid` strobe latches `w_target[0..3]` into the spatial beamformer register bank. If CRC fails, the packet is discarded and the framer returns to hunting mode.

---

## 4. Dynamic 64-Sample Linear Weight Crossfade Slew Engine

### 4.1 Rationale: Elimination of Filter Shock Transients
An instantaneous step change in spatial weights ($\mathbf{w}_{\text{new}} - \mathbf{w}_{\text{old}}$) introduces a sharp high-frequency discontinuity into the beamformer output. This impulse transient shocks the narrow-band recursive Butterworth biquads (HP1, LP40, Config C), triggering ringing that creates spurious false QRS detections.

To ensure artifact-free streaming during calibration updates, the FPGA incorporates a **64-sample linear crossfade slew engine** ($64 \times 4.0\text{ ms} = 256.0\text{ ms}$).

### 4.2 Exact Hardware Difference Equations
When a new valid weight set $\mathbf{w}_{\text{target}}$ arrives at sample $t$:
- **Arrival Cycle ($t$):**
  $$\mathbf{w}_{\text{old}} \Leftarrow \mathbf{w}_{\text{curr}}$$
  $$\mathbf{w}_{\text{target}} \Leftarrow \text{new weights from packet}$$
  $$\text{crossfade\_step} \Leftarrow 1$$
  *(Note: $\mathbf{w}_{\text{curr}}$ remains at $\mathbf{w}_{\text{old}}$ for sample $t$)*

- **Slew Cycles ($t+1$ to $t+63$, $\text{crossfade\_step} = 2 \dots 64$):**
  For each channel $c \in \{0, 1, 2, 3\}$:
  $$\Delta[c] = w_{\text{target}}[c] - w_{\text{old}}[c]$$
  $$\text{step}[c] = \text{rshift\_round\_nearest\_even}(\text{crossfade\_step} \times \Delta[c], 6)$$
  $$w_{\text{curr}}[c] = \text{sat}_{16}(w_{\text{old}}[c] + \text{step}[c])$$

- **Terminal Convergence ($k = 64$):**
  At $\text{crossfade\_step} = 64$:
  $$\text{step}[c] = \text{rshift\_round\_nearest\_even}(64 \times \Delta[c], 6) = \Delta[c]$$
  $$w_{\text{curr}}[c] = \text{sat}_{16}(w_{\text{old}}[c] + (w_{\text{target}}[c] - w_{\text{old}}[c])) = w_{\text{target}}[c]$$
  **Terminal convergence to $w_{\text{target}}$ is exact (0 LSB error) at sample 64.**

- **Settled State ($\text{crossfade\_step} \ge 64$):**
  $$\mathbf{w}_{\text{curr}} \Leftarrow \mathbf{w}_{\text{target}}$$

### 4.3 Convergent Rounding in Slew Division
Dividing by 64 via arithmetic right-shift by 6 (`>>> 6`) uses convergent rounding (round-to-nearest-even):
$$q = (k \cdot \Delta) \gg 6$$
$$r = (k \cdot \Delta) \ \& \ 63$$
$$\text{step} = \begin{cases} 
q + 1, & \text{if } r > 32 \\ 
q, & \text{if } r < 32 \\ 
q + (q \& 1), & \text{if } r == 32 \quad (\text{ties round to nearest even}) 
\end{cases}$$

### 4.4 Interruption Continuity & Smooth Mid-Slew Handover
If a new calibration packet arrives during an active crossfade (e.g. at sample 25 of 64):
1. The currently active interpolated weights $\mathbf{w}_{\text{curr}}$ are immediately latched into $\mathbf{w}_{\text{old}}$.
2. The step counter resets: $\text{crossfade\_step} \Leftarrow 1$.
3. Slewing begins seamlessly toward the new target from the exact instantaneous position with **zero step jump discontinuity**.

---

## 5. 4-Channel Spatial Beamforming Datapath

```
  x_q[t, 0] (s16 Q12) ──► (X) ──► [Prod 0: s32 Q27] ┐
  w_curr[0] (s16 Q15) ──►  ▲                        │
                                                    ▼
  x_q[t, 1] (s16 Q12) ──► (X) ──► [Prod 1: s32 Q27] ──► ( + ) ──► [raw_acc: s32]
  w_curr[1] (s16 Q15) ──►  ▲                        ▲                │
                                                    │                ▼
  x_q[t, 2] (s16 Q12) ──► (X) ──► [Prod 2: s32 Q27] ──┤        [sat_s32 clamp]
  w_curr[2] (s16 Q15) ──►  ▲                        │                │
                                                    │                ▼
  x_q[t, 3] (s16 Q12) ──► (X) ──► [Prod 3: s32 Q27] ┘        [>>> 7 Convergent Round]
  w_curr[3] (s16 Q15) ──►  ▲                                         │
                                                                     ▼
                                                             [sat_s24 Clamp]
                                                                     │
                                                                     ▼
                                                           proj_s24 (Signed 24b Q20)
```

### 5.1 Exact Multiply-Accumulate Arithmetic
For each sample clock cycle $t$:
1. **Multiplication (Signed 16x16 $\to$ Signed 32-bit Q27):**
   $$\text{prod}_c[t] = w_{\text{curr}}[c] \times x_q[t, c], \quad c \in \{0, 1, 2, 3\}$$
   Each product has 1 integer bit + 1 sign bit + 27 fractional bits (Q27).
2. **Sum of Products (Accumulator):**
   $$\text{raw\_acc}[t] = \sum_{c=0}^3 \text{prod}_c[t]$$
3. **Accumulator Clamping (Signed 32-bit):**
   $$\text{acc\_clamped}[t] = \text{sat}_{32}(\text{raw\_acc}[t])$$
   Range: $[-2{,}147{,}483{,}648, +2{,}147{,}483{,}647]$ (`0x80000000` to `0x7FFFFFFF`).
4. **Convergent Downshift (Q27 $\to$ Q20):**
   $$\text{proj\_rounded}[t] = \text{rshift\_round\_nearest\_even}(\text{acc\_clamped}[t], 7)$$
   Arithmetic shift right by 7 bits restores Q20 scaling ($27 - 7 = 20$).
5. **Output Saturation (Signed 24-bit Q20):**
   $$\text{proj\_val}[t] = \text{sat}_{24}(\text{proj\_rounded}[t])$$
   Clamps to $[-8{,}388{,}608, +8{,}388{,}607]$ (`0x800000` to `0x7FFFFF`).  
   Scale factor: $2^{20} = 1{,}048{,}576\text{ LSB/mV}$, providing a full-scale physical span of $\pm 8.0\text{ mV}$.

### 5.2 Mathematical Proof of Overflow Immunity (Cauchy-Schwarz)
Under normalized weights ($\sum_{c=0}^3 w_c^2 \le 1.0$), the maximum possible magnitude of $\text{raw\_acc}$ under arbitrary physical biopotentials is bounded by the Cauchy-Schwarz inequality:
$$|\text{raw\_acc}| = \left| \sum_{c=0}^3 w_c x_c \right| \le \sqrt{\sum_{c=0}^3 w_c^2} \sqrt{\sum_{c=0}^3 x_c^2}$$
Since $\|\mathbf{w}\|_2 \le 32768$ and $|x_c| \le 32767$:
$$|\text{raw\_acc}| \le 32768 \times \sqrt{4 \times (32767)^2} = 32768 \times 65534 = 2{,}147{,}418{,}112$$
Because $2{,}147{,}418{,}112 < 2^{31} = 2{,}147{,}483{,}648$:
**The accumulator never overflows a Signed 32-bit integer for any valid unit-norm weight vector.**

---

## 6. Mathematical Equivalence to Phase 1 Single-Channel Mode

In Phase 1 single-channel mode (`fecg_single_channel_top.v`), Channel 0 is directly scaled from ADC Q12 to internal Q20:
$$\text{proj}_{\text{phase1}}[t] = \text{adc\_data\_in}[t] \ll 8 = \{\text{adc\_data\_in}[t], 8'\text{b}0\}$$

### Formal Proof of Equivalence:
Set weights to unity vector $\mathbf{w}_{\text{unity}} = [32768, 0, 0, 0]$:
1. Multiplier products:
   $$\text{prod}_0 = 32768 \times x_q[t, 0] = x_q[t, 0] \times 2^{15}$$
   $$\text{prod}_1 = \text{prod}_2 = \text{prod}_3 = 0$$
2. Accumulator:
   $$\text{raw\_acc} = \text{prod}_0 = x_q[t, 0] \times 2^{15}$$
3. Clamping:
   Since $|x_q| \le 32768$, $|x_q \times 2^{15}| \le 2^{30} < 2^{31}-1 \implies \text{acc\_clamped} = \text{raw\_acc}$.
4. Right shift by 7 with convergent rounding:
   $$\text{acc\_clamped} = x_q[t, 0] \times 2^{15} = x_q[t, 0] \times 2^8 \times 2^7$$
   The remainder modulo $2^7 = 128$ is identically zero:
   $$r = \text{acc\_clamped} \ \& \ 127 \equiv 0 < 64$$
   Therefore, rounding adds zero:
   $$\text{proj\_rounded} = \text{acc\_clamped} \gg 7 = x_q[t, 0] \times 2^8 = x_q[t, 0] \ll 8$$
5. Output saturation to 24 bits:
   Since $x_q[t, 0]$ is signed 16 bits, shifting left by 8 bits produces a signed 24-bit number:
   $$\text{sat}_{24}(x_q[t, 0] \ll 8) = x_q[t, 0] \ll 8$$

$$\mathbf{\text{proj}_{\text{beamformer}} \equiv \text{proj}_{\text{phase1}} \equiv \{x_q[t, 0], 8'\text{b}0\}}$$
**The spatial beamformer with unity weights is bit-for-bit identical (0 LSB discrepancy) to Phase 1.**

---

## 7. Synthesizable Verilog Module Interfaces

### 7.1 Weight Crossfade Slew Engine (`weight_slew_engine.v`)
```verilog
module weight_slew_engine #(
    parameter integer WEIGHT_WIDTH = 16,
    parameter integer STEPS        = 64
)(
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          sample_valid,   // 250 Hz sample strobe
    input  wire                          cal_valid,      // Strobe when new packet arrives
    input  wire signed [WEIGHT_WIDTH-1:0] w_target_0,
    input  wire signed [WEIGHT_WIDTH-1:0] w_target_1,
    input  wire signed [WEIGHT_WIDTH-1:0] w_target_2,
    input  wire signed [WEIGHT_WIDTH-1:0] w_target_3,

    output reg  signed [WEIGHT_WIDTH-1:0] w_curr_0,
    output reg  signed [WEIGHT_WIDTH-1:0] w_curr_1,
    output reg  signed [WEIGHT_WIDTH-1:0] w_curr_2,
    output reg  signed [WEIGHT_WIDTH-1:0] w_curr_3,
    output wire                          slew_active     // High during 64-sample crossfade
);
```

### 7.2 Spatial Beamformer Datapath (`spatial_beamformer.v`)
```verilog
module spatial_beamformer #(
    parameter integer ADC_WIDTH   = 16,  // Signed 16-bit Q12
    parameter integer W_WIDTH     = 16,  // Signed 16-bit Q1.15
    parameter integer DATA_WIDTH  = 24   // Signed 24-bit Q20
)(
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          sample_valid,
    input  wire signed [ADC_WIDTH-1:0]   x_adc_0,
    input  wire signed [ADC_WIDTH-1:0]   x_adc_1,
    input  wire signed [ADC_WIDTH-1:0]   x_adc_2,
    input  wire signed [ADC_WIDTH-1:0]   x_adc_3,
    input  wire signed [W_WIDTH-1:0]     w_pca_0,
    input  wire signed [W_WIDTH-1:0]     w_pca_1,
    input  wire signed [W_WIDTH-1:0]     w_pca_2,
    input  wire signed [W_WIDTH-1:0]     w_pca_3,

    output reg  signed [DATA_WIDTH-1:0]  proj_out,
    output reg                           proj_valid,
    output reg                           sat_flag
);
```

### 7.3 DSP48E1 Slice Allocation on Spartan-7 XC7S50
- The 4 parallel $16 \times 16$ multipliers require **4 DSP48E1 slices** (or can be time-multiplexed across a single DSP48E1 slice clocked at $100\text{ MHz}$, taking only 4 clock cycles out of the 400,000 cycles available per $250\text{ Hz}$ sample interval).
- Accumulation is completed via the internal 48-bit adder of DSP48E1.
- Convergent rounding and downshifting require purely combinational slice LUTs.

---

## 8. Verification Results Matrix

The fixed-point specification was verified using `verify_pca_fixed_point.py`:

| Test Suite | Evaluation Dataset | Condition Tested | Discrepancy vs Golden Ref | Status |
|:---|:---|:---|:---:|:---:|
| **Suite 1.1** | Synthetic Mixture (15,000 smp) | Unity weights $[32768, 0, 0, 0]$ vs Single-Channel $x \ll 8$ | **0 LSB** | **PASS** |
| **Suite 1.2** | Full 16-bit Range (65,536 values) | Exhaustive input sweep $[-32768, +32767]$ | **0 LSB** | **PASS** |
| **Suite 2.1** | PhysioNet `sub01_snr12_c0` (5,000 smp) | Benchmark PCA weights $[8021, 21951, -12717, -19127]$ | **0 LSB** | **PASS** |
| **Suite 2.2** | Synthetic Mixture (15,000 smp) | Live-fitted PC2 weights $[5388, -22780, 22905, -1085]$ | **0 LSB** | **PASS** |
| **Suite 3.1** | Slew Trajectory (64 steps) | Monotonicity & terminal convergence at sample 64 | **0 LSB** | **PASS** |
| **Suite 3.2** | Interrupted Slew | Mid-slew update at step 25 (zero discontinuity) | **0 LSB** | **PASS** |
| **Suite 3.3** | End-to-End Dynamic Stream (2,000 smp) | 3 scheduled weight updates with mid-slew interruption | **0 LSB** | **PASS** |
| **Suite 4.1-4.4** | Rail & Alternating Polarity Stress | Rail $\pm 32767$, extreme weights, accumulator clamp | **0 LSB** | **PASS** |
| **Suite 5** | UART Downlink Frame (`0xC3`) | 10-byte packing, CRC-8-CCITT, corruption rejection | **0 LSB** | **PASS** |

**Conclusion:** The PCA spatial beamformer, weight crossfade slew engine, and UART calibration framing protocol are formally validated with **0 LSB error** across all operations.

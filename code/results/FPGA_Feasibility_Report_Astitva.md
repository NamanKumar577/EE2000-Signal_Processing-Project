# Spartan-7 FPGA Feasibility & Hardware Roadmap for SWT–LMS–SSNF

**Author:** Astitva (EE2000 Signal Processing Project)  
**Target Architecture:** AMD / Xilinx Spartan-7 FPGA (e.g., XC7S25 / XC7S50, CSGA324)  
**Method Evaluated:** Stationary Wavelet Transform (SWT) + Least Mean Squares (LMS) + Spatial Subband Noise Filter (SSNF)

---

## 1. Executive Summary & Hardware Feasibility Verdict

The **SWT–LMS–SSNF** hybrid pipeline combines multi-resolution analysis with adaptive noise cancellation and non-linear inter-scale shrinkage. While the method provides a strong signal-to-noise theoretical foundation in floating-point software, its direct hardware port to an entry-level cost-optimized FPGA like the **Spartan-7** presents severe architectural challenges in terms of **DSP slice consumption** and **Block RAM (BRAM) storage**.

| Metric | Software Reference (Python/SciPy) | Proposed Spartan-7 FPGA Realization | Hardware Impact / Feasibility |
|---|---|---|---|
| **Sampling Rate ($f_s$)** | $250\text{ Hz}$ ($4\text{ ms}$ sample period) | $250\text{ Hz}$ input clock, $50\text{ MHz}$ core clock | Extreme slack ($200,000$ clock cycles per sample) |
| **Transform Type** | Stationary Wavelet Transform (SWT, undecimated) | Modified Decimated DWT or Circular-Buffer À Trous | SWT without decimation requires $O(N \cdot L)$ memory buffers |
| **Arithmetic Type** | 64-bit IEEE-754 Floating-Point | Fixed-Point: **Q1.15 (Data)**, **Q2.30 (Adaptive Weights)** | Fits DSP48E1 $25 \times 18$ multiplier slices |
| **Estimated DSP48E1 Slices** | N/A | **8 – 16 DSP slices** (time-multiplexed) | Moderate (XC7S25 has 80 DSP slices, ~15% utilization) |
| **Estimated BRAM36k Slices** | N/A | **6 – 12 BRAM blocks** | High for undecimated buffers, moderate for decimated |
| **Power Consumption** | CPU Workstation (~45W) | Spartan-7 Estimated Core Power: **< 120 mW** | Ideal for battery-powered wearable fetal monitors |

---

## 2. Computational Complexity & Operation Breakdown

At $f_s = 250\text{ Hz}$, each new ECG sample arrives every $4\text{ ms}$. Operating the Spartan-7 system clock at a modest $50\text{ MHz}$ provides:
$$\text{Clock cycles available per sample} = \frac{50 \times 10^6\text{ Hz}}{250\text{ Hz}} = 200,000\text{ cycles}$$

Because the throughput requirement is exceptionally low compared to the system clock frequency, **full parallel unrolling is unnecessary**. All FIR convolutions and LMS updates can be fully **time-multiplexed** onto a minimal set of shared **DSP48E1** execution units.

### 2.1 Operation Count per Sample ($L = 4$ Levels, Mother Wavelet: Sym4)

1. **Stationary Wavelet Decomposition (SWT / "À Trous" Algorithm):**
   - For Sym4, the filter length is $K = 8$ taps.
   - For level $j \in \{1, 2, 3, 4\}$, the filter taps are dilated with $2^{j-1}-1$ zeros between coefficients.
   - Number of non-zero multiplier-accumulator (MAC) operations per level:
     - Approximation filter $H(z)$: $8\text{ MACs}$
     - Detail filter $G(z)$: $8\text{ MACs}$
     - Total per level: $16\text{ MACs}$
   - Total for 4 decomposition levels: $4 \times 16 = \mathbf{64\text{ MACs/sample}}$ for the mixture, plus $64\text{ MACs/sample}$ for the reference signal ($128\text{ MACs/sample}$ total).

2. **LMS Adaptive Filtering Stage:**
   - Filter order $M = 32$ taps per subband.
   - Evaluated across detail subbands $cD_1 \dots cD_4$ and approximation $cA_4$ ($5$ subbands):
     - Filter output convolution: $y(n) = \sum_{k=0}^{M-1} w_k(n) x(n-k) \longrightarrow 32\text{ MACs}$
     - Error computation: $e(n) = d(n) - y(n) \longrightarrow 1\text{ subtract}$
     - Weight adaptation: $w_k(n+1) = w_k(n) + \mu \cdot e(n) \cdot x(n-k) \longrightarrow 32\text{ MACs}$
     - Total per subband: $64\text{ MACs}$
   - Total across 5 subbands: $5 \times 64 = \mathbf{320\text{ MACs/sample}}$.

3. **Spatial Subband Noise Filter (SSNF) & Inter-Scale Correlation:**
   - Inter-scale product: $P_j(n) = |w_j(n) \cdot w_{j-1}(n)| \longrightarrow 1\text{ Multiply + Absolute Value}$
   - Dynamic threshold comparison: soft-shrinkage requires magnitude subtraction and sign restoration:
     $$\hat{w}(n) = \text{sign}(w(n)) \cdot \max(|w(n)| - \lambda, 0)$$
   - Zero DSP multipliers required if thresholds are quantized to powers of two (arithmetic bit-shifts) or 4 time-shared multiplier cycles.

4. **Inverse Stationary Wavelet Transform (ISWT):**
   - Reconstruction synthesis filter banks: $4 \times 16 = \mathbf{64\text{ MACs/sample}}$.

### Total Computational Load:
$$\text{Total MACs per sample} = 128 + 320 + 4 + 64 = \mathbf{516\text{ MACs/sample}}$$
At $50\text{ MHz}$, a single DSP48E1 slice can execute all 516 operations in **$10.32\text{ }\mu\text{s}$**, which utilizes only **$0.26\%$** of the available $4\text{ ms}$ processing time budget!

---

## 3. Fixed-Point Word-Length & Precision Analysis

To eliminate floating-point arithmetic cores, all calculations are mapped to 2's complement fixed-point formats natively supported by Spartan-7 DSP48E1 slices ($25 \times 18$ multiplier pre-adder and 48-bit accumulator):

```
ECG Input Sample (Q1.15)  ──────►  [  DSP48E1  ]  ──────►  Accumulator (Q9.39)
Wavelet Coeffs   (Q1.15)  ──────►  [ Multiplier]  ──────►  Truncate / Round to Q1.15
LMS Weights      (Q2.30)  ──────►  [ 25 x 18   ]  ──────►  Weight Storage (32-bit BRAM)
```

### 3.1 Format Specifications
- **Input Mixture & Filter Coefficients ($Q1.15$):**
  - 16-bit signed fraction with 1 sign bit and 15 fractional bits (range $[-1.0, +0.9999]$).
  - Matches typical 12-bit / 16-bit medical ADC resolution.
  - Sym4 coefficients normalized such that $\sum h_k^2 = 1$.
- **LMS Weights ($Q2.30$):**
  - Requires high precision (32 bits) to avoid weight stalling ("gradient freezing").
  - If step size $\mu = 2^{-6} = 0.015625$, the update term $\mu \cdot e(n) \cdot x(n-k)$ can be implemented as a clean 6-bit arithmetic right-shift, avoiding a dedicated multiplier.
- **Accumulator Word Length (48-bit):**
  - Uses the full 48-bit internal register of the DSP48E1 slice, preventing overflow during 32-tap summations without intermediate rounding noise.

### 3.2 Stability & Finite Word-Length Hazards
1. **LMS Weight Drift & Bursting:** In single-channel mode, during periods of low maternal electrical activity (isoelectric intervals), the input autocorrelation matrix eigenvalues become small. Leaky LMS ($w_{k+1} = (1 - \gamma) w_k + \mu e x$) should be implemented on FPGA by injecting a slight attenuation bit $\gamma = 2^{-12}$ to guarantee long-term bounded weights.
2. **Limit Cycles:** Fixed-point truncation in IIR preprocessing filters can cause limit cycle oscillations. The team's choice of FIR for LMS and Wavelet ensures inherent linear-phase FIR stability (no feedback poles).

---

## 4. Memory & Buffering Architecture on Spartan-7

The primary hardware limitation of the **Stationary** Wavelet Transform on FPGA is that, unlike the discrete wavelet transform (DWT), **no decimation is performed**. 

### 4.1 BRAM Requirements for Dilated Filters (À Trous)
At level $j = 4$, the filter tap delay is $7 \times 2^{4-1} = 56$ samples. For delay-matching between branches and maintaining shift-invariance across all 4 levels:
- Each delay line must store incoming streaming samples in dual-port circular buffers inside Block RAM.
- Spartan-7 Block RAM tiles are 36 Kb each (configurable as two independent 18 Kb blocks).
- Required storage for state histories: $< 4,096$ words $\times$ 16 bits = **$64\text{ Kb}$** total RAM.
- **BRAM Utilization:** **2 to 4 BRAM36E1 tiles** (out of 45 available on XC7S25, ~6% utilization).

---

## 5. Architectural Comparison: SWT–LMS–SSNF vs. SVD vs. Template Subtraction

To assist the team in selecting the final algorithm for the Spartan-7 hardware deliverable (Milestone M7), the three team methods are compared below:

| Feature / Metric | Template Subtraction (Anshu) | SVD Extraction (Naman) | SWT–LMS–SSNF (Astitva) |
|---|---|---|---|
| **Mathematical Core** | Ensemble average subtraction | Eigen-decomposition ($U \Sigma V^T$) | Multi-rate FIR filter bank + LMS + Soft thresholding |
| **FPGA Logic Complexity** | **Very Low** (Accumulators, RAM buffer) | **Extreme** (Requires Jacobi/SVD systolic array or soft-core MicroBlaze) | **Low to Moderate** (Standard FIR MAC engine + state machine) |
| **Streaming / Causality** | Causal with 1-beat latency ($~0.8\text{ s}$) | High latency (needs matrix of 5–10 beats: 5–10 seconds buffer) | **Fully Streaming / Causal FIR** (sample-by-sample LMS update) |
| **DSP48E1 Utilization** | 1 – 2 DSP slices | 20 – 40 DSP slices | **4 – 8 DSP slices** |
| **BRAM Utilization** | 1 – 2 BRAM36 blocks | 8 – 16 BRAM36 blocks | 2 – 4 BRAM36 blocks |
| **Noise Robustness ($0\text{ dB}$ TC3)** | Struggles with deformed beats | High mathematical separation | Subband localization suppresses out-of-band noise |
| **Suitability for RTL Design** | Easiest to write in Verilog/VHDL | Difficult; requires HLS or matrix IP | **High; standard adaptive filter architecture** |

### Verdict for Team Hardware Implementation:
While Template Subtraction provides the simplest FPGA datapath and SVD provides strong matrix decomposition, **SWT–LMS–SSNF represents the optimal digital signal processing architecture for streaming real-time hardware**. Its structure consists exclusively of shift registers, FIR filter banks, and multiplier-accumulators, all of which map 1:1 onto Xilinx DSP48E1 slices without requiring matrix inversion or complex stateful solvers.

# Final Algorithm Specification (Pre-FPGA Frozen Baseline)

## 1. End-to-End Processing Architecture

The system pipeline operates across five synchronous processing stages:

```mermaid
flowchart TD
    subgraph Host_Calibration ["Stage 1: Host Calibration (Off-Chip)"]
        H1["10s 4-Ch Abdominal Window (2,500 samples @ 250 Hz)"] --> H2["Sample Covariance Matrix C = (1/N) X X^T"]
        H2 --> H3["SVD / Eigendecomposition -> 4 Principal Components"]
        H3 --> H4["Envelope Autocorrelation in Lag Window [83, 136] (110-180 bpm)"]
        H4 --> H5["Confidence Check: Margin >= 0.20, Peak >= 0.15"]
        H5 -->|Confident| H6["Quantize to Signed 16-bit Q1.15 -> Transmit 10-Byte Packet (0xC3)"]
        H5 -->|Uncertain| H7["Retain Previous Valid Weights w[n] = w[n-1]"]
    end

    subgraph FPGA_Spatial ["Stage 2: FPGA Spatial Beamformer (On-Chip)"]
        F0["4-Ch Signed 16-bit ADC (x27, x26, x28, x25)"] --> F1["Linear Cross-Fade Slew (64 samples = 256 ms)"]
        F1 --> F2["Dot Product: s[n] = sum(wi * xi) in Signed 32-bit (Q2.30)"]
        F2 --> F3["Shift >>> 7 with Convergent Rounding -> Sat to Signed 24-bit (Q1.23)"]
    end

    subgraph FPGA_Filtering ["Stage 3: FPGA Pre-Filter & Detector Bandpass"]
        F3 --> F4["Recursive 1st-Order HP1 Baseline Subtraction (Signed 32-bit Accumulator, k=6)"]
        F4 --> F5["LP40 Lowpass Filter (2 Biquads DF2T, 40 Hz, Signed 18-bit Q3.15 Coeffs, 48-bit States)"]
        F5 --> F6["Clean FECG Output (Signed 24-bit Q1.23)"]
        F6 --> F7["Config C Detector Bandpass (4 Biquads DF2T, 12-35 Hz, 8th Order, 48-bit States)"]
        F7 --> F8["Shift >>> 8 with Convergent Rounding -> Sat to Signed 16-bit (Q1.15)"]
    end

    subgraph FPGA_Detector ["Stage 4: FPGA Adaptive QRS Detector"]
        F8 --> F9["Squarer: sq[n] = bp16^2 (Unsigned 32-bit Product)"]
        F9 --> F10["Moving Window Integrator: W = 30 samples (120 ms, Unsigned 36-bit Ring Buffer)"]
        F10 --> F11["Adaptive Dual-Threshold Follower (EMA 1/8 Peak & Noise Tracking)"]
        F11 --> F12["Refractory Lockout Counter: 50 samples (200 ms = max 300 bpm)"]
        F12 --> F13["Trailing Local Peak Window: 26 samples (104 ms)"]
        F13 --> F14["Latency Compensation: Subtract 18 samples (Config C Group Delay @ 15 Hz)"]
    end

    subgraph FPGA_FHR ["Stage 5: FPGA FHR Post-Processor & Telemetry"]
        F14 --> F15["Interval Fusion: Merge Split Detections with RR < 50 samples into Single Event"]
        F15 --> F16["Causal Median-of-5 Buffer on Valid RR intervals [50, 300] samples (50 to 300 bpm)"]
        F16 --> F17["FHR ROM Lookup Table: 251 entries (0.1 bpm resolution: 500 to 3000)"]
        F17 --> F18["UART Telemetry Packet: 8 Bytes (Header 0xAA, 24-bit Time, 16-bit FHR, 8-bit Status, CRC8)"]
    end

    Host_Calibration --> FPGA_Spatial
```

---

## 2. Master Numerical Specification Table

| Stage | Parameter | Specification | Format | Hardware Resource |
| :--- | :--- | :--- | :--- | :--- |
| **System** | Sampling Rate ($f_s$) | $250\text{ Hz}$ ($T_s = 4.0\text{ ms}$) | Synchronous Strobe | System Clock Divider |
| **System** | FPGA Clock Frequency | $100.0\text{ MHz}$ ($10\text{ ns}$ cycle) | Internal Clock | Boolean Board On-board Osc |
| **I/O** | Input Channels | $4\text{ channels}$ (`[x27, x26, x28, x25]`) | Signed 16-bit (Q1.15) | ADC Interface / Serial Rx |
| **I/O** | Communication Baud | $921,600\text{ baud}$ (8-N-1) | Asynchronous Serial | FTDI USB-UART Bridge |
| **Calibration** | Duration | $4.0\text{ seconds}$ ($1,000\text{ samples}$) | Off-chip array | Host PC RAM / SVD |
| **Calibration** | Lag Search Window | $[83, 136]\text{ samples}$ ($110\text{--}180\text{ bpm}$) | Integer lag indices | Autocorrelation Engine |
| **Calibration** | Fallback Rule | Retain previous valid weights | Persistent Register | Host PC Calibration FSM |
| **Projection** | Transition Engine | $64\text{ samples}$ ($256\text{ ms}$) Linear Slew | Signed 16-bit weights | Logic Accumulator |
| **Projection** | Accumulator | $\sum_{i=0}^3 w_i x_i$ | Signed 32-bit (Q2.30) | 1x DSP48E1 Slice |
| **HP1** | High-Pass Filter | $y[n] = x[n] - \text{base}[n-1]$; $\text{base}[n] += y[n] \gg 6$ | Signed 32-bit Accumulator | Shift-Add Logic (0 DSPs) |
| **LP40** | Clean Low-Pass | 4th-order Butterworth ($40\text{ Hz}$ cutoff), 2 biquads | Signed 18-bit Q3.15, 48-bit states | 2x DSP48E1 Slices |
| **Bandpass**| Detector Bandpass | 8th-order Butterworth ($12\text{--}35\text{ Hz}$), 4 biquads | Signed 18-bit Q3.15, 48-bit states | 2x DSP48E1 Slices (multiplexed) |
| **Squarer** | Non-Linear Stage | $y[n] = (bp16)^2$ | Unsigned 32-bit (U0.30) | 1x DSP48E1 Slice |
| **MWI** | Moving Window Sum | $W = 30\text{ samples}$ ($120\text{ ms}$) | Unsigned 36-bit (U6.30) | Distributed RAM Ring Buffer |
| **Threshold**| Dual Peak Follower | $\text{thr} = \text{noise} + (\text{peak} - \text{noise}) \gg 2$ | Unsigned 36-bit registers | EMA Shift-Add Logic |
| **Refractory**| Lockout Period | $50\text{ samples}$ ($200\text{ ms} = 300\text{ bpm}$) | 6-bit down-counter | Logic Counter |
| **Search** | R-Peak Localizer | Trailing $26\text{ samples}$ ($104\text{ ms}$) | Comparator + Pointer | Circular Register File |
| **Latency** | Group Delay Comp | $-18\text{ samples}$ ($72\text{ ms}$) | Subtractor | Constant Logic |
| **Fusion** | Interval Fusion | Merge detections if $RR < 50\text{ samples}$ | Timestamp replacement | FSM Comparator |
| **Median5** | FHR Smoothing | 5-beat causal FIFO on valid $RR \in [50, 300]$ | Median of 5 elements | 5-register sorting network |
| **FHR LUT** | Instantaneous Rate | $FHR = 150,000 / RR$ for $RR \in [50, 300]$ | 251 words x 12-bit (0.1 bpm) | Block ROM ($256 \times 12$) |

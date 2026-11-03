# Stage-by-Stage QRS Timestamp Generation and Delay Analysis

## 1. Overview of the Causal Processing Pipeline

The real-time fetal ECG QRS detection pipeline operates strictly causally at a sampling rate of $f_s = 250\text{ Hz}$ ($T_s = 4.0\text{ ms}$). Every input biopotential sample passes through the following sequential stages:

```
[4-Channel Raw ECG] 
       │
       ▼
 1. Spatial Projection (Q1.15 weights)  ──> Delay: 0.0 samples (0.0 ms)
       │
       ▼
 2. HP1 Filter (1 Hz, 1st-order IIR)    ──> Delay: ~0.05 samples (0.2 ms)
       │
       ▼
 3. LP40 Filter (40 Hz, 2nd-order SOS)  ──> Delay: ~2.75 samples (11.0 ms)
       │ (Clean FECG Stream)
       ▼
 4. Detector Bandpass (12-35 Hz, 4th SOS) ─> Broadband Pulse Delay: ~9.2 samples (36.8 ms)
       │ (abs_bp signal)
       ▼
 5. Squaring & MWI (30-sample trailing) ──> Centroid Shift: +14.5 samples (58.0 ms)
       │ (x_int signal)
       ▼
 6. Local Max Declared (at t = m + 1)   ──> Declaration Lookahead: +1.0 sample (4.0 ms)
       │
       ▼
 7. Retrospective Search in abs_bp      ──> REWINDS past MWI & Declaration delays!
       │                                     Locks directly onto abs_bp peak!
       ▼
 8. Raw Timestamp (best_idx)            ──> Total Raw Peak Delay: ~12.1 samples (48.4 ms)
       │
       ▼
 9. Latency Rewind Subtractor (-12)     ──> Final Compensated Timestamp: True Peak +- 0 samples!
```

---

## 2. Sample-Index Step-by-Step Trace Example

To understand exactly how delays accumulate and where they are removed, let us trace an isolated fetal QRS complex whose **true anatomical peak occurs at sample $t^* = 1000$**:

### Stage 1: Spatial Beamforming
- **Operation:** Instantaneous linear combination of the 4 abdominal leads:
  $$y[t] = \sum_{c=0}^3 w_c x_c[t]$$
- **Sample $t = 1000$:** The beamformed sample $y[1000]$ immediately contains the maximum projected fetal R-peak amplitude.
- **Accumulated Delay:** **0.0 samples** ($0.0\text{ ms}$).

---

### Stage 2: High-Pass Preprocessing Filter (HP1)
- **Topology:** 1st-order causal IIR with baseline wander tracking:
  $$y[t] = x[t] - B[t-1], \quad B[t] = B[t-1] + 2^{-8}(x[t] - B[t-1])$$
- **Phase Delay:** At typical QRS frequencies ($20 \dots 35\text{ Hz}$), the phase response is virtually flat:
  $$\tau_{\text{HP1}} \approx 0.05\text{ samples} \quad (0.2\text{ ms})$$
- **Accumulated Delay:** **0.05 samples**.

---

### Stage 3: Low-Pass Preprocessing Filter (LP40)
- **Topology:** 2nd-order Butterworth IIR low-pass filter ($f_c = 40.0\text{ Hz}$).
- **Phase Delay:** Across $20 \dots 35\text{ Hz}$, the group delay is:
  $$\tau_{\text{LP40}} \approx 2.75\text{ samples} \quad (11.0\text{ ms})$$
- **Signal Position:** The output waveform `fecg` (clean FECG) reaches its local peak at:
  $$t_{\text{fecg\_peak}} \approx 1000 + 0.05 + 2.75 = \mathbf{1003}$$
- **Accumulated Delay:** **~3.0 samples** ($12.0\text{ ms}$).

---

### Stage 4: Detector Bandpass Filter (Config C: 12 to 35 Hz)
- **Topology:** 4th-order Butterworth cascade (two Direct Form II Transposed biquad sections).
- **Theoretical Group Delay vs Broadband Envelope Delay:**
  - A common misconception is that the group delay of an IIR filter evaluated at a single frequency (e.g. 15.0 Hz) equals the peak delay of a signal.
  - At 15.0 Hz (the lower roll-off transition edge), the filter group delay is steep: $\tau_{\text{BP}}(15\text{ Hz}) = 15.15\text{ samples}$ (Total = $17.92\text{ samples}$).
  - However, empirical spectral analysis of fetal QRS complexes in the PhysioNet dataset reveals that the **spectral centroid of the fetal QRS pulse is at $29.2\text{ Hz}$**, spanning $20\text{ Hz}$ to $35\text{ Hz}$.
  - In this midband passband, the bandpass group delay drops significantly:
    - At 20 Hz: 9.22 samples
    - At 25 Hz: 8.24 samples
    - At 30 Hz: 9.01 samples
    - At 35 Hz: 10.60 samples
  - For a broadband fetal QRS pulse, the effective envelope delay through the combined filter cascade (HP1 + LP40 + BP) is **12.1 samples** ($48.4\text{ ms}$).
- **Signal Position:** The rectified bandpass signal `abs_bp` ($|x_{\text{bp}}[t]|$) reaches its true peak at:
  $$t_{\text{abs\_bp\_peak}} \approx 1000 + 12.1 = \mathbf{1012}$$
- **Accumulated Delay:** **~12.1 samples** ($48.4\text{ ms}$).

---

### Stage 5: Squaring and Moving Window Integration (MWI)
- **Topology:** Trailing boxcar moving sum over $W = 30\text{ samples}$ ($120.0\text{ ms}$):
  $$x_{\text{int}}[t] = \sum_{k=0}^{29} x_{\text{bp}}[t - k]^2$$
- **Centroid Shift:** A trailing rectangular window of width $W = 30$ introduces an intrinsic phase centroid delay of:
  $$\tau_{\text{MWI}} = \frac{W - 1}{2} = \frac{30 - 1}{2} = \mathbf{14.5\text{ samples}} \quad (\mathbf{58.0\text{ ms}})$$
- **Signal Position:** The integrated energy waveform $x_{\text{int}}[t]$ reaches its maximum at:
  $$m_{\text{int\_peak}} \approx 1012 + 14.5 \approx \mathbf{1026 \text{ or } 1027}$$
- **Accumulated Delay in $x_{\text{int}}$:** **~26.6 samples** ($106.4\text{ ms}$).

---

### Stage 6: Local Maximum Declaration
- **Causal Rule:** To declare a local maximum in $x_{\text{int}}$ at sample $m$, the detector requires one sample of lookahead:
  $$x_{\text{int}}[m - 1] < x_{\text{int}}[m] \ge x_{\text{int}}[m + 1]$$
- **Declaration Sample:** This condition is evaluated and confirmed at sample:
  $$t_{\text{decl}} = m + 1 \approx 1026 + 1 = \mathbf{1027}$$
- **Total Declaration Latency:** The hardware processor discovers that a beat occurred at sample **1027**, which is $27\text{ samples}$ ($108.0\text{ ms}$) after the physiological R-peak entered the chest leads.

---

### Stage 7: Retrospective Local Peak Search (The Critical Decoupling)
- **The Architectural Mechanism:**
  Crucially, the algorithm **does NOT record $m = 1026$ or $t_{\text{decl}} = 1027$ as the beat timestamp!**
  Instead, when the threshold gate fires at $t = 1027$, the hardware executes a retrospective backward search in the rectified bandpass history `abs_bp` across a trailing window of `loc_window = 26` samples:
  $$\text{Search Window: } [t - 25, t] = [1027 - 25, 1027] = [\mathbf{1002}, \mathbf{1027}]$$
- **Finding the True R-Peak:**
  Inside $[\mathbf{1002}, \mathbf{1027}]$, the detector locates:
  $$\text{best\_idx} = \arg\max_{i \in [1002, 1027]} |x_{\text{bp}}[i]|$$
  Because the maximum of `abs_bp` occurred at sample $1012$, and $1012 \in [1002, 1027]$, the search engine locks directly onto:
  $$\mathbf{\text{best\_idx} = 1012 = \text{raw\_peak}}$$
- **Significance of Decoupling:**
  The retrospective search **completely unwinds and eliminates both the 14.5-sample MWI integration delay and the 1-sample declaration delay!**
  The reported `raw_peak` index is purely the position of the maximum in `abs_bp`.
  Therefore, the only remaining delay in `raw_peak` is the **~12.1 sample filter group delay of `abs_bp`**.

---

### Stage 8: Latency Compensation Subtractor
- **Correct Subtractor (12 Samples):**
  $$\text{Final Compensated Timestamp} = \max(0, \text{best\_idx} - 12) = 1012 - 12 = \mathbf{1000}$$
  The final reported timestamp aligns **identically with the true QRS peak at sample 1000**. Timing error = **0 samples** ($0.0\text{ ms}$).

- **Flawed Subtractor (18 Samples):**
  $$\text{Final Compensated Timestamp} = \max(0, \text{best\_idx} - 18) = 1012 - 18 = \mathbf{994}$$
  The final reported timestamp is **6 samples early** (-24.0 ms), severely misaligning the beat against clinical ground truth.

---

## 3. Summary of Delays and Compensations

| Pipeline Stage | Mathematical Delay | Compensated Internally? | Residual Delay at Declaration | Residual Delay After Subtractor (-12) |
|---|:---:|:---:|:---:|:---:|
| Spatial Projection | 0.0 samples | N/A | 0.0 samples | 0.0 samples |
| Preprocessing HP1 + LP40 | ~2.8 samples | No | ~2.8 samples | ~2.8 samples |
| Detector Bandpass (Config C) | ~9.2 samples | No | ~9.2 samples | ~9.2 samples |
| Moving Window Integration (MWI) | +14.5 samples | **YES (by Retrospective Search)** | **0.0 samples** | 0.0 samples |
| Local Max Declaration Lookahead | +1.0 sample | **YES (by Retrospective Search)** | **0.0 samples** | 0.0 samples |
| **Total Uncompensated Peak Delay** | **12.08 samples** | **Partial (MWI removed)** | **12.08 samples** | **+0.08 samples (+0.32 ms)** |

# Filter Latency and Empirical Group Delay Compensation Audit

## 1. Resolution of the 12.4 vs 18 Samples Contradiction

### 1.1 The Previous Conflict
- Earlier project documentation specified: **"Filter group delay: 12.4 +- 1.8 samples."**
- The Phase 2 reference model implemented: **"latency = 18 samples."**
- These conflicting claims caused confusion because an IIR filter has frequency-dependent group delay that cannot be described by a single scalar without qualification.

### 1.2 Mathematical & Architectural Root Cause
1. **Filter Topology Evolution:**
   - In the initial baseline system, the detector bandpass filter was **Config Default (8 to 30 Hz)**.
     At the typical fetal QRS center frequency of 15.0 Hz, the total group delay of HP1 + LP40 + BP_8-30 is:
     $$\text{Delay}_{\text{legacy}}(15\text{ Hz}) = 0.05 + 2.72 + 9.59 = \mathbf{12.36\text{ samples}} \quad (\mathbf{49.4\text{ ms}})$$
     This is the origin of the historical *"12.4 samples"* figure.
   - To optimize maternal QRS suppression, the final architecture transitioned to **Config C (12 to 35 Hz)**.
     Because the lower transition band shifted from 8 Hz to 12 Hz (closer to 15 Hz), the phase slope steepened significantly. At 15.0 Hz, the total group delay of HP1 + LP40 + BP_12-35 is:
     $$\text{Delay}_{\text{Config C}}(15\text{ Hz}) = 0.05 + 2.72 + 15.15 = \mathbf{17.92\text{ samples}} \approx \mathbf{18\text{ samples}} \quad (\mathbf{71.7\text{ ms}})$$

2. **Frequency Dependence:**
   From `FILTER_GROUP_DELAY.csv`:
   - At 12.0 Hz (band edge): 26.94 samples (107.8 ms).
   - At 15.0 Hz (QRS fundamental): **17.86 samples** (71.4 ms).
   - At 20.0 Hz (midband): 12.04 samples (48.1 ms).
   - At 25.0 Hz: 11.24 samples (45.0 ms).
   - At 35.0 Hz: 13.69 samples (54.8 ms).

---

## 2. Empirical Detector Timing Verification

From `QRS_TIMING_COMPENSATION_RESULTS.csv` (evaluated across 30 records and 19,288 reference beats):

| Compensation Scheme | Nominal Delay Subtracted | Mean Timing Bias (samples) | Mean Timing Bias (ms) | MAE Timing Error (samples) | Exact 0-Sample Match (%) | Match within +-2 Samples (%) | Detector F1 (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **No Compensation (Raw)** | 0 samples (0 ms) | +17.85 | +71.4 ms | 17.85 | 0.00% | 0.00% | 89.42% |
| **Legacy Baseline Filter**| 12 samples (48 ms) | +5.85 | +23.4 ms | 5.86 | 0.12% | 0.98% | 89.42% |
| **Config C Empirical Lock**| **18 samples (72 ms)**| **-0.15** | **-0.6 ms** | **0.78** | **71.84%** | **96.88%** | **89.42%** |

### Key Conclusions:
1. With **zero compensation**, detected peaks lag true reference R-peaks by exactly **+17.85 samples (+71.4 ms)**, in near-perfect agreement with the theoretical 17.86 sample group delay at 15 Hz.
2. With **12-sample compensation**, detections still lag by +5.85 samples (23.4 ms), achieving only 0.12% exact timing match.
3. With **18-sample compensation**, the mean timing bias drops to **-0.15 samples (-0.6 ms)**, and **96.88% of beats align within +-2 samples (+-8 ms)** of gold-standard annotations.
4. Therefore, the **18-sample subtractor is formally retained as the locked empirical latency compensation constant**.

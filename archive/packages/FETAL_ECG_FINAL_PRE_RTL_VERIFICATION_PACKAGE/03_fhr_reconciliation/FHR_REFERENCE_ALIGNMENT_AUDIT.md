# FHR Reference Time Alignment & Resampling Methodology Audit

## 1. Reference Signal Derivation
1. **Ground Truth Annotations:** Extracted from PhysioNet WFDB annotation files (`.qrs`).
2. **Instantaneous Reference Heart Rate:** For each consecutive pair of annotated beats $i$ and $i+1$:
   $$RR_{\text{ref}}[i] = t_{\text{ref}}[i+1] - t_{\text{ref}}[i] \quad (\text{samples @ } 250\text{ Hz})$$
   $$FHR_{\text{ref}}[i] = \frac{60 \times 250}{RR_{\text{ref}}[i]} = \frac{15,000}{RR_{\text{ref}}[i]} \quad (\text{bpm})$$
3. **Time Assignment:** The rate $FHR_{\text{ref}}[i]$ is timestamped at the terminating R-peak $t_{\text{ref}}[i+1] / 250\text{ seconds}$.

## 2. Estimated Signal Derivation
1. **Compensated Timestamps:** Each detected beat $t_R$ is latency-compensated by $-18\text{ samples}$ ($72.0\text{ ms}$).
2. **Physiological Validity Range:** $RR \in [50, 300]\text{ samples}$ ($50.0\text{ to }300.0\text{ bpm}$).
3. **Dropout Handling:** When $RR > 300\text{ samples}$ ($> 1.2\text{ s}$), the telemetry engine asserts `FLAG_HELD_FHR` (`10`) and retains the previously verified FHR.
4. **Causal Median-of-5:** Evaluated over the 5 most recent valid physiological intervals. Zero forward lookahead.

## 3. Uniform Temporal Grid Alignment
- Both reference and estimated FHR trajectories are resampled via linear interpolation onto a **common 2 Hz temporal grid** ($T_s = 0.5\text{ s}$, duration $= 300.0\text{ s}$, 600 points).
- **Warmup Masking:** The initial $2.5\text{ seconds}$ ($t < 2.5\text{ s}$, 5 grid points) is permanently masked out to allow filter settling.
- **Metric Definitions:**
  $$\text{MAE} = \frac{1}{N} \sum_{k=1}^N |FHR_{\text{est}}[k] - FHR_{\text{ref}}[k]|$$
  $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{k=1}^N (FHR_{\text{est}}[k] - FHR_{\text{ref}}[k])^2}$$
  $$\text{Concordance}_{\pm 5\text{bpm}} = \frac{1}{N} \sum_{k=1}^N \mathbb{I}(|FHR_{\text{est}}[k] - FHR_{\text{ref}}[k]| \le 5.0) \times 100\%$$

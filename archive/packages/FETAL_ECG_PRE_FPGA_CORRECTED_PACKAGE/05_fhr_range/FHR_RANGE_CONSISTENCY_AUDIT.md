# FHR & RR Operational Range Consistency Audit

## 1. Mathematical Analysis of the 250 Hz Discrepancy

At sampling frequency $f_s = 250\text{ Hz}$, the relationship between cardiac period $RR$ (in samples) and Heart Rate $FHR$ (in beats per minute) is:

$$RR = \frac{60 \times f_s}{FHR} = \frac{15,000}{FHR} \iff FHR = \frac{15,000}{RR}$$

### Mapping Across Physiological Extremes
| Cardiac State | FHR (bpm) | Period (ms) | $RR$ (samples @ $250\text{ Hz}$) | Previous Status | Corrected Status |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Severe Bradycardia** | $50.0\text{ bpm}$ | $1,200\text{ ms}$ | **$300\text{ samples}$** | Supported ($RR_{\max} = 300$) | **Supported** ($RR_{\max} = 300$) |
| **Baseline Normal** | $140.0\text{ bpm}$ | $428.6\text{ ms}$ | **$107\text{ samples}$** | Supported | **Supported** |
| **High Normal** | $180.0\text{ bpm}$ | $333.3\text{ ms}$ | **$83\text{ samples}$** | Supported | **Supported** |
| **Severe Tachycardia** | $250.0\text{ bpm}$ | $240.0\text{ ms}$ | **$60\text{ samples}$** | Cutoff ($RR_{\min} = 60$) | **Supported** |
| **Extreme Tachycardia** | $300.0\text{ bpm}$ | $200.0\text{ ms}$ | **$50\text{ samples}$** | **INCONSISTENT (Fused / Cut off!)** | **Supported** ($RR_{\min} = 50$) |

### The Previous Range Conflict
1. In the previous specification, `RR_MIN` was hardcoded to `60 samples` ($240\text{ ms} = 250\text{ bpm}$).
2. In the same document, the text claimed: *"Supports fetal tachycardia up to 300 bpm."*
3. Because $300\text{ bpm}$ corresponds to $50\text{ samples}$, setting `RR_MIN = 60` caused any rhythm between $250$ and $300\text{ bpm}$ to be caught by the interval fusion check (`raw_rr < 60`) and fused as a duplicate peak!
4. Furthermore, the refractory period was set to $50\text{ samples}$ ($200\text{ ms}$), meaning the raw detector was physically capable of firing at $300\text{ bpm}$, but the post-processing stage was discarding it!

---

## 2. Reconciled Range Specification

To guarantee mathematical consistency across all hardware modules, look-up tables, and documentation:
1. **Refractory Period:** Locked at **$50\text{ samples}$** ($200\text{ ms}$), allowing physical firing up to $300.0\text{ bpm}$.
2. **Valid RR Interval Range:** **$[50, 300]\text{ samples}$** ($50.0\text{ to }300.0\text{ bpm}$).
3. **Interval Fusion Threshold:** Set to **$RR < 50\text{ samples}$** ($< 200\text{ ms}$, i.e., $> 300\text{ bpm}$). Any pair of detections faster than $300\text{ bpm}$ is physically impossible for a fetal heart and is safely merged as a split QRS complex.
4. **FHR Hardware LUT:** Reconciled to **$251\text{ entries}$** covering $RR \in [50, 300]$:
   $$\text{LUT}[i] = \text{round}\left(\frac{150,000}{50 + i}\right) \quad \text{for } i \in [0, 250]$$
   Outputs FHR in units of $0.1\text{ bpm}$ ($500\text{ to }3,000$).

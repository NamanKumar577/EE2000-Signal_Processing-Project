# Spatial Calibration Metric Definitions & Criteria

## 1. Ground Truth Oracle Definition
The oracle component $j^* \in \{0, 1, 2, 3\}$ is defined as the spatial eigenvector that maximizes the physical Signal-to-Interference Ratio (SIR):

$$\text{SIR}_j = 10 \log_{10}\left(\frac{\sum_{n} (\mathbf{s}_{\text{fecg}}[n] \mathbf{w}_j)^2}{\sum_{n} (\mathbf{s}_{\text{mecg}}[n] \mathbf{w}_j)^2}\right) \quad \text{for } j=0, 1, 2, 3$$

$$j^* = \arg\max_j \text{SIR}_j$$

---

## 2. Seven Disentangled Calibration Metrics

In Phase 2, the metric `is_correct_selection` conflated exact oracle matching with fetal-dominant selection (`sirs[best_j] >= 0.0 or best_j == oracle_j`). This Phase 3 specification separates and locks seven distinct evaluation metrics:

### Metric 1: Exact Oracle Component Match
- **Definition:** `selected_j == oracle_j`.
- **Meaning:** Measures whether the label-free autocorrelation selector picked the single highest-SIR component out of the 4 candidates.
- **Observed Benchmark Rate:** **53.18%** overall (**66.67%** on held-out test).

### Metric 2: Fetal-Dominant Selection
- **Definition:** `selected_sir >= 0.0 dB`.
- **Meaning:** Measures whether the selected projection suppresses maternal QRS sufficiently for fetal power to equal or exceed maternal power ($	ext{SIR} \ge 0\text{ dB}$).
- **Clinical Relevance:** Any component with $\text{SIR} \ge 0\text{ dB}$ provides an extractable fetal signal.
- **Observed Benchmark Rate:** **93.65%** overall (**98.33%** on held-out test).

### Metric 3: Extraction Success (Downstream Utility)
- **Definition:** Downstream detector achieves $\text{Micro } F1 \ge 70.0\%$.
- **Meaning:** Measures whether the selected beamformer weights actually produce reliable clinical QRS detections.
- **Observed Benchmark Rate:** **81.6%** overall (**77.5%** on held-out test).

### Metric 4: Calibration Acceptance Rate
- **Definition:** Top autocorrelation score $R_1 \ge 0.15$ and confidence margin $\frac{R_1 - R_2}{R_1} \ge 0.20$.
- **Meaning:** Fraction of calibration windows where the selector asserts high confidence.
- **Observed Benchmark Rate:** **44.8%** across all records.

### Metric 5: Calibration Rejection Rate
- **Definition:** $1.0 - \text{Acceptance Rate}$ ($R_1 < 0.15$ or margin $< 0.20$).
- **Meaning:** The selector withheld new weights and asserted status flag `0x00: UNCERTAIN`.

### Metric 6: False Confidence Rate
- **Definition:** Selector asserted high confidence (`is_confident == True`), but the selected component had $\text{SIR} < 0.0\text{ dB}$.
- **Safety Criterion:** Must be $< 2.0\%$.
- **Observed Benchmark Rate:** **0.67%** (only 2 out of 299 records).

### Metric 7: Uncertain Selection Rate
- **Definition:** Margin $< 0.20$. Identifies borderline components where PC2 and PC3 have comparable energy.

# Final Calibration Window Specification and Tradeoff Analysis

## 1. Experimental Comparison: 4-Second vs 10-Second Calibration Window

An empirical evaluation was conducted across all 120 training and validation recordings (`sub01` through `sub08`, 3 SNRs, 5 physiological conditions) comparing a 4.0-second ($1,000\text{ samples}$) against a 10.0-second ($2,500\text{ samples}$) calibration window:

| Evaluation Metric | 4.0-Second Calibration ($1,000\text{ samples}$) | 10.0-Second Calibration ($2,500\text{ samples}$) | Engineering Tradeoff & Impact |
| :--- | :---: | :---: | :--- |
| **Fetal-Dominant Selection ($\text{SIR} \ge 0\text{ dB}$)** | **95.00%** (114 / 120) | **95.83%** (115 / 120) | Identical clinical capability ($\Delta = +0.83\%$) |
| **Exact Oracle Component Match** | **45.00%** (54 / 120) | **47.50%** (57 / 120) | Negligible difference ($\Delta = +2.50\%$) |
| **Mean Confidence Margin** | **0.2974** | **0.2542** | **4-second yields higher confidence separation** |
| **Host Ingestion Buffer RAM** | **8.0 KB** ($4 \times 1,000 \times 2\text{ B}$) | **20.0 KB** ($4 \times 2,500 \times 2\text{ B}$) | **60% reduction in memory footprint** |
| **Initial Acquisition Latency** | **4.0 seconds** ($+2.05\text{ s} = 6.05\text{ s}$) | **10.0 seconds** ($+2.05\text{ s} = 12.05\text{ s}$) | **6.0 seconds faster time-to-first-FHR** |
| **Covariance Compute Complexity** | $4 \times 1,000 = 4,000\text{ MACs}$ | $4 \times 2,500 = 10,000\text{ MACs}$ | **60% reduction in host CPU cycles** |

---

## 2. Frozen Architectural Decision

The system formally freezes **4.0 seconds ($1,000\text{ samples}$)** as the single authoritative calibration window length across all documents, configuration files, and software/hardware implementations:

1. **Clinical Latency:** 4.0 seconds provides clinical FHR output within **$6.05\text{ seconds}$** of sensor placement, complying with emergency intrapartum guidelines.
2. **Memory Efficiency:** Sizing the buffer to 1,000 samples requires only 8 KB of RAM, allowing direct buffering on microcontrollers or Spartan-7 distributed BRAM without external DDR memory.
3. **Statistical Stability:** At $250\text{ Hz}$, 1,000 samples captures 8 to 12 complete fetal cardiac cycles and 4 to 6 maternal cycles, providing ample statistical power for covariance matrix conditioning ($4 \times 4$).

# Phase 7: Clinical NIFEA Validation Report

**Document ID:** `validation/clinical/NIFEA_VALIDATION_REPORT.md`  
**Database:** Non-Invasive Fetal ECG Arrhythmia Database (NIFEA, 26 Records)  
**Artifacts Generated:**  
- `validation/clinical/NIFEA_DATASET_AUDIT.md`  
- `validation/clinical/NIFEA_RESULTS.csv`  

---

## 1. Executive Summary & Clinical Reality Check

Testing the 4-channel FPGA causal pipeline on real in-vivo clinical recordings from the NIFEA database reveals significant differences between synthetic simulation models (FECGSYNDB) and true clinical biopotentials:

| Evaluation Metric | Synthetic Dataset (FECGSYNDB) | Clinical Normal Cohort (NIFEA `NR`) | Clinical Arrhythmia Cohort (NIFEA `ARR`) |
| :--- | :---: | :---: | :---: |
| **Median Detected FHR** | **$143.0\text{ bpm}$** (Accurate) | **$131.2\text{ bpm}$** (Plausible) | **$157.9\text{ bpm}$** (Tachycardic bias) |
| **% Beats in Normal Window [110, 160] bpm** | **$88.1\%$** | **$6.6\%$** | **$5.9\%$** |
| **Maternal Thoracic Leakage Coincidence** | **$< 2.5\%$** | **$5.3\%$** | **$8.5\%$** |
| **Failure Rate (Zero Detections in PC3)** | **$0.0\%$** | **$42.8\%$** (6/14 records) | **$33.3\%$** (4/12 records) |

---

## 2. Root-Cause Analysis of Clinical Degradation

### 2.1 The Clinical Signal-to-Interference Disparity
- In synthetic models (FECGSYNDB), fetal ECG amplitude was simulated at $\sim 50\text{ to }100\ \mu\text{V}$ relative to maternal amplitude of $\sim 500\ \mu\text{V}$ (fetal-to-maternal ratio $\approx -14\text{ dB}$). Under these conditions, the covariance matrix consistently places the fetal dipole into Eigenvector 3 (`PC3`).
- In real clinical abdominal biopotentials (NIFEA), maternal ECG amplitude often exceeds $1.5\text{ to }3.0\text{ mV}$, while the fetal biopotential is frequently $< 10\ \mu\text{V}$ (fetal-to-maternal ratio $\approx -35\text{ to }-45\text{ dB}$).
- In 10 out of 26 NIFEA records, maternal biopotential energy spans all 3 primary spatial dimensions. As a result, static selection of `PC3` captures either maternal residue or baseline instrumentation noise, yielding 0 detections.

### 2.2 Electrode Montage Incompatibility
- FECGSYNDB uses a 32-channel grid with electrodes directly positioned on the gravid uterus (leads 25, 26, 27, 28 form a tight diamond over the fetal heart).
- NIFEA uses 5 arbitrary abdominal electrodes distributed across the entire maternal abdomen without standard spatial coordinates. Without standardized lead placement, a fixed channel subset `[1, 2, 3, 4]` does not guarantee spatial orthogonality.

---

## 3. Clinical Recommendations Before Hardware Trial

1. **Host-Side Dynamic Component Selection:** The FPGA must not be permanently hardwired to `PC3`. The host calibration engine must analyze all 4 principal components using periodicity scoring (`periodic_rr`) or envelope autocorrelation before assigning weights to FPGA register registers.
2. **Standardized Electrode Placement:** In clinical deployment, electrodes must be placed according to a strict anatomical protocol (e.g. supra-pubic, umbilical, left and right lower quadrant) rather than arbitrary placement.
3. **Maternal QRS Cancellation Pre-Stage:** For weak fetal biopotentials, incorporating an adaptive maternal template subtraction stage prior to beamforming provides $+15\text{ dB}$ additional maternal suppression.

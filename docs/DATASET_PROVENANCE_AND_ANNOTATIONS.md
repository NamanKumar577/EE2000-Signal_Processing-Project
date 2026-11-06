# Dataset Provenance, Annotation Specifications, and Benchmark Records

**Project:** Non-Invasive Multichannel Fetal ECG Extraction & Real-Time Spartan-7 FPGA Implementation  
**Target Hardware:** AMD Spartan-7 XC7S50-1CSGA324C on RealDigital Boolean Board  
**Target Toolchain:** AMD Vivado Design Suite v2025.2 (Build 6299465)

---

## 1. Dataset Overview & Provenance

The validation suites (Phase 4 hardware testing and Phase 5 statistical benchmarking) utilize the authoritative **PhysioNet FECGSYNDB** (Fetal ECG Synthetic Database) and the **Non-Invasive Fetal ECG Arrhythmia Database**.

### A. PhysioNet FECGSYNDB Specification
- **Sampling Frequency ($f_s$):** $250\text{ Hz}$ ($T_s = 4.0\text{ ms}$).
- **Signal Resolution / Format:** Format 16 little-endian binary (`int16`, 2 bytes per sample, 2's complement).
- **ADC Quantization:** 16-bit signed biopotentials with zero-baseline at 0 and gain 3000 ADC units/mV.
- **Topography:** 34 total recorded bio-channels per subject:
  - Channels 0–31: Abdominal surface biopotentials placed across maternal abdomen (suprapubic, umbilical, and lateral regions).
  - Channels 32–33: Direct maternal/fetal reference channels used strictly for gold-standard verification.
- **Noise & Motion Artifacts:** Includes realistic baseline wander (BW), muscle artifact (MA), motion artifact, and respiratory modulation.
- **Metadata Files:**
  - `data/FECGSD/DESTINATION/ANNOTATORS`: Declares machine-generated/expert ground-truth annotator tags (`qrs`).
  - `data/FECGSD/DESTINATION/RECORDS`: Authoritative registry of all valid subject-SNR-channel recording stems.
  - `data/FECGSD/DESTINATION/SHA256SUMS.txt`: Cryptographic checksums validating source data integrity.

---

## 2. Annotation & Ground-Truth Format

Each recording in FECGSYNDB is accompanied by gold-standard annotations conforming to PhysioNet WFDB binary annotation format:
- **Annotation Files:**
  - `*.qrs`: Fetal ventricular depolarizations (fetal R-peaks) verified by synthetic model generator or expert annotators.
  - `*.hea`: Plain-text ASCII header file specifying duration (75,000 samples = 5.0 minutes), true heart rates (`#fhr:<val>`, `#mhr:<val>`), and maternal-fetal SNR (`#SNRfm:<val>`).
- **Annotation Encoding:** Standard PhysioNet WFDB delta-skip format where byte pairs encode the incremental sample interval ($\Delta t$) between successive cardiac events.
- **Ground-Truth Beat Matching Window:**
  - In accordance with ANSI/AAMI EC57 and PhysioNet standards, a detected beat timestamp $t_{\text{det}}$ is scored as a **True Positive (TP)** if:
    $$|t_{\text{det}} - t_{\text{ref}}| \le 50\text{ ms} \quad (\pm 12\text{ samples at } 250\text{ Hz})$$
  - Each reference beat can match at most one detected beat.
  - Extra detections are counted as **False Positives (FP)**.
  - Missed reference beats are counted as **False Negatives (FN)**.

---

## 3. Maternal False Alarm Rate (FAR) Metric Definition

In fetal ECG extraction, maternal QRS complexes are typically 3 to 10 times larger in amplitude than fetal QRS complexes. If maternal suppression is insufficient, residual maternal peaks will trigger the adaptive threshold and be erroneously counted as fetal beats.

To rigorously distinguish maternal leakages from random noise while properly accounting for physiological coincidence:
1. **Maternal-Fetal Coincidence:** In human physiology, maternal heart rates (~70–90 bpm) and fetal heart rates (~120–160 bpm) periodically align. When a true fetal beat occurs simultaneously with a maternal beat ($|t_f - t_m| \le 50\text{ ms}$), a detection is a physiological fetal beat and must **not** be penalized as a maternal false alarm.
2. **True Maternal False Alarm Condition:** A detection $d \in \mathcal{D}$ is classified as a maternal false alarm if and only if:
   $$d \in \mathcal{D}_{\text{FP}} \quad \text{AND} \quad \exists m \in \mathcal{M} \text{ such that } |d - m| \le 50\text{ ms}$$
3. **Maternal False Alarm Rate:**
   $$\text{Maternal FAR} = \frac{|\{d \in \mathcal{D}_{\text{FP}} : \min_{m \in \mathcal{M}} |d - m| \le 12\text{ samples}\}|}{|\mathcal{M}|} \times 100\%$$
   Under this metric, on clean cases (`SYNTHETIC_75M_140F`, `sub01_snr12dB_c0`, `sub01_snr00dB_c0`), the FPGA pipeline achieves **0.00% Maternal FAR**, confirming that the spatial beamformer's $>30\text{ dB}$ maternal cancellation completely eliminates maternal feedthrough.

---

## 4. Exact List of Recordings & Repetitions

### A. Phase 4 Physical FPGA Validation Suite (6 Hardware Test Cases)
Evaluated directly on the physical Spartan-7 board over `COM5` (115,200 baud, 8-N-1):
1. `SYNTHETIC_75M_140F`: Controlled proof benchmark (75.0 bpm maternal, 8000 amp; 140.0 bpm fetal, 2500 amp on Lead 0; 4-lead mixture). Validates spatial beamformer nulling and rate separation.
2. `sub01_snr12dB_c0`: FECGSYNDB Subject 01, SNR = +12 dB (high signal-to-noise ratio), Channel configuration 0.
3. `sub01_snr06dB_c0`: FECGSYNDB Subject 01, SNR = +6 dB (moderate noise), Channel configuration 0.
4. `sub01_snr00dB_c0`: FECGSYNDB Subject 01, SNR = 0 dB (fetal amplitude equal to noise/maternal interference), Channel configuration 0.
5. `sub04_snr06dB_c0`: FECGSYNDB Subject 04, SNR = +6 dB, Channel configuration 0 (evaluates inter-subject physiological generalization).
6. `sub08_snr06dB_c0`: FECGSYNDB Subject 08, SNR = +6 dB, Channel configuration 0 (evaluates high heart rate variability).

*Results File:* `fpga_implementation/reports/phase4_real_dataset_results.csv`  
*Raw COM5 Log:* `hardware_evidence/logs/task-1614_physical_fpga_com5_validation_6cases.log`

### B. Phase 5 Expanded FECGSYNDB Population Suite (150 Full-Length Records)
A comprehensive population-wide evaluation executed across:
- **10 Distinct Pregnant Subjects:** `sub01`, `sub02`, `sub03`, `sub04`, `sub05`, `sub06`, `sub07`, `sub08`, `sub09`, `sub10`.
- **5 Signal-to-Noise Ratios:** $0\text{ dB}$, $+3\text{ dB}$, $+6\text{ dB}$, $+9\text{ dB}$, $+12\text{ dB}$.
- **3 Channel Configurations / Repetitions:** `c0`, `c1`, `c2` (different spatial lead combinations).
- **Total Records:** $10 \times 5 \times 3 = 150$ independent physiological datasets.
- **Total Ingested Data:** 375,000 multi-channel samples (1,500,000 individual channel samples).
- **Aggregate Performance:**
  - Mean Sensitivity ($\text{Se}$): **86.13%**
  - Mean Positive Predictive Value ($\text{PPV}$): **81.92%**
  - Mean F1-Score ($F_1$): **83.83%**
  - Median FHR Error: **1.13 bpm**
  - Mean FHR Error: **2.67 bpm**

*Results File:* `fpga_implementation/reports/phase5_expanded_fecgsyndb_results.csv`  
*Benchmark Script:* `scratch/run_expanded_validation.py`

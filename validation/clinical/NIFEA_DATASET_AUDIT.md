# Phase 7: NIFEA Clinical Database Audit

**Document ID:** `validation/clinical/NIFEA_DATASET_AUDIT.md`  
**Database Name:** Non-Invasive Fetal ECG Arrhythmia Database (NIFEA)  
**Location:** `data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION/`  
**Audit Date:** October 2026  

---

## 1. Database Overview & Structure

The NIFEA database contains in-vivo multichannel physiological biopotential recordings acquired from pregnant subjects admitted for suspected fetal cardiac arrhythmias or routine monitoring:

| Category | Record Count | Record Identifiers | Clinical Classification |
| :--- | :---: | :--- | :--- |
| **Arrhythmia Cohort** | 12 | `ARR_01` to `ARR_12` | Fetal arrhythmias, extrasystoles, heart block, or brady/tachycardia. |
| **Normal Cohort** | 14 | `NR_01` to `NR_14` | Normal singleton pregnancies without known cardiac pathology. |
| **Total Records** | **26** | Complete set audited | In-vivo clinical biopotentials |

---

## 2. Technical Characteristics & Audit Findings

### 2.1 Sampling Rates & Anti-Aliasing Decimation Requirements
- **1000 Hz Sampling Frequency (22 Records):** `ARR_01`–`ARR_05`, `ARR_10`–`ARR_12`, and all 14 `NR_01`–`NR_14` records.
  - *Decimation Requirement:* Downsampling by integer factor $M = 4$ to match target FPGA system clock sampling ($250\text{ Hz}$).
  - *Filter:* 8th-order Chebyshev Type I lowpass filter with cutoff at $0.8 \times \frac{f_s}{2 \times 4} = 100\text{ Hz}$ to prevent high-frequency aliasing.
- **500 Hz Sampling Frequency (4 Records):** `ARR_06`, `ARR_07`, `ARR_08`, `ARR_09`.
  - *Decimation Requirement:* Downsampling by integer factor $M = 2$ using anti-aliasing decimation.
- **AUDIT WARNING:** Never feed raw 1000 Hz or 500 Hz biopotential streams directly into digital filters synthesized for 250 Hz operation; doing so would compress filter cutoffs by $4\times$ (shifting $8\text{--}30\text{ Hz}$ bandpass to $32\text{--}120\text{ Hz}$).

### 2.2 Channel Ordering and Lead Montages
- Each record contains 5 to 6 channels:
  - `Channel 0 (`ECG`)`: Maternal thoracic reference lead (placed on maternal chest).
  - `Channels 1–5 (`Abdomen_1` through `Abdomen_5`)`: 4 to 5 abdominal biopotential electrodes placed over maternal abdomen.
- For our 4-channel FPGA beamformer pipeline, we map `[Abdomen_1, Abdomen_2, Abdomen_3, Abdomen_4]` (Channels 1, 2, 3, 4).

### 2.3 Reference Annotation Availability
- **CRITICAL AUDIT FINDING:** The NIFEA dataset directory contains **zero ground truth fetal R-peak annotations** (`.qrs` or `.atr` files are absent).
- Only maternal thoracic biopotentials are available as an objective reference.
- Consequently, clinical evaluation must rely on surrogate statistical markers:
  1. Percentage of detections in the physiological fetal window ($110\text{--}160\text{ bpm}$).
  2. RR interval regularity and coefficient of variation ($\text{CV} = \sigma_{RR} / \mu_{RR}$).
  3. Maternal QRS coincidence leakage ratio (fetal detections synchronous with thoracic MECG peaks).

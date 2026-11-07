# Master Dataset Validation & Evidence Synthesis

**Directory:** `validation/complete_dataset_validation_20261106/`  
**Date:** November 6, 2026  
**Hardware Target:** AMD Spartan-7 XC7S50-1CSGA324C on RealDigital Boolean Board  
**Bitstream:** `fpga_implementation/bitstream/fecg_multichannel_top.bit`  
**Bitstream SHA-256:** `503abc132ee4614f8868f2aca74cca0b0a396f90607d6356f17ae537f753023f`  

---

## 1. Multi-Tier Evidence Matrix

To establish scientific rigor, this project classifies all experimental results across four distinct verification tiers:

| Tier | Domain / Environment | Target Code / Mechanism | Tested Scope | Strengths | Limitations |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | **Software Floating-Point** | `src/causal_pipeline.py` / `scipy` | 1,493 FECGSYNDB cases; preliminary NIFEA sweeps | High-level algorithmic reference; rapid exploration of PCA rules. | Uses 64-bit float math; does not model fixed-point quantization, overflow saturation, or latency. |
| **Tier 2** | **Bit-Accurate Python Model** | `src/fecg/hardware/bit_accurate_reference.py` | **1,493 FECGSYNDB cases**; **all 26 NIFEA cases** | Emulates exact 18-bit biquad DF2T math, 48-bit states, 36-bit squaring, 50-sample refractory, and integer LUT. | Runs on CPU host; does not verify physical clock timing, UART framing, or silicon pinout. |
| **Tier 3** | **RTL Behavioral Simulation** | AMD Vivado 2025.2 `xsim` (`tb_fecg_single_channel_top.v`) | 1 synthetic benchmark + 4 FECGSYNDB cases | Compiles true synthesizable Verilog; verifies cycle-exact clocking, reset logic, and register pipelines. | Simulation speed is ~500x slower than real time; impractical for full 1,500-case database runs. |
| **Tier 4** | **Physical FPGA Silicon** | Spartan-7 XC7S50 via FTDI UART on `COM5` (115,200 baud) | 6 Phase 4 cases (15,000 samples) + 5 NIFEA cases (12,500 samples) | **Actual hardware execution on physical board.** Verifies timing closure (25 MHz), UART buffering, and true live operation. | Throughput is paced by 115,200 baud UART (4 ms/sample); full multi-hour datasets must be streamed in batches. |

---

## 2. Answers to Specific User Questions

### Question 1: How much of FECGSYNDB has actually been tested?
- **Full Specification Grid:** 10 subjects $\times$ 5 SNRs $\times$ 5 layouts $\times$ 6 conditions = **1,500 combinations**.
- **Historical Benchmark (Phase 5):** Evaluated **150 recordings (10.0%)** (Layout `l1` only, conditions `c0`, `c1`, `c2`).
- **Complete Audit & Evaluation (Today):** Evaluated **1,493 recordings (99.53%)** using the frozen bit-accurate RTL reference pipeline ([`run_bit_accurate_pipeline_final`](file:///D:/signal_project/src/fecg/hardware/bit_accurate_reference.py)).
- **Definitive Single-Fetus Performance (1,244 eligible records):**
  - **Mean F1 Score:** **79.41%** (Sensitivity: 80.92%, PPV: 78.77%)
  - **Maternal Suppression:** **25.64 dB**
  - **FHR Mean Absolute Error:** **29.79 bpm**
  - **Layout Invariance:** Mean F1 varies by only $\pm 0.7\text{ pp}$ across all 5 layouts ($78.93\%\text{ in }l3\text{ to }80.29\%\text{ in }l5$).

### Question 2: How many NIFEA recordings were successfully processed?
- **Total Database Size:** 26 in-vivo clinical recordings (14 Normal, 12 Arrhythmia).
- **Unique Recordings:** **24 unique recordings** (discovered that `NR_13` is an exact binary duplicate of `ARR_02`, and `NR_14` is an exact duplicate of `NR_07`).
- **Successfully Processed:** **15 out of 26 recordings ($57.7\%$)** yielded successful fetal ECG extraction and physiological fetal heart rate tracking (Median FHR: 120.0 to 185.2 bpm; Maternal Leakage: 3.4% to 36.6%).
- **Normal Cohort Success:** 8 of 14 records ($57.1\%$).
- **Arrhythmia Cohort Success:** 7 of 12 records ($58.3\%$).

### Question 3: How many were physically tested on FPGA?
- **NIFEA Physical Tests:** **5 representative clinical recordings** (`NR_01`, `NR_02`, `ARR_02`, `ARR_06`, `ARR_10`) were streamed through the physical Spartan-7 FPGA on `COM5` at 250 Hz (12,500 samples total).
- **FECGSYNDB Physical Tests:** **6 test cases** (1 synthetic + 5 FECGSYNDB cases, 15,000 samples total) were physically revalidated in Phase 4.
- **Total Physical FPGA Hardware Execution:** **11 recordings / 27,500 samples**, achieving **0 LSB error** and **100.00% exact bit match** under continuous state alignment.

### Question 4: What failed or was incompatible?
1. **FECGSYNDB Excluded Files (7 records):**
   - 3 records missing binary `.dat` files on disk (`sub09_snr00dB_l4_c5`, `l5_c0`, `l5_c1`).
   - 4 records with IEEE NaNs in `noise1.dat` due to upstream simulation EHG generator overflow (`sub03_snr12dB_l2_c3`, `sub04_snr03dB_l2_c3`, `sub07_snr12dB_l5_c3`, `sub08_snr03dB_l4_c3`).
2. **FECGSYNDB Twin Pregnancy (`c5`, 250 records):**
   - Incompatible with the single rank-1 spatial projection and single refractory counter. Classified as **ARCHITECTURALLY UNSUPPORTED**.
3. **NIFEA Sub-threshold Warmup Rejections (7 records):**
   - Records `ARR_01`, `ARR_11`, `NR_03`, `NR_05`, `NR_06`, `NR_09`, `NR_10` produced 0 beat detections because weak fetal biopotentials ($< 5\ \mu\text{V}$) were lower than the ambient noise floor, causing the warmup threshold detector to stay disabled.
4. **NIFEA Powerline Noise Outliers (4 records):**
   - Records `ARR_06`, `ARR_07`, `ARR_10`, `NR_04` had high outlier counts ($>50\%$) due to unmitigated European 50 Hz AC mains interference.

### Question 5: What can be quantitatively evaluated?
- **FECGSYNDB:** Bit-level F1 score, sensitivity, PPV, maternal false detection count, maternal suppression in dB, and FHR MAE can be quantitatively evaluated with high precision because synchronized ground-truth fetal R-peak annotations (`.qrs`) and pure component files (`_fecg1`, `_mecg`, `_noise1`, `_noise2`) are available.
- **NIFEA:** Only objective surrogate markers can be quantitatively evaluated:
  - Maternal heart rate (derived from Channel 0 thoracic ECG).
  - Maternal leakage coincidence (% of detected beats falling within $\pm 25$ ms of a maternal thoracic R-peak).
  - Percentage of beats within physiological ($110\text{--}160\text{ bpm}$) and plausible ($100\text{--}180\text{ bpm}$) windows.
  - RR interval coefficient of variation ($\text{CV}$).

### Question 6: What remains unverified?
- **Clinical Diagnostic Accuracy on In-Vivo Data:** Because NIFEA lacks simultaneous fetal scalp electrode (FSE) ground truth, fetal beat sensitivity and false discovery rates cannot be formally proven on clinical patients. Physiological plausibility does not constitute clinical validation.
- **Clinical Readiness:** The system is **NOT clinically ready** for hospital deployment until three front-end upgrades are integrated:
  1. A front-end $50\text{ Hz} / 60\text{ Hz}$ notch pre-filter.
  2. Dynamic analog front-end channel selection (to choose the optimal 4 leads from an 8-lead abdominal array).
  3. Maternal QRS template subtraction pre-filtering to handle patients where maternal ECG amplitude exceeds fetal amplitude by $>40\text{ dB}$.

---

## 3. Inventory of Generated Deliverables

All deliverables have been saved into `validation/complete_dataset_validation_20261106/`:

```
validation/complete_dataset_validation_20261106/
├── FECGSYNDB_COVERAGE_MATRIX.csv         (1,500-row itemized coverage matrix with F1, Sens, PPV, Suppr)
├── FECGSYNDB_COVERAGE_AUDIT.md           (Forensic report on FECGSYNDB coverage and layout invariance)
├── NIFEA_DATASET_INVENTORY.csv           (Detailed inventory of all 26 clinical NIFEA records)
├── NIFEA_VALIDATION_RESULTS.csv          (Clinical validation metrics across all 26 NIFEA records)
├── NIFEA_VALIDATION_REPORT.md            (Clinical report separating normal and arrhythmia cohorts)
├── FPGA_HARDWARE_VALIDATION_SUMMARY.md   (Spartan-7 FPGA hardware streaming results on COM5)
├── NIFEA_FPGA_PHYSICAL_RESULTS.csv       (0 LSB error and packet metrics on physical hardware)
├── MASTER_DATASET_VALIDATION_SUMMARY.md  (This master synthesis report)
├── scripts/
│   ├── run_complete_fecgsyndb_evaluation.py (Full 1,500-record execution script)
│   ├── run_nifea_validation.py              (Complete NIFEA processing script)
│   └── run_nifea_fpga_stream.py             (Physical Spartan-7 FPGA streaming script)
├── logs/
│   ├── fecgsyndb_evaluation.log          (Console log from 1,493-case FECGSYNDB run)
│   ├── nifea_validation.log              (Console log from 26-case NIFEA run)
│   └── nifea_fpga_physical_stream.log    (Console log from COM5 hardware streaming)
├── waveforms/
│   ├── nifea/                            (26 per-record CSV waveform exports, 2500 samples each)
│   └── fpga_hardware/                    (5 physical FPGA captured waveform CSVs, 2500 samples each)
└── plots/
    └── nifea/                            (8 diagnostic 4-panel clinical PNG figures)
```

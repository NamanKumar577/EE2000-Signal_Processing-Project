# Comprehensive Repository and Pipeline Audit

**Document ID:** `validation/audit/PROJECT_AUDIT.md`  
**Git Branch:** `fpga-causal-pipeline`  
**Commit Baseline:** `582fc21`  
**Evaluation Date:** October 2026  
**Deliverable:** Phase 0 Deliverable  

---

## 1. Repository Inventory and Directory Structure

The project repository (`d:\signal_project`) is organized into dedicated functional modules:

```
d:\signal_project/
├── CLAUDE.md                   # Operational guidelines (surgical changes, testing)
├── FPGA_SPEC.md                # Target hardware specification (Spartan-7 XC7S50, Boolean Board)
├── DATASHEETS_AND_HARDWARE_SPECS.md # Detailed hardware & biopotential reference
├── code/
│   ├── config.yaml             # Global system hyperparameters
│   ├── requirements.txt        # Python dependency manifest
│   ├── src/
│   │   ├── __init__.py
│   │   ├── causal_pipeline.py  # Causal, sample-by-sample floating-point reference pipeline
│   │   ├── fpga_int_model.py   # Pure-integer fixed-point golden simulator (bit-accurate to RTL)
│   │   ├── pca_extractor.py    # Non-causal/batch PCA, ICA, FastICA, and SVD decomposition
│   │   ├── preprocessing.py    # Zero-phase batch filtering (FiltFilt, Wavelet denoising)
│   │   ├── qrs_detector.py     # Batch Pan-Tompkins QRS detector (non-causal)
│   │   ├── evaluation.py       # Metrics: TP, FP, FN, PPV, Se, F1, RMSE, FHR MAE
│   │   ├── run_benchmark.py    # 35-case benchmark runner (frozen legacy baseline)
│   │   └── run_causal_benchmark.py # Causal pipeline benchmark across subjects/SNRs
│   ├── tests/
│   │   ├── test_causal_pipeline.py  # 26 unit tests for causal filters, MWI, detector
│   │   ├── test_evaluation.py       # 17 unit tests for metric computations
│   │   ├── test_fixed_point.py      # 15 unit tests for integer models & LUTs
│   │   ├── test_fpga_spec.py        # 16 unit tests for hardware specification alignment
│   │   ├── test_pca.py              # 25 unit tests for decomposition & component selection
│   │   ├── test_preprocessing.py    # 17 unit tests for filtering routines
│   │   └── test_qrs.py              # 24 unit tests for peak matching & detection
│   └── results/
│       ├── metrics.csv              # Frozen baseline results (35 recordings)
│       └── mega_benchmark_results.csv # 250-record batch results
├── data/
│   ├── FECGSD/DESTINATION/          # 1,750 synthetic FECGSYNDB simulation records
│   └── Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION/ # 26 clinical records
├── rtl/                        # Hardware description files (Verilog)
│   ├── fpga_top.v              # Top-level integration module
│   ├── beamformer.v            # 4-channel dot-product MAC engine
│   ├── biquad_sos.v            # Direct Form II Transposed IIR biquad
│   ├── mwi.v                   # Moving window integrator ring buffer
│   ├── qrs_engine.v            # Peak detector & dual-threshold FSM
│   └── uart_tx_rx.v            # 921,600 baud streaming interface
├── tools/
│   ├── audit_mtr8.py           # Integrity auditor (15/15 checks pass)
│   └── validation/             # Validation campaign execution scripts
└── validation/                 # Mega-validation outputs and deliverables
```

---

## 2. Module-by-Module Technical Audit

### 2.1 Dataset Ingestion & Preprocessing
- **`code/src/preprocessing.py`**:
  - Implements zero-phase 4th-order Butterworth bandpass filtering ($0.5\text{--}40\text{ Hz}$) via `scipy.signal.filtfilt`.
  - **Audit Finding:** Non-causal! Requires entire signal in memory and performs forward-backward filtering. Deliberately preserved for reproducing legacy results, but incompatible with real-time FPGA deployment.
- **`code/src/causal_pipeline.py`**:
  - Replaces `filtfilt` with a 2-stage causal filter:
    1. HP1: 1st-order recursive high-pass ($f_c \approx 0.62\text{ Hz}$) implemented with bit-shifts (`k=6`).
    2. LP40: 4th-order low-pass ($40\text{ Hz}$) using Direct Form II Transposed Second-Order Sections (`sosfilt`).
  - **Audit Finding:** Fully causal and hardware-synthesizable. Group delay is constant across passband ($\approx 5.8\text{ samples}$).

### 2.2 Extraction & Component Selection
- **`code/src/pca_extractor.py`**:
  - Computes spatial covariance matrix $\mathbf{R}_{xx}$ across 4 channels and applies `np.linalg.eigh`.
  - Supports multiple heuristics:
    - `oracle`: Peeks at ground-truth annotations to find the PC that maximizes fetal F1. **Must never be used in autonomous production!**
    - `autocorr`: Evaluates autocorrelation peaks in the range $[60, 150]\text{ samples}$ ($100\text{--}250\text{ bpm}$).
    - `periodic_rr`: Computes candidate R-peaks across all components and scores inter-peak regularity.
    - `pc3`: Static selection of the 3rd eigenvector.
  - **Audit Finding:** The `pc3` rule achieves $90.90\%$ F1 without peeking at ground truth on `sub01`, because maternal ECG consistently spans eigenvectors 1 and 2, while sensor noise is concentrated in eigenvector 4.

### 2.3 Fixed-Point Representation (`code/src/fpga_int_model.py`)
- Employs bit-accurate integer mathematics matching Spartan-7 DSP48E1 primitives:
  - Input biopotentials: 16-bit signed $\mathbb{Q}_{1.15}$.
  - Weights: 16-bit signed $\mathbb{Q}_{1.15}$.
  - Projection: 24-bit signed $\mathbb{Q}_{1.23}$.
  - SOS filter coefficients: 18-bit signed $\mathbb{Q}_{3.15}$ to accommodate $b_1 \approx 2.0$.
  - MWI accumulator: 36-bit unsigned ($u36$).
  - FHR computation: 241-entry LUT ROM avoiding runtime division.
- **Audit Finding:** 100% compliant with hardware constraints.

### 2.4 Existing Test Suite Status
- Total unit tests executed: **140 tests**.
- Tests passed: **140 (100%)**.
- Tests failed: **0**.
- Code coverage: Covers causal filters, integer quantization, overflow saturation, MWI ring buffers, QRS detection FSM, and evaluation metrics.

---

## 3. Discrepancy Findings Summary

1. **Condition Codes in FECGSYNDB:** The documentation interchangeably referenced 5 or 6 conditions. Our dataset inventory confirms there are **6 distinct conditions** (`c0` baseline, `c1` motion, `c2` dynamic FHR, `c3` contractions, `c4` ectopic beats, `c5` twins).
2. **Twins Handling in `c5`:** `c5` recordings have two distinct ground-truth annotation files: `_fecg1.hea` / `_fecg1.atr` and `_fecg2.hea` / `_fecg2.atr`. Evaluation must grade detection against each twin independently without fusing beat streams.
3. **Beamformer Weight Generation:** FPGA RTL does not implement online SVD. A host or microcontroller must calibrate $\mathbf{w}$ from an initial data window and transmit it to FPGA registers via UART.

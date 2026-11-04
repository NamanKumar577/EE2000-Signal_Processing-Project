# Python Source Code Audit Report

**Project:** Multichannel Fetal ECG Extraction & Spartan-7 FPGA Implementation (EE2000 Paper ID: 0008)  
**Date:** 2026-11-03  
**Auditor:** Teamwork Source Code Audit Coordinator  
**Target Scope:** `code/src/` (24 files + subdirectories), package source trees (`FETAL_ECG_*/11_source_code/`), duplicate analysis, and dependency graph.

---

## 1. Executive Summary

The active source code directory for the project is located at `code/src/`. It contains 24 top-level Python modules, an algorithm suite in `code/src/methods/`, deep learning architectures in `code/src/models/`, and execution benchmarks.

In commit `b8c2ebc` (2026-11-03), several historical variants and package artifacts were copied into `code/src/` alongside the original codebase and recent causal FPGA additions (`commit 582fc21`). This created multiple co-existing versions of critical modules (e.g., three versions of `bit_accurate_reference_model*.py`, two versions of `uart_protocol*.py`, and two versions of `fhr*.py`).

This audit establishes the definitive classification of all Python source modules into **ACTIVE (Authoritative)**, **HISTORICAL / SUPERSEDED**, and **DUPLICATE** implementations.

---

## 2. Inventory of Source Modules in `code/src/`

| File | Status | Authoritative Variant | Key Responsibilities & Role |
| :--- | :--- | :--- | :--- |
| `causal_pipeline.py` | **ACTIVE** | **Canonical (v0.2)** | Causal, streaming sample-by-sample float reference pipeline (0.5–40 Hz SOS bandpass, 4-lead PCA beamforming, Pan-Tompkins peak detector, label-free component selection). Identical across all 3 verification packages (MD5: `475af842`). |
| `fpga_int_model.py` | **ACTIVE** | **Canonical (v0.2)** | Bit-true integer-only golden model of Spartan-7 hardware datapath. Emulates fixed-point arithmetic, saturation, shift-rounding, and dumps intermediate per-stage hex test vectors for RTL testbenches (MD5: `2e0446d9`). |
| `bit_accurate_reference_model_final.py` | **ACTIVE** | **Canonical (v3)** | Final pre-RTL verified bit-accurate fixed-point reference model matching `FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE`. Incorporates full filter delay compensation and strict bit-width scaling (MD5: `b1f116fb`). |
| `bit_accurate_reference_model_corrected.py` | **SUPERSEDED** | Package v2 | Corrected intermediate fixed-point reference model from `FETAL_ECG_PRE_FPGA_CORRECTED_PACKAGE` (MD5: `4af8d228`). Replaced by `_final.py`. |
| `bit_accurate_reference_model.py` | **HISTORICAL** | Package v1 | Initial fixed-point reference model from `FETAL_ECG_PRE_FPGA_VALIDATION_PACKAGE` (MD5: `d2ef0ca5`). Pre-correction baseline. |
| `fixed_point_model.py` | **HISTORICAL** | Mid-Term Baseline | Initial fixed-point emulation model created during Phase 3 for mid-term report milestone. |
| `svd_fixed_point_model.py` | **HISTORICAL** | SVD Specific | Fixed-point model specifically developed for Naman's SVD extraction hardware sizing. |
| `uart_protocol_final.py` | **ACTIVE** | **Canonical (v3)** | Authoritative UART telemetry and packet framing implementation (@ 921,600 baud, 8-N-1). Matches `FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/07_uart/UART_PACKET_IMPLEMENTATION_FINAL.py` (MD5: `a5d33182`). |
| `uart_protocol.py` | **SUPERSEDED** | Package v2 | Intermediate UART protocol implementation from `FETAL_ECG_PRE_FPGA_CORRECTED_PACKAGE` (MD5: `f733eaab`). |
| `fhr_implementation_corrected.py` | **ACTIVE** | **Canonical (v2/v3)** | Corrected FHR processing with interval fusion, ectopic rejection (5-beat causal median), and physiological bounds (50–240 bpm) (MD5: `9ccf801a`). |
| `fhr.py` | **HISTORICAL** | Mid-Term Baseline | Baseline FHR estimation module developed for mid-term milestone. Contains uncorrected edge-case handling superseded by `fhr_implementation_corrected.py`. |
| `qrs_detector.py` | **ACTIVE** | **Canonical** | Standardized Pan-Tompkins inspired QRS detector (5-point derivative, squaring, moving window integrator $W=15$, dual adaptive EMA thresholds SPKI/NPKI, 200 ms blanking). |
| `preprocessing.py` | **ACTIVE** | **Canonical** | 4-section Butterworth SOS IIR bandpass filter (0.5–40 Hz), notch filter, baseline wander removal. |
| `mixture.py` | **ACTIVE** | **Canonical** | FECGSYNDB synthetic abdomen mixture loader, realistic SNR mixing, fetal-maternal ratio (FMR) topography. |
| `data_loader.py` | **ACTIVE** | **Canonical** | PhysioNet WFDB format loader, subject-disjoint cross-validation split (Train: sub01–07, Val: sub08, Test: sub09–10). |
| `evaluation.py` | **ACTIVE** | **Canonical** | PhysioNet CinC 2013 compliance metrics: $\pm 50$ ms bipartite matching, Se, PPV, F1-Score, FHR MAE, RMSE. |
| `multichannel_study.py` | **ACTIVE** | **Canonical** | 34-channel topographic FMR spatial analysis, optimal 4-lead suprapubic sub-array selector ($\mathcal{C}_{\text{opt}} = \{27, 26, 28, 25\}$). |
| `train_deep_model.py` | **ACTIVE** | Deep Learning | GPU training pipeline for 1D U-Net fetal ECG extraction on held-out subject splits. |
| `run_causal_benchmark.py` | **ACTIVE** | Benchmark | Full 250-record sweep of the causal FPGA pipeline across calibration windows and component selection rules. |
| `run_benchmark.py` | **ACTIVE** | Benchmark | Comparative benchmark suite evaluating traditional extraction methods across SNR levels. |
| `run_mega_benchmark.py` | **ACTIVE** | Benchmark | Large-scale validation harness running across all subjects and noise conditions. |

---

## 3. Extraction Algorithms in `code/src/methods/`

All traditional extraction algorithms inherit from `BaseExtractor` in `code/src/methods/base.py`:

1. **`methods/svd.py` (Naman — Lead Architect):**
   - Implements SVD extraction variants (Variant 1: Raw SVD on Hankel matrix; Variant 2: Fast Truncated SVD; Variant 3: Deflation SVD). Active and fully verified.
2. **`methods/template_subtraction.py` (Anshu Ram):**
   - Implements maternal QRS template subtraction using running median and exponential moving average (EMA) templates.
3. **`methods/swt_lms_ssnf.py` (Astitva):**
   - Implements Stationary Wavelet Transform (SWT) multi-resolution decomposition coupled with Least Mean Squares (LMS) adaptive noise cancellation and Spectral Subtraction (SSNF).
4. **`methods/alternative.py` (Vivek):**
   - Implements Wavelet-Thresholding hybrid and SVD-Template combination for complex collision cases.

---

## 4. Deep Learning Architectures in `code/src/models/`

- **`models/fecg_unet.py`:**
  - 1D Convolutional U-Net architecture with skip connections for deep fetal biopotential denoising and direct end-to-end extraction.
  - Active implementation designed for PyTorch GPU acceleration.

---

## 5. Duplicate and Evolution Analysis

### A. Fixed-Point Reference Models (3 Variants)
- `bit_accurate_reference_model.py` (v1, MD5: `d2ef0ca5`): Initial package version; contains minor group delay discrepancy.
- `bit_accurate_reference_model_corrected.py` (v2, MD5: `4af8d228`): Corrected QRS timing compensation and scaling.
- `bit_accurate_reference_model_final.py` (v3, MD5: `b1f116fb`): **Authoritative**. Final pre-RTL sign-off version matching package v3. Full equivalence to `fpga_int_model.py`.
- **Decision:** Retain `bit_accurate_reference_model_final.py` as primary active reference; archive v1 and v2 into `archive/historical_reference_models/`.

### B. UART Telemetry Protocols (2 Variants)
- `uart_protocol.py` (v2, MD5: `f733eaab`): 8-byte status packet framing.
- `uart_protocol_final.py` (v3, MD5: `a5d33182`): **Authoritative**. Complete specification with calibration window update packet, error status byte, and 921,600 baud timing.
- **Decision:** Retain `uart_protocol_final.py` as active; archive v2 into `archive/historical_protocols/`.

### C. FHR Post-Processing (2 Variants)
- `fhr.py` (v1): Original baseline module with basic median filter.
- `fhr_implementation_corrected.py` (v2/v3): **Authoritative**. Includes interval fusion, 50–240 bpm boundary clamp, and 5-beat causal median filter.
- **Decision:** Promote `fhr_implementation_corrected.py` to canonical `fhr.py` in the proposed `src/` hierarchy, preserving the original in `archive/`.

---

## 6. Dependencies and Runtime Requirements

- **Numerical & Scientific:** `numpy >= 1.22.0`, `scipy >= 1.9.0` (signal SOS filtering, eigendecomposition)
- **Biomedical Signal I/O:** `wfdb >= 4.1.0` (PhysioNet format reading, annotation parsing)
- **Deep Learning (Optional):** `torch >= 2.0.0` (for `models/fecg_unet.py` and `train_deep_model.py`)
- **Data & Visualization:** `pandas >= 1.5.0`, `matplotlib >= 3.6.0`
- **Standard Library Only:** `causal_pipeline.py`, `fpga_int_model.py`, `uart_protocol_final.py` rely strictly on `math`, `struct`, `dataclasses`, and `typing`, ensuring zero-dependency hardware synthesis and C/RTL translation.

---

## 7. Proposed Source Code Organization

We propose reorganizing `code/src/` into a modular package under `src/fecg/`:

```text
src/
└── fecg/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   ├── preprocessing.py          # Butterworth SOS bandpass filter
    │   ├── mixture.py                # Synthetic mixture and noise generation
    │   ├── data_loader.py            # WFDB record parsing
    │   └── evaluation.py             # CinC 2013 evaluation metrics
    ├── pipelines/
    │   ├── __init__.py
    │   ├── causal_pipeline.py        # Active streaming float reference pipeline
    │   └── multichannel_study.py     # 34-channel spatial array study
    ├── detection/
    │   ├── __init__.py
    │   ├── qrs_detector.py           # Pan-Tompkins peak detector
    │   └── fhr.py                    # Consolidated corrected FHR engine
    ├── methods/                      # Traditional signal separation methods
    │   ├── __init__.py
    │   ├── base.py                   # BaseExtractor abstract class
    │   ├── svd.py                    # SVD Variants 1, 2, 3 (Naman)
    │   ├── template_subtraction.py   # Maternal template subtraction (Anshu)
    │   ├── swt_lms_ssnf.py           # Wavelet LMS SSNF (Astitva)
    │   └── alternative.py            # Wavelet-SVD hybrid (Vivek)
    ├── models/                       # Deep learning models
    │   ├── __init__.py
    │   └── fecg_unet.py              # 1D Conv U-Net
    ├── hardware/                     # Bit-accurate and FPGA golden models
    │   ├── __init__.py
    │   ├── fpga_int_model.py         # Integer golden model with hex vector dumps
    │   └── bit_accurate_reference.py # Canonical pre-RTL reference model (from final.py)
    └── telemetry/
        ├── __init__.py
        └── uart_protocol.py          # 921,600 baud UART protocol (from final.py)
```

Scripts for running benchmarks (`run_causal_benchmark.py`, `run_benchmark.py`, `run_mega_benchmark.py`, `train_deep_model.py`) should be relocated to a top-level `scripts/` directory.

---
*Report compiled autonomously by Teamwork Source Code Auditor.*

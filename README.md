# Non-Invasive Fetal ECG Extraction & FPGA Hardware Implementation

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-ee4c2c.svg)](https://pytorch.org/)
[![Target Hardware](https://img.shields.io/badge/FPGA-Xilinx%20Spartan--7%20%7C%20Artix--7-red.svg)](https://www.xilinx.com/products/silicon-devices/fpga/spartan-7.html)
[![Tests](https://img.shields.io/badge/Tests-204%20passed%20%7C%203%20skipped-brightgreen.svg)](#running-tests)
[![Course](https://img.shields.io/badge/EE2000-Signal%20Processing%20Project-green.svg)](#)

---

## Executive Summary

This repository hosts the complete algorithmic research, multi-channel spatial beamforming pipelines, deep learning models, bit-accurate fixed-point software models, and FPGA hardware architectural sizing for the **EE2000 Signal Processing Course Project (Paper ID: 0008)** by **Team 8**.

The primary objective is the extraction of the weak **Fetal Electrocardiogram (FECG)** (20–100 µV) from composite maternal **Abdominal Electrocardiogram (AECG)** mixtures (1.0–5.0 mV, 20–34 dB peak disparity) and the continuous estimation of **Fetal Heart Rate (FHR)**, followed by edge deployment on low-cost, low-power **AMD / Xilinx Spartan-7 (XC7S50)** FPGAs.

### Team 8 Members

| Member | Primary Architecture | Key Modules |
| :--- | :--- | :--- |
| **Naman** | SVD Extraction Suite (V1, V2, V3) | `src/fecg/methods/svd.py`, `scripts/benchmarks/` |
| **Vivek** | Wavelet-Threshold Hybrid & SVD-Template | `src/fecg/methods/alternative.py`, `src/fecg/core/evaluation.py` |
| **Anshu Ram** | Maternal Template Subtraction | `src/fecg/detection/qrs_detector.py`, `src/fecg/pipelines/multichannel_study.py` |
| **Astitva** | SWT + LMS + SSNF Wavelet Hybrid | `src/fecg/methods/swt_lms_ssnf.py`, `src/fecg/core/preprocessing.py` |

---

## Repository Structure

```text
├── src/fecg/                  # Active Python package (authoritative source code)
│   ├── core/                  #   Preprocessing, data loading, evaluation, mixture
│   ├── pipelines/             #   Causal streaming FPGA pipeline, multichannel study
│   ├── detection/             #   Pan-Tompkins QRS detector, corrected FHR estimation
│   ├── methods/               #   Extraction algorithms (SVD, Template, SWT-LMS, Hybrid)
│   ├── models/                #   Deep learning (1D Conv U-Net)
│   ├── hardware/              #   FPGA integer golden model, bit-accurate reference
│   └── telemetry/             #   921,600 baud UART protocol implementation
│
├── tests/                     # Unified test suite (207 tests: 204 pass, 3 skip)
│   ├── unit/                  #   Core unit tests
│   ├── integration/           #   Pipeline, end-to-end, timing tests
│   ├── hardware/              #   Bit-accurate, fixed-point, integer model tests
│   └── regression/            #   Pre-FPGA regression suite
│
├── scripts/benchmarks/        # Benchmark and training execution scripts
├── scripts/validation/        # Verification audit runners
├── data/fecgsyndb/            # PhysioNet FECGSYNDB recordings (test1–test5)
├── results/                   # Benchmark CSVs, figures, and validation reports
├── hardware/spec/             # Spartan-7 FPGA specifications and datasheets
├── docs/                      # Architecture decisions, literature, trackers, audits
├── report/                    # IEEE CVF mid-term conference submission
├── tools/                     # Development and maintenance utilities
├── archive/                   # Historical packages, superseded code, logs
├── code/                      # Legacy source tree (preserved for compatibility)
│
├── CLAUDE.md                  # LLM engineering guidelines
├── requirements.txt           # Python dependencies
└── .gitignore                 # Git ignore patterns
```

---

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd EE2000-Signal_Processing-Project

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Running Tests

```bash
# Run all 207 tests (unit, integration, hardware, regression)
.venv/bin/pytest tests

# Run specific test categories
.venv/bin/pytest tests/unit           # Core unit tests
.venv/bin/pytest tests/integration    # Pipeline and end-to-end tests
.venv/bin/pytest tests/hardware       # Bit-accurate and fixed-point verification
.venv/bin/pytest tests/regression     # Pre-FPGA regression suite

# Run legacy test suite (backward compatible)
PYTHONPATH=code .venv/bin/pytest code/tests
```

---

## Running Benchmarks

```bash
# Causal FPGA pipeline benchmark sweep
.venv/bin/python scripts/benchmarks/run_causal_benchmark.py --help

# Traditional extraction method comparison
.venv/bin/python scripts/benchmarks/run_benchmark.py --help

# Full population mega-benchmark (requires full FECGSYNDB dataset)
.venv/bin/python scripts/benchmarks/run_mega_benchmark.py --help
```

---

## Datasets

The `data/fecgsyndb/` directory contains 5 PhysioNet FECGSYNDB recordings (97.4 MB) in standard WFDB format (`.hea`, `.dat`, `.qrs` files) at 250 Hz with 34 channels each. The full 250-record dataset (2.55 GB) can be obtained from [PhysioNet FECGSYNDB](https://physionet.org/content/fecgsyndb/).

---

## FPGA Hardware Documentation

- **Frozen Architecture Spec (v0.2):** [`hardware/spec/FPGA_SPEC.md`](hardware/spec/FPGA_SPEC.md)
- **Hardware Datasheets & Constraints:** [`hardware/spec/DATASHEETS_AND_HARDWARE_SPECS.md`](hardware/spec/DATASHEETS_AND_HARDWARE_SPECS.md)
- **Synthesis Feasibility Report:** [`hardware/spec/MASTER_FPGA_IMPLEMENTATION_AND_FEASIBILITY_REPORT.md`](hardware/spec/MASTER_FPGA_IMPLEMENTATION_AND_FEASIBILITY_REPORT.md)

---

## Mid-Term Submission

- **Canonical Report (PDF):** [`report/mtr-8.pdf`](report/mtr-8.pdf)
- **Submission Archive (ZIP):** [`report/mtr-8.zip`](report/mtr-8.zip)

---

## Repository Audit & Restructuring

See [`docs/REPOSITORY_INVENTORY.md`](docs/REPOSITORY_INVENTORY.md) and [`docs/PROPOSED_STRUCTURE.md`](docs/PROPOSED_STRUCTURE.md) for the complete repository audit and migration blueprint. Detailed per-domain audits are in `docs/audit/`.

# FECG Extraction & FPGA Verification — Codebase

This directory contains the complete Python implementation, benchmark test runners, fixed-point emulation models, and deep learning architectures for the **EE2000 Fetal ECG Signal Processing Project**.

For complete project documentation, system architecture, FPGA synthesis reports, and benchmark analysis, please see the [**Root README.md**](file:///d:/signal_project/README.md).

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Benchmarks
```bash
# Run all extraction algorithms across TC1 to TC5
python src/run_benchmark.py --tc all --method all

# Run Vivek's hybrid method on TC1
python src/run_benchmark.py --tc TC1 --method alternative

# Run multi-channel scaling study (1 to 34 leads)
python src/multichannel_study.py

# Run cross-subject mega benchmark (250 runs)
python src/run_mega_benchmark.py
```

### 3. Run Bit-Accurate Fixed-Point Emulation
```bash
# Generate 16-bit golden test vectors for Vivado RTL testbenches
python src/fixed_point_model.py

# Run fixed-point SVD power iteration model
python src/svd_fixed_point_model.py
```

### 4. Run Unit Tests
```bash
pytest tests/ -v
```

---

## Directory Overview

- [`configs/`](file:///d:/signal_project/code/configs): Preprocessing filter parameters (`preprocessing.yaml`) and test-case registry (`tests.yaml`).
- [`src/`](file:///d:/signal_project/code/src): Core algorithms, mixture builder, QRS detector, FHR analysis, evaluation routines, and fixed-point models.
- [`src/methods/`](file:///d:/signal_project/code/src/methods): Individual extraction modules (`alternative.py`, `template_subtraction.py`, `svd.py`, `swt_lms_ssnf.py`).
- [`src/models/`](file:///d:/signal_project/code/src/models): Deep 1D Convolutional U-Net model (`fecg_unet.py`).
- [`results/`](file:///d:/signal_project/code/results): Benchmark metrics (`metrics.csv`, `mega_benchmark_summary.csv`, `multichannel_scaling_metrics.csv`), diagnostic plots, and golden test vectors.
- [`tests/`](file:///d:/signal_project/code/tests): Pytest automated unit test suite.

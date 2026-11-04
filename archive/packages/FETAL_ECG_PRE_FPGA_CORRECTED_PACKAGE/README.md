# Fetal ECG Pre-FPGA Corrected & Reconciled Engineering Package

Target Device: AMD/Xilinx Spartan-7 XC7S50-1CSGA324C (RealDigital Boolean Board)

This archive contains the independently verified, reconciled, and corrected engineering deliverables,
numerical specifications, bit-accurate reference models, and regression test suites.

## How to Run Tests
From the root of this extracted directory:
```bash
python -m pytest 10_regression/tests/ -v
```
Or run:
```bash
bash 10_regression/run_all_tests.sh
```

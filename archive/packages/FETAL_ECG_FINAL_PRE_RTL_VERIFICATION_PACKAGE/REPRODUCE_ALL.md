# Complete Pre-RTL Verification Reproduction Guide

This guide provides step-by-step instructions to independently reproduce every test, numerical audit, and CSV deliverable in the **FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE**.

---

## 1. Environment Setup

### System Prerequisites
- **Operating System:** Linux, macOS, or Windows (WSL / PowerShell)
- **Python Version:** Python 3.10, 3.11, 3.12, or 3.13 (64-bit)

### Installation
From the root of the unzipped package:

```bash
# 1. Create a clean virtual environment
python -m venv venv

# 2. Activate virtual environment
# On Linux / macOS:
source venv/bin/activate
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1

# 3. Install frozen dependencies
pip install -r 10_regression/requirements.txt
```

---

## 2. Executing the Pre-RTL Regression Test Suite

To run all 34 bit-accurate unit, equivalence, and integration tests:

### Using Pytest directly:
```bash
pytest 10_regression/tests -v
```

### Using the Shell Runner:
```bash
bash 10_regression/run_all_tests.sh
```

### Expected Output:
```text
============================= test session starts =============================
collected 34 items

10_regression/tests/test_calibration_confidence_and_recalibration.py ... PASSED
10_regression/tests/test_end_to_end_pipeline_synthetic.py .............. PASSED
10_regression/tests/test_fhr_interval_fusion_and_median5.py ............ PASSED
10_regression/tests/test_filter_coefficients_exact.py .................. PASSED
10_regression/tests/test_filter_delay_and_timing_compensation.py ....... PASSED
10_regression/tests/test_fixed_point_scaling_exact.py .................. PASSED
10_regression/tests/test_hardware_arithmetic_exact.py .................. PASSED
10_regression/tests/test_qrs_matching_strict.py ........................ PASSED
10_regression/tests/test_uart_protocol_final.py ........................ PASSED
10_regression/tests/test_weight_crossfade_slew.py ....................... PASSED

============================= 34 passed in 1.68s ==============================
```

---

## 3. Reproducing Complete Numerical Verification Audits

To re-run the complete set of audits on the physiological dataset (`data/FECGSD/DESTINATION`):

```bash
bash 10_regression/run_all_experiments.sh
```

Or execute each audit script individually using Python:

### Step 3.1: Priority A & B (Scaling, SQNR & Hardware Arithmetic)
```bash
python 11_source_code/tools/run_fixed_point_scaling_audit.py
```
- Regenerates:
  - `01_fixed_point_scaling/FIXED_POINT_SCALING_CORRECTED.csv`
  - `01_fixed_point_scaling/FIXED_POINT_STAGE_ERROR.csv`
  - `01_fixed_point_scaling/FIXED_POINT_EQUIVALENCE_FINAL.csv`
  - `02_hardware_arithmetic/OVERFLOW_ANALYSIS_FINAL.csv`

### Step 3.2: Priority C (FHR Metric Reconciliation)
```bash
python 11_source_code/tools/run_fhr_reconciliation_audit.py
```
- Regenerates:
  - `03_fhr_reconciliation/FHR_RESULTS_REGENERATED.csv`
  - `03_fhr_reconciliation/FHR_AGGREGATE_RESULTS.csv`
  - `03_fhr_reconciliation/FHR_CONDITION_ANALYSIS.csv`

### Step 3.3: Priority D & F (Calibration & Dynamic Recalibration)
```bash
python 11_source_code/tools/run_calibration_audit.py
```
- Regenerates:
  - `04_calibration/CALIBRATION_METRICS_CORRECTED.csv`
  - `04_calibration/CALIBRATION_AVAILABILITY_FINAL.csv`
  - `04_calibration/CONTINUOUS_RECALIBRATION_RESULTS.csv`

### Step 3.4: Priority E (Filter Group Delay & Timing Compensation)
```bash
python 11_source_code/tools/run_filter_delay_audit.py
```
- Regenerates:
  - `05_filter_timing/FILTER_GROUP_DELAY.csv`
  - `05_filter_timing/QRS_TIMING_COMPENSATION_RESULTS.csv`

---

## 4. Standalone Clean Extraction Verification

To verify that the deliverable package is 100% self-contained and free of host repository dependencies:

```bash
# 1. Extract package zip into an isolated temporary folder
unzip FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE.zip -d /tmp/clean_extraction_test

# 2. Change directory into extracted location
cd /tmp/clean_extraction_test

# 3. Run regression suite directly
pytest 10_regression/tests -v
```
All tests will execute and pass without requiring any files outside the unzipped directory.

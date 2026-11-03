# Instructions to Reproduce All Results
1. Ensure Python 3.10+ with numpy, scipy, wfdb, pytest is installed.
2. Set PYTHONPATH to 'code':
   export PYTHONPATH=code
3. Run the complete regression test suite:
   bash 10_regression_tests/run_all_tests.sh
4. To reproduce individual benchmarks:
   python 02_full_layout_validation/scripts/run_full_layout_reproduction.py
   python 03_spatial_calibration/scripts/run_autocorr_rigorous_validation.py
   python 04_qrs_fhr_validation/scripts/run_raw_qrs_vs_fhr_study.py
   python 05_detector_validation/scripts/run_detector_rigorous_audit.py
   python 11_source_code/tools/run_fixed_point_audit.py

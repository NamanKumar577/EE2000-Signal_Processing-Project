# Instructions to Reproduce All Results

1. Install requirements:
   pip install -r 10_regression/requirements.txt
2. Run complete regression suite:
   python -m pytest 10_regression/tests/ -v
3. To reproduce individual priority audits:
   python 11_source_code/tools/reconcile_qrs_metrics.py
   python 11_source_code/tools/audit_calibration_fallback.py
   python 11_source_code/tools/run_fixed_point_audit_corrected.py
   python 11_source_code/tools/run_fhr_stage_audit.py
   python 11_source_code/tools/run_benchmark_coverage_and_twin_audit.py
   python 11_source_code/tools/generate_filter_spec.py

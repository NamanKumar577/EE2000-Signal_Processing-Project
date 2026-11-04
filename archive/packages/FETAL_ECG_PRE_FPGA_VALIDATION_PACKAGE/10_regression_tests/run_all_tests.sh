#!/usr/bin/env bash
# run_all_tests.sh - Execute complete Pre-FPGA regression suite
set -e
echo "================================================================================"
echo " EXECUTING PRE-FPGA REGRESSION TEST SUITE (171 TOTAL TESTS)"
echo "================================================================================"
export PYTHONPATH=code
python -m pytest code/tests/test_pre_fpga_regression.py -v
python -m pytest code/tests/ -v
echo "================================================================================"
echo " ALL TESTS PASSED SUCCESSFULLY"
echo "================================================================================"

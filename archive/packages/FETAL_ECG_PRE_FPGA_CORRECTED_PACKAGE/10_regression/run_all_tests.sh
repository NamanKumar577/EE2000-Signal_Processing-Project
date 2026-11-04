#!/usr/bin/env bash
# Execute all Pre-FPGA corrected regression tests
set -e
echo "================================================================================"
echo " RUNNING PRE-FPGA CORRECTED REGRESSION TEST SUITE (27 TESTS)"
echo "================================================================================"
python -m pytest 10_regression/tests/ -v
echo "================================================================================"
echo " ALL TESTS PASSED SUCCESSFULLY"
echo "================================================================================"

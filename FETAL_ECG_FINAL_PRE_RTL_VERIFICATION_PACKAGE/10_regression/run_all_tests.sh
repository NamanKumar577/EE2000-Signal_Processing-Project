#!/usr/bin/env bash
# ==============================================================================
# run_all_tests.sh - Pre-RTL Bit-Accurate Verification Regression Suite
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "======================================================================"
echo "Starting Pre-RTL Hardware Reference Model Regression Test Suite"
echo "Package Root: ${PKG_ROOT}"
echo "Timestamp:    $(date -u +"%Y-%m-%d %H:%M:%SZ")"
echo "======================================================================"

# Determine Python command (virtualenv or system python)
if [ -f "${PKG_ROOT}/venv/Scripts/python" ]; then
    PYTHON="${PKG_ROOT}/venv/Scripts/python"
elif [ -f "${PKG_ROOT}/../venv/Scripts/python" ]; then
    PYTHON="${PKG_ROOT}/../venv/Scripts/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

echo "Using Python: $(${PYTHON} --version)"

# Execute Pytest on regression suite
TEST_DIR="${SCRIPT_DIR}/tests"
RESULTS_FILE="${SCRIPT_DIR}/test_results.txt"

echo "Executing pytest on ${TEST_DIR}..."
${PYTHON} -m pytest "${TEST_DIR}" -v | tee "${RESULTS_FILE}"
TEST_EXIT_CODE=${PIPESTATUS[0]}

if [ ${TEST_EXIT_CODE} -eq 0 ]; then
    echo "======================================================================"
    echo "ALL REGRESSION TESTS PASSED (Exit Code: 0)"
    echo "Results saved to: ${RESULTS_FILE}"
    echo "======================================================================"
    exit 0
else
    echo "======================================================================"
    echo "REGRESSION TESTS FAILED (Exit Code: ${TEST_EXIT_CODE})"
    echo "======================================================================"
    exit ${TEST_EXIT_CODE}
fi

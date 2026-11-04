#!/usr/bin/env bash
# ==============================================================================
# run_all_experiments.sh - Reproduce All Pre-RTL Verification Audits
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "======================================================================"
echo "Starting Complete Pre-RTL Verification Audit Execution"
echo "Package Root: ${PKG_ROOT}"
echo "Timestamp:    $(date -u +"%Y-%m-%d %H:%M:%SZ")"
echo "======================================================================"

# Determine Python binary
if [ -f "${PKG_ROOT}/venv/Scripts/python" ]; then
    PYTHON="${PKG_ROOT}/venv/Scripts/python"
elif [ -f "${PKG_ROOT}/../venv/Scripts/python" ]; then
    PYTHON="${PKG_ROOT}/../venv/Scripts/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

TOOLS_DIR="${PKG_ROOT}/11_source_code/tools"

echo "[1/4] Running Priority A & B Scaling & Hardware Arithmetic Audit..."
${PYTHON} "${TOOLS_DIR}/run_fixed_point_scaling_audit.py"

echo "[2/4] Running Priority C FHR Reconciliation Audit..."
${PYTHON} "${TOOLS_DIR}/run_fhr_reconciliation_audit.py"

echo "[3/4] Running Priority D & F Calibration & Recalibration Audit..."
${PYTHON} "${TOOLS_DIR}/run_calibration_audit.py"

echo "[4/4] Running Priority E Filter Group Delay Audit..."
${PYTHON} "${TOOLS_DIR}/run_filter_delay_audit.py"

echo "======================================================================"
echo "ALL AUDITS AND NUMERICAL EXPERIMENTS COMPLETED SUCCESSFULLY"
echo "======================================================================"

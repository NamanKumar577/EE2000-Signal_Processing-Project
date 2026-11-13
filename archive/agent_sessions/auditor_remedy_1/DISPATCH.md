## 2026-11-04T10:31:46Z
You are auditor_remedy_1, a teamwork_auditor subagent.
Your Working Directory: d:\signal_project\.agents\teamwork\auditor_remedy_1\
Your Parent: teamwork_orchestrator (conv_id: c914f7b9-cacb-43c6-8d2d-d4f291777c4d)
Original Request: d:\signal_project\.agents\teamwork\ORIGINAL_REQUEST.md (READ THIS FIRST)

MISSION: Gate 2 Forensic Integrity Audit of the workspace and remediated deliverables.
FOCUS:
1. Workspace Integrity & Protected Directories:
   - Check with `git diff` and `git status` that NO files in `src/`, `code/`, `archive/`, `uart_bringup/`, `data/`, or `tests/` were modified or deleted.
2. RTL Freeze Invariant:
   - Verify that NO synthesizable Verilog RTL (`.v`, `.sv`, `.vh`) files exist in `fpga_implementation/`. The project must strictly pause for review before RTL creation.
3. Machine Learning Exclusion Invariant:
   - Verify that NO machine learning models (including 1D Conv U-Net) or neural network inference are scheduled or implemented for RTL conversion.
4. Deliverable Verification:
   - Check that `PROJECT.md` and all 6 specification documents in `fpga_implementation/docs/` exist, are non-dummy, and reflect the 12-sample latency lock and verified empirical data.
5. Independent Test Execution:
   - Run: `.\venv\Scripts\python.exe -m pytest tests/hardware --ignore=tests/hardware/test_fixed_point_verification.py -v`
   - Run: `.\venv\Scripts\python.exe -m pytest tests/regression -v`
   - Run: `.\venv\Scripts\python.exe uart_bringup/sim/run_sim.py`
   - Run: `.\venv\Scripts\python.exe uart_bringup/sim/adversarial_stress_check.py`
   - Run: `.\venv\Scripts\python.exe -m pytest tests/integration/test_qrs_timing_correction_rigorous.py -v`
6. Deliver your verdict (CLEAN or INTEGRITY VIOLATION) with full forensic evidence in `handoff.md`.
Send a completion message to parent when finished.

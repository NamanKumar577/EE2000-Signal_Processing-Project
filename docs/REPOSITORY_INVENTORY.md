# Repository Inventory and Audit Report

**Project:** Real-Time Multichannel Fetal ECG Extraction & Spartan-7 FPGA Hardware Implementation  
**Course & Milestone:** EE2000 Signal Processing Project (Paper ID: 0008) — Post Mid-Term / Pre-RTL Phase  
**Active Branch:** `fpga-causal-pipeline` (Commit: `b8c2ebc`)  
**Date:** 2026-11-03  
**Status:** Completed Initial Repository Audit

---

## 1. Executive Summary

A comprehensive, non-destructive audit of the repository was conducted. The repository represents the multi-stage research, algorithm benchmarking, fixed-point integer modeling, and hardware architectural sizing of **Team 8** for extracting the weak fetal biopotential ($20$–$100\,\mu\text{V}$) from composite maternal abdominal recordings ($1.0$–$5.0\,\text{mV}$) on an AMD/Xilinx Spartan-7 FPGA.

### Global Repository Statistics
- **Total Git-Tracked Files:** 1,264 files
- **Total Tracked Storage Size:** 262.90 MB
- **Local Virtual Environment (`.venv`):** 32,677 untracked files (977.73 MB, Python 3.14)
- **Knowledge Graph (`graphify-out`):** 454 files (15.41 MB)
- **Automated Verification Status:** **198 / 198 unit & regression tests pass (100%)** in 2.14s.

---

## 2. Directory Inventory & Metrics Breakdown

| Top-Level Directory | Files | Size (MB) | Primary File Types | Description & Role |
| :--- | :---: | :---: | :--- | :--- |
| **`test/`** | 52 | 97.38 MB | `.dat` (20), `.hea` (20), `.qrs` (10) | **Physiological ECG Dataset:** 5 PhysioNet FECGSYNDB recordings (`test1`–`test5`) @ 250 Hz, 34 channels. *Not a software test folder.* |
| **`report/`** | 70 | 60.78 MB | `.png` (37), `.pdf` (7), `.py` (7), `.tex` (4) | **Mid-Term Deliverables:** IEEE CVF Conference report (`mtr-8.pdf`), LaTeX source, 37 publication figures, submission archive (`mtr-8.zip`). |
| **`(root)`** | 28 | 35.73 MB | `.md` (15), `.zip` (4), `.pdf` (4), `.txt` (3) | **Root Documents & Archives:** 15 Markdown specs/trackers, large submission archive `mtr-8.zip` (25.7 MB), package zips, transient logs. |
| **`code/`** | 139 | 25.01 MB | `.py` (56), `.png` (46), `.hex` (14), `.csv` (6) | **Active Codebase:** Source modules (`code/src/`), 24 unit test files (`code/tests/`), benchmark results (`code/results/`), plots (`code/visualization/`). |
| **`graphify-out/`** | 454 | 15.41 MB | `.json` (450), `.html` (1), `.md` (1) | **Knowledge Graph:** AST structural graph, community hubs, and Graphify report. |
| **`papers/`** | 9 | 14.97 MB | `.pdf` (9) | **Reference Literature:** Landmark peer-reviewed papers on SVD, LMS, wavelets, and Pan-Tompkins ECG processing. |
| **`QRS_RESIDUAL_TIMING_ANALYSIS/`** | 13 | 4.78 MB | `.png` (7), `.csv` (3), `.md` (1), `.txt` (1) | **Timing Diagnostic Package:** High-resolution residual delay plots (4.72 MB), 250-record error CSVs, and standalone test script. |
| **`validation/`** | 133 | 2.65 MB | `.md` (62), `.csv` (57), `.py` (8), `.png` (4) | **Subsystem Evidence:** 15 subdirectories with empirical markdown audits and benchmark tables across all project phases. |
| **`page/`** | 2 | 2.48 MB | `.pdf` (2) | **Conference Template Pages:** IEEE CVF review template page extracts. |
| **`FETAL_ECG_PRE_FPGA_VALIDATION_PACKAGE/`** | 64 | 0.90 MB | `.md` (27), `.py` (17), `.csv` (13), `.txt` (6) | **Historical Package v1:** Initial pre-FPGA validation deliverable (12 numbered sections). |
| **`previous_package_extracted/`** | 64 | 0.90 MB | `.md` (27), `.py` (17), `.csv` (13), `.txt` (6) | **Redundant Duplicate:** Exact byte-for-byte duplicate of historical package v1. |
| **`FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/`** | 93 | 0.65 MB | `.py` (44), `.md` (26), `.csv` (15), `.txt` (5) | **Historical Package v3:** Final Pre-RTL sign-off package with UART telemetry, exact filter delay, and integer LUTs. |
| **`FETAL_ECG_PRE_FPGA_CORRECTED_PACKAGE/`** | 85 | 0.60 MB | `.py` (37), `.md` (27), `.csv` (14), `.txt` (5) | **Historical Package v2:** Intermediate corrected package (2026-10-31) addressing initial audit findings. |
| **`tools/`** | 39 | 0.45 MB | `.py` (39) | **Verification & Utility Scripts:** 6 subdirs (`final_verification`, `improvements`, `pre_fpga`, `pre_fpga_corrected`, `qrs_timing_correction`, `validation`). |
| **`docs/`** | 9 | 0.12 MB | `.md` (9) | **Documentation Archive:** Archived individual team member FPGA feasibility reports and trackers. |
| **`QRS_TIMING_CORRECTION/`** | 6 | 0.07 MB | `.md` (2), `.csv` (2), `.txt` (1), `.py` (1) | **Timing Correction Bundle:** Timestamp pipeline explanation, delay reconciliation CSVs, and unit test. |
| **`tests/`** | 2 | 0.02 MB | `.py` (2) | **Root Test Duplicates:** `test_qrs_timing_correction_rigorous.py` and `test_residual_timing_analysis.py`. |
| **`.agents/`** | 2 | 0.00 MB | `.md` (2) | **Agent Rules:** Graphify rules and workflows. |

---

## 3. Major Project Observations

### Observation 1: Active Source Code is Located in `code/src/`
Git history and commit logs demonstrate that active development is centered in `code/src/`:
- **Commit `582fc21`:** Introduced the causal, streaming, label-free FPGA pipeline (`causal_pipeline.py`), integer-only golden model (`fpga_int_model.py`), and causal benchmark sweep (`run_causal_benchmark.py`).
- **Commit `b8c2ebc`:** Copied pre-RTL verified models (`bit_accurate_reference_model_final.py`, `uart_protocol_final.py`, `fhr_implementation_corrected.py`) into `code/src/`.
- All 198 unit tests in `code/tests/` target modules under `src.*` when executed with `PYTHONPATH=code`.

### Observation 2: `test/` is an ECG Signal Dataset, NOT Unit Tests
The directory named `test/` at the root contains 97.38 MB of raw PhysioNet FECGSYNDB physiological signals (`test1` through `test5`). Software tests reside in `code/tests/` and root `tests/`. Renaming/moving `test/` to `data/` will resolve confusion and prevent tooling errors.

### Observation 3: Triple Package Lineage and Exact Duplicate
Three generations of engineering verification packages exist in parallel:
1. **v1:** `FETAL_ECG_PRE_FPGA_VALIDATION_PACKAGE/` + `.zip` (Initial baseline)
2. **Duplicate:** `previous_package_extracted/` is a 100% byte-for-byte duplicate of v1.
3. **v2:** `FETAL_ECG_PRE_FPGA_CORRECTED_PACKAGE/` + `.zip` (Reconciled metrics)
4. **v3:** `FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/` + `.zip` (Final pre-RTL sign-off)
All three packages plus their `.zip` archives should be cleanly isolated in `archive/packages/`.

### Observation 4: Root Directory Clutter
The root directory currently contains **28 files** (35.73 MB), including 15 extensive Markdown documents, 4 compiled PDFs, 4 `.zip` files (including the 25.7 MB `mtr-8.zip` which duplicates `report/mtr-8.zip`), and temporary execution logs (`audit_before.txt`, `clean_extraction_test.log`).

### Observation 5: Duplicate Python Implementations
Commit `b8c2ebc` introduced multiple generations of the same components into `code/src/`:
- **Fixed-Point Models:** `bit_accurate_reference_model.py` (v1), `bit_accurate_reference_model_corrected.py` (v2), and `bit_accurate_reference_model_final.py` (v3, authoritative).
- **UART Protocols:** `uart_protocol.py` (v2) and `uart_protocol_final.py` (v3, authoritative).
- **FHR Post-Processing:** `fhr.py` (v1) and `fhr_implementation_corrected.py` (v2/v3, authoritative).

### Observation 6: Test Suite Discoverability & Python Path
Running `pytest` at the root fails with `ModuleNotFoundError: No module named 'src'` because tests expect `code/` to be on `sys.path`. Consolidating all tests into a standard top-level `tests/` directory with `src/` as a proper Python package will fix discovery permanently.

---

## 4. Key Configuration Files

The following configuration files must remain protected during any restructuring:
1. **`.gitignore` (Root):** Contains critical ignore patterns for `.venv/`, `data/`, `__pycache__/`, `.DS_Store`.
2. **`CLAUDE.md` (Root):** Behavioral guidelines and surgical code modification protocol.
3. **`code/requirements.txt`:** Runtime dependency specifications (`numpy`, `scipy`, `wfdb`, `torch`, `pandas`, `pytest`).
4. **`.agents/`:** Graphify agent rules (`rules/graphify.md`) and workflow directives (`workflows/graphify.md`).

---

## 5. Unexplored Areas & Limitations

1. **`tools/pre_fpga_corrected/reconcile_qrs_metrics.cpython-314.pyc`:** Untracked/compiled byte artifact in a tool folder.
2. **`code/brain/`:** Contains local scratch/agent state from past sessions; should be evaluated for archiving.
3. **Large Datasets Outside Repo:** The full 250-record PhysioNet FECGSYNDB dataset (2.55 GB) is hosted externally; only 5 records (97.4 MB) are tracked locally in `test/`.

---
*Report compiled autonomously by Lead Repository Architect.*

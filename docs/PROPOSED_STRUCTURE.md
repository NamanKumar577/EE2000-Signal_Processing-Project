# Proposed Clean Repository Structure & Migration Mapping

**Project:** Real-Time Multichannel Fetal ECG Extraction & Spartan-7 FPGA Hardware Implementation  
**Course & Milestone:** EE2000 Signal Processing Project (Paper ID: 0008)  
**Date:** 2026-11-03  
**Status:** Architecture Proposal & Migration Blueprint

---

## 1. Overview of Proposed Repository Structure

The current repository layout suffers from significant root clutter (28 files, 35.7 MB), duplicate packages, test fragmentation across multiple directories, and confusion caused by naming the dataset directory `test/`.

The proposed clean structure organizes all repository assets into **8 logical domains**:

```text
EE2000-Signal_Processing-Project/
├── .agents/                          # Agent rules and workflow definitions (PRESERVED)
├── .gitignore                        # Git ignore patterns (PRESERVED)
├── CLAUDE.md                         # LLM engineering protocols (PRESERVED)
├── README.md                         # Clean master entry point and project documentation
├── requirements.txt                  # Promoted master Python dependencies
│
├── src/                              # Active, authoritative Python implementation
│   └── fecg/                         # Clean 'fecg' Python package
│       ├── __init__.py
│       ├── core/                     # Preprocessing, data loading, evaluation, mixture
│       ├── pipelines/                # Streaming causal FPGA pipeline & multichannel analysis
│       ├── detection/                # Pan-Tompkins QRS detector & corrected FHR estimation
│       ├── methods/                  # Extraction algorithms (SVD, Template, SWT-LMS, Hybrid)
│       ├── models/                   # Deep learning architectures (1D Conv U-Net)
│       ├── hardware/                 # Bit-accurate and integer FPGA golden models
│       └── telemetry/                # 921,600 baud UART protocol implementation
│
├── tests/                            # Unified test discovery suite (207 tests)
│   ├── conftest.py                   # Pytest fixtures and synthetic signal generators
│   ├── unit/                         # Core unit tests (preprocessing, loader, metrics, etc.)
│   ├── integration/                  # Causal pipeline, end-to-end synthetic, UART protocol
│   ├── hardware/                     # Bit-accurate, fixed-point SQNR, and integer model tests
│   └── regression/                   # Pre-FPGA regression test suite
│
├── scripts/                          # Runnable execution, benchmark and validation scripts
│   ├── benchmarks/                   # run_causal_benchmark, run_benchmark, run_mega_benchmark
│   └── validation/                   # Multi-record audit runners (calibration, FHR, fixed-point)
│
├── data/                             # Physiological signal datasets (moved from 'test/')
│   └── fecgsyndb/                    # PhysioNet FECGSYNDB recordings (test1 through test5)
│       ├── test1/                    # WFDB records (.hea, .dat, .qrs)
│       ├── test2/
│       ├── test3/
│       ├── test4/
│       └── test5/
│
├── results/                          # Consolidated experimental outputs and figures
│   ├── benchmarks/                   # TC1–TC5 matrices, population CSVs, timing CSVs
│   ├── figures/                      # Generated signal plots and diagnostic histograms
│   └── validation_reports/           # Empirical evidence folders (relocated from 'validation/')
│
├── hardware/                         # AMD/Xilinx Spartan-7 FPGA & Telemetry Architecture
│   ├── spec/                         # Authoritative FPGA_SPEC.md (v0.2), DATASHEETS_AND_HARDWARE_SPECS.md
│   ├── telemetry/                    # Authoritative UART_PROTOCOL_SPEC.md, packet framing
│   └── rtl_prep/                     # FINAL_HARDWARE_PARAMETERS.json, FHR integer LUTs
│
├── docs/                             # Project documentation and literature
│   ├── architecture/                 # Algorithmic decisions, project context, validation reports
│   ├── literature/                   # Literature notes, citations, and papers/ (9 PDFs)
│   ├── trackers/                     # Active team tasks, unresolved decisions, work plan
│   └── audit/                        # Subagent audit reports (SOURCE_CODE, TEST, DATA, DOCS)
│
├── report/                           # IEEE CVF Mid-Term Conference Submission
│   ├── mtr-8.pdf                     # Canonical 18-page conference paper
│   ├── mtr-8.zip                     # Authoritative submission ZIP archive
│   ├── mid_term/                     # LaTeX sources, CHANGELOG_MTR8.md, publication figures
│   └── preliminary/                  # Conference review template extracts
│
├── tools/                            # Development and repository maintenance utilities
│   ├── audit_mtr8.py                 # MTR-8 paper compliance audit
│   └── clean_anonymity.py            # Double-blind review sanitization script
│
└── archive/                          # Historical packages, superseded code, and transient logs
    ├── packages/                     # Historical packages (v1, v2, v3) and package zips
    │   ├── FETAL_ECG_PRE_FPGA_VALIDATION_PACKAGE/
    │   ├── FETAL_ECG_PRE_FPGA_CORRECTED_PACKAGE/
    │   ├── FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/
    │   └── *.zip
    ├── historical_code/              # Superseded Python files (v1/v2 bit_accurate, v2 uart, v1 fhr)
    ├── timing_bundles/               # QRS_RESIDUAL_TIMING_ANALYSIS, QRS_TIMING_CORRECTION
    └── logs/                         # Transient terminal logs (audit_*.txt, *.log)
```

---

## 2. Directory and File Migration Mapping

The table below defines the exact source-to-destination mapping for every directory and root file in the repository:

| Existing Location | Proposed Destination | Classification | Rationale & Notes |
| :--- | :--- | :--- | :--- |
| **`test/`** | `data/fecgsyndb/` | **ACTIVE DATASET** | Resolves name collision; `test/` is 97.4 MB of raw WFDB ECG signals, not unit tests. |
| **`code/src/`** | `src/fecg/` | **ACTIVE SOURCE** | Promotes active codebase to standard Python package layout. |
| **`code/src/methods/`** | `src/fecg/methods/` | **ACTIVE SOURCE** | SVD, Template, SWT-LMS, Alternative extraction algorithms. |
| **`code/src/models/`** | `src/fecg/models/` | **ACTIVE SOURCE** | 1D U-Net deep learning models. |
| **`code/src/run_*benchmark*.py`** | `scripts/benchmarks/` | **ACTIVE SCRIPTS** | Separates executable benchmark CLI runners from library code. |
| **`code/src/train_deep_model.py`** | `scripts/benchmarks/` | **ACTIVE SCRIPTS** | Training script for deep U-Net. |
| **`code/tests/`** | `tests/` | **ACTIVE TESTS** | Consolidates 198 passing tests into standard top-level test tree. |
| **`root tests/`** | `tests/integration/` | **ACTIVE TESTS** | Consolidates timing correction and residual analysis tests. |
| **`code/results/`** | `results/benchmarks/` | **ACTIVE RESULTS** | Consolidated benchmark CSV outputs and TC1–TC5 matrices. |
| **`code/visualization/`** | `results/figures/waveforms/` | **ACTIVE ARTIFACTS** | 46 generated signal processing stage plots. |
| **`code/requirements.txt`** | `requirements.txt` (Root) | **ACTIVE CONFIG** | Promotes requirements to root for standard pip/venv setup. |
| **`code/configs/`** | `src/fecg/configs/` | **ACTIVE CONFIG** | Detector and model YAML configuration files. |
| **`code/brain/`** | `archive/scratch/` | **ARCHIVE** | Historical agent scratchpad directory. |
| **`validation/`** | `results/validation_reports/` | **ACTIVE EVIDENCE** | Preserves all 133 empirical evidence files without cluttering root. |
| **`tools/final_verification/`** | `scripts/validation/` | **ACTIVE SCRIPTS** | Pre-RTL sign-off verification runners. |
| **`tools/improvements/`** | `scripts/validation/` | **ACTIVE SCRIPTS** | Algorithmic parameter sweep runners. |
| **`tools/pre_fpga*/`** | `archive/package_assemblers/` | **ARCHIVE TOOLS** | Packaging and historical reconciliation scripts. |
| **`tools/qrs_timing_correction/`**| `scripts/validation/` | **ACTIVE SCRIPTS** | Timing compensation evaluation scripts. |
| **`tools/*.py` (Root tools)** | `tools/` | **ACTIVE TOOLS** | `audit_mtr8.py` and `clean_anonymity.py`. |
| **`papers/`** | `docs/literature/papers/` | **ACTIVE DOCS** | 9 reference PDF papers. |
| **`page/`** | `docs/literature/template_pages/` | **ACTIVE DOCS** | 2 template extract PDFs. |
| **`FPGA_SPEC.md`** | `hardware/spec/FPGA_SPEC.md` | **AUTHORITATIVE SPEC** | Frozen Spartan-7 spec v0.2. |
| **`DATASHEETS_AND_HARDWARE_SPECS.md`** | `hardware/spec/DATASHEETS_AND_HARDWARE_SPECS.md` | **AUTHORITATIVE SPEC** | Hardware component and board electrical constraints. |
| **`MASTER_FPGA_IMPLEMENTATION_AND_FEASIBILITY_REPORT.md`** | `hardware/spec/MASTER_FPGA_FEASIBILITY_REPORT.md` | **AUTHORITATIVE SPEC** | Synthesis results and resource budget sign-off. |
| **`MASTER_ALGORITHM_SELECTION_AND_FPGA_DECISION.md`** | `docs/architecture/MASTER_ALGORITHM_SELECTION.md` | **AUTHORITATIVE DOC** | Canonical algorithm selection decision report. |
| **`FECG_MEGA_VALIDATION_FINAL_REPORT.md`** | `docs/architecture/FECG_MEGA_VALIDATION_FINAL_REPORT.md`| **AUTHORITATIVE DOC** | Full population validation sign-off. |
| **`Fetal_ECG_Project_Context_and_Plan.md`** | `docs/architecture/` | **ACTIVE DOCS** | System context and phase roadmap. |
| **`Fetal_ECG_Preliminary_Report_Missing_Sections.md`** | `docs/architecture/` | **HISTORICAL DOCS** | Mid-term report draft notes. |
| **`TEAM_TASKS_AND_WORK_TRACKER.md`** | `docs/trackers/TEAM_TASKS_AND_WORK_TRACKER.md` | **ACTIVE TRACKER** | Current team task tracker. |
| **`UNRESOLVED.md`** | `docs/trackers/UNRESOLVED.md` | **ACTIVE TRACKER** | Open technical and hardware decisions. |
| **`fecg_team_work_plan.md`** | `docs/trackers/` | **HISTORICAL TRACKER** | Initial team work plan. |
| **`FECG_FPGA_Literature_Notes.md`** | `docs/literature/FECG_FPGA_Literature_Notes.md` | **ACTIVE DOCS** | Comprehensive literature review. |
| **`refs_audit.md` & `papers.txt`** | `docs/literature/` | **ACTIVE DOCS** | Citation audit and bibliography lists. |
| **`CHANGELOG_MTR8.md`** | `report/mid_term/CHANGELOG_MTR8.md` | **HISTORICAL DOCS** | Mid-term report revision changelog. |
| **`PPR-8.pdf` & `project.pdf`** | `docs/literature/project_guidelines/`| **REFERENCE DOCS** | Course project description and review template. |
| **`mtr-8.pdf` (Root)** | `report/mtr-8.pdf` (Merge/Retain) | **CANONICAL REPORT** | Keep single canonical PDF in `report/`. |
| **`mtr8_corrected.pdf` (Root)**| `archive/submissions/` | **DUPLICATE** | Duplicate of `mtr-8.pdf`. |
| **`mtr-8.zip` (Root)** | `archive/submissions/` | **DUPLICATE** | 25.7 MB duplicate of `report/mtr-8.zip`. |
| **`FETAL_ECG_*_PACKAGE/`** | `archive/packages/` | **HISTORICAL PACKAGES** | Preserves package v1, v2, v3 in historical archive. |
| **`previous_package_extracted/`** | `archive/packages/` | **REDUNDANT DUPLICATE** | 100% duplicate of package v1. |
| **`FETAL_ECG_*_PACKAGE.zip`** | `archive/packages/` | **HISTORICAL ARCHIVES** | Zipped package distributions. |
| **`QRS_RESIDUAL_TIMING_ANALYSIS/`** | `archive/timing_bundles/` | **HISTORICAL BUNDLE** | Preserved after extracting tests and results. |
| **`QRS_TIMING_CORRECTION/`** | `archive/timing_bundles/` | **HISTORICAL BUNDLE** | Preserved after extracting tests and results. |
| **`audit_before.txt`, `audit_after.txt`** | `archive/logs/` | **TRANSIENT LOGS** | Transient audit output. |
| **`clean_extraction_test.log`** | `archive/logs/` | **TRANSIENT LOGS** | Transient execution log. |

---

## 3. Duplicate Resolution & Authoritative Implementations

The following table explicitly resolves all duplicate code implementations identified in `code/src/`:

| Component | Authoritative File (to be promoted to `src/fecg/`) | Superseded Variants (to be moved to `archive/historical_code/`) | Justification & Verification Evidence |
| :--- | :--- | :--- | :--- |
| **Fixed-Point Reference Model** | `bit_accurate_reference_model_final.py` $\rightarrow$ `src/fecg/hardware/bit_accurate_reference.py` | `bit_accurate_reference_model.py` (v1)<br>`bit_accurate_reference_model_corrected.py` (v2) | `_final.py` incorporates full filter group-delay compensation, strict bit-width scaling, and achieves 100% equivalence with Spartan-7 integer hardware testbenches (MD5: `b1f116fb`). |
| **FPGA Golden Model** | `fpga_int_model.py` $\rightarrow$ `src/fecg/hardware/fpga_int_model.py` | None | Bit-true integer golden model for RTL verification. Unique and canonical (MD5: `2e0446d9`). |
| **Causal Streaming Pipeline** | `causal_pipeline.py` $\rightarrow$ `src/fecg/pipelines/causal_pipeline.py` | None | Float reference pipeline for real-time FPGA deployment (MD5: `475af842`). |
| **UART Protocol** | `uart_protocol_final.py` $\rightarrow$ `src/fecg/telemetry/uart_protocol.py` | `uart_protocol.py` (v2) | `_final.py` includes full calibration packet framing, error status byte, and 921,600 baud timing verification (MD5: `a5d33182`). |
| **FHR Estimation** | `fhr_implementation_corrected.py` $\rightarrow$ `src/fecg/detection/fhr.py` | `fhr.py` (v1) | Corrected implementation resolves edge-case RR interval fusion, clamps to physiological 50–240 bpm, and applies 5-beat causal median filter. |

---

## 4. Protected Configuration Files

The following files will remain **unmodified and in-place at the repository root**:
- **`.gitignore`**
- **`CLAUDE.md`**
- **`.agents/rules/graphify.md`**
- **`.agents/workflows/graphify.md`**
- **`.git/` (Never modified)**

---

## 5. Items Marked `NEEDS_REVIEW`

1. **`tools/pre_fpga_corrected/reconcile_qrs_metrics.cpython-314.pyc`:** Python bytecode artifact; recommended for deletion during cleanup.
2. **`code/brain/`:** Scratch files from earlier sessions; quarantined in `archive/scratch/`.
3. **`mtr-8.zip` (Root, 25.7 MB):** Confirmed duplicate of `report/mtr-8.zip`. Quarantined in `archive/submissions/` to preserve git history without root clutter.

---
*Blueprint compiled autonomously by Lead Repository Architect.*

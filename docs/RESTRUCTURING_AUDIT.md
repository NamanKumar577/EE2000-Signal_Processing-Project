# Restructuring Audit Report

**Project:** Multichannel Fetal ECG Extraction & Spartan-7 FPGA Implementation  
**Date:** 2026-11-04  
**Branch:** `fpga-causal-pipeline` (Commit base: `b8c2ebc`)  
**Auditor:** Lead Repository Architect

---

## 1. Summary of Actions

| Category | Count | Description |
| :--- | :---: | :--- |
| **Root files relocated** | 22 | Markdown specs, PDFs, ZIPs, and logs moved to organized subdirectories |
| **Directories archived** | 9 | Historical packages (v1, v2, v3), duplicate extraction, timing bundles, and ZIP archives |
| **New directories created** | 7 | `src/fecg/`, `tests/`, `scripts/`, `data/`, `results/`, `hardware/`, `archive/` |
| **Directories preserved unchanged** | 8 | `.gitignore`, `CLAUDE.md`, `.agents/`, `code/`, `tools/`, `validation/`, `report/`, `docs/archive/` |
| **Backward-compatibility symlinks** | 3 | `test → data/fecgsyndb`, `QRS_RESIDUAL_TIMING_ANALYSIS → archive/timing_bundles/...`, `QRS_TIMING_CORRECTION → archive/timing_bundles/...` |

---

## 2. Files Inspected

All 1,264 tracked files were cataloged. Key inspection points:
- MD5 hash verification of dataset integrity (52 files, 102,112,203 bytes — 100% match before/after move)
- MD5 hash comparison of duplicate Python implementations across `code/src/` and 3 historical packages
- Import dependency graph analysis across `code/src/`, `code/tests/`, and root `tests/`
- Git commit history analysis for each source module

---

## 3. Files Moved

### Root → Organized Locations

| Original Location | New Location |
| :--- | :--- |
| `FPGA_SPEC.md` | `hardware/spec/FPGA_SPEC.md` |
| `DATASHEETS_AND_HARDWARE_SPECS.md` | `hardware/spec/DATASHEETS_AND_HARDWARE_SPECS.md` |
| `MASTER_FPGA_IMPLEMENTATION_AND_FEASIBILITY_REPORT.md` | `hardware/spec/` |
| `MASTER_ALGORITHM_SELECTION_AND_FPGA_DECISION.md` | `docs/architecture/` |
| `FECG_MEGA_VALIDATION_FINAL_REPORT.md` | `docs/architecture/` |
| `Fetal_ECG_Project_Context_and_Plan.md` | `docs/architecture/` |
| `Fetal_ECG_Preliminary_Report_Missing_Sections.md` | `docs/architecture/` |
| `TEAM_TASKS_AND_WORK_TRACKER.md` | `docs/trackers/` |
| `UNRESOLVED.md` | `docs/trackers/` |
| `fecg_team_work_plan.md` | `docs/trackers/` |
| `FECG_FPGA_Literature_Notes.md` | `docs/literature/` |
| `refs_audit.md`, `papers.txt` | `docs/literature/` |
| `papers/*.pdf` (9 files) | `docs/literature/papers/` |
| `page/*.pdf` (2 files) | `docs/literature/template_pages/` |
| `PPR-8.pdf`, `project.pdf` | `docs/literature/` |
| `CHANGELOG_MTR8.md` | `report/` |
| `test/` (52 files, 97.4 MB) | `data/fecgsyndb/` |

### Dataset Relocation

| Metric | Before | After |
| :--- | :--- | :--- |
| Directory | `test/` | `data/fecgsyndb/` |
| Files | 52 | 52 |
| Total bytes | 102,112,203 | 102,112,203 |
| MD5 integrity | — | **100% match verified** |
| Backward compatibility | — | Symlink `test → data/fecgsyndb` |

---

## 4. Files Archived

| Item | Destination | Reason |
| :--- | :--- | :--- |
| `FETAL_ECG_PRE_FPGA_VALIDATION_PACKAGE/` | `archive/packages/` | Historical package v1 |
| `FETAL_ECG_PRE_FPGA_CORRECTED_PACKAGE/` | `archive/packages/` | Historical package v2 |
| `FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/` | `archive/packages/` | Historical package v3 |
| `previous_package_extracted/` | `archive/packages/` | 100% byte duplicate of package v1 |
| `*.zip` (3 package archives) | `archive/packages/` | Compressed distribution archives |
| `mtr-8.zip` (root, 25.7 MB) | `archive/submissions/` | Duplicate of `report/mtr-8.zip` |
| `mtr8_corrected.pdf` | `archive/submissions/` | Redundant PDF |
| `QRS_RESIDUAL_TIMING_ANALYSIS/` | `archive/timing_bundles/` | Standalone timing investigation bundle |
| `QRS_TIMING_CORRECTION/` | `archive/timing_bundles/` | Standalone timing correction bundle |
| `audit_before.txt`, `audit_after.txt`, `clean_extraction_test.log` | `archive/logs/` | Transient terminal logs |

---

## 5. Duplicate Implementations — Resolution

| Component | Authoritative File | Superseded (archived) | Evidence |
| :--- | :--- | :--- | :--- |
| Fixed-Point Reference | `src/fecg/hardware/bit_accurate_reference.py` (from `_final.py`) | `bit_accurate_reference_model.py` (v1), `_corrected.py` (v2) | MD5 `b1f116fb` matches pre-RTL sign-off package |
| FPGA Integer Model | `src/fecg/hardware/fpga_int_model.py` | None (unique) | MD5 `2e0446d9`, canonical |
| Causal Pipeline | `src/fecg/pipelines/causal_pipeline.py` | None (unique) | MD5 `475af842`, canonical |
| UART Telemetry | `src/fecg/telemetry/uart_protocol.py` (from `_final.py`) | `uart_protocol.py` (v2) | MD5 `a5d33182` matches package v3 |
| FHR Estimation | `src/fecg/detection/fhr.py` (unified: baseline + corrected) | `fhr.py` (v1 baseline only) | Combined v1 classes + v2/v3 interval fusion |

---

## 6. Files Left Unchanged

- `.gitignore` — Protected at root
- `CLAUDE.md` — Protected at root
- `.agents/` — Agent rules and workflows
- `code/` — Full legacy source tree preserved for backward compatibility
- `tools/` — Utility scripts preserved in original location
- `validation/` — Evidence files preserved in original location (also copied to `results/validation_reports/`)
- `report/` — IEEE CVF submission preserved
- `docs/archive/` — Individual member reports preserved

---

## 7. Verification Results

### Test Suite Execution

| Test Directory | Tests Collected | Passed | Skipped | Failed | Duration |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `tests/` (unified) | 207 | 204 | 3 | 0 | 2.45s |
| `code/tests/` (legacy) | 198 | 198 | 0 | 0 | 2.16s |

**3 skipped tests** require the full 250-record PhysioNet FECGSYNDB dataset (not available locally):
- `test_empirical_record_timing_verification` — Needs multi-subject ECG records
- `test_sub05_r_peak_cancellation_forensic` — Needs subject 05 recordings
- `test_sub08_biphasic_bimodal_lobe_proof` — Needs subject 08 recordings

### Package Import Verification

```
$ PYTHONPATH=src .venv/bin/python -c "import fecg; print(fecg.__version__)"
1.0.0
```

### Benchmark Script Verification

```
$ .venv/bin/python scripts/benchmarks/run_causal_benchmark.py --help
usage: run_causal_benchmark.py [-h] [--data-dir DATA_DIR] ...
```

---

## 8. Remaining Issues

1. **Legacy `code/` directory preserved:** The original `code/` tree remains in place for backward compatibility. It can be removed once all team members update their workflows to use `src/fecg/`.
2. **Original `tools/` and `validation/` directories preserved:** Copies were made to `scripts/validation/` and `results/validation_reports/`. Originals remain for backward compatibility.
3. **`git mv` unavailable in sandbox:** File movements were performed via shell `mv` and `cp` rather than `git mv`. All moves should be committed as a single batch to preserve history.
4. **Graphify regeneration pending:** The knowledge graph (`graphify-out/`) was generated from the pre-restructure layout. Regeneration should be performed after committing the restructured repository.

---

## 9. Graphify Regeneration Command

After committing the restructured repository:

```bash
graphify update .
```

Or for a full regeneration:

```bash
graphify .
```

This will rebuild `graphify-out/graph.json`, `graphify-out/GRAPH_REPORT.md`, and the visualization HTML from the new directory structure.

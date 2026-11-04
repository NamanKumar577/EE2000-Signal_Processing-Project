# Archive — Historical Implementations and Packages

This directory contains historical, superseded, and archival material preserved
for reference and audit trail purposes. **None of this code is active.**

The authoritative active source code lives in `../src/fecg/`.

---

## Directory Structure

### `packages/`
Three generations of pre-FPGA engineering verification packages:

| Package | Version | Date | Description |
| :--- | :---: | :--- | :--- |
| `FETAL_ECG_PRE_FPGA_VALIDATION_PACKAGE/` | v1 | 2026-10-27 | Initial pre-FPGA validation deliverable (12 numbered sections) |
| `FETAL_ECG_PRE_FPGA_CORRECTED_PACKAGE/` | v2 | 2026-10-31 | Corrected & reconciled engineering package |
| `FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/` | v3 | 2026-11-03 | Final pre-RTL sign-off package with UART, filter delay, integer LUTs |
| `previous_package_extracted/` | — | — | 100% byte-for-byte duplicate of v1 (historical extraction artifact) |
| `*.zip` | — | — | Compressed distribution archives of each package version |

### `historical_code/`
Superseded Python source modules that have been replaced by authoritative versions in `src/fecg/`:

| File | Superseded By | Notes |
| :--- | :--- | :--- |
| `bit_accurate_reference_model_v1.py` | `src/fecg/hardware/bit_accurate_reference.py` | Initial fixed-point reference model |
| `bit_accurate_reference_model_v2.py` | `src/fecg/hardware/bit_accurate_reference.py` | Corrected intermediate version |
| `uart_protocol_v2.py` | `src/fecg/telemetry/uart_protocol.py` | Pre-final UART protocol |
| `fhr_baseline.py` | `src/fecg/detection/fhr.py` | Original FHR module without interval fusion |
| `fixed_point_model.py` | `src/fecg/hardware/bit_accurate_reference.py` | Mid-term phase fixed-point emulator |
| `svd_fixed_point_model.py` | `src/fecg/hardware/bit_accurate_reference.py` | SVD-specific fixed-point sizing model |

### `timing_bundles/`
Standalone timing investigation packages:
- `QRS_RESIDUAL_TIMING_ANALYSIS/` — Residual delay diagnostic plots and per-record CSVs
- `QRS_TIMING_CORRECTION/` — Timestamp pipeline delay reconciliation

### `submissions/`
Historical submission archives:
- `mtr-8.zip` — 25.7 MB mid-term submission ZIP (duplicate of `report/mtr-8.zip`)
- `mtr8_corrected.pdf` — Redundant PDF copy

### `logs/`
Transient execution logs from auditing sessions:
- `audit_before.txt`, `audit_after.txt` — Terminal output from pre/post-audit scans
- `clean_extraction_test.log` — One-off extraction test output

### `scratch/`
Historical agent scratchpad files.

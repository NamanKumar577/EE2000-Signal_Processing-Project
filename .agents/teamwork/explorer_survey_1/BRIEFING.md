# BRIEFING — 2026-11-04T09:38:00Z

## Mission
Survey and trace the authoritative Non-ML Python Signal Processing Pipeline in `src/fecg/`, distinguish from ML modules, evaluate tests/reference data, and map historical vs authoritative discrepancies.

## 🔒 My Identity
- Archetype: explorer
- Roles: teamwork_explorer
- Working directory: d:\signal_project\.agents\teamwork\explorer_survey_1\
- Original parent: c914f7b9-cacb-43c6-8d2d-d4f291777c4d
- Milestone: Survey & Trace Non-ML Python Signal Processing Pipeline

## 🔒 Key Constraints
- Read-only investigation — do NOT implement or modify source code
- Maintain progress.md with timestamps
- Deliver analysis in analysis.md and handoff in handoff.md
- Communicate to parent via send_message

## Current Parent
- Conversation ID: c914f7b9-cacb-43c6-8d2d-d4f291777c4d
- Updated: 2026-11-04T09:25:10Z

## Investigation State
- **Explored paths**: `src/fecg/` (core, detection, hardware, methods, models, pipelines, telemetry), `tests/` (hardware, regression, integration, unit), `data/FECGSD/`, `code/`, `archive/packages/` (v1, v2, v3), `archive/historical_code/`, `archive/timing_bundles/`
- **Key findings**:
  1. Authoritative 8-stage causal pipeline established in `src/fecg/hardware/bit_accurate_reference.py` and `src/fecg/hardware/fpga_int_model.py`.
  2. Deep learning U-Net isolated in `src/fecg/models/fecg_unet.py` and strictly excluded.
  3. Tests in `tests/`: 26/26 hardware tests pass, 26/26 regression tests pass, 33/34 integration tests pass, 49/49 algorithmic unit tests pass. Identified Windows git symlink checkout artifacts (`core.symlinks=false`) as cause of collection errors.
  4. Discrepancies resolved: 12.4 vs 18 sample latency resolved (Config C 12-35 Hz bandpass has 17.86 sample group delay @ 15 Hz, locked at 18-sample rewind); -42 dB scaling bug resolved (omitted 128x factor corrected to $2^{20}\text{ LSB/mV}$ scaling chain).
- **Unexplored areas**: None within scope. All mission items thoroughly surveyed.

## Key Decisions Made
- Fully documented 8-stage pipeline equations, numerical wordlengths, and internal states.
- Cataloged complete inventory of test vectors and reference recordings.
- Produced comprehensive `analysis.md` and complete 5-component `handoff.md`.

## Artifact Index
- DISPATCH.md — incoming dispatch record
- BRIEFING.md — persistent working memory
- progress.md — liveness heartbeat
- analysis.md — deep investigation findings
- handoff.md — structured handoff report

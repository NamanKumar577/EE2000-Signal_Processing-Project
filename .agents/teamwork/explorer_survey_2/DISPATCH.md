## 2026-11-04T09:25:16Z
You are explorer_survey_2, a teamwork_explorer subagent.
Your Working Directory: d:\signal_project\.agents\teamwork\explorer_survey_2\
Your Parent: teamwork_orchestrator (conv_id: c914f7b9-cacb-43c6-8d2d-d4f291777c4d)
Original Request: d:\signal_project\.agents\teamwork\ORIGINAL_REQUEST.md (READ THIS FIRST)

MISSION: Survey existing hardware models, specs, difference equations, and fixed-point definitions.
FOCUS AREAS:
1. Inspect existing models in `src/fecg/hardware/` and `hardware/spec/` (bit-accurate and integer reference models, difference equations, filters, peak detection, etc.).
2. Detail the exact mathematical difference equations, state registers, arithmetic operations, and pipelining needed for each conventional ECG processing stage.
3. Define the bit widths, signedness, fractional bits, rounding mode, truncation, and overflow saturation rules for all arithmetic operations.
4. Separate single-channel processing feasibility from operations requiring multichannel spatial processing (e.g. ICA, multi-channel adaptive cancellation).
5. If `graphify-out/` exists, follow the project rules in `d:\signal_project\.agents\rules\graphify.md`.

CONSTRAINTS:
- You are read-only! DO NOT modify or delete any files in `src/`, `code/`, `archive/`, or anywhere else.
- Maintain `progress.md` with timestamps in your working directory.
- Deliver your comprehensive findings in `d:\signal_project\.agents\teamwork\explorer_survey_2\analysis.md` and write a complete `handoff.md`.
- Send a completion message to your parent (c914f7b9-cacb-43c6-8d2d-d4f291777c4d) once done.

# WS1 patch (applied by fixes/WS1/apply.py, exact unique string matching)

## Moves (text unchanged, headings demoted one level, placed in App. A right after its intro block)
| Old location | New location | Label change |
|---|---|---|
| Sec. 3 "Problem Statement and Formal Engineering Objectives" (w = v2 formulation, O1--O5 list) | App. A.1 | `sec:problem_statement` -> `sec:midterm_problem` (old label reused by the new Sec. 3) |
| Sec. 4 "Physiological Signal Model and Dataset" (dipole model, FECGSYNDB paragraph, Fig. fmr_topography, lead-selection paragraph, Fig. filter_responses, Butterworth/notch preprocessing list, data-split protocol) | App. A.2 | `sec:dataset` -> `sec:midterm_dataset` (old label reused by the new Sec. 4) |
| Sec. 5 "Multi-Channel Signal Processing Architectures" (Tab. method_inventory, M1 PCA beamformer, detector, U-Net, M4--M9) | App. A.3 | none |

## New sections (blue, own files)
- `sections/ws1_problem.tex`: new Sec. 3 "Problem Statement and Final Objectives" (inputs, constraints, outputs, targets -> Tab. clinical_specs, tab:objective_status, tab:final_objectives, tab:o3o4).
- `sections/ws1_dataset.tex`: new Sec. 4 "Data Sets and Signal Model" (dipole model Eq., data sets, final front end). Front-end values from `tools/report_stats/front_end_check.py` -> `tools/report_stats/out/front_end.csv` (computed from `fpga_implementation/v6/model/coef_q28.h` and `hp_q` in `fpga_model.c`): one-pole HP 0.63 Hz; LP 4th-order 60 Hz (2 SOS); maternal band 5--25 Hz 4th-order (2 SOS); track band 15--40 Hz 8th-order (4 SOS); no notch filter in model/ or rtl/.

## Text replacements
1. Intro: "offers the ideal clinical alternative: ... and complete safety for mother and fetus." -> "offers \fin{an alternative}: ... and \fin{no invasive risk} for mother and fetus."
2. Intro: "Crucially, maternal and fetal cardiac biopotentials exhibit" -> "Maternal and fetal cardiac biopotentials exhibit"
3. Intro: "However, benchmark evaluations reveal a critical mathematical failure mode:" -> "\fin{Our benchmark evaluations showed a failure mode}:"
4. Research gap: "they frequently depend on multi-DSP architectures or require dedicated maternal thoracic reference leads. This project works toward realizing an end-to-end, bit-accurate, and latency-deterministic NIFECG extraction pipeline targeting" -> "\fin{they often require a dedicated maternal thoracic reference lead. Our final design uses 43 DSP slices (Tab.~\ref{tab:hw_summary}) and no reference lead. This project builds an end-to-end, bit-accurate and deterministic} NIFECG extraction pipeline \fin{on}"
5. Sec. 2 latency: "Latency (per-sample filter group delay) must remain strictly below $100\,$ms to trigger emergency alerts. Note that downstream beat-to-display telemetry includes a 5-beat median filter which adds approximately $2.1\,$s of beat-level smoothing." -> "\fin{The original (mid-term) target was a per-sample latency below $100\,$ms; the final design reports live beats after 1.5--2\,s and final beats after about $13.5\,$s, and the target is re-baselined in \cref{tab:o3o4}.}"
6. Sec. 2 power: "Boolean Board total power is estimated analytically; physical board current measurement remains future work." -> "\fin{The on-chip power of the final design is a Vivado estimate ($0.445\,$W, \cref{tab:hw_summary}); the board current was not measured.}"

# Night log, 2026-11-09/10: real-data accuracy, fully on the FPGA

**Goal:** the PC only streams the recording; the FPGA does all the processing.

**Rules:**
- Causal and label-free; annotations are used only for scoring.
- No data manipulation.
- Development sets:
  - **syn:** FECGSYNDB, every 21st record (59 records);
  - **cdev:** CinC 2013 set-a, odd-numbered records (38);
  - **ad:** ADFECGDB (5 records).
- **Held-out set:** CinC even-numbered records, touched only once, for the final frozen design.

**Metric:** beat F1, ±50 ms tolerance, scored from 20 s.

## Timeline

| Time | Step | Set | Result (mean F1 %) | Decision / note |
|---|---|---|---|---|
| 21:30 | Commit v4 prototype as baseline (`0747ac6`); back up the v2 bitstream | — | — | — |
| 21:40 | Baseline `devbench.py v3 v4` (`baseline_devbench.csv`) | syn / cdev / ad | v3: 95.22 / 59.35 / 78.65; v4: 92.08 / 68.42 / 91.26 | v4 is better on real data but loses 3.1 points on syn. Fix that before freezing. |
| 21:45 | Decision: v5 = MicroBlaze (FPU) soft core plus BRAM on the xc7s50. The whole algorithm runs on the FPGA in C. The PC only streams samples in lock-step blocks. | — | — | Hand-written RTL for GEVD, SVD template fitting and 12 trackers is not feasible overnight. The soft core is the on-FPGA implementation. |
| 22:00 | Ablation of v4 components (`exp_v5_ablate.py`) | syn / cdev / ad | Dropping the v2 host-beamformer track: syn 95.0→67.4, cdev 66.4→68.7, ad 87.9→92.3 (quality selection) | Synthetic data depends on the v2 raw-lead track. Real data is better without it. |
| 22:20 | Self-calibrated raw-lead GEVD candidates (tracker and threshold detector) replace v2 (`exp_v5_raw.py`) | " | No v2 + raw: syn 89.6, but real data collapses (cdev 37, ad 46) | Raw candidates lock onto the mother on real data. |
| 22:35 | **Label-free maternal-coincidence penalty** in selection: quality × clip((0.6−c)/0.3, 0, 1), where c = fraction of beats within ±48 ms of a maternal R peak (`exp_v5_coinc.py`, `exp_v5_gate.py`) | " | No v2 + raw + penalty: syn 78.8 / **cdev 72.8** / **ad 92.3** | Best real-data result so far (v4 was 68.4 / 91.3). Synthetic loss: the maternal detector picks the fetal train in some FECGSYNDB records (fetal-vs-maternal coincidence ≈ 0.8). |
| 22:50 | Fixes for the wrong maternal train on syn: rate-continuity rule; refractory 100/115; rate gate 95–115; penalty floor 0.1–0.5 (`exp_v5_mat.py`, `exp_v5_matref.py`, `exp_v5_floor.py`) | " | None improves syn without losing real data (e.g. floor 0.5: syn 93.1, cdev 45.3) | Not adopted. Real data has priority; the synthetic regression is documented. |
| 23:40 | **C port of the algorithm** (`fpga_implementation/v5/algo/fecg_v5.c`): streaming, float32, static memory, fully causal (fixed Z delay 176 samples; selection decision made 150 samples after its window ends, so no look-ahead remains). The PC build of the firmware source is the reference model (`tools/accuracy/v5c.py`). | syn / cdev / ad | **C v5: 78.73 / 70.84 / 91.68** (Python 78.8 / 72.8 / 92.3) | Within about 2 points of Python. The differences come from strict causality, the block-median prominence approximation and int16 input. The C model is now the development platform. |
| 00:10 | **Maternal-reference confidence gate:** apply the coincidence penalty only when the chosen maternal train comes from a PCA component holding ≥ 10% of the maternal-band energy. A train on a weak component is usually the fetus or noise. Label-free. (`pen_minfrac` sweep 0.01 / 0.05 / 0.1 / 0.2 / 0.35) | syn / cdev / ad | 0.05: 89.19 / 70.84 / 91.68; **0.1: 91.32 / 70.86 / 91.68**; 0.2: 92.03 / 69.13 / 91.68 | Adopt 0.1. syn +12.6 points, real data unchanged. |
| 00:30 | Candidate subsets: drop the 4 PCA candidates (16 tracks: 4 leads + 4 GEVD on Z, 4 GEVD tracker + 4 GEVD detector on raw) | syn / cdev / ad | 91.32 / 70.96 / 91.72 (20 tracks: 91.32 / 70.86 / 91.68) | Adopted (cheaper). Without the raw detector tracks: cdev −1.2. |
| 00:40 | Diagnostic (labels, dev only, `diag_v5.py`): selected output vs best single track vs per-5 s-window oracle | cdev | 71.0 / 82.8 / 85.5 (ad 91.7 / 94.4 / 96.5) | Label-free selection loses about 12 points on CinC, so selection is the main lever. |
| 00:50 | Selection improvements: RR-regularity factor (fraction of RR within 15% of the median) to the power p; quality window 10 s vs 20 s; hysteresis | " | reg^1: 91.12 / 72.52 / 92.6; reg^2: 90.96 / 73.21 / 92.84; **reg^2 + 20 s window: 91.45 / 73.45 / 93.10**; reg^3 + 20 s + hysteresis 0.2: 91.47 / 73.59 / 93.23 | Adopt reg^2 + 20 s window (the hysteresis gain is within noise; keep it simple). |

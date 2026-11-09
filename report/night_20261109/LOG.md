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
| 01:20 | **MicroBlaze platform up** (fork agent; `fpga_implementation/v5/README.md`): MicroBlaze v11 with FPU at 73.728 MHz; 256 KB LMB plus 32 KB AXI BRAM (72/75 BRAM36 tiles); UART16550 at 921600 baud; lock-step frames; 31× real time with the stub; timing met (WNS +1.91 ns) | board | — | — |
| 01:30 | Memory fit: int16 sample rings (3072 deep, which covers the start-up burst), bf16 envelope rings, int8 peak-normalised beat snapshots, calibration buffers sharing memory with the trackers, canceller history in AXI BRAM. EMA template tried instead of the median template: cdev −1.1, rejected. | syn / cdev / ad | 91.59 / 73.29 / 93.10 | Fits: LMB 253.8 / 256 KB, AXI 24 / 32 KB |
| 01:45 | **First run of the full algorithm on the FPGA** (ADFECGDB r01, 5 min) | board | F1 96.86, board output **bit-exact** with the PC build | 163k cycles per sample (1.7× real time) |
| 02:00 | Speed: incremental raw Gram plus top-2 subspace iteration (replaces 20×20 Jacobi), exact int32 history sums, running MWI, quickselect medians, ring indexing | syn / cdev / ad | 91.65 / 73.18 / 93.15 (accuracy unchanged) | Board: **46.8k cycles per sample = 5.4× real time** (63% of the real-time budget at 73.7 MHz), still bit-exact |
| 02:20 | Selection period 5 s → 2.5 s; cross-track agreement factor (0.5 + agreement) | syn / cdev / ad | hop 2.5 s: 91.83 / 73.83 / 93.44; **+ agreement: 91.87 / 73.93 / 93.44**; hop 1 s: no further gain | Adopt 2.5 s + agreement |
| 02:35 | Diagnostic again: selected 73.9 vs best single track 82.6 vs window oracle 85.0 (cdev). Worst records (a69, a27) select raw-lead tracks locked onto the mother at about 90 bpm. | cdev | — | — |
| 02:40 | Also trust the maternal reference when its rate is < 95–105 bpm, even from a weak component (`pen_rate_ok`) | " | cdev +0.06; syn −1.6 | Rejected |
| 02:50 | **Physiological FHR prior** in selection quality: weight ramps from 0.2 at 80 bpm to 1 at `rate_full` | " | 100: 91.61 / 75.04 / 93.44; 110: 91.79 / 75.14; **120: 91.92 / 75.26 / 93.44**; 130: 91.89 / 75.70 / 93.48; 140: 91.87 / 75.67 | Adopt 120. A higher threshold gains 0.4 but would penalise true fetal bradycardia (FHR < 110), which is clinically important. This is a documented limitation. |
| 03:05 | Tracker parameters (acceptance 0.15 / 0.35; window 75–125% or 65–135% of RR) | syn / cdev / ad | Best: 65–135%: 91.79 / 75.92 / 93.32 (default 91.92 / 75.26 / 93.44) | Within noise; defaults kept |
| 03:15 | Output gap filling from the 2nd-ranked track (simulated, `exp_fill.py`) | " | cdev +0.57, ad +0.1, syn +0.03 | Not adopted (adds output delay and complexity for 0.5 point) |
| 03:20 | Board run, intermediate firmware v5a (before the 2.5 s hop, agreement and FHR prior) | **board** cdev / ad | **73.18 / 93.15** (5.2–5.5× real time) | `board_v5a/` (the bit-exact column is invalid for this run: the PC model was rebuilt mid-run) |
| 03:30 | **DESIGN FROZEN** (`fecg_v5.c` md5 b572675564772e878b73877742cfd10e; `download_v5_final.bit` md5 8a266869d92c971f3ba4d2ebfc3b0d20) | — | — | — |
| 03:35 | Frozen v5, PC model: **full FECGSYNDB (1,248 records)** | syn-all | F1 **91.46** (Se 89.98, PPV 93.63), FHR MAE 5.18 bpm. By condition: c0 96.8, c1 96.9, c2 91.8, c3 93.4, c4 78.5 | v2 was 95.6. A 4-point synthetic regression traded for the real-data gains. |
| 03:40 | **Held-out CinC test half (37 even records), first and only touch** | **ctest** | **v5 65.75** (Se 64.7, PPV 67.3, FHR MAE 17.9); v4 53.08; v3 49.94; v2 41.22; old design 16.66. Reliable references only (33): **v5 70.89**, v4 56.0, v3 53.3, v2 43.2. Records ≥ 90%: v5 13, v4 5, v2 3. | +24.5 points over the v2 design on the board; +12.7 over v4 |
| 04:00 | **Final board run, frozen firmware**: CinC held-out | **board** ctest | **65.75** (Se 64.68, PPV 67.33, FHR MAE 17.94); **37/37 records bit-exact** with the PC model; 5.0× real time | Identical to the PC model |
| 04:25 | Final board run: CinC dev + ADFECGDB | **board** cdev / ad | **75.26 / 93.44** (FHR MAE 12.5 / 1.6); **43/43 bit-exact** | — |
| 05:45 | Final board run: FECGSYNDB subset (every 21st record) | **board** syn | **91.92** (Se 90.75, PPV 93.77, FHR MAE 5.17); **60/60 bit-exact**; 3.8× real time | All final board runs done: 140/140 records bit-exact with the PC model |

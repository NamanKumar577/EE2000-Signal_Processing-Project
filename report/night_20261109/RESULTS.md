# FECG v5: the whole algorithm on the FPGA, with real-data accuracy

**Night of 2026-11-09/10.** The step-by-step record of every experiment and decision is in `LOG.md`.

## What changed
In v2, the FPGA ran the filters, a spatial beamformer and a threshold detector, while the **PC computed the beamformer weights**.

In **v5 the PC only streams the raw recording**: int16, 4 abdominal leads, 250 Hz, over UART at 921600 baud. Everything else runs on the Spartan-7:
- maternal R-peak detection;
- per-lead maternal ECG cancellation;
- 16 candidate spatial filters with self-calibration;
- 16 beat trackers;
- label-free candidate selection;
- FHR.

This runs on a MicroBlaze soft processor with a hardware FPU, built into the xc7s50 fabric. Details are in `fpga_implementation/v5/README.md` (platform) and `fpga_implementation/v5/algo/README.md` (algorithm).

| | v2 (previous) | **v5 (this night)** |
|---|---|---|
| Where the algorithm runs | FPGA filters and detector; PC computes the weights | **All on the FPGA** |
| FPGA resources | 3.9k LUT, 39 DSP, 0 BRAM | 3.3k LUT (10%), 5 DSP, 72/75 BRAM36 |
| Clock | 25 MHz DSP pipeline | 73.728 MHz MicroBlaze (WNS +1.91 ns) |
| Speed | real time | 4–5× faster than real time; about 50k of the 295k cycles available per sample |
| Output latency | about 50 ms | about 1.5–2 s (causal tracker and selection decision delay) |
| Board vs PC model | bit-exact | **bit-exact on every record tested (37 + 43 + 59)** |

## Accuracy
Beat-level F1 is scored from 20 s with a ±50 ms tolerance. All methods are strictly causal and label-free; annotations are used only for scoring.

For CinC, design decisions used only the odd-numbered records. The even-numbered (held-out) records were scored **once**, on the frozen design.

| Data set | Records | Old design | v2 | v3 (Python) | v4 (Python) | **v5 on the FPGA board** |
|---|---|---|---|---|---|---|
| **CinC 2013 held-out (even)** | 37 | 16.7 | 41.2 | 49.9 | 53.1 | **65.8** |
| CinC held-out, reliable references only | 33 | 17.5 | 43.2 | 53.3 | 56.0 | **70.9** |
| CinC held-out, records with F1 ≥ 90% | 37 | 0 | 3 | 4 | 5 | **13** |
| CinC 2013 dev (odd) | 38 | — | 42.0 | 59.4 | 68.4 | **75.3** |
| ADFECGDB (scalp-electrode reference) | 5 | — | 37.0 | 78.7 | 91.3 | **93.4** (FHR MAE 1.6 bpm) |
| FECGSYNDB, all 1,248 (PC model of the same C) | 1,248 | 82.2 | **95.6** | 95.0 | 92.1 (subset) | 91.5 |
| FECGSYNDB subset (every 21st record) | 59 | — | — | 95.2 | 92.1 | see `board_final/board_syn.csv` |

**Notes on the table:**
- CinC held-out, v5 on the board: Se 64.7%, PPV 67.3%, FHR MAE 17.9 bpm (v2: 49.6 bpm).
- The FECGSYNDB result for all 1,248 records comes from the bit-exact PC model of the identical C source, not from the board.
- FECGSYNDB v5 by condition: c0 96.8, c1 96.9, c2 91.8, c3 93.4, c4 78.5.
- **Real data improved substantially:**
  - CinC held-out: +24.6 F1 over v2 and +12.7 over v4;
  - ADFECGDB: +56 over v2.
- **Synthetic data regressed by 4.1 points** relative to v2. This is the price of tracking real noisy recordings. The main remaining cause is that, on some synthetic records, the maternal detector locks onto the fetus.

## What made the difference
Dev-set numbers below are syn / cdev / ad, in that order.

1. **Removed the PC-dependent v2 beamformer track.**
   - Replacement: self-calibrated raw-lead GEVD candidates, each with both a tracker and a threshold detector.
   - Plus a **label-free maternal-coincidence penalty**: candidates whose beats coincide with maternal R peaks are suppressed.
   - Result: cdev 68.4 → 72.8.
2. **Maternal-reference confidence gate.** The penalty is used only if the maternal train comes from a component holding ≥ 10% of the maternal-band energy.
   - This fixes FECGSYNDB records where the "mother" was really the fetus.
   - syn 78.7 → 91.3, real data unchanged.
3. **Better selection quality:**
   - RR-regularity² and a 20 s window: cdev +2.6;
   - 2.5 s hop and cross-track agreement: +0.7;
   - physiological FHR prior: +1.3.
4. **Fitting the FPGA** (int16 and bf16 storage, shared buffers, incremental eigen-solver): accuracy kept within 0.3 points, at 3.5× the speed.

Ideas that were tried and rejected, with numbers, are in `LOG.md`:
- running (EMA) template;
- rate-continuity rule for the maternal train;
- longer maternal refractory;
- penalty floors;
- tracker parameter changes;
- gap filling.

## Remaining gap and limits
- **Diagnostic (uses labels; dev only):** on CinC dev the best single candidate track averages 82.6% and a per-window oracle 85.0%, against 75.3% for the label-free selection. Most of the remaining real-data loss is selection; the rest is the candidate trackers.
- **Dev/test gap:** 75.3 vs 65.8 on CinC. Part of it is natural variation between the record halves; part is design selection on dev. The test half was not used for any decision.
- **FHR prior:** it starts down-weighting candidates below 120 bpm. Fetal bradycardia (< 110 bpm) can therefore be under-selected. The prior was deliberately kept mild: 130 bpm scored 0.4 higher but was rejected.
- **Output latency** is about 1.5–2 s, which is acceptable for FHR monitoring but not for beat-synchronous triggering.
- **Ectopic beats (FECGSYNDB c4)** reach 78.5% and **twins** are not supported, as before.
- **No spare memory:** the on-chip memory is full (254.6/256 KB LMB, 30.4/32 KB AXI). Further algorithm growth needs external RAM or moving parts (filters, envelopes) back into RTL.

## Files
| Path | Content |
|---|---|
| `fpga_implementation/v5/algo/fecg_v5.c` | Algorithm (firmware source and PC reference) |
| `fpga_implementation/v5/build/download_v5_final.bit` | Frozen bitstream with firmware |
| `fpga_implementation/uart_host/run_v5_board_eval.py` | Board evaluation (stream, score, bit-exact check) |
| `tools/accuracy/v5c.py`, `final_eval_pc.py`, `diag_v5.py`, `exp_v5_*.py`, `exp_fill.py` | PC model runner, final PC evaluation, diagnostics, experiments |
| `report/night_20261109/board_final/` | Per-record board results |
| `report/night_20261109/board_v5a/` | Intermediate firmware board run |
| `tools/accuracy/results_v5_final_*.csv` | PC-model results (synall, cdev, ctest, ad) |

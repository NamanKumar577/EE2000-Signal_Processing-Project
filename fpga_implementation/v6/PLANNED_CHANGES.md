# v6 planned changes (not implemented yet)

Started 2026-11-13. Collect items here first and implement them together.
Flow for every item: C model (`model/fpga_model.c`), then RTL, then `sim/regress.sh`, then build, then board check with `uart_host/run_v6_board_eval.py`.

## 1. Block RAM reduction (now 74.5 / 75 tiles, 99%)

Tile counts are estimates from the array sizes. The build report has no per-memory breakdown.

| # | Change | Where | Saves (est.) | Accuracy effect |
|---|---|---|---|---|
| 1a | Share one memory between `ymem` (used only in the first 10 s, for the PCA replay) and `emem` (envelope history, filled only from sample 3877, about 15.5 s) | `v6_mat.v:39`, `v6_trk.v:74` | ~15 tiles | none (bit-exact) |
| 1b | Stream the GEVD calibration data (Z/Xf, samples 750..3750) to the PC as it is produced, instead of buffering 12 s and sending it at 15 s. Then shrink `xring`/`zring` from 4096 to the real look-back (~512) | `v6_core.v:36-37`, `proto.h` CAL_*, `brain.c` | ~10-14 tiles | none (same data); adds ~4 KB/s of link traffic for 12 s |
| 1c | Check the maximum envelope look-back; if it is under 1024 samples, halve `emem` (2048 to 1024 per track) | `v6_trk.v`, `ERING` in `fpga_model.c` | ~8 tiles | none if the look-back fits |

Target: about 60% BRAM, with the board still bit-exact with the model.

## 2. Accuracy (to be decided)
- Candidate selection: on CinC dev the label-free choice scores ~75 F1; the best single track scores 82.6 and a per-window oracle 85.0 (`report/night_20261109/RESULTS.md`).
- Periodic recalibration (idea, not tried yet in v5/v6): today the maternal PCA (at 10 s) and the GEVD calibration (at 15 s) run once and stay fixed. Redo them every N s (e.g. 30-60 s) on the most recent 12 s, without labels. Swap in the new tracks only if a label-free quality check says they are better, or run them as extra candidates next to the old ones so the selector can choose. Depends on item 1b: with streamed calibration data the PC already has the data, so this costs no FPGA RAM. Test on ADFECGDB (5 min) and FECGSYNDB c1-c3; CinC records are only 60 s, so it can barely help there.
- Tune only on CinC dev (odd records). CinC test (even records) has already been used once, so a fresh held-out split must be declared before the next reported number.

## 3. Measurements to add
- RTL-only compute time per second of recording (cycles per sample, from xsim), separate from UART and PC-brain wait time.
- Output latency per beat on the board (documented as ~1.5-2 s in the v5 report).

## 4. Local web demo (done 2026-11-14)
- `fpga_implementation/webdemo/` (`server.py` + `index.html`): upload WFDB or CSV, stream to the board in real time, live FHR, board status and stage; accuracy shown when annotations exist. Board only.
- Board check on a01 through the page: F1 95.05, 101 beats, FHR MAE 3.51, identical to `report/rtl_pc_split/board`.
- If the memory changes in section 1 alter the protocol (item 1b), update `server.py` too.

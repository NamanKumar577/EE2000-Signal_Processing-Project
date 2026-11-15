# v6.1 (causal, improved) and v7-LA (non-causal look-ahead) — work log, 2026-11-14

**Request:** implement the three improvement ideas from the final report on the current design, then build a separate version that may use future samples.

**Rules kept:**
- No annotations are used by any method; they are used only for scoring.
- All design decisions were made on the dev sets:
  - FECGSYNDB subset (every 21st record, 60 records);
  - CinC 2013 odd records (CinC dev, 38);
  - ADFECGDB (5).
- The held-out CinC 2013 even records (CinC test, 37) were scored once per frozen design. Caveat: this half had already been scored for v5 and v6, so it is not a fresh test set, but no v6.1 or v7-LA decision used it.

**Tools:**
- `tools/accuracy/devbench_v6.py`: compiles C-model variants with `-D` switches and scores them in parallel.
- `tools/accuracy/diag_v6_tracks.py`: per-track and oracle diagnostics, dev only.
- `tools/accuracy/learn_selector.py`: the learned-selector experiment.
- `tools/accuracy/v7_offline.py`: v7-LA.

## Part 1 — the three ideas on the current design (C model)

Mean F1 (%) on the dev sets.

| Variant | CinC dev | ADFECGDB | FECGSYNDB subset |
|---|---|---|---|
| v6 (frozen, = board) | 76.04 | 92.73 | 91.83 |
| **Idea 1:** maternal detector warm-up starts at sample 256 | 77.12 | 92.83 | 91.65 |
| Idea 1: detector peak decays after 2 s without a detection | 78.96 | 92.83 | 91.47 |
| **Idea 1: both (adopted)** | **79.52** | **93.31** | **91.11** |
| Idea 1: both, decay gap 1 / 3 / 4 s | 80.35 / 79.41 / 79.68 | 93.31 | 91.13 / 91.10 / 91.16 |
| Idea 2 (on idea 1): maternal-rate penalty ×0.5 / ×0.2 | 79.72 / 80.04 | 93.31 | 90.37 / 89.72 |
| Idea 2: rate voting across tracks | 78.40 | 93.31 | 90.82 |
| Idea 2: FHR continuity (10 / 20 bpm) | 79.01 / 79.41 | 93.24 / 93.28 | 91.08 |
| Idea 2: selection window 15 / 30 s | 79.56 / 79.06 | 93.40 / 93.51 | 91.06 / 90.81 |
| Idea 2: RR-regularity power 1 / 3 | 79.02 / 79.00 | 93.05 / 93.48 | 91.04 / 91.09 |
| Idea 2: agreement weight 0.25 / 1.0 | 79.43 / 79.55 | 93.31 / 93.26 | 91.04 / 91.11 |
| Idea 2: logistic selector trained on 120 other synthetic records (offline replay) | 78.91 (replay base 79.41) | 93.68 (93.31) | 90.83 (91.11) |
| **Idea 3** (on idea 1): recalibrate every 30 / 45 / 60 s, replace filters | 79.97 / 79.52 / 79.52 | 93.11 / 93.27 / 93.30 | 91.16 / 91.35 / 91.27 |
| Idea 3: recalibrate every 20 / 30 / 45 s, keep old filter unless new one is better | 79.09 / **80.41** / 79.52 | 93.49 / **92.87** / 93.41 | 91.35 / **91.64** / 91.70 |
| **v6.1 = idea 1 + idea 3 (30 s, keep-if-better)** | **80.41** | **92.87** | **91.64** |

### Findings
- **Idea 1:** in 4 of the 5 CinC failures where no maternal train was found, all four maternal detectors fired zero times in the whole recording. The detector's peak level was only updated on a detection, so a large early transient set a threshold that was never crossed again.
  - With the warm-up after the filter transient and a slow decay of the peak level after 2 s without a detection, the mother is found in those records. For example, a73 finds it at 96 bpm, and in a65 the real 81-bpm mother now replaces a fetal-rate train.
- **Idea 2:** after idea 1 the chooser still loses about 5 points to the best single track. Diagnostic on dev with labels:

  | Set | Selected | Best track | Per-window oracle |
  |---|---|---|---|
  | CinC dev | 79.5 | 84.7 | 87.2 |
  | FECGSYNDB subset | 91.1 | 96.6 | 96.8 |

  None of the label-free rules or the learned selector closed this gap reliably. The current chooser was kept.
- **Idea 3:** recalibration gives small gains, mostly on the 5-min records. CinC records are 60 s, so they get at most one recalibration.

### v6.1 results
- **CinC test (held out, scored once):**

  | Model | F1 | FHR MAE | Records ≥ 90% |
  |---|---|---|---|
  | v6 | 65.48 | 18.37 bpm | 13 |
  | **v6.1** | **71.94** | **11.16 bpm** | **15** |

  - Reliable references only (33 records): 70.45 → 77.19.
  - 12 records better, 11 worse (by more than 1 point).
- **FECGSYNDB, all 1,248 records:**

  | Model | F1 | c0 | c1 | c2 | c3 | c4 | FHR MAE |
  |---|---|---|---|---|---|---|---|
  | v6 | 91.44 | 96.8 | 96.9 | 91.7 | 93.3 | 78.5 | 5.20 bpm |
  | **v6.1** | **91.89** | 97.2 | 96.9 | 91.5 | 96.0 | 77.9 | **4.85 bpm** |

- **Status:**
  - v6.1 exists in the bit-accurate C model and PC brain (`-DV61`; `fpga_implementation/v6/model/v61_sim.exe`, `v61_brain.exe`). The default build is unchanged: it is byte-identical with the board on the four records checked by MD5.
  - v6.1 has since been ported to the RTL and checked on the board (Part 3).

## Part 2 — v7-LA: a non-causal "offline look-ahead" version

**What it is.** A post-processing version that runs on the PC after the recording and may use future samples. It still uses no annotations.

**How it works:**
1. The v6.1 front end (bit-accurate C model, so the same as a board run) gives the 16 candidate tracks over the whole recording: beats, 31-sample beat snapshots, envelope medians and maternal R peaks.
2. Each track is scored in **centred** ±15-s windows, looking at the past and the future. The scores are:
   - beat-shape consistency;
   - completeness;
   - RR regularity squared;
   - the mild FHR prior;
   - maternal coincidence, trusted only when the maternal train comes from a component with ≥ 10% of the maternal-band energy, as in the brain;
   - agreement with the other tracks.
3. **Viterbi over 2.5-s segments for the whole recording:** pick the track path with the best total log-quality. A switch costs 1, unless the two tracks agree on more than 80% of the beats.
4. **Beat clean-up using the rhythm on both sides:** fill a single missed beat from the nearest candidate beat, or the predicted time, when an interval is 1.6–2.5× the local RR; drop a beat that splits an interval.
5. **FHR** from a centred 5-beat median.

### Development (dev sets)

| Variant | CinC dev | ADFECGDB | FECGSYNDB subset |
|---|---|---|---|
| v6.1 causal (front end of v7-LA) | 80.41 | 92.87 | 91.64 |
| v7-LA first version, maternal penalty without the confidence gate | 84.40 | 95.64 | 78.43 |
| + maternal confidence gate | 84.40 | 95.64 | 93.79 |
| without the beat clean-up | 83.44 | 94.25 | 92.94 |
| centred window ±10 / ±15 / ±20 / ±25 s | 84.45 / **84.55** / 84.40 / 84.20 | 95.91 / **95.80** / 95.64 / 95.73 | 93.55 / **93.91** / 93.79 / 93.79 |
| switch cost 0.5 / 1 / 2 | 84.43 / 84.40 / 84.40 | 95.64 | 93.78 / 93.79 / 93.73 |
| **v7-LA frozen (±15 s, switch 1, clean-up)** | **84.55** | **95.80** | **93.91** |

Dev FHR MAE: CinC dev 8.91 → 6.69 bpm; ADFECGDB 1.72 → 2.21 bpm; FECGSYNDB subset 5.36 → 4.32 bpm.

### v7-LA results
- **CinC test (held out, scored once):**

  | Model | F1 | Se | PPV | FHR MAE | Records ≥ 90% |
  |---|---|---|---|---|---|
  | **v7-LA** | **75.64** | 75.05 | 76.41 | 10.67 bpm | **18** |
  | v6.1 | 71.94 | | | 11.16 bpm | 15 |
  | v6 | 65.48 | | | 18.37 bpm | 13 |

  - Reliable references only: **80.94** (v6.1 77.19).
- **FECGSYNDB, all 1,248 records:** see the end of this file.
- **Limits:**
  - v7-LA needs the whole recording (or at least 15 s of look-ahead), so it is for offline analysis and review, not for live monitoring.
  - It reuses the causal front end, so a recording processed on the board can be post-processed with v7-LA from the board's output stream.

### v7-LA on all 1,248 FECGSYNDB records

| | F1 | c0 | c1 | c2 | c3 | c4 | FHR MAE |
|---|---|---|---|---|---|---|---|
| v6.1 (causal front end) | 91.89 | 97.2 | 96.9 | 91.5 | 96.0 | 77.9 | 4.85 bpm |
| **v7-LA** | **94.34** | 98.7 | 98.9 | 91.7 | 96.7 | **85.8** | **3.48 bpm** |

The largest gain is on ectopic beats (c4, +7.9). We have not analysed the cause per record; the centred quality windows and the two-sided beat clean-up are the likely reasons.

## Part 3 — v6.1 in the RTL

**RTL changes (Verilog define `V61`; without it the RTL is the frozen v6):**
- `v6_det.v`:
  - new init input `i_decay`;
  - when it is set, the peak level drops by 1/8 at every sub-threshold local maximum once 500 samples have passed without a detection (C model `det_step`).
- `v6_mat.v`:
  - maternal detectors start their warm-up at sample 256;
  - `i_decay = 1`.
- `v6_trk.v`, recalibration states 220–229:
  - keeps the current weights;
  - reads the last 3,000 samples of Z/Xf back from the rings and sends them as CALDATA (2,048 + 952 samples);
  - sends REQ_CAL and waits for the new weights;
  - restarts the 64-sample cross-fade from the kept weights.

  The cross-fade now uses per-track previous weights (`w0f`, 1,024 bits) and a ramp start (`rbase`) instead of the fixed lead-0 start. The protocol is unchanged.
- **Scripts:**
  - `sim/run_tb.sh` (`DEFS="-d V61"`) and `sim/regress.sh` (`SIMEXE=../model/v61_sim.exe`);
  - `build_v61.tcl` writes to `build/v61/`, and `program_v61.tcl` programs it;
  - `V6_VARIANT=v61` selects the v6.1 brain and model in `uart_host/run_v6_board_eval.py` and `webdemo/server.py`.

**RTL simulation (xsim) against the v6.1 C model: 8/8 records, 0 byte errors.**

| Record | Uplink bytes | Frames |
|---|---|---|
| CinC a01 | 443,151 | 6,452 |
| ADFECGDB r01 (120 s, 3 recalibrations) | 933,458 | 12,921 |
| CinC a07 | 443,960 | 6,329 |
| CinC a29 | 461,474 | 6,215 |
| CinC a65 | 442,026 | 6,477 |
| CinC a71 | 462,284 | 6,790 |
| FECGSYNDB sub01 l1 c0 (120 s) | 1,145,511 | 15,022 |
| FECGSYNDB sub01 l5 c1 (120 s) | 1,231,006 | 15,665 |

The frozen v6 RTL still matches the v6 model (r_ad_r01 838,652 bytes, a65 427,056 bytes, both 0 errors).

**Implementation (`build/v61/`), XC7S50 at 50 MHz:**

| | v6 | v6.1 |
|---|---|---|
| LUTs | 18,127 (55.6%) | 18,986 (58.2%) |
| Flip-flops | 10,015 | 11,179 (17.1%) |
| Block RAM tiles | 60 | 60 |
| DSP | 33 | 33 |
| Worst slack | +0.26 ns | +0.41 ns |
| Power (estimate) | 0.374 W | 0.386 W |

**Board (Spartan-7, `program_v61.tcl`, `V6_VARIANT=v61 run_v6_board_eval.py --sets cdev,ad,ctest,syn`): 140/140 records bit-exact with the v6.1 C model** (207,020,008 uplink bytes). Output in `board_v61/board_cdev_ad_ctest_syn.csv`, console log in `board_v61.log`.

| Set | Records | F1 | Se | PPV | FHR MAE | Board F1 = model F1 | Speed |
|---|---|---|---|---|---|---|---|
| CinC dev | 38 | 80.41 | 78.51 | 82.62 | 8.91 bpm | yes | 4.5× real time |
| ADFECGDB | 5 | 92.87 | 91.09 | 94.73 | 1.72 bpm | yes | 4.3× |
| CinC test | 37 | 71.94 | 70.79 | 73.39 | 11.16 bpm | yes | 4.5× |
| FECGSYNDB subset | 60 | 91.64 | 90.29 | 93.63 | 5.36 bpm | yes | 4.0× |

Because the board output is byte-identical with the model, v7-LA on the board's uplink gives exactly the v7-LA numbers in Part 2.

## Part 4 — v7-DL: the look-ahead on the FPGA ("delayed live")

**Request:** run v7 on the FPGA itself, with the recording still sent in small parts (not uploaded whole), and the final answer computed on the board; a 15–20 s delay is acceptable.

**Design.** v7-DL = v6.1 + a new RTL unit `v7_la` (no extra work on the PC).
- `v7_la` only listens: it taps every uplink word the other units write (BEAT, FEAT, MPK, COV) and the PC responses RSP_V / RSP_MK, so the v6.1 output is untouched.
- Every 2.5 s it scores the 16 tracks over a window from 15 s before to 10 s after the segment, runs one Viterbi step, takes the chosen track's beats, cleans them up (fill a missed beat, drop a split beat) and computes a centred 5-interval median FHR.
- It sends the final beats as new uplink frames: OUT7 (0x8D: t, fhr_x10, track) and, after the host's FLUSH (new downlink 0x03) at the end of the recording, END7 (0x8E: count).
- Integer only: log2 quality in Q8 (64-entry table), shape consistency = norm of the mean of the normalised beat snapshots (sum per 2.5-s slot, so only 31 sums per slot are stored), lower medians, the maternal gate 10·v'Cv ≥ trace(C) from the COV frame and RSP_V.
- Parameters: window 6 segments back / 3 forward, margin 1.5 s, Viterbi lag 0, one clean-up pass, deadline 15 s. Output delay: median 13.5 s, at most 17.5 s.
- Files: `fpga_implementation/v6/model/v7_post.c` (bit-accurate model, `-DV7`), `rtl/v7_la.v`, `rtl/v7_disp.v` (final FHR and beat count on the board's two 4-digit displays), `build_v7.tcl`, `program_v7.tcl`, `v7.xdc`; host: `V6_VARIANT=v7` in `uart_host/run_v6_board_eval.py` and `webdemo/server.py`.

**Choosing the delay (dev sets only).** Float study `tools/accuracy/v7_live.py`, then the integer C model (`devbench_v6.py`):

| Variant (C model, integer) | CinC dev | ADFECGDB | FECGSYNDB subset | Median / max delay |
|---|---|---|---|---|
| v6.1 causal | 80.41 | 92.87 | 91.64 | 1.5–2 s |
| future 3 segments, lag 0, 1 clean-up pass | 84.68 | 96.10 | 93.39 | 13.5 s / 24.1 s |
| future 3, lag 1, 2 passes | 84.87 | 96.11 | 93.45 | 17.9 s / 30.4 s |
| future 4, lag 0, 1 pass | 84.59 | 96.17 | 93.51 | 16.0 s / 27.5 s |
| **frozen: future 3, lag 0, 1 pass, deadline 15 s** | **84.68** | **96.10** | **93.39** | **13.5 s / 17.5 s** |
| v7-LA offline (whole recording, float) | 84.55 | 95.80 | 93.91 | — |

Dev FHR MAE (frozen v7-DL): CinC dev 6.45, ADFECGDB 2.13, FECGSYNDB subset 4.23 bpm (v6.1: 8.91 / 1.72 / 5.36).

**RTL simulation (xsim) against the v7 C model:** CinC a01 30 s and 60 s, ADFECGDB r01, CinC a07, a29, a65, a71, FECGSYNDB sub01 l1 c0 and l5 c1: all 0 byte errors, including the FLUSH and END7 at the end.

**Area.** The first RTL version needed 13.2k LUTs on its own and the full design did not fit (101% LUTs). The final version does the shifts, divisions and log2 one bit per cycle and uses single-port small memories: 8.4k LUTs on its own. The unit runs once per 2.5 s of signal, so the extra cycles do not matter.

**Board (Spartan-7, `program_v7.tcl`; `V6_VARIANT=v7 run_v6_board_eval.py --sets cdev,ad,ctest,syn`): 140/140 records bit-exact with the v7 C model** (207,603,379 uplink bytes, including the OUT7 frames, FLUSH and END7). The recording is streamed in 64-sample chunks as before, and the final beats are computed on the FPGA. Output: `board_v7/board_cdev_ad_ctest_syn.csv`, log `board_v7.log`.

| Set | Records | v7-DL F1 (board) | Se | PPV | FHR MAE | v6.1 F1 (same run) | v6.1 FHR MAE |
|---|---|---|---|---|---|---|---|
| CinC dev | 38 | **84.68** | 83.45 | 86.03 | 6.45 bpm | 80.41 | 8.91 bpm |
| ADFECGDB | 5 | **96.10** | 96.37 | 95.84 | 2.13 bpm | 92.87 | 1.72 bpm |
| CinC test (held out, scored once) | 37 | **76.91** | 76.22 | 77.83 | 11.53 bpm | 71.94 | 11.16 bpm |
| FECGSYNDB subset | 60 | **93.39** | 92.56 | 94.49 | 4.23 bpm | 91.64 | 5.36 bpm |

- CinC test:
  - Reliable references only (33 records): **81.95** (v6.1 77.19, v7-LA offline 80.94).
  - Records ≥ 90%: 18 (v6.1 15).
  - 33 records better and 1 worse by more than 1 point.
  - FHR MAE is slightly worse (11.53 vs 11.16 bpm).
- All 1,248 FECGSYNDB records (C model = board):

  | Model | F1 | c0 | c1 | c2 | c3 | c4 | FHR MAE |
  |---|---|---|---|---|---|---|---|
  | v6.1 | 91.89 | 97.2 | 96.9 | 91.5 | 96.0 | 77.9 | 4.85 bpm |
  | **v7-DL** | **93.69** | 98.0 | 97.8 | 91.9 | 96.8 | 84.0 | **3.98 bpm** |
  | v7-LA (offline) | 94.34 | 98.7 | 98.9 | 91.7 | 96.7 | 85.8 | 3.48 bpm |

- Speed: 4.0–4.5× real time on the board, as v6.1. The look-ahead unit runs once per 2.5 s of signal.
- Web demo (`V6_VARIANT=v7 webdemo/server.py`), CinC a01 streamed in real time: the 102 final beats on the page (F1 98.02) are identical to the model's OUT7 beats (times, FHR, track).
- Web page updated for v7:
  - the header shows the design on the board;
  - the main heart-rate value is the final one from the FPGA, with the live v6.1 estimate under it;
  - a new card shows the look-ahead delay;
  - the lead window follows the final beats, with live beats as short marks;
  - the heart-rate trend shows the final line, a dashed live line and a shaded "not final yet" area;
  - the stages and the FLUSH step at the end are shown in the log.
  - Check on CinC a03 through the page: live and final beats arrive separately, and the first final beat appears 14.4 s after its beat time.

**Implementation (`build/v7/`):**

| | v6.1 | v7-DL |
|---|---|---|
| LUTs | 18,986 (58%) | 26,701 (82%) |
| Flip-flops | 11,179 | 15,970 |
| Block RAM tiles | 60 | 71 / 75 |
| DSP | 33 | 43 |
| Worst slack (50 MHz) | +0.41 ns | +0.05 ns |
| Power (estimate) | 0.386 W | 0.445 W |

**Tests:**
- `tests/system/test_v6_system_model.py`:
  - v7 model = board MD5 on 3 records;
  - v7 leaves the v6.1 stream untouched;
  - the output before FLUSH is causal and END7 equals the OUT7 count;
  - delay ≤ 17.5 s;
  - ADFECGDB guard ≥ 95.5.
- `tests/hardware/test_v6_rtl_regression.py` runs the v7 RTL as well (`RUN_RTL=1`).
- Full suite: 270 passed, 3 skipped.

## Part 5 — F1 against output delay (2026-11-15, dev sets only)

**Request:** a reviewer asked for F1 against output delay, so a reader can pick the trade-off.

**Method:** `tools/accuracy/v7_delay_sweep.py` builds the v7 C model with the future window `V7_WF` = 0…5 segments (2.5 s each), everything else frozen, and a few shorter deadlines `V7_DL`. Delay comes from the model's own histogram (`V7_DELAY=1`): median of the per-record medians, maximum of the per-record maxima. Sets: FECGSYNDB subset (60), CinC dev (38), ADFECGDB (5). CinC test was not used. Per-record results: `tools/accuracy/results_v7_delay_sweep.csv`; summary: `report/final_report/tables/v7_delay_sweep.csv`; figure: `report/final_report/figures/fin_v7_delay.png` (`tools/make_delay_figure.py`).

| Future window | Median delay | Max delay (15-s deadline) | Max delay (shorter deadline) | CinC dev | ADFECGDB | FECGSYNDB subset |
|---|---|---|---|---|---|---|
| v6.1 live | 1.5–2 s | | | 80.41 | 92.87 | 91.64 |
| 0 | 6.0 s | 16.6 s | 8.0 s (5-s deadline) | 83.53 | 95.58 | 93.32 |
| 1 (2.5 s) | 8.5 s | 17.4 s | 12.5 s (10-s) | 84.22 | 96.14 | 93.32 |
| 2 (5 s) | 11.0 s | 17.4 s | 14.7 s (12-s) | 84.17 | 96.16 | 93.39 |
| **3 (7.5 s, frozen)** | **13.5 s** | **17.5 s** | | **84.68** | **96.10** | **93.39** |
| 4 (10 s) | 16.0 s | 18.0 s | | 84.59 | 96.17 | 93.51 |
| 5 (12.5 s) | 16.2 s | 18.2 s | | 84.68 | 96.12 | 93.55 |

- The frozen point reproduces the v7-DL numbers exactly.
- Most of the gain needs little future: no future segments already gives +3.1 points on CinC dev over v6.1 at a 6-s median delay.
- The deadline only sets the maximum delay; it changed no F1 by more than 0.01 points.

## Part 6 — Delay-tap (spatio-temporal) GEVD candidates (2026-11-15, dev sets only)

**Request:** a reviewer suggested spatio-temporal GEVD (each filter also weights delayed copies of the leads) to get better candidate tracks on weak CinC recordings.

**Method:** `tools/accuracy/exp_taps.py` on a copy of the C model in `tools/accuracy/_taps/model/` (originals untouched). Switches `TAPS` = K and `TAPD` = D: every GEVD track (the 12 Z and Xf GEVD tracks) gets 4·K weights, lead l at tap j applied to sample s − j·D. The self-referencing GEVD in `brain.c` solves the 4K×4K problem the same way as the 4×4 one. The 4 raw-lead tracks, the selector and the v7 look-ahead are unchanged. Sets: FECGSYNDB subset (60), CinC dev (38), ADFECGDB (5). CinC test was not used. Labels are used only for scoring and for the two diagnostics below. "Best track" = per record, the F1 of the best single track; "oracle" = per 5-s window, the best track. `base` (K = 1) gives byte-identical output to the original model on all 103 records. Per-record results: `tools/accuracy/_taps/results.csv`.

| Variant | CinC dev F1 | ADFECGDB F1 | FECGSYNDB F1 | CinC dev best track | CinC dev oracle | CinC dev FHR MAE |
|---|---|---|---|---|---|---|
| **K=1 (frozen v7-DL)** | **84.68** | **96.10** | **93.39** | **84.98** | **87.82** | **6.45** |
| K=2, D=1 | 85.66 | 96.52 | 93.29 | 87.44 | 90.12 | 6.25 |
| K=2, D=2 | 84.68 | 96.59 | 93.45 | 87.50 | 89.92 | 6.34 |
| K=2, D=4 | 77.93 | 97.55 | 95.66 | 87.13 | 89.30 | 11.10 |
| K=2, D=8 | 77.99 | 96.93 | 95.56 | 85.88 | 88.79 | 10.95 |
| K=3, D=1 | 84.14 | 97.71 | 94.29 | 88.89 | 91.00 | 7.49 |
| K=3, D=2 | 84.02 | 97.05 | 93.51 | 87.78 | 90.23 | 7.70 |

**Findings:**
- The taps make better candidates: on CinC dev the best track rises from 85.0 to 87.4–88.9 and the per-window oracle from 87.8 to 89.3–91.0; ADFECGDB and FECGSYNDB rise too.
- The label-free selector does not keep the gain on CinC dev. K=3, D=1 has the best candidates (oracle 91.0) but a lower final F1 (84.1 against 84.7). Per record it is 13 better and 8 worse by more than 1 point, with changes from −60 to +22.
- Wider spacing (D = 4, 8) helps FECGSYNDB (+2.2) but drops CinC dev by 6.7 points.
- K=2, D=1 is the only variant that is not worse on any set (+1.0 / +0.4 / −0.1). Per record on CinC dev it is 11 better and 5 worse, median change 0, with changes from −17 to +20. This is the best of 6 variants picked on the same 38 records, so the +1.0 is not reliable evidence.
- **Verdict:** the frozen design is unchanged. Delay taps are a good source of candidates, but they only pay off once the selection is reworked to use them. That is a larger dev-set study, not a switch to flip.

**RTL cost (estimate, not built):** the delayed samples are already in the 4096-sample Z/Xf rings, so no new memory is needed. Each GEVD track needs 4(K−1) more multiply-adds per sample: 48 for K = 2 and 96 for K = 3 over 12 tracks. That is well inside the 200,000-cycle sample period (median use 1,485 cycles). The calibration message grows from 4 to 4K weights per track. The PC eigen-solve grows from 4×4 to 4K×4K.

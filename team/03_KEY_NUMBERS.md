# Key numbers (one page)

Sources:
- `report/v61_v7/LOG.md`;
- `report/final_report/fpr-8.tex`;
- board CSVs in `report/v61_v7/board_v61/` and `board_v7/`;
- Vivado reports in `fpga_implementation/v6/build/`.

Final design = **v7-DL**.

## Beat F1 (%) by version

| Version | CinC test (37, held out) | CinC dev (38) | ADFECGDB (5) | FECGSYNDB subset (60) | FECGSYNDB all 1,248 (C model) |
|---|---|---|---|---|---|
| Mid-term design (causal re-run) | 16.7 | 22.8 | – | – | 82.2 (in batch mode on 250 records: 93.0) |
| v2 | 41.2 | 42.0 | 37.0 | – | 95.6 |
| v5 (MicroBlaze) | 65.8 | 75.3 | 93.4 | – | 91.5 |
| v6 (board) | 65.48 | 76.04 | 92.73 | 91.83 | 91.44 |
| v6.1 (board) | 71.94 | 80.41 | 92.87 | 91.64 | 91.89 |
| **v7-DL (board, final)** | **76.91** | **84.68** | **96.10** | **93.39** | **93.69** |
| v7-LA (PC, offline, whole recording) | 75.64 | 84.55 | 95.80 | 93.91 | 94.34 |

Extra detail:

| Item | v6 | v6.1 | v7-LA | v7-DL |
|---|---|---|---|---|
| CinC test, reliable references only (33 records) | 70.45 | 77.19 | 80.94 | **81.95** |
| CinC test records with F1 ≥ 90% | 13 | 15 | 18 | 18 |

- v7-DL CinC test 95% CI: **76.9 [68.3, 84.7]**; v6.1: 71.9 [63.2, 80.2].
- v7-DL Se / PPV:

  | Set | Se / PPV (%) |
  |---|---|
  | CinC dev | 83.45 / 86.03 |
  | ADFECGDB | 96.37 / 95.84 |
  | CinC test | 76.22 / 77.83 |
  | FECGSYNDB subset | 92.56 / 94.49 |

- v7-DL vs live v6.1 (same board run, more than 1 point):

  | Records | Better | Worse |
  |---|---|---|
  | CinC test | 33 | 1 |
  | all 75 CinC | 63 | 2 |

- U-Net (mid-term): 90.0% on a 179-record synthetic subset → 17.7% on ADFECGDB.

## FHR error (MAE, bpm)

| Version | CinC test | CinC dev | ADFECGDB | FECGSYNDB subset | FECGSYNDB all |
|---|---|---|---|---|---|
| v6 | 18.37 | 12.52 | 2.03 | 5.24 | 5.20 |
| v6.1 | 11.16 | 8.91 | 1.72 | 5.36 | 4.85 |
| **v7-DL** | **11.53** | **6.45** | **2.13** | **4.23** | **3.98** |
| v7-LA | 10.67 | 6.69 | 2.21 | 4.32 | 3.48 |

## FECGSYNDB by condition (all 1,248, F1 %)

| | c0 baseline | c1 fetal movement | c2 HR changes | c3 contractions | c4 ectopic beats |
|---|---|---|---|---|---|
| v6 | 96.8 | 96.9 | 91.7 | 93.3 | 78.5 |
| v6.1 | 97.2 | 96.9 | 91.5 | 96.0 | 77.9 |
| **v7-DL** | **98.0** | **97.8** | **91.9** | **96.8** | **84.0** |
| v7-LA | 98.7 | 98.9 | 91.7 | 96.7 | 85.8 |

## Why CinC is lower (v7-DL, all 75 CinC records)

- Mean final F1 **80.8%** vs **82.1%** for the best single candidate track, so selection is no longer the main loss.
- 15 records are below 70%:
  - 5 have unreliable references (a38, a52, a54, a71, a74);
  - 8 have no candidate track above 70% (best 42–69%);
  - 2 have a best track of 71–73%;
  - 0 had a good track (≥ 85%) that was not chosen.
- The maternal train is found in all 75 records.
- The challenge flags 7 of the 75 CinC references as unreliable.

## Timing and delay

| Item | Value |
|---|---|
| Scoring | from 20 s, tolerance ±50 ms (13 samples at 250 Hz) |
| First output | about 19.5–20 s (10 s maternal PCA, GEVD calibration on [3, 15) s) |
| Live beat delay (v6, v6.1, live stream of v7) | 1.5–2 s |
| **v7-DL final beat delay** | **median 13.5 s, max 17.5 s** (15-s deadline) |
| v7-DL window | 15 s before to 7.5 s after each 2.5-s segment, + 1.5 s margin; 1 Viterbi step and 1 clean-up pass |
| Track decision (live) | every 2.5 s |
| Recalibration (v6.1, v7) | every 30 s on the latest 12 s, 64-sample cross-fade |

## Board and speed

| Item | Value |
|---|---|
| Bit-exact board vs C model | **140/140 records** for v6, v6.1 and v7-DL (v7: 207,603,379 uplink bytes) |
| RTL simulation (xsim) | v6.1: 8/8 records, v7: 9/9 records, 0 byte errors |
| Board speed | **4.0–4.5× real time**: CinC 4.5×, ADFECGDB 4.4×, FECGSYNDB 4.0× |
| Time per record (v7) | 60-s CinC ≈ 13 s; 5-min synthetic ≈ 74 s; all 140 records ≈ 1.6 h |
| RTL alone | median **1,485 cycles/sample** (≈ 30 µs at 50 MHz) → **≈ 140× real time**; 301 cycles before 10 s; one-off peak 1.12 M cycles at tracker start |
| Web demo a01 (v7) | 102 final beats, F1 98.0% (live v6.1: 95.05%), identical to the C model |
| Tests | **270 passed, 3 skipped** (3 = RTL xsim tests, need `RUN_RTL=1`) |

## FPGA resources (XC7S50, 50 MHz, Vivado post-route)

| | v6 | v6.1 | **v7-DL** | device |
|---|---|---|---|---|
| LUTs | 18,127 (55.6%) | 18,986 (58.2%) | **26,701 (81.9%)** | 32,600 |
| Flip-flops | 10,015 (15.4%) | 11,179 (17.1%) | **15,970 (24.5%)** | 65,200 |
| BRAM tiles | 60 (80%) | 60 (80%) | **71 (94.7%)** | 75 |
| DSP48 | 33 (27.5%) | 33 | **43 (35.8%)** | 120 |
| Worst setup slack | +0.26 ns | +0.41 ns | **+0.05 ns** (0.048) | |
| Power (Vivado estimate) | 0.374 W | 0.386 W | **0.445 W** (0.369 dynamic + 0.076 static) | |

- v7 look-ahead unit `v7_la`:
  - the first version used 13.2k LUTs on its own, and the design did not fit (101%);
  - doing shifts, divisions and log2 one bit per cycle cut it to **8.4k** on its own;
  - in the routed design `util_hier.rpt` shows 7,297 LUTs and 10 DSP;
  - `v7_la` + `v7_disp` add 7.7k LUTs and 11 BRAM tiles to v6.1.
- v6 before the shared block RAM: 74.5/75 BRAM (99%) → 60 (80%).
- Older designs:

  | Design | Resources |
  |---|---|
  | v5 MicroBlaze | 3.3k LUT, 5 DSP, 72/75 BRAM, 73.7 MHz |
  | v2 | 3.9k LUT, 39 DSP, 0 BRAM, 25 MHz |

## Protocol and system

| Item | Value |
|---|---|
| UART | 921,600 baud, 8-N-1; frame `A5 5A cmd len16 payload xor8` |
| Samples | 64-sample SAMPLES frames (0.256 s), 4 leads × int16, 250 Hz; host waits for DONE (0x8C) |
| PC decisions (5) | maternal PCA (once, 10 s); maternal train choice (every 5 s); template basis (each maternal beat); GEVD calibration (15 s, then every 30 s); track selection (every 2.5 s) |
| v7 new frames | **FLUSH 0x03** (PC → board); **OUT7 0x8D** (u32 t, u16 fhr×10, u8 track; 16 = filled beat) and **END7 0x8E** (u32 number of OUT7), board → PC |
| Live output frame | OUT 0x8B (same fields as OUT7) |
| Board displays (v7) | display 0 = final FHR (bpm, `----` before the first final beat); display 1 = number of final beats; cleared when a new recording starts (at 10 s) |
| Data sets | CinC 2013 set-a: 75 × 60 s, 4 leads, 1 kHz (odd = dev 38, even = test 37); ADFECGDB: 5 × 5 min; FECGSYNDB: 1,248 usable × 5 min (subset = every 21st, 60) |

## Story in one line

The CinC held-out F1 rose step by step:

| Design | CinC test F1 (%) |
|---|---|
| mid-term | 16.7 |
| v2 | 41.2 |
| v5 | 65.8 |
| v6 | 65.5 |
| v6.1 | 71.9 |
| **v7-DL** | **76.9** (82.0 on reliable references) |

Every board run is bit-exact with the C model.

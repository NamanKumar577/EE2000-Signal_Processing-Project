# v6 changes: planned and done

Started 2026-11-13. Collect items here first and implement them together.
Flow for every item: C model (`model/fpga_model.c`), then RTL, then `sim/regress.sh`, then build, then board check with `uart_host/run_v6_board_eval.py`.

## 1. Block RAM reduction (was 74.5 / 75 tiles, 99%)

Per-memory tiles from the synthesis "Block RAM: Final Mapping Report" (`build/build.log` of the 2026-11-10 build): emem 16, ymem 14.5, xring 7.5, zring 7.5, hist 7.5, bmem 4, mwi rings 4+1+1, hsum 2, link bram 1.5, others 1 each.

| # | Change | Status |
|---|---|---|
| 1a | One shared 32K x 13 memory in `v6_core.v` (`umem`): `v6_mat` stores the first 2500 maternal-band samples there (10 x 13-bit words each, T < 2500, replayed at T = 2499); `v6_trk` uses it for the 16 x 2048 envelope codes, written only from s = 3750 (T = 3926). Envelope codes are < 2^13 (largest enc_e code is 7423), so 13 bits suffice. Saves ymem (14.5) + 3 tiles of width. | **done 2026-11-14**; model unchanged (bit-exact) |
| 1b | ~~Stream the calibration data to the PC~~: it is already streamed (CALDATA, `fpga_model.c:533`). The rings are 4096 deep because of the start-up burst: at T = 2604 the maternal peaks of the first 10 s are cancelled at once, which reads Xf back to sample ~0, and CALDATA starts at T = 2718 from sample 750. Shrinking the rings would change results. | dropped |
| 1c | ~~Halve emem to 1024 per track~~: a tracker restart reads e[ts .. ts+999] with s - ts up to 1000 + 0.3 R (about 1057), so 1024 entries are not enough. | dropped |

Proof that stale envelope data is never read (needed for 1a): (1) the C model with the envelope rings filled with garbage at calibration (except e[3749], which the RTL zeroes) gives identical uplink streams; (2) the old RTL never cleared emem between RESETs and was still bit-exact on 140 consecutive board records.

## 2. Accuracy (done 2026-11-14 as v6.1: C model, RTL, board). Details: `report/v61_v7/LOG.md`
| Idea | Result on dev (CinC dev / ADFECGDB / FECGSYNDB subset) | Decision |
|---|---|---|
| Maternal detector robustness: warm-up starts at sample 256, peak level decays after 2 s without a detection | 76.0 / 92.7 / 91.8 -> 79.5 / 93.3 / 91.1; in 4 of 5 "no mother found" failures all 4 detectors had fired 0 times | **adopted (v6.1)** |
| Smarter selection: maternal-rate penalty, rate voting, FHR continuity, window / regularity / agreement sweeps, logistic selector trained on synthetic records | best +0.5 on CinC dev but -0.6 to -1.4 on FECGSYNDB; the learned selector -0.5 | not adopted |
| Periodic recalibration every 30 s on the latest 12 s, keep a track's old filter unless the new one scores higher (label-free) | 79.5 / 93.3 / 91.1 -> 80.4 / 92.9 / 91.6 | **adopted (v6.1)** |

- v6.1 = build with `-DV61` (`model/v61_sim.exe`, `model/v61_brain.exe`). The default build is still the frozen v6 that matches the board bitstream.
- RTL (define `V61`): detector warm-up start and decay in `v6_det`/`v6_mat`; recalibration states in `v6_trk` (CALDATA from the rings, REQ_CAL, cross-fade from the previous weights). xsim: 8/8 records bit-exact with the v6.1 model. Build `build/v61/v61.bit`: 18,986 LUTs, 60 BRAM, WNS +0.41 ns. The protocol does not change.
- Board: 140/140 records bit-exact with the v6.1 model; F1 equal to the model on every set (`report/v61_v7/board_v61/`).
- CinC test was scored once for v6.1 (it had already been used for v5/v6; no v6.1 decision used it).

## 3. Measurements (done 2026-11-14)
- RTL-only compute time: median 1,485 clock cycles per sample after calibration (301 before 10 s), 210.6 ms of simulated time for 30 s of CinC a01, so about 140x real time (`sim/wave/run_wave.sh`, `report/final_report/tools/plot_waves.py`). One-off peak of 1.12 M cycles at the tracker start.
- Output latency per beat: about 1.5-2 s (tracker confirmation plus the selection delay), as in v5.
- Power (Vivado estimate, default activity): 0.374 W on-chip (`report_power_v6.tcl`).

## 4. Local web demo (done 2026-11-14)
- `fpga_implementation/webdemo/` (`server.py` + `index.html`): upload WFDB or CSV, stream to the board in real time, live FHR, board status and stage; accuracy shown when annotations exist. Board only.
- Board check on a01 through the page: F1 95.05, 101 beats, FHR MAE 3.51, identical to `report/rtl_pc_split/board`.
- If the memory changes in section 1 alter the protocol (item 1b), update `server.py` too.

## 5. v7-DL: look-ahead on the FPGA (done 2026-11-14)
- New RTL unit `v7_la` (+ `v7_disp` for the displays). C model `model/v7_post.c` (`-DV7`). Protocol: FLUSH (0x03) down; OUT7 (0x8D) and END7 (0x8E) up.
- Dev (C model): CinC dev 84.68, ADFECGDB 96.10, FECGSYNDB subset 93.39 (v6.1: 80.41 / 92.87 / 91.64). Delay median 13.5 s, max 17.5 s.
- xsim: 9/9 records bit-exact with the model. Build: 26,701 LUTs, 71 BRAM, WNS +0.05 ns.
- The first RTL version did not fit (101% LUTs); shifts, divisions and log2 were made sequential (13.2k -> 8.4k LUTs for the unit).
- Board: 140/140 bit-exact; F1 CinC dev 84.68, ADFECGDB 96.10, CinC test 76.91 (scored once), FECGSYNDB subset 93.39. Web demo with v7 checked on a01 (identical to the model).

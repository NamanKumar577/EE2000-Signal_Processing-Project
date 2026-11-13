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

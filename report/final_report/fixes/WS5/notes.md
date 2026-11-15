# WS5 notes: missing checks that need no board

No RTL, committed model, algorithm or result file was changed. Work copies live in `tools/report_stats/ws5/`
(`neg/` perturbed model + testbench copy, `gevd/` logging-only model copy, `vivado/` strategy sweep).
CinC test was used only for scoring (clinical agreement); every other check uses development sets.
Apply with `venv/Scripts/python.exe report/final_report/fixes/WS5/apply.py` (exact, unique strings; asserts).

## Results (all files in tools/report_stats/out/ws5/)

| Check | Result | Source |
|---|---|---|
| (1a) negative control, board comparison | v7-DL model stream of ADFECGDB r01 = 2,466,548 B, MD5 ee79...6a84 = board CSV MD5; one flipped bit (byte 1,233,274) -> `exact=False`, first difference at the flipped byte | `negctrl_board.txt`, script `tools/report_stats/ws5/negctrl_board.py` |
| (1b) negative control, xsim | LAT_OUT 13 -> 12 in a model copy: testbench reports MISMATCH from byte 99,258 (OUT frame, beat time 0x45 vs 0x46), "too many errors" after 20; unchanged model: 0 byte errors | `negctrl_xsim_lat12.log`, `negctrl_xsim_baseline.log` |
| (2) clinical agreement (+-5 bpm, harness `fhr_within5`, from 20 s) | v7-DL: CinC dev 78.19, CinC test 67.56, ADFECGDB 92.29, FECGSYNDB subset 90.58 %; v6.1: 74.70 / 65.43 / 96.48 / 87.35 % | `agreement.csv`, `agreement_per_record.csv`, script `ws5/agreement.py`. Beats from the C model; F1 equals the board CSV F1 on all 140 records (max diff 1.4e-14) |
| (3) GEVD optimality | 103 dev records, logging copy byte-identical 103/103; 15,610 solves, max rel. |J(w) - lambda_max| = 1.36e-10; median lambda_max/lambda_min 10.70 (1.25-9909.74) | `gevd_check.txt`, `gevd_check.csv`, script `ws5/gevd_check.py` |
| (4) template residual | NOT DONE: sigma^2 (noise in the maternal-band segments) is not observable separately on real data, and on FECGSYNDB the C model sees only the mixture; a valid check needs the canceller output compared with the separately filtered fecg+noise components, i.e. a new instrumented pipeline. Left as "not measured". | -- |
| (5) collision proxy (FPGA maternal peaks) | CinC dev 20.1 % measured vs 20.8 % predicted (mean maternal RR 681 ms, 38 rec.); ADFECGDB 19.8 vs 20.0 % (701 ms, 5 rec.) | `collision_proxy.csv/.txt`, script `ws5/collision_proxy.py` |
| (6) Vivado strategies | DONE (same RTL+XDC; `tools/report_stats/ws5/vivado/strategies_v7.tcl`): Default +0.048 ns (= committed build), Explore -0.078 ns (FAILS timing), ExtraNetDelay_high +0.796 ns. Timing closure depends on the strategy; the committed bitstream (Default) meets timing with +0.048 ns. CSV and timing reports in `out/ws5/`. Register row: C, Sec. hw_summary, "strategy sweep not done" -> 3 strategies, WNS +0.048 / -0.078 / +0.796 ns. apply.py writes "not yet available"; when the log has all STRATEGY lines run `apply_vivado.py --from-log` (writes `out/ws5/vivado_wns.csv`, replaces the sentence, drops "Vivado seed sweeps" from the not-measured list) | `ws5/vivado/vivado.log` |
| (7) spatio-temporal numbers | verified: `tools/accuracy/_taps/results.csv`, CinC dev best track base 84.98, k2d1 87.44, k3d1 88.89; final 85.66 / 84.14 (base 84.68) -> text kept, source added | `taps_cdev.txt` |

If Vivado did not finish, run: `cd tools/report_stats/ws5/vivado && vivado -mode batch -nojournal -log vivado.log -source strategies_v7.tcl`
then `grep STRATEGY vivado.log` and write `vivado_wns.csv` (columns strategy,wns_ns) before applying.

## Register rows (Table 23)
- C: Tab. 1 clinical agreement, final design: "not measured" -> CinC test 67.6 %, CinC dev 78.2 %, ADFECGDB 92.3 %, FECGSYNDB subset 90.6 % (v7-DL); Sec. 2; computed from C-model beats bit-exact with the board (ws5/agreement.py).
- C: Sec. analysis (b): "derived; not checked" -> "derived; checked against data" (J = lambda_max within 1.4e-10, 15,610 solves); logging copy.
- C: Sec. analysis (a): real-data collision rate "not checked" -> proxy 20.1 % (CinC dev) / 19.8 % (ADFECGDB).
- C: Sec. hw_summary: negative control "not done" -> done (board-stream bit flip; xsim with LAT_OUT 12).
- C (if vivado_wns.csv): Vivado strategy sweep "not done" -> 3 strategies, WNS values.
- Limitations "not measured" list shortened accordingly.

## Not done and why
- Template-residual check (4): see table.
- Board power: needs a USB power meter on the Boolean Board.
- Seed sweeps proper: Vivado 7-series has no placer seed option; placement/routing directives are used as strategies instead.

# WS4 notes: untraceable mid-term figures and claims

Apply with `venv/Scripts/python.exe report/final_report/fixes/WS4/apply.py`. The script holds 16 exact replacements; each old string occurs once in fpr-8.tex as of commit 7256a63. Apply it after WS1. If WS1 moves text unchanged the strings still match; if WS1 rewrites Sec. 1 or 5.1, re-check patches 1, 3 and 4. The figures are already regenerated in report/final_report/figures/; do not rerun them out of order.

## Done
- New script `tools/report_stats/fmr_measured.py`, with output in `out/fmr_measured.csv` (per-lead FMR) and `out/amplitude_measured.csv`:
  - Median beat peak-to-peak on the training leads: maternal 1.98, fetal 0.54, a ratio of 3.6× (11.2 dB).
  - FECGSYNDB signals are in normalised units (".hea" files say `3000(0)/nu`), not mV.
  - RMS FMR per abdominal lead is 0.08–0.61 (lead 19 highest); the FMR claim is now traced.
- New script `report/final_report/tools/ws4_figures.py`. It writes into `report/final_report/figures/` only:
  - **Fig. 1:** measured maternal and fetal amplitudes. The EMG and baseline bars were unmeasured and are gone.
  - **Figs. 31, 33, 34** (f1_comparison, snr_curve, heatmap):
    - Single-channel rows come from `code/results/metrics.csv`.
    - The 4-lead PCA and MC-fusion rows come from `code/results/multichannel_scaling_metrics.csv`.
    - The U-Net 1-ch row comes from `code/results/mega_benchmark_results.csv` (sub01, layout l1, TC records). The matrix is saved as `out/ws4_subject1_matrix.csv`.
    - Every value equals the old figure except the U-Net row: 99.7/99.8/99.4/99.6/94.5 became 99.8/100.0/92.2/99.7/86.6.
  - **Fig. 41** (eigen spectrum): drawn from WS3's `out/r3_eigen.csv`. v1 94.0%, v2 5.3%; fetal energy v1 70.7%, v2 25.6%.
  - **Fig. 43** (FPGA scaling): drawn from the analytical-model columns of `multichannel_scaling_metrics.csv`. 4 leads: 1 DSP, 830 LUTs, 3.0% UART.
- `fix_midterm_figures.py` no longer draws Fig. 1 or the heatmap. The run order is fix_midterm_figures.py, then ws4_figures.py.
- **Fig. 30** (quantization sweep): the bound values 95.1, 71.0 and 59.0 dB are evaluations of Eq. null_bound (checked by hand). The "simulation" curve and "empirical 95.0 dB" are marked not traceable, and the 95.0 dB claim is deleted.
- **Fig. 44** (HW trade-off): F1 is traced to `mega_benchmark_summary.csv`; LUTs are marked as untraceable paper estimates; "optimal" is removed.
- **Fig. 45** (radar): marked illustrative and not traceable; the "most balanced profile" claim is removed.
- **A.4.1 and Sec. 5.1:** the typed-in eigen shares are replaced by computed ones. The text now says the data do not support "w = v2 isolates the fetal signal". "Crucially" is removed.
- **Mid-term AI disclosure:** a blue final-phase note follows the "eliminating manual transcription errors" claim. The original sentence and who-did-what are unchanged.
- 95.3% (two-lead planar cancellation in A.4.1) is traced: `multichannel_scaling_metrics.csv`, PCA, 2 leads, TC1, F1 0.9526. No change.

## Register rows (Table 23)
| Item | Old | New | Section | Reason |
|---|---|---|---|---|
| C-W4-1 | 2.50 mV vs 0.04 mV = 62.5× (35.9 dB) measured on FECGSYNDB | 1.98 vs 0.54 normalised units, 3.6× (11.2 dB) | Sec. 1, Fig. 1 | not reproducible from data; FECGSYNDB units are normalised (fmr_measured.py) |
| C-W4-2 | Fig. 1 EMG 0.15 mV and baseline 0.25 mV bars | removed | Fig. 1 | typed-in, not measured |
| C-W4-3 | v1 88.4%, v2 7.8%, v3 2.6%, v4 1.2%, first two 96.2%; v2 holds 15.0% fetal energy | v1 94.0%, v2 5.3%, first two 99.3%; fetal energy v1 70.7%, v2 25.6% | Sec. 5.1, A.4.1, Fig. 41 | typed-in values; computed by r3_eigen.py |
| C-W4-4 | U-Net 1-ch heatmap row 99.7/99.8/99.4/99.6/94.5 | 99.8/100.0/92.2/99.7/86.6 | Figs. 31, 33, 34 | typed row untraceable; mega_benchmark_results.csv sub01 TC records |
| C-W4-5 | empirical null depth 95.0 dB (bit-true simulation) | removed; bound 95.1 dB kept as derived | A.1, Fig. 30 | no result file |
| C-W4-6 | 4 leads <2.2% UART, 100 MHz | 1 DSP, 830 LUTs, 3.0% UART (model, 50 MHz, 11-byte frame) | Fig. 43 | from multichannel_scaling_metrics.csv |
| C-W4-7 | radar scores; "most balanced profile" | marked illustrative, claim removed | Fig. 45 | typed-in heuristic scores |
| C-W4-8 | HW trade-off LUTs presented as estimates of fact; "optimal trade-off" | LUTs marked untraceable paper estimates | Fig. 44 | typed into the figure script |
| F-W4-1 | "w = v2 isolates the fetal dipole" | data do not support it; v2 holds 25.6% of fetal energy | A.4.1 | measured eigen-energy shares |

## Open issues (outside WS4 or not fixable here)
- **Table 5 (master benchmark, appendix):** the U-Net 1-ch row labelled TC1 (712/716/712/0/4, F1 99.72) equals the mega-benchmark TC4 record (sub01 snr06 c1). The rows look mislabelled. WS6 or main should check them against `mega_benchmark_results.csv`; I did not change that table.
- **Sec. 5.1 still reads "Selecting w = v2 extracts the fetal scalar signal".** That is the mid-term description; WS1 moves Sec. 5 to the appendix. A.4.1 now carries the correction.
- **Fig. 1 still says "Signal component amplitude disparity... 10–250× (literature)"** with no citation in the caption; the Sec. 1 text cites abel2023 and sornmo_ecg.
- The regenerated figures were not compiled into the PDF here (main thread compiles).

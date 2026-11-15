# WS4 patch

The exact old -> new LaTeX strings are in `apply.py` (list `P`, 16 entries), so the quoted text cannot drift from what is applied. Each entry, in order:

1. Fig. 1 caption: "measured on FECGSYNDB training leads: $2.50\,$mV vs $0.04\,$mV $= 62.5\times$ / $35.9\,$dB" becomes the measured "maternal 1.98 vs fetal 0.54 (normalised units), 3.6× / 11.2 dB".
2. Fig. 1 caption end: adds a note on the disparity and the [L1] source tag (amplitude_measured.csv, fmr_measured.py, ws4_figures.py).
3. Sec. 1 text: the same 2.50/0.04 mV claim becomes "median beat peak-to-peak ratio is only 3.6×, 11.2 dB, in normalised units".
4. Sec. 5.1: "(capturing 88.4% of total mixture energy)" becomes "94.0% of total mixture variance, mean of the training subjects".
5. Fig. 30 caption: the bound is kept as derived; the simulation curve is marked "Illustrative, not traceable".
6. A.1 text: "In bit-accurate simulation, empirical null depth reaches 95.0 dB" is deleted (no result file).
7. Fig. 31 caption: adds the per-row source tag.
8. Fig. 33 caption: adds the source tag.
9. Fig. 34 caption: "confirming ... dominance" becomes neutral wording, plus the source tag and a note on the U-Net row change.
10. Fig. 41 caption: rewritten with the computed shares (r3_eigen.csv).
11. A.4.1: "Crucially, our" becomes "Our".
12. A.4.1: the typed-in eigen paragraph is replaced by the computed shares and the consequence for w = v2.
13. Fig. 43 caption: becomes the analytical-model values (1 DSP, 830 LUTs, 3.0% UART) with the source.
14. Fig. 44 caption: "optimal trade-off" is removed; F1 is sourced and LUTs are marked as untraceable paper estimates.
15. Fig. 45 caption: "most balanced profile" becomes "Illustrative, not traceable".
16. Sec. 19 (mid-term AI disclosure): a blue final-phase note follows "eliminating manual transcription errors".

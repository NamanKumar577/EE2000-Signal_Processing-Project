#!/usr/bin/env python3
"""WS5 patches (missing checks). Applies exact, unique string replacements to fpr-8.tex and section files.
Run from anywhere:  venv/Scripts/python.exe report/final_report/fixes/WS5/apply.py
Vivado wording is taken from tools/report_stats/out/ws5/vivado_wns.csv if it exists."""
import csv
from pathlib import Path

R = Path(__file__).resolve().parents[2]            # report/final_report
ROOT = R.parents[1]
OUT = ROOT / "tools/report_stats/out/ws5"

viv = OUT / "vivado_wns.csv"
if viv.exists():
    rows = list(csv.DictReader(open(viv)))
    wns = [float(r["wns_ns"]) for r in rows]
    viv_txt = (f"Three placement/routing strategies of v7-DL ({', '.join(r['strategy'] for r in rows)}; same RTL and constraints) "
               f"gave worst setup slack {', '.join(f'{w:+.3f}' for w in wns)}\\,ns (\\texttt{{tools/report_stats/out/ws5/vivado\\_wns.csv}}); "
               f"{'all meet' if min(wns) >= 0 else 'not all meet'} timing at 50\\,MHz.")
    seeds_done = True
else:
    viv_txt, seeds_done = "", False

P = {
 "fpr-8.tex": [
  (r"Clinical agreement ($\pm 5\,$bpm) & $\ge 95\%$ baseline, $>50\%$ overall & not measured for the final design & -- & -- &",
   r"Clinical agreement ($\pm 5\,$bpm) & $\ge 95\%$ baseline, $>50\%$ overall & CinC test $67.6\%$, CinC dev $78.2\%$, ADFECGDB $92.3\%$, FECGSYNDB subset $90.6\%$ & Not met & L5 (C model, bit-exact) & % source: tools/report_stats/out/ws5/agreement.csv"
   "\n"),
  (r"on CinC dev the best single track per record rose from $85.0\%$ to $87.4$--$88.9\%$ F1. The label-free selection kept little of this gain (final F1 $84.1$--$85.7\%$, against $84.7\%$),",
   r"on CinC dev the best single track per record rose from $85.0\%$ to $87.4$--$88.9\%$ F1. The label-free selection kept little of this gain (final F1 $84.1$--$85.7\%$, against $84.7\%$; \texttt{tools/accuracy/\_taps/results.csv}, variants k2d1 and k3d1), % verified: tools/report_stats/out/ws5/taps_cdev.txt"
   "\n"),
 ],
 "sections/analysis.tex": [
  (r"real recordings were not checked because CinC and ADFECGDB have no maternal annotations.",
   r"CinC and ADFECGDB have no maternal annotations, so as a proxy we used the maternal R peaks found by the FPGA itself (v7-DL C model, bit-exact with the board): $20.1\%$ of the fetal reference beats collide on CinC dev (predicted $20.8\%$ from the mean maternal RR of $681\,$ms) and $19.8\%$ on ADFECGDB (predicted $20.0\%$; \texttt{tools/report\_stats/out/ws5/collision\_proxy.csv}). The detector's delay shifts all maternal peaks by a constant, which does not change the expected rate for independent rhythms."),
  (r"\noindent\textbf{(b) GEVD gives the maximum output SNR (derived; not checked against data).}",
   r"\noindent\textbf{(b) GEVD gives the maximum output SNR (derived; checked against data).}"),
  (r"Per-record output-SNR gains of the GEVD filters were not saved, so the bound is not compared with data (not measured).",
   r"A logging-only copy of the C model (output stream byte-identical to the committed model on all 103 development records) recorded every GEVD solve: over 15,610 solves $J(\mathbf{w})$ equals $\lambda_{\max}$ within a relative $1.4\cdot10^{-10}$, and the median ratio $\lambda_{\max}/\lambda_{\min}$ is $10.7$ (range $1.25$--$9{,}910$; \texttt{tools/report\_stats/out/ws5/gevd\_check.txt}). The output SNR of the resulting tracks against the true fetal signal was not measured."),
 ],
 "sections/hardware.tex": [
  (r"\noindent\textbf{Not done.} Vivado seed or strategy sweeps, a word-length study for the final design, a negative control on the bit-exact test (a deliberately corrupted model or bitstream to show that the comparison can fail) and a measurement of board power were not done.",
   (r"\noindent\textbf{Negative controls of the bit-exact test.} (a) Flipping one bit of the v7-DL model stream of ADFECGDB r01 (2,466,548 bytes, MD5 equal to the saved board stream) makes the board-evaluation comparison report a mismatch, first at the flipped byte (\texttt{tools/report\_stats/out/ws5/negctrl\_board.txt}). (b) Changing the latency compensation from 13 to 12 samples in a copy of the C model makes the xsim system testbench report byte mismatches from byte 99,258 (an OUT frame whose beat time is one sample off) and stop after 20 errors, while the unchanged model gives 0 errors (\texttt{negctrl\_xsim\_lat12.log}, \texttt{negctrl\_xsim\_baseline.log}). The comparison can therefore fail and does detect a one-sample model change."
    + ("\n\n\\noindent\\textbf{Implementation strategies.} " + viv_txt if seeds_done else "")
    + "\n\n\\noindent\\textbf{Not done.} "
    + ("A word-length study for the final design" if seeds_done else "Vivado seed or strategy sweeps, a word-length study for the final design")
    + " and a measurement of board power were not done.")),
 ],
 "sections/limitations_items.tex": [
  (r"clinical agreement ($\pm 5\,$bpm) for the final design; board power (only the Vivado on-chip estimate, $0.445\,$W); per-record GEVD output SNR; template-subtraction residual power; Vivado seed sweeps; a word-length study of the final RTL; a negative control for the bit-exact test (a deliberately changed model that the comparison must reject); twins and fetal bradycardia cases.",
   r"board power (only the Vivado on-chip estimate, $0.445\,$W); output SNR of the GEVD tracks against the true fetal signal; template-subtraction residual power; "
   + ("" if seeds_done else "Vivado seed sweeps; ")
   + r"a word-length study of the final RTL; twins and fetal bradycardia cases. Clinical agreement, the GEVD optimality check and the negative controls of the bit-exact test are now measured (Tab.~\ref{tab:clinical_specs}, Secs.~\ref{sec:analysis} and~\ref{sec:hw_summary})."),
 ],
}
for f, reps in P.items():
    p = R / f
    s = p.read_text(encoding="utf-8")
    for old, new in reps:
        assert s.count(old) == 1, (f, old[:70])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8", newline="")
    print("patched", f, len(reps))

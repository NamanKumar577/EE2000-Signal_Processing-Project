"""WS6 consistency audit: applied directly to fpr-8.tex and sections/claims.tex (exact unique strings)."""
from pathlib import Path

R = Path(__file__).resolve().parents[2]
P = R / "fpr-8.tex"
s = P.read_text(encoding="utf-8")


def rep(a, b, text=None):
    global s
    t = s if text is None else text
    n = t.count(a)
    assert n == 1, f"{n}x: {a[:80]}"
    t = t.replace(a, b)
    if text is None:
        s = t
    return t


SPD = r"% speed: record_s / stream_s per record in the board CSVs (tools/report_stats/out/hw_table.csv)"
# 1. speed figures: per-record range and mean of per-record ratios
rep(r"running 4--4.5$\times$ faster than real time",
    r"running on average 4.35$\times$ faster than real time (mean of per-record ratios; per-record range 3.4--5.6$\times$)")
rep(r"board 4--4.5$\times$ real time incl.\ UART and PC",
    r"board 4.35$\times$ real time on average (per-record range 3.4--5.6$\times$) incl.\ UART and PC")
rep(r"With the PC in the loop the v7-DL board runs 3.4--5.6$\times$ faster than real time (v6: 3.7--9.4$\times$,",
    r"With the PC in the loop the v7-DL board runs 3.4--5.6$\times$ faster than real time (\emph{per-record range}: record duration divided by streaming time, per record; \emph{mean of per-record ratios} $4.35\times$; v6: 3.7--9.4$\times$, mean $4.81\times$;")
rep(r"On the board the system runs 4--5$\times$ real time",
    r"On the board v6 runs $4.81\times$ real time on average (per-record range 3.7--9.4$\times$)")
rep(r"the 4--5$\times$ on the board is set by",
    r"the $4.35\times$ on the board (v7-DL, mean of per-record ratios) is set by")
rep(r"board 4--5$\times$ real time incl.\ UART and PC;",
    r"board $4.35\times$ real time on average (per-record range 3.4--5.6$\times$) incl.\ UART and PC;")
rep(r"(RTL $135\times$, board 4--5$\times$ faster)", r"(RTL $135\times$, board $4.35\times$ faster on average)")
rep(r"running on the Spartan-7 board 4--5$\times$ faster than real time,",
    r"running on the Spartan-7 board $4.35\times$ faster than real time on average (per-record range 3.4--5.6$\times$),")
rep(r"50\,MHz, 4--5$\times$ real time;", r"50\,MHz, $4.81\times$ (v6) and $4.35\times$ (v7-DL) real time on average;")

# 2. maternal train claim: dev sets only (traceable)
rep(r"and with v7-DL no CinC record is left without a maternal train (Sec.~\ref{sec:v7_where}).",
    r"and with v7-DL the maternal train is found in all 38 CinC dev and 5 ADFECGDB records (at least 67 maternal R peaks per record; CinC test was not checked). % source: tools/report_stats/out/ws5/collision_proxy.csv (n_maternal)")

# 3. versions of the oracle numbers
rep(r"For v6 on CinC dev the best single track scored $82.6\%$ and a per-window oracle $85.0\%$, against about $75\%$ for the causal choice (Fig.~\ref{fig:fin_gap});",
    r"In the v5 C-model diagnostic (\texttt{tools/accuracy/results\_diag\_v5.csv}, Fig.~\ref{fig:fin_gap}) the best single track on CinC dev scored $82.6\%$ and a per-window oracle $85.0\%$, against about $75\%$ for the causal choice;")
rep(r"7.5\,s of future did (v7-DL $84.7\%$ against $85.0\%$ for the best track on CinC dev).",
    r"7.5\,s of future did (v7-DL dev oracle, Tab.~\ref{tab:selloss}: $84.7\%$ against $85.0\%$ for the best track on CinC dev).")

# 4. duplicated source tag (paired table)
rep(r"(zero differences dropped). Source: \texttt{tools/report\_stats/out/paired.csv}. \textbf{[L5 board / L2]} Source: tools/report\_stats/out/paired.csv.}",
    r"(zero differences dropped). \textbf{[L5 board / L2]} Source: tools/report\_stats/out/paired.csv.}")

# 5. TSpca value: only what could be read
rep(r"TS / TSpca, Behar \etal~\cite{behar2014b} & 68 & 81.6 / 86.1 \\",
    r"TS / TSpca, Behar \etal~\cite{behar2013cinc}$^d$ & 68 & 81.6 / 86.0 \\")
rep(r"$^a$5 records excluded, parameters tuned on set-a. $^b$Median F1.",
    r"$^a$5 records excluded, parameters tuned on set-a. $^b$Median F1. $^d$Table~2 of~\cite{behar2013cinc} (full text read); the TSpca value $86.1\%$ quoted earlier from~\cite{behar2014b} could not be re-read and is not used.")
rep(r"TS $81.6\%$, TSpca $86.1\%$)", r"TS $81.6\%$, TSpca $86.0\%$)")

# 6. appendix Table 5 U-Net rows and Fig. 10 caption
rep(r"\caption{\tagLone/\tagLtwo\ Controlled In-Sample Stress Benchmark on Subject 1",
    r"\caption{\tagLone/\tagLtwo\ \fin{[Final-phase note: the Deep 1D U-Net (1-Ch) rows do not match \texttt{code/results/mega\_benchmark\_results.csv} (e.g.\ TC1 there: 713/716 beats, F1 $99.79\%$; TC3: $92.17\%$; the ``TC1'' row below equals the TC4 record); they came from an evaluation whose output was not saved and are not traceable.]} Controlled In-Sample Stress Benchmark on Subject 1")
rep(r"(\fin{TC1, \texttt{sub01} at 12\,dB; $r = 0.966$ over the record, Tab.~\ref{tab:master_benchmark}})",
    r"(\fin{TC1, \texttt{sub01} at 12\,dB; the $r$ of the U-Net rows in Tab.~\ref{tab:master_benchmark} is not traceable; \texttt{mega\_benchmark\_results.csv} gives $r = 0.790$ for this record})")
rep(r"The U-Net row now comes from the mega-benchmark run;", r"The U-Net row now comes from the 250-record benchmark run;")

# 7. register continuation table
i = s.index(r"\label{tab:register}")
j = s.index(r"\end{table*}", i) + len(r"\end{table*}")
reg2 = r"""

\begin{table*}[t]
\fb
\caption{\fb Register of changes, continued: corrections and design-description changes of the final report revision (15 November). \textbf{[--]} Source: the scripts and result files named in each row (\texttt{tools/report\_stats/}).}
\label{tab:register2}
\centering
\resizebox{\textwidth}{!}{%
\begin{tabular}{@{}p{2.6cm}p{4.0cm}p{4.8cm}p{1.8cm}p{4.6cm}@{}}
\toprule
\textbf{Item} & \textbf{Old} & \textbf{New} & \textbf{Section} & \textbf{Reason / source} \\
\midrule
C-19: power & ``estimated analytically'' & Vivado estimate $0.445\,$W; board not measured & \ref{sec:clinical_specs} & \texttt{build/v7/power.rpt} \\
C-20: latency & $<100\,$ms stated as requirement & original target, re-baselined & \ref{sec:clinical_specs}, \ref{tab:o3o4} & live 1.5--2\,s, final 13.5\,s \\
C-21: intro & FPGA designs ``depend on multi-DSP architectures'' & removed & \ref{sec:intro} & final design uses 43 DSP \\
F-20: structure & Secs.~3--5 on the mid-term beamformer & moved to App.~\ref{app:midterm}; new Secs.~3--4 on the final design & \ref{sec:problem_statement}, \ref{sec:dataset} & main body describes the final design \\
F-21: front end & 0.5--40\,Hz Butterworth + 50/60\,Hz notch & one-pole HP 0.63\,Hz, 4th-order 60\,Hz LP, 5--25\,Hz maternal band, 15--40\,Hz track band, no notch & \ref{sec:dataset} & \texttt{out/front\_end.csv} from \texttt{coef\_q28.h} \\
C-22: references & edwin2022 title/DOI; pani2016; delathauwer2000 DOI & corrected title/DOI; muceli2007; DOI 10.1109/10.841326 & \ref{sec:literature_survey} & old entries did not exist or resolved elsewhere (Crossref) \\
C-23: survey & ``single-DSP edge execution''; ICA ``incompatible'' with FPGA & removed & \ref{sec:literature_survey} & contradicted by our design / unsupported \\
F-22: survey & paradigm list & organised by use in the final design & \ref{sec:literature_survey} & -- \\
C-24: R3 & typed-in shares 88.4/7.8\% & variance 94.0/5.3/0.7/0.0\%; fetal energy 70.7\% in $\mathbf{v}_1$, 25.6\% in $\mathbf{v}_2$ & \ref{sec:replications} & \texttt{out/r3\_eigen.csv} \\
C-25: R5 & mean 59.4\% only & median 61.3\% (mean 59.4\%) & \ref{sec:replications} & same statistic as the published median; \texttt{out/r5\_median.csv} \\
F-23: R8 & -- & Behar TS/TSpca on 68 set-a records: mean 63.9 / 67.8\%, FAIL; tolerance preregistered (commit 6e5e0cd) & \ref{sec:replications} & \texttt{out/behar\_replication\_summary.csv} \\
C-26: summary & 0 of 7 within tolerance & 0 of 8; 2 outside (R5, R8) & \ref{sec:replications} & new row R8 \\
C-27: Fig.~\ref{fig:amplitude_disparity} & 2.50\,mV vs 0.04\,mV $= 62.5\times$; EMG and baseline bars & 1.98 vs 0.54 (normalised units) $= 3.6\times$; typed-in bars removed & \ref{sec:intro} & \texttt{out/amplitude\_measured.csv} \\
C-28: eigen shares & 88.4 / 7.8 / 2.6 / 1.2\% & 94.0 / 5.3 / 0.7 / 0.0\% & App.~\ref{app:midterm} & \texttt{out/r3\_eigen.csv} \\
C-29: Subject-1 figures & U-Net row 99.7/99.8/99.4/99.6/94.5 & 99.8/100.0/92.2/99.7/86.6 & App.~\ref{app:midterm} & \texttt{mega\_benchmark\_results.csv} \\
C-30: null depth & ``empirical 95.0\,dB'' & removed (bound 95.1\,dB kept) & App.~\ref{app:midterm} & no result file \\
C-31: Figs. & UART $<2.2\%$; radar, LUT estimates as facts & from \texttt{multichannel\_scaling\_metrics.csv}; others marked illustrative & App.~\ref{app:midterm} & typed-in values \\
F-24: $\mathbf{w}=\mathbf{v}_2$ & ``isolates the fetal dipole'' & not supported by the data & App.~\ref{app:midterm} & $\mathbf{v}_2$ holds 25.6\% of fetal energy \\
C-32: Tab.~\ref{tab:clinical_specs} & clinical agreement ``not measured'' & v7-DL: CinC test 67.6\%, dev 78.2\%, ADFECGDB 92.3\%, FECGSYNDB subset 90.6\% & \ref{sec:clinical_specs} & \texttt{out/ws5/agreement.csv} \\
C-33: analysis (a), (b) & ``not checked'' & checked: $J = \lambda_{\max}$ within $1.4\cdot10^{-10}$; collision proxy 20.1 / 19.8\% & \ref{sec:analysis} & \texttt{out/ws5/gevd\_check.txt}, \texttt{collision\_proxy.csv} \\
C-34: negative control & not done & bit flip and LAT\_OUT 12 both detected & \ref{sec:hw_summary} & \texttt{out/ws5/negctrl\_*} \\
C-35: speed & ``4--4.5$\times$'' / ``4--5$\times$'' & v7-DL $4.35\times$ mean of per-record ratios, range 3.4--5.6$\times$ (v6 $4.81\times$, 3.7--9.4$\times$) & abstract, \ref{sec:pc_loop}, \ref{sec:conclusions} & board CSVs \\
C-36: maternal train & ``no CinC record left without'' & found in all 38 CinC dev and 5 ADFECGDB records; test not checked & \ref{sec:final_fail} & \texttt{out/ws5/collision\_proxy.csv} \\
C-37: oracle version & ``for v6'' & v5 diagnostic (\texttt{results\_diag\_v5.csv}) & \ref{sec:final_obs} & file is the v5 diagnostic \\
C-38: TSpca & 86.1\% (Behar 2014) & 86.0\% (Behar 2013, Tab.~2) & \ref{sec:v7_literature} & 2014 value could not be re-read \\
C-39: Tab.~\ref{tab:master_benchmark} & U-Net 1-ch rows as measured & flagged not traceable & App.~\ref{app:midterm} & do not match \texttt{mega\_benchmark\_results.csv} \\
\bottomrule
\end{tabular}%
}
\end{table*}"""
s = s[:j] + reg2 + s[j:]
P.write_text(s, encoding="utf-8", newline="")

# 8. claims table rows
C = R / "sections/claims.tex"
c = C.read_text(encoding="utf-8")
rows = r"""Bit-exact comparison detects a single flipped bit and a perturbed model constant (LAT\_OUT 13$\to$12) & \ref{sec:hw_summary} & \ref{tab:hw_summary} & \texttt{tools/report\_stats/out/ws5/negctrl\_board.txt}, \texttt{negctrl\_xsim\_lat12.log} & L2 / L3 \\
Clinical agreement ($\pm 5\,$bpm), v7-DL CinC test $67.6\%$ & \ref{sec:clinical_specs} & \ref{tab:clinical_specs} & \texttt{tools/report\_stats/out/ws5/agreement.csv} & L2 (= L5 beats) \\
GEVD achieves $J(\mathbf{w}) = \lambda_{\max}$ (15,610 solves, rel.\ error $\le 1.4\cdot10^{-10}$) & \ref{sec:analysis} & -- & \texttt{tools/report\_stats/out/ws5/gevd\_check.txt} & L2 \\
Behar TS / TSpca replication: mean $63.9$ / $67.8\%$ on 68 set-a records (FAIL) & \ref{sec:replications} & \ref{tab:replication_scorecard} & \texttt{tools/report\_stats/out/behar\_replication\_summary.csv} & L1 \\
4-lead eigen-energy shares $94.0/5.3/0.7/0.0\%$; fetal energy $70.7\%$ in $\mathbf{v}_1$ & \ref{sec:replications} & \ref{tab:replication_scorecard} & \texttt{tools/report\_stats/out/r3\_eigen.csv} & L1 \\
Maternal-to-fetal amplitude ratio $3.6\times$ on FECGSYNDB (normalised units) & \ref{sec:intro} & -- & \texttt{tools/report\_stats/out/amplitude\_measured.csv} & L1 \\
"""
c = rep(r"\bottomrule", rows + r"\bottomrule", c)
c = rep(r"Board (v7-DL) 3.4--5.6$\times$ faster than real time incl.\ UART and PC (v6: 3.7--9.4$\times$)",
        r"Board (v7-DL) 3.4--5.6$\times$ faster than real time incl.\ UART and PC, mean $4.35\times$ (v6: 3.7--9.4$\times$, mean $4.81\times$)", c)
C.write_text(c, encoding="utf-8", newline="")
print("WS6 applied")

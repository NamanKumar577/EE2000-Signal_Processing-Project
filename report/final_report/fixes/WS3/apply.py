"""WS3 patch: Sec. 13 replication text and table, new reference behar2013cinc. Exact, unique string replacement."""
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "fpr-8.tex"
s = P.read_text(encoding="utf-8")

i = s.index("\\begin{finalpart}\nWe re-implemented seven published methods")
j = s.index("\\end{table*}", i) + len("\\end{table*}")
assert s.count("\\begin{finalpart}\nWe re-implemented seven published methods") == 1

NEW = r"""\begin{finalpart}
We re-implemented seven published methods or ideas from their descriptions (no third-party code) during the mid-term phase, and in this revision added one replication on real data (R8) and recomputed R3 and R5. \Cref{tab:replication_scorecard} compares each with the published value where one exists on a comparable metric and data set.

\noindent\textbf{Tolerance rules.} A result is within tolerance if our beat F1 is within the stated distance of the published F1 for the same data set and the same statistic (mean or median). Rows without a published number on a comparable metric and data set are \emph{qualitative only}. For the original rows R1--R7 the rule was $\pm 2$ points and was fixed after their results were known. For the results added in this revision (R3 recomputation, R5 median, R8) the rule, $\pm 5$ points with the same statistic, record set and $\pm 50\,$ms matching, was written down and committed (\texttt{report/final\_report/fixes/WS3/preregistration.md}, commit \texttt{6e5e0cd}) before the new results were computed. Our values come from \texttt{code/results/metrics.csv}, \texttt{code/results/mega\_benchmark\_results.csv}, \texttt{tools/report\_stats/out/r3\_eigen.csv}, \texttt{r5\_median.csv} and \texttt{behar\_replication\_summary.csv}; published values from the cited papers.

\noindent\textbf{R8: template subtraction on real data.} We re-implemented TS and TSpca from the description in~\cite{behar2013cinc} (same method family as~\cite{behar2014b}): 10--99\,Hz filtering, maternal QRS detection on each channel, a template from 20 aligned maternal cycles (TS) or from the first 2 principal components of 20 cycles (TSpca), fetal QRS detection on each residual and selection of the channel with the smoothest FHR (\texttt{tools/report\_stats/replicate\_behar.py}). On the paper's 68 set-a records (2--58\,s, $\pm 50\,$ms) the mean F1 is $63.9\%$ (TS) and $67.8\%$ (TSpca), against the published $81.6\%$ and $86.0\%$ (\cite{behar2013cinc}, Tab.~2): both are outside tolerance. The result is bimodal: the medians are $89.3\%$ and $89.8\%$, the records that work score $91$--$94\%$ on average, and 27 (TS) and 24 (TSpca) of the 68 records fall below $50\%$. The paper does not specify the QRS detector bands, thresholds, cycle window or template scaling; our choices for these make whole records fail (wrong channel or a detector locked onto the maternal residual), so R8 does not test the published result itself. For comparison, v7-DL scores $84.0\%$ on the same 68 records. % sources: tools/report_stats/out/behar_replication_summary.csv, behar_replication_per_record.csv

\noindent\textbf{R3 recomputed.} On the training subjects (\texttt{sub01}--\texttt{sub07}, 12\,dB, l1, c0) the 4-lead covariance of leads $[27, 26, 28, 25]$ puts $94.0\%$, $5.3\%$, $0.7\%$ and $0.0\%$ of the variance in $\mathbf{v}_1$--$\mathbf{v}_4$ (the mid-term figure used typed-in values $88.4\%$ and $7.8\%$), and the fetal component's energy falls $70.7\%$ in $\mathbf{v}_1$ and $25.6\%$ in $\mathbf{v}_2$. The data therefore do not support the mid-term statement that the fetal signal is isolated in $\mathbf{v}_2$. % source: tools/report_stats/out/r3_eigen.csv

\noindent\textbf{Summary: 0 of 8 within tolerance, 0 explained, 2 outside tolerance (R5, R8), 5 qualitative only, 1 not run (R7).}
\end{finalpart}

\begin{table*}[t]
\fb
\caption{\fb Replication scorecard. R1--R7: mid-term re-implementations, verdicts by the $\pm 2$-point rule fixed after the results were known; R3 (recomputed), R5 (median) and R8: added in this revision, verdicts by the $\pm 5$-point rule committed before these results were computed (Sec.~\ref{sec:replications}). \textbf{[L1]} Source: \texttt{code/results/metrics.csv}, \texttt{code/results/mega\_benchmark\_results.csv}, \texttt{tools/report\_stats/out/r3\_eigen.csv}, \texttt{r5\_median.csv}, \texttt{behar\_replication\_summary.csv}.}
\label{tab:replication_scorecard}
\centering
\resizebox{\textwidth}{!}{%
\begin{tabular}{@{}lp{2.3cm}p{4.0cm}p{3.6cm}p{3.6cm}p{1.2cm}p{3.6cm}@{}}
\toprule
\textbf{ID} & \textbf{Study} & \textbf{Published value (data set, metric)} & \textbf{Our setup} & \textbf{Our value} & \textbf{Tol.} & \textbf{Verdict and cause} \\
\midrule
R1 & Ahlstrom \etal~\cite{ahlstrom1985} & Filter design only; no detection metric & 4 SOS (8th-order) Butterworth bandpass 0.5--40\,Hz, $f_s = 250\,$Hz & $>56\,$dB at 0.1\,Hz, $>18\,$dB at 60\,Hz (computed from the coefficients) & -- & \textbf{QUALITATIVE ONLY}: design reproduced, nothing to compare \\
R2 & Kanjilal \etal~\cite{kanjilal1997} & Qualitative extraction on real single-lead recordings; no F1 & Hankel SVD, rank-2 subtraction, one lead & TC1 $76.4\%$, TC3 $23.7\%$ & -- & \textbf{QUALITATIVE ONLY}: collapse at low SNR seen, no published F1 \\
R3 & De Lathauwer \etal~\cite{delathauwer2000} & Qualitative BSS on real cutaneous recordings & 4-lead covariance eigen-decomposition, \texttt{sub01}--\texttt{sub07} & variance in $\mathbf{v}_1$--$\mathbf{v}_4$: $94.0$ / $5.3$ / $0.7$ / $0.0\%$; fetal energy $70.7\%$ in $\mathbf{v}_1$, $25.6\%$ in $\mathbf{v}_2$ & -- & \textbf{QUALITATIVE ONLY}: fetal signal not isolated in $\mathbf{v}_2$ (contradicts the mid-term claim) \\
R4 & Widrow \etal~\cite{widrow1975}, Hasan \etal~\cite{hasan2009} & Reference-free single-lead adaptive cancellation described as unreliable; no F1 & SWT + LMS + SSNF on one lead & TC1 $15.1\%$, FHR MAE $46.6\,$bpm & -- & \textbf{QUALITATIVE ONLY}: failure mechanism consistent \\
R5 & Andreotti \etal~\cite{andreotti2016} & FECGSYNDB, template subtraction, median F1 $96.0\%$ ($\pm 50\,$ms) & Fixed ensemble template on one lead, mid-term detector, 250 records & median $61.3\%$ (mean $59.4\%$); TC1 $76.4\%$, TC3 $23.9\%$ & $\pm 5$ & \textbf{FAIL}: same statistic now, still $34.7$ points below; our single-lead fixed-template implementation with the mid-term detector is far weaker than the published methods \\
R6 & Ronneberger \etal~\cite{ronneberger2015} & 2D U-Net, image segmentation; no ECG metric & 1D U-Net, test subjects \texttt{sub09}--\texttt{sub10} & test $83.9\%$ (1-ch), $97.5\%$ (4-ch) & -- & \textbf{QUALITATIVE ONLY}: architecture adapted; training split not verifiable \\
R7 & Widrow \etal~\cite{widrow1975} & ANC with a thoracic maternal reference; no FECGSYNDB F1 in this paper & planned: NLMS with thoracic lead 32 & no in-house result & -- & \textbf{NOT RUN} \\
R8 & Behar \etal~\cite{behar2013cinc} & CinC 2013 set-a, 68 records, mean F1 (Tab.~2, 10-Hz high-pass): TS $81.6\%$, TSpca $86.0\%$ & TS / TSpca from the paper's description, lowest-SMI channel, $\pm 50\,$ms, 2--58\,s & mean $63.9\%$ / $67.8\%$; median $89.3\%$ / $89.8\%$; 27 / 24 records below $50\%$ & $\pm 5$ & \textbf{FAIL}: bimodal; unspecified detector and channel-selection details (our choices) make whole records fail \\
\bottomrule
\end{tabular}%
}
\end{table*}"""
s = s[:i] + NEW + s[j:]

BIB = r"""\bibitem{behar2013cinc}
J.~Behar, J.~Oster, and G.~D. Clifford.
\newblock Non-invasive {FECG} extraction from a set of abdominal sensors.
\newblock In {\em Computing in Cardiology}, volume~40, pages 297--300, 2013. \url{https://physionet.org/files/challenge-2013/1.0.0/papers/0297.pdf}

"""
assert "behar2013cinc}" not in s.split("\\begin{thebibliography}")[1]
k = s.index("\\end{thebibliography}")
s = s[:k] + BIB + s[k:]
P.write_text(s, encoding="utf-8", newline="")
print("WS3 patch applied")

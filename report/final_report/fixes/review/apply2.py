from pathlib import Path

p = Path(__file__).resolve().parents[2] / "fpr-8.tex"
s = p.read_text(encoding="utf-8")
pairs = [
    (r"120\,s; \texttt{tools/pc\_link\_traffic.py})", r"120\,s; \texttt{report/final\_report/tools/pc\_link\_traffic.py})"),
    (r"Link traffic is about 9.4\,KB/s down and 7.2\,KB/s up per second of recording, so the 921,600-baud link allows up to about $10\times$ real time.",
     r"Link traffic of v6 is about 9.4\,KB/s down and 7.2\,KB/s up per second of recording (report/rtl\_pc\_split/LOG.md, lines 47--50), so the 921,600-baud link allows up to about $10\times$ real time."),
    (r"Vivado, 50\,MHz; slack $+0.26$ / $+0.41$ / $+0.05\,$ns \\",
     r"Vivado, 50\,MHz; slack $+0.26$ / $+0.41$ / $+0.05\,$ns (Default strategy; Sec.~\ref{sec:hw_summary}) \\"),
]
rows = r"""C-40: App.~A host interface & ``mid-term and final system'' & mid-term only (no AFE in either) & App.~\ref{app:midterm} & final design calibrates at 15\,s, streams 64-sample frames \\
C-41: F-10 & v6 resources as final, ``timing met'' & v7-DL 26,701 LUT, 43 DSP, 71/75 BRAM, $+0.048\,$ns, Default strategy only & Tab.~\ref{tab:register} & \texttt{build/v7/util.rpt}, \texttt{timing.rpt}, \texttt{out/ws5/vivado\_wns.csv} \\
C-42: Fig.~\ref{fig:fin_arch}, Fig.~\ref{fig:fin_resources} & ``Final architecture (v6)''; ``each hardware version'' & architecture of v6; v2/v5/v6 only & \ref{sec:final_hw} & v6.1 / v7-DL add units \\
C-43: Tab.~\ref{tab:v61_ideas} source & \texttt{results\_devbench\_v6.csv} & \texttt{report/v61\_v7/LOG.md} 28--38 & \ref{sec:v61} & CSV was overwritten by the v7 run \\
C-44: Tab.~\ref{tab:final_resources} first build & v6 build reports & \texttt{report/rtl\_pc\_split/LOG.md} 102--133 & \ref{sec:final_hw} & no Vivado report of that build on disk \\
C-45: source paths & \texttt{fpga\_implementation/v2}; \texttt{tools/pc\_link\_traffic.py} & \texttt{reports/multichannel\_out/}; \texttt{report/final\_report/tools/} & \ref{sec:final_hw}, \ref{sec:pc_loop} & wrong paths \\
C-46: board speed v6.1/v7-DL & ``4.0--4.5$\times$ for both'' & per-set 4.04--4.54 / 3.99--4.53$\times$; per record 3.4--5.6$\times$ & \ref{sec:v7_results} & board CSVs \\
C-47: RTL speed & ``about $140\times$'' & $142\times$ whole run, $135\times$ median & \ref{sec:final_waves} & two definitions \\
C-48: timing claims & ``timing met'' & met with the Default strategy only & Tab.~\ref{tab:clinical_specs}, Tab.~\ref{tab:claims} & Explore $-0.078\,$ns \\
C-49: literature headline & $84.0\%$, ``runs causally'' & held-out $82.0\%$ first; 84.0 includes 35 dev records; ``fixed delay'' & \ref{sec:v7_literature} & tuning overlap \\
C-50: clinical agreement status & not met & partly met & Tab.~\ref{tab:clinical_specs} & all sets $>50\%$ \\
C-51: TSpca-ICA / fusion source & \cite{behar2014b} & \cite{behar2013cinc} Tab.~2 & Tab.~\ref{tab:v7_literature} & values verified there \\
C-52: references & hasan2009, callaerts1990 DOIs; Zaunseder ``F.''; cerutti1986 4 authors & corrected DOIs; S.~Zaunseder; 7 authors; Vantrappen, Janssens added & bibliography & Crossref \\
"""
for a, b in pairs:
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
i = s.index("\\label{tab:register2}")
j = s.index("\\bottomrule", i)
s = s[:j] + rows + s[j:]
p.write_text(s, encoding="utf-8", newline="")
print("ok")

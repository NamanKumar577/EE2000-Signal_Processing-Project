"""Fixes for the independent review (items 1-26). Exact unique string replacements."""
from pathlib import Path

R = Path(__file__).resolve().parents[2]


def patch(fn, pairs):
    p = R / fn
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (fn, n, a[:80])
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8", newline="")
    print("patched", fn, len(pairs))


T = "fpr-8.tex"
patch(T, [
    # 1 App. A host interface: mid-term only
    (r"\fin{In the mid-term and the final system}, physical AFE and ADC hardware are modeled rather than physically built; 16-bit signed samples are assumed.",
     r"In the mid-term system, physical AFE and ADC hardware are modeled rather than physically built; 16-bit signed samples are assumed \fin{(no analogue front end was built for the final design either; everything else in this subsection describes the mid-term design only)}."),
    # 2 F-10, F-12
    (r"F-10: Clock / resources & 100\,MHz, 990 LUT, 1 DSP (sized) & 50\,MHz, 18.1k LUT, 33 DSP, 60/75 BRAM (measured) & -- & Real design, timing met \\",
     r"F-10: Clock / resources & 100\,MHz, 990 LUT, 1 DSP (sized) & v7-DL: 50\,MHz, 26,701 LUT, 43 DSP, 71/75 BRAM, slack $+0.048\,$ns with the Default strategy (v6: 18,127 LUT, 33 DSP, 60/75 BRAM) & Sec.~\ref{sec:hw_summary} & Real design; timing met with the Default strategy only (Explore fails at $-0.078\,$ns) \\ % build/v7/util.rpt, timing.rpt; out/ws5/vivado_wns.csv"),
    (r"F-12: Demonstration & 7-segment display and switch presets & Live web page with board status, stages, FHR and accuracy & -- & Any recording can be shown \\",
     r"F-12: Demonstration & 7-segment display and switch presets & Live web page with board status, stages, FHR and accuracy; the v7-DL RTL also drives the 7-segment displays (\texttt{v7\_disp.v}; not confirmed by looking at the board) & Sec.~\ref{sec:final_demo} & Any recording can be shown \\"),
    # 3 architecture caption, resources caption
    (r"\caption{\fb Final architecture (v6).", r"\caption{\fb Architecture of v6 (v6.1 and v7-DL add units to it, Sec.~\ref{sec:final_v7})."),
    (r"\caption{\fb FPGA utilisation of each hardware version. v2 needed little logic",
     r"\caption{\fb FPGA utilisation of v2, v5 and v6 (v6.1 and v7-DL: Tabs.~\ref{tab:v7_hw} and~\ref{tab:hw_summary}). v2 needed little logic"),
    # 6 v2 path
    (r"Source: fpga\_implementation/v2, v5 and v6 build reports.}",
     r"Source: fpga\_implementation/reports/multichannel\_out/ (v2), fpga\_implementation/v5 and v6/build reports.}"),
    # 4 v6.1 ideas source
    (r"Each row adds to the adopted rows above it. \textbf{[L2 C model]} Source: tools/accuracy/results\_devbench\_v6.csv.}",
     r"Each row adds to the adopted rows above it. \textbf{[L2 C model]} Source: report/v61\_v7/LOG.md, lines 28--38 (the per-record file results\_devbench\_v6.csv was later overwritten and now holds the v7-DL synthetic run).}"),
    (r"and the learned selector lost 0.5 on CinC dev (Tab.~\ref{tab:v61_ideas}), so the v6 selector was kept. After idea 1 the causal choice still lost about 5 points to the best single track (CinC dev $79.5$ against $84.7$, FECGSYNDB subset $91.1$ against $96.6$).",
     r"and the learned selector lost 0.5 on CinC dev (Tab.~\ref{tab:v61_ideas}; source report/v61\_v7/LOG.md), so the v6 selector was kept. After idea 1 the causal choice still lost about 5 points to the best single track (CinC dev $79.5$ against $84.7$, FECGSYNDB subset $91.1$ against $96.6$; diagnostic table in report/v61\_v7/LOG.md, lines 44--49)."),
    # 5 final_resources first build source
    (r"\textbf{[L4 Vivado]} Source: fpga\_implementation/v6/build/ utilisation, timing and power reports.}",
     r"\textbf{[L4 Vivado]} Source: shared-BRAM column fpga\_implementation/v6/build/ utilisation, timing and power reports; first-build column report/rtl\_pc\_split/LOG.md, lines 102--133 (no Vivado report of that build is on disk).}"),
    # 7 text numbers with sources
    (r"It reaches only $60\%$ mean F1, and $65\%$ when causal maternal template subtraction is applied first.",
     r"It reaches only $60\%$ mean F1, and $65\%$ when causal maternal template subtraction is applied first (tools/accuracy/README.md, lines 89--90; per-record file not on disk)."),
    (r"165,000 samples with 0 LSB difference from the model and 1,116 beats with identical time stamps.",
     r"165,000 samples with 0 LSB difference from the model and 1,116 beats with identical time stamps (validation/v2\_hardware\_20261107/README.md)."),
    (r"Tab.~\ref{tab:final_versions} and the development logs.}",
     r"Tab.~\ref{tab:final_versions}, Sec.~\ref{sec:final_realdata} (evaluation rules) and report/v61\_v7/LOG.md.}"),
    # 8 speed sentence
    (r"the board runs 4.0--4.5$\times$ faster than real time for both versions.",
     r"per data set the board runs 4.04--4.54$\times$ (v7-DL) and 3.99--4.53$\times$ (v6.1) faster than real time (total record time / total streaming time per set); per record the v7-DL range is 3.4--5.6$\times$, mean $4.35\times$. % board_v7 / board_v61 CSVs, record_s / stream_s"),
    # 9 RTL speed
    (r"so the RTL alone runs about $140\times$ faster than real time (about 7\,ms of FPGA time per second of signal).",
     r"so over the whole run the RTL alone is about $142\times$ faster than real time (about 7\,ms of FPGA time per second of signal); after calibration the median of 1,485 cycles per sample gives $135\times$ (Tab.~\ref{tab:hw_margin})."),
    # 10 Tab. 1 clock row
    (r"Clock & Boolean Board & $50\,$MHz (PLL), worst slack $+0.05\,$ns & Met & L4 & $100\,$MHz target (sized) \\",
     r"Clock & Boolean Board & $50\,$MHz (PLL), worst slack $+0.05\,$ns with the Default strategy (Explore: $-0.078\,$ns) & Met with the Default strategy & L4 & $100\,$MHz target (sized) \\"),
    # 12 clinical agreement status
    (r"FECGSYNDB subset $90.6\%$ & Not met & L5 (C model, bit-exact) &",
     r"FECGSYNDB subset $90.6\%$ & Partly met ($>50\%$ overall met; $95\%$ baseline not met) & L5 (C model, bit-exact) &"),
    # 11 + 13 literature text
    (r"v7-DL is the only method in the table that runs causally on hardware, and under that stricter setting it scores $84.0\%$ on real CinC data, at the level of the classic template-subtraction methods that filter the whole record offline (TS $81.6\%$, TSpca $86.0\%$); the best offline methods score about 10 points higher. On ADFECGDB ($96.1\%$) and FECGSYNDB (median $99.8\%$) v7-DL is within the published range.",
     r"v7-DL is the only method in the table that runs on hardware with a fixed delay. On the 33 held-out records with reliable references it scores $82.0\%$; the $84.0\%$ on all 68 reliable records includes the 35 CinC dev records the design was developed on. Both are at the level of the classic template-subtraction methods that filter the whole record offline (TS $81.6\%$, TSpca $86.0\%$); the best offline methods score about 10 points higher. On ADFECGDB ($96.1\%$) and FECGSYNDB (median $99.8\%$ over all 1,248 records) v7-DL is within the published range."),
    # 21 behar2014b values
    (r"TSpca-ICA / fusion, Behar \etal~\cite{behar2014b} & 68 & 93.0 / 96.0 \\",
     r"TSpca-ICA / fusion, Behar \etal~\cite{behar2013cinc}$^d$ & 68 & 93.0 / 96.0 \\"),
    # 23, 24 footnotes
    (r"$^d$Table~2 of~\cite{behar2013cinc} (full text read); the TSpca value $86.1\%$ quoted earlier from~\cite{behar2014b} could not be re-read and is not used.",
     r"$^d$Table~2 of~\cite{behar2013cinc} (full text read; fusion = FUSE-SMOOTH); the TSpca value $86.1\%$ quoted earlier from~\cite{behar2014b} could not be re-read and is not used. QRStree~\cite{zhong2019} excludes 3 channels on ADFECGDB. Values of~\cite{jaeger2024,asadi2026,shokouhmand2023} and the medians of~\cite{andreotti2016} were not re-checked against the papers."),
    # 15-18 bibliography
    (r"\url{https://doi.org/10.1186/1477-3155-7-3}", r"\url{https://doi.org/10.1007/s12575-009-9006-z}"),
    (r"D.~Callaerts, B.~De~Moor, J.~Vandewalle, and W.~Sansen.", r"D.~Callaerts, B.~De~Moor, J.~Vandewalle, W.~Sansen, G.~Vantrappen, and J.~Janssens."),
    (r"\url{https://doi.org/10.1007/BF02442682}", r"\url{https://doi.org/10.1007/BF02442670}"),
    (r"F.~Andreotti, J.~Behar, F.~Zaunseder, J.~Oster, and G.~D. Clifford.", r"F.~Andreotti, J.~Behar, S.~Zaunseder, J.~Oster, and G.~D. Clifford."),
    (r"S.~Cerutti, G.~Baselli, S.~Civardi, and E.~Ferrazzi.", r"S.~Cerutti, G.~Baselli, S.~Civardi, E.~Ferrazzi, A.~M. Marconi, M.~Pagani, and G.~Pardi."),
])

# claims table timing
patch("sections/claims.tex", [
    (r"Timing met at 50\,MHz (worst slack $+0.05\,$ns, v7-DL)",
     r"Timing met at 50\,MHz with the Default strategy (worst slack $+0.05\,$ns, v7-DL; Explore fails at $-0.078\,$ns)"),
    (r"synthesis logs (\path{report/v61_v7/LOG.md}); xsim regression",
     r"\path{report/v61_v7/LOG.md} line 215 (no Vivado report of the 13.2k build on disk); xsim regression"),
])

# level tags on section tables
patch("sections/hardware.tex", [
    (r"\caption{\fb Re-baselined mid-term objectives O3 and O4 (\cref{tab:objective_status}).}",
     r"\caption{\fb Re-baselined mid-term objectives O3 and O4 (\cref{tab:objective_status}). \textbf{[L3/L4/L5]} Source: \texttt{tools/report\_stats/out/hw\_table.csv}, Tab.~\ref{tab:hw_margin}.}"),
    (r"\caption{\fb Margins of the final design.", r"\caption{\fb \textbf{[L3/L4/L5]} Margins of the final design."),
])
patch("sections/analysis.tex", [
    (r"Source: \texttt{tools/report\_stats/out/selection\_loss.csv}.}",
     r"\textbf{[L2 C model]} Source: \texttt{tools/report\_stats/out/selection\_loss.csv}.}"),
])

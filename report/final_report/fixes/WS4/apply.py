#!/usr/bin/env python3
"""WS4 patch: apply to report/final_report/fpr-8.tex (each old string must occur exactly once)."""
from pathlib import Path

TEX = Path(__file__).resolve().parents[2] / "fpr-8.tex"
P = [
# Fig. 1 caption: untraceable 2.50 mV / 0.04 mV replaced by the measured ratio (normalised units)
(r"measured on FECGSYNDB training leads: $2.50\,$mV vs $0.04\,$mV $= 62.5\times$ / $35.9\,$dB; RMS FMR",
 r"\fin{measured on the FECGSYNDB training leads (median beat peak-to-peak, normalised units): maternal $1.98$ vs fetal $0.54$, $3.6\times$ / $11.2\,$dB}; RMS FMR"),
(r"ranges from \fin{$0.08$ to $0.61$, $-21.6$ to $-4.3\,$dB}), illustrating why linear single-channel frequency filtering fails.}",
 r"ranges from \fin{$0.08$ to $0.61$, $-21.6$ to $-4.3\,$dB}), illustrating why linear single-channel frequency filtering fails. \fin{The synthetic database has a far smaller amplitude disparity than the literature range. [L1] Source: \texttt{tools/report\_stats/out/amplitude\_measured.csv} (\texttt{tools/report\_stats/fmr\_measured.py}); figure by \texttt{report/final\_report/tools/ws4\_figures.py}.}}"),
# Sec. 1 text
(r"measured on FECGSYNDB training leads: $2.50\,$mV vs $0.04\,$mV $= 62.5\times$ or $35.9\,$dB)",
 r"\fin{on the FECGSYNDB training leads the median beat peak-to-peak ratio is only $3.6\times$, $11.2\,$dB, in the database's normalised units; Fig.~\ref{fig:amplitude_disparity}})"),
# Sec. 5.1 eigen share (typed-in 88.4%)
(r"(capturing $88.4\%$ of total mixture energy)",
 r"(capturing \fin{$94.0\%$} of total mixture \fin{variance, mean of the training subjects; Fig.~\ref{fig:eigen_spectrum}})"),
# Fig. quantization sweep
(r"against bit-true simulation. Target format ($B=16$) achieves $95.1\,$dB nulling, safely exceeding the $55\,$dB clinical requirement.}",
 r"against bit-true simulation. Target format ($B=16$): \fin{bound $95.1\,$dB, computed from Eq.~\ref{eq:null_bound}, above the $55\,$dB requirement. [L2] Illustrative, not traceable: the simulation curve was typed into the mid-term figure script and no result file exists.}}"),
(r"In bit-accurate simulation, empirical null depth reaches $95.0\,$dB (Fig.~\ref{fig:quantization_sweep}), safely exceeding the $55\,$dB requirement",
 r"\fin{The simulation curve of Fig.~\ref{fig:quantization_sweep} cannot be traced to a result file, so no simulated null depth is reported; the bound exceeds the} $55\,$dB requirement"),
# Fig. F1 comparison, SNR curve, heatmap: now drawn from result files
(r"Deep U-Net bars represent in-sample baseline on Subject 1.}",
 r"Deep U-Net bars represent in-sample baseline on Subject 1. \fin{[L1] Source: \texttt{code/results/metrics.csv} (single-channel methods), \texttt{code/results/multichannel\_scaling\_metrics.csv} (4-lead PCA and MC fusion), \texttt{code/results/mega\_benchmark\_results.csv} (U-Net, the sub01 records of TC1--TC5, a separate run); drawn by \texttt{report/final\_report/tools/ws4\_figures.py}.}}"),
(r"Spatial PCA maintains $100\%$ detection down to $0\,$dB on Subject 1, while single-channel baselines degrade to $<25\%$.}",
 r"Spatial PCA maintains $100\%$ detection down to $0\,$dB on Subject 1, while single-channel baselines degrade to $<25\%$. \fin{[L1] Source: as Fig.~\ref{fig:f1_comparison} (TC1--TC3).}}"),
(r"confirming Spatial PCA and Deep U-Net dominance on Subject 1.}",
 r"\fin{with Spatial PCA and Deep U-Net highest on Subject 1. [L1] Source: as Fig.~\ref{fig:f1_comparison}; values in \texttt{tools/report\_stats/out/ws4\_subject1\_matrix.csv}. The U-Net row now comes from the mega-benchmark run; the earlier typed-in row ($99.7$, $99.8$, $99.4$, $99.6$, $94.5\%$) could not be traced.}}"),
# Fig. eigen spectrum: computed shares (WS3)
(r"\caption{\tagLone\ Covariance eigen-spectrum and torso subspace dimensionality: (a)~4-Lead covariance eigen-spectrum ($[27, 26, 28, 25]$), showing maternal dipole energy concentrated in $\mathbf{v}_1$ ($88.4\%$) and fetal signal in $\mathbf{v}_2$ ($7.8\%$); (b)~Cumulative explained variance across 4-lead and 8-lead arrays, confirming that the first two components capture $>96\%$ of mixture variance.}",
 r"\caption{\tagLone\ \fin{Covariance eigen-structure of the 12-dB mixture on leads $[27, 26, 28, 25]$, mean of the training subjects \texttt{sub01}--\texttt{sub07} (dots: subjects): (a)~share of the mixture variance, $\mathbf{v}_1$ $94.0\%$, $\mathbf{v}_2$ $5.3\%$, first two $99.3\%$; (b)~share of the fetal signal energy, $\mathbf{v}_1$ $70.7\%$, $\mathbf{v}_2$ $25.6\%$. [L1] Source: \texttt{tools/report\_stats/out/r3\_eigen.csv} (\texttt{tools/report\_stats/r3\_eigen.py}); replaces typed-in values.}}"),
# A.4.1
(r"Crucially, our beamformer employs a heuristic",
 r"\fin{Our} beamformer employs a heuristic"),
(r"Empirical evaluation on training records confirms that $\mathbf{v}_1$ accounts for $88.4\%$ of total mixture variance and holds $82.6\%$ of overlapping maternal energy, whereas $\mathbf{v}_2$ (capturing $7.8\%$ of total variance) contains $15.0\%$ of fetal signal energy while attenuating $\mathbf{v}_1$ maternal spikes. Eigenvectors $\mathbf{v}_3$ ($2.6\%$) and $\mathbf{v}_4$ ($1.2\%$) are dominated by high-frequency EMG noise. The first two components together capture $96.2\%$ of total energy (Fig.~\ref{fig:eigen_spectrum}).",
 r"\fin{Computed on the training subjects (12-dB mixture, Fig.~\ref{fig:eigen_spectrum}), $\mathbf{v}_1$ accounts for $94.0\%$ of the mixture variance and $\mathbf{v}_2$ for $5.3\%$ (first two: $99.3\%$), but $\mathbf{v}_1$ also holds $70.7\%$ of the fetal energy and $\mathbf{v}_2$ only $25.6\%$. The earlier values ($88.4\%$, $7.8\%$, $82.6\%$, $15.0\%$, $96.2\%$) had been typed into the figure script and could not be reproduced. The data therefore do not support the claim that $\mathbf{w} = \mathbf{v}_2$ isolates the fetal signal; the projection mainly removes the maternal axis.}"),
# Fig. FPGA scaling: from the study's analytical model file
(r"\caption{\tagLtwo/\tagLfour\ Hardware resource scaling and UART bus utilization across lead counts on Spartan-7 at 100\,MHz target clock. A 4-lead array requires only 1 DSP slice and consumes $<2.2\%$ of UART throughput at 921,600 baud.}",
 r"\caption{\tagLtwo/\tagLfour\ \fin{Analytical resource model of the mid-term beamformer across lead counts (a model, not synthesis). With 4 leads the model gives 1 DSP slice, 830 LUTs and $3.0\%$ UART use at 921,600 baud (11-byte frame; the earlier $<2.2\%$ counted the 8-byte payload only). [L4 target, model] Source: \texttt{code/results/multichannel\_scaling\_metrics.csv} (\texttt{calculate\_fpga\_metrics} in \texttt{src/fecg/pipelines/multichannel\_study.py}, 50\,MHz); figure by \texttt{report/final\_report/tools/ws4\_figures.py}.}}"),
# Fig. HW trade-off
(r"Spatial PCA (4-Ch) provides the optimal trade-off: 93.00\% population mean F1 consuming $\approx 3.0\%$ LUTs (990 of 32,600) and 1 DSP slice on XC7S50.}",
 r"\fin{Spatial PCA (4-Ch): $93.00\%$ population mean F1 at a paper estimate of 990 LUTs and 1 DSP slice. [L1 / L4 target] Source: F1 from \texttt{code/results/mega\_benchmark\_summary.csv}; the LUT values are paper estimates typed into the figure script and are not traceable to a synthesis report.}}"),
# Fig. radar
(r"Spatial PCA offers the most balanced profile for edge FPGA implementation.}",
 r"\fin{Illustrative, not traceable: the axis scores were typed into the mid-term figure script; they are not used anywhere else in the report.}}"),
# Mid-term AI disclosure: factual note after the audit claim (who-did-what unchanged)
(r"directly against raw CSV outputs, eliminating manual transcription errors.",
 r"directly against raw CSV outputs, eliminating manual transcription errors. \fin{(Final-phase note: these checks covered the tables and text they were written for; several mid-term figures were still drawn from values typed into the figure script, see App.~\ref{app:midterm}.)}"),
]


def main():
    s = TEX.read_text(encoding="utf-8")
    for old, new in P:
        n = s.count(old)
        assert n == 1, f"{n}x: {old[:80]}"
        s = s.replace(old, new)
    TEX.write_text(s, encoding="utf-8", newline="")
    print(f"WS4: applied {len(P)} replacements")


if __name__ == "__main__":
    main()

# Final project report (FPR-8)

| File | What it is |
|---|---|
| `fpr-8.pdf` | Final report. Mid-term text is black; everything new is blue. |
| `fpr-8.tex` | LaTeX source (same IEEE CVF template as the mid-term: `cvpr.sty`, `numbers.tex`). |
| `AI_PROMPTS.pdf` | AI prompts (course requirement): Part A Antigravity, Part B Claude Code, each prompt tagged with the team member it belongs to. Goes to the top of `fpr-8.zip`. |
| `AI_PROMPTS.tex` | LaTeX source of `AI_PROMPTS.pdf`. |
| `figures/` | Mid-term figures plus the new ones: results `fin_*.png`, simulation waveforms `wave_*.png`. |
| `tables/` | `board_f1_ci.csv` (v6 confidence intervals), `board_v7_f1_ci.csv` (v6.1 and v7-DL), `cinc_failures.csv` (failure analysis per CinC record), `v7_delay_sweep.csv` (v7-DL F1 against output delay, dev sets). |

| Script (`tools/`) | What it does |
|---|---|
| `make_final_figures.py` | Result figures `fin_*.png` from the saved result CSVs (`--trace` also redraws the r01 FHR trace with the C model). |
| `plot_waves.py` | Simulation figures `wave_*.png` from the xsim VCD (`fpga_implementation/v6/sim/wave/run_wave.sh`); also prints cycles per sample. |
| `make_v7_figures.py` | Figures of the v6.1 / v7 section (`fin_v7_*.png`) and the v6.1 / v7-DL confidence intervals, from the board and C-model result files. |
| `make_delay_figure.py` | `fin_v7_delay.png` and `tables/v7_delay_sweep.csv` from `tools/accuracy/results_v7_delay_sweep.csv` (written by `tools/accuracy/v7_delay_sweep.py`). |
| `final_analysis.py` | Confidence intervals, failure analysis on all 75 CinC records (C model), project timeline. |
| `check_final_numbers.py` | Recomputes the key numbers from the result files and checks that `fpr-8.tex` quotes them. |
| `extract_ai_prompts.py` | Collected the prompts from the Claude Code session logs for the first prompt log (`AI_PROMPTS.md`, since replaced by `AI_PROMPTS.pdf`). Not needed any more. |
| `package_submission.py` | Builds `fpr-8.zip` (code, data, PDF) in the repository root. |

Rebuild everything (from the repository root):

```
venv/Scripts/python.exe report/final_report/tools/make_final_figures.py
venv/Scripts/python.exe report/final_report/tools/plot_waves.py
venv/Scripts/python.exe report/final_report/tools/final_analysis.py
venv/Scripts/python.exe report/final_report/tools/make_v7_figures.py
venv/Scripts/python.exe report/final_report/tools/make_delay_figure.py
venv/Scripts/python.exe report/final_report/tools/check_final_numbers.py
cd report/final_report && pdflatex fpr-8.tex && pdflatex fpr-8.tex && pdflatex fpr-8.tex && cd ../..
cd report/final_report && pdflatex AI_PROMPTS.tex && pdflatex AI_PROMPTS.tex && cd ../..
venv/Scripts/python.exe report/final_report/tools/package_submission.py
```

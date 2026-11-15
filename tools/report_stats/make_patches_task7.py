"""Build tools/report_stats/out/patches_task7.json (caption level/source tags, Claude reference, merged register)."""
import json
import re
from pathlib import Path

from list_captions import captions, TEX

OUT = Path(__file__).resolve().parent / "out"
s = TEX.read_text(encoding="utf-8")

B6 = "report/rtl\\_pc\\_split/board\\_umem/"
B61 = "report/v61\\_v7/board\\_v61/"
B7 = "report/v61\\_v7/board\\_v7/"
ACC = "tools/accuracy/"
TAG = {
    "tab:clinical_specs": ("L2--L5", "per-row levels; board files in " + B7 + ", Vivado reports in fpga\\_implementation/v6/build/v7/"),
    "tab:method_inventory": ("L1", "mid-term method list (code/src/methods/)"),
    "fig:fin_synreal": ("L2 C model / L5 board", ACC + "results\\_unet\\_syn.csv, results\\_unet\\_adfecgdb.csv, results\\_bitaccurate.csv, results\\_v5\\_final\\_synall.csv, " + B6),
    "tab:final_versions": ("L1--L5 by row", ACC + " result files and the board files in " + B6 + ", " + B61 + ", " + B7),
    "fig:fin_progression": ("L1--L5 by version", "values of Tab.~\\ref{tab:final_versions}"),
    "fig:fin_arch": ("L3/L5", "design diagram of fpga\\_implementation/v6/rtl and model/brain.c"),
    "tab:pc_jobs": ("L2", "fpga\\_implementation/v6/model/proto.h, brain.c"),
    "tab:pc_traffic": ("L2 C model", "report/final\\_report/tables/pc\\_link\\_traffic.csv (tools/pc\\_link\\_traffic.py)"),
    "fig:wave_overview": ("L3 xsim", "fpga\\_implementation/v6/sim/wave/wave.vcd (run\\_wave.sh, CinC a01, 30\\,s)"),
    "fig:wave_signals": ("L3 xsim", "wave.vcd, CinC a01"),
    "fig:wave_canc": ("L3 xsim", "wave.vcd, CinC a01; C-model beats sim/wave/beats\\_model.txt"),
    "fig:wave_sample": ("L3 xsim", "wave.vcd, CinC a01"),
    "fig:wave_req": ("L3 xsim", "wave.vcd, CinC a01"),
    "fig:wave_cycles": ("L3 xsim", "wave.vcd, CinC a01"),
    "fig:fin_timeline": ("L2", "constants of fpga\\_implementation/v6/model/proto.h"),
    "tab:final_resources": ("L4 Vivado", "fpga\\_implementation/v6/build/ utilisation, timing and power reports"),
    "tab:module_resources": ("L4 Vivado", "fpga\\_implementation/v6/build/ hierarchical utilisation report"),
    "fig:fin_resources": ("L4 Vivado", "fpga\\_implementation/v2, v5 and v6 build reports"),
    "tab:final_results": ("L5 board", B6 + "board\\_cdev\\_ad\\_ctest\\_syn.csv"),
    "fig:fin_dist": ("L5 board", B6 + "board\\_cdev\\_ad\\_ctest\\_syn.csv"),
    "fig:fin_seppv": ("L5 board", B6 + "board\\_cdev\\_ad\\_ctest\\_syn.csv"),
    "fig:fin_trace": ("L2 C model", "fpga\\_implementation/v6/model/v6\\_sim.exe on ADFECGDB r01"),
    "fig:fin_cinc": ("L5 board / L2", ACC + "results\\_cinc2013.csv (v2), " + B6),
    "fig:fin_syn": ("L2 C model", ACC + "results\\_bitaccurate.csv, results\\_v5\\_final\\_synall.csv"),
    "fig:fin_gap": ("L2 C model", ACC + "results\\_diag\\_v5.csv"),
    "fig:fin_speed": ("L5 board", B6 + "board\\_cdev\\_ad\\_ctest\\_syn.csv (stream\\_s, record\\_s)"),
    "tab:final_ci": ("L5 board", "report/final\\_report/tables/board\\_f1\\_ci.csv"),
    "fig:fin_fail": ("L2 C model", "report/final\\_report/tables/cinc\\_failures.csv"),
    "tab:v61_ideas": ("L2 C model", ACC + "results\\_devbench\\_v6.csv"),
    "fig:fin_v7_timing": ("L2", "constants of fpga\\_implementation/v6/model/v7\\_post.c"),
    "fig:fin_v7_delay": ("L2 C model", "report/final\\_report/tables/v7\\_delay\\_sweep.csv"),
    "tab:v7_hw": ("L4 Vivado", "fpga\\_implementation/v6/build/, build/v61/, build/v7/ reports"),
    "fig:fin_v7_results": ("L5 board / L2", B6 + ", " + B61 + ", " + B7 + ", " + ACC + "results\\_v7la\\_*.csv"),
    "tab:v7_results": ("L5 board / L2", "report/final\\_report/tables/board\\_v7\\_f1\\_ci.csv; tools/report\\_stats/out/cluster.csv"),
    "fig:fin_v7_cinc": ("L5 board", B7 + "board\\_cdev\\_ad\\_ctest\\_syn.csv (f1, f1\\_causal)"),
    "tab:paired": ("L5 board / L2", "tools/report\\_stats/out/paired.csv"),
    "tab:ledger": ("--", "Tab.~\\ref{tab:final_versions} and the development logs"),
    "fig:fin_v7_cond": ("L2 C model", ACC + "results\\_v7dl\\_synall.csv"),
    "tab:v7_literature": ("L5 board / L2", "cited papers; " + B7 + ", " + ACC + "results\\_v7dl\\_synall.csv"),
    "tab:final_status": ("L1--L5", "result files listed in Sec.~\\ref{sec:final_code}"),
    "tab:final_objectives": ("L3--L5", B7 + ", " + ACC + "results\\_v7dl\\_synall.csv, Vivado reports"),
    "fig:fin_project_timeline": ("--", "git history of the repository"),
    "tab:contrib": ("--", "team records"),
    "tab:objective_status": ("L1--L4", "mid-term report MTR-8"),
    "tab:fixed_point_specs": ("L2", "mid-term fixed-point model src/fixed\\_point\\_model.py"),
    "tab:cycle_schedule": ("L4 target, paper sizing", "mid-term analysis (no build)"),
}

patches = []
for a, b, body, lab in captions(s):
    if re.search(r"\\tagL|\[L[1-5]", body) or lab not in TAG or lab == "tab:final_changes":
        continue
    lvl, src = TAG[lab]
    add = f" \\textbf{{[{lvl}]}} Source: {src}."
    if not body.startswith("\\fb"):
        add = " \\fin{" + add.strip() + "}"
    old = s[a:b + 1]
    if s.count(old) != 1:
        print("not unique:", lab); continue
    patches.append(dict(old=old, new=s[a:b] + add + "}", why=f"level label and data source for {lab}"))

# Claude reference
old = "Anthropic.\n\\newblock The Claude 3.5 Sonnet language model.\n\\newblock Large language model system, 2024. \\url{https://www.anthropic.com/claude}"
assert s.count(old) == 1
patches.append(dict(old=old, new="Anthropic.\n\\newblock Claude 3.5 Sonnet (model announcement).\n\\newblock 2024. \\url{https://www.anthropic.com/news/claude-3-5-sonnet}",
                    why="proper reference entry for the AI model used at mid-term"))

# Register: replace the whole table
i = s.index("\\begin{table*}[t]\n\\fb\n\\caption{\\fb Register of changes")
j = s.index("\\end{table*}", i) + len("\\end{table*}")
old = s[i:j]
rows_old = re.findall(r"\\textbf\{(F-\d+)\} & ([^&]*) & ([^&]*) & ([^&]*) & (.*?) \\\\\n", old)
assert len(rows_old) == 19, len(rows_old)
rows = [(f"{k}: {cat}", mt, fin, "--", eff) for k, cat, mt, fin, eff in rows_old]
C = [
    ("C-01: Fig.~\\ref{fig:runtime_bars} runtimes", "Hankel-SVD 75.9\\,s (bar) / 107.5\\,s (caption); adaptive EMA 245.0\\,ms; FPGA 96\\,ms", "75.9\\,ms; 44.7\\,ms; 111\\,ms (148 cycles)", "App.~\\ref{app:midterm}", "values of code/results/mega\\_benchmark\\_summary.csv; FPGA bar left from a 128-cycle schedule"),
    ("C-02: Tab.~\\ref{tab:clinical_specs} U-Net held-out MAE", "3.57\\,bpm", "2.43\\,bpm", "Sec.~\\ref{sec:clinical_specs}", "3.57 is the 10-subject mean; held-out sub09--10 value from mega\\_benchmark\\_results.csv"),
    ("C-03: Bland--Altman limits", "$[-6.75, +5.90]$\\,bpm", "$[-4.75, +5.88]$\\,bpm", "App.~\\ref{app:midterm}", "caption now matches the plotted limits"),
    ("C-04: Fig.~\\ref{fig:deep_learning_plot} correlation", "$r = 0.979$", "$r = 0.966$ (TC1)", "App.~\\ref{app:midterm}", "figure shows TC1; 0.979 is the 5-case mean"),
    ("C-05: XADC scaling", "$G = 200$ into the XADC", "$G = 100$ needed", "App.~\\ref{app:midterm}", "7-series XADC accepts at most 1\\,V peak-to-peak (UG480)"),
    ("C-06: filter order", "``4th-order Butterworth''", "4th-order prototype, 8th-order bandpass (4 SOS)", "several", "terminology made consistent"),
    ("C-07: Fig.~\\ref{fig:fmr_topography} FMR", "typed-in values; Lead 27 = 0.46 called the peak", "measured: Lead 19 = 0.61 highest, Lead 27 = 0.51; selection was anatomical", "App.~\\ref{app:midterm}", "values recomputed from FECGSYNDB sub01--sub07"),
    ("C-08: FMR range", "0.20--0.54", "0.08--0.61", "Sec.~\\ref{sec:intro}", "measured per-lead training means"),
    ("C-09: CinC test use", "scored for 5 designs", "scored for 9 designs", "Secs.~\\ref{sec:final_obs}, \\ref{sec:limitations}", "Tab.~\\ref{tab:final_versions} lists 9 scored designs"),
    ("C-10: replication R5", "published $\\approx 78\\%$ (12\\,dB), $<35\\%$ (0\\,dB)", "Andreotti TS median 96.0\\%; verdict FAIL", "Sec.~\\ref{sec:replications}", "earlier value could not be traced to the paper"),
    ("C-11: replication R7", "literature $\\approx 81.2\\%$ / $42.1\\%$ quoted as result", "no in-house result; NOT RUN", "Sec.~\\ref{sec:replications}", "numbers not traceable, method never run"),
    ("C-12: replication R4 setup", "32-tap transversal LMS", "SWT + LMS + SSNF", "Sec.~\\ref{sec:replications}", "the reported numbers come from swt\\_lms\\_ssnf in code/results/metrics.csv"),
    ("C-13: RTL speed", "about $140\\times$ real time", "about $135\\times$ (median cycles per sample)", "Sec.~\\ref{sec:final_obs}", "200,000 / 1,485 cycles; $140\\times$ is the whole-run ratio"),
    ("C-14: PC data", "PC ``never sees the recording''", "never receives the raw recording", "Abstract, Sec.~\\ref{sec:final_hw}", "the PC receives beat segments and calibration buffers"),
    ("C-15: AI disclosure, final phase", "Antigravity used once", "Antigravity used 31 Oct--6 Nov", "Sec.~\\ref{sec:final_ai}", "matches the prompt log"),
    ("C-16: Fig.~\\ref{fig:fhr_bland_altman} legend", "``Vivek Hybrid''", "``Wavelet Hybrid''", "App.~\\ref{app:midterm}", "anonymity"),
    ("C-17: U-Net split", "strict disjoint split stated as fact", "split not verifiable from the archive", "Secs.~\\ref{sec:unet}, \\ref{sec:final_realdata}", "training script trains on the whole folder; no record list saved"),
    ("C-18: structure", "mid-term Secs.~6--10 in the main text", "moved to App.~\\ref{app:midterm}", "App.~\\ref{app:midterm}", "superseded design separated from the final design"),
]
body = "\n".join(f"{a} & {b} & {c} & {d} & {e} \\\\" for a, b, c, d, e in rows + C)
new = ("\\begin{table*}[t]\n\\fb\n\\caption{\\fb Register of changes from the mid-term report (MTR-8) to this final report: design changes (F) and corrections of reported values (C). \\textbf{[--]} Source: this report and the result files named in each row.}\n"
       "\\label{tab:final_changes}\\label{tab:register}\n\\centering\n\\resizebox{\\textwidth}{!}{%\n\\begin{tabular}{@{}p{3.0cm}p{3.8cm}p{4.6cm}p{2.0cm}p{4.4cm}@{}}\n\\toprule\n"
       "\\textbf{Item} & \\textbf{Old (mid-term)} & \\textbf{New (final)} & \\textbf{Section} & \\textbf{Reason / effect} \\\\\n\\midrule\n"
       + body + "\n\\bottomrule\n\\end{tabular}%\n}\n\\end{table*}")
patches.append(dict(old=old, new=new, why="register merged into one table with item/old/new/section/reason; corrections added"))

for p in patches:
    assert s.count(p["old"]) == 1
OUT.mkdir(exist_ok=True)
(OUT / "patches_task7.json").write_text(json.dumps(patches, indent=1), encoding="utf-8")
print(len(patches), "patches")

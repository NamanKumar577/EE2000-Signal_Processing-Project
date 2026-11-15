"""WS1: main-body restructure of report/final_report/fpr-8.tex (exact unique string matching only).
Run first in the WS1..WS5 sequence:  venv/Scripts/python.exe report/final_report/fixes/WS1/apply.py"""
import re
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "fpr-8.tex"
s = P.read_text(encoding="utf-8")


def one(old):
    n = s.count(old)
    assert n == 1, f"expected 1 match, found {n}: {old[:80]!r}"


def rep(old, new):
    global s
    one(old)
    s = s.replace(old, new)


def cut(start, end):
    """remove s[start:end) (end marker kept) and return it"""
    global s
    one(start)
    i = s.index(start)
    j = s.index(end, i)
    block = s[i:j]
    s = s[:i] + s[j:]
    return block


def demote(t):
    t = re.sub(r"\\subsection\{", r"\\subsubsection{", t)
    return re.sub(r"\\section\{", r"\\subsection{", t)


# ---- 1. Introduction: tone and research gap ----
rep("offers the ideal clinical alternative: it delivers continuous morphological telemetry, passive long-term wearability, and complete safety for mother and fetus.",
    "offers \\fin{an alternative}: it delivers continuous morphological telemetry, passive long-term wearability, and \\fin{no invasive risk} for mother and fetus.")
rep("Crucially, maternal and fetal cardiac biopotentials exhibit", "Maternal and fetal cardiac biopotentials exhibit")
rep("However, benchmark evaluations reveal a critical mathematical failure mode:", "\\fin{Our benchmark evaluations showed a failure mode}:")
rep("they frequently depend on multi-DSP architectures or require dedicated maternal thoracic reference leads. This project works toward realizing an end-to-end, bit-accurate, and latency-deterministic NIFECG extraction pipeline targeting",
    "\\fin{they often require a dedicated maternal thoracic reference lead. Our final design uses 43 DSP slices (Tab.~\\ref{tab:hw_summary}) and no reference lead. This project builds an end-to-end, bit-accurate and deterministic} NIFECG extraction pipeline \\fin{on}")

# ---- 2. Sec. 2: power and latency target ----
rep("Latency (per-sample filter group delay) must remain strictly below $100\\,$ms to trigger emergency alerts. Note that downstream beat-to-display telemetry includes a 5-beat median filter which adds approximately $2.1\\,$s of beat-level smoothing.",
    "\\fin{The original (mid-term) target was a per-sample latency below $100\\,$ms; the final design reports live beats after 1.5--2\\,s and final beats after about $13.5\\,$s, and the target is re-baselined in \\cref{tab:o3o4}.}")
rep("Boolean Board total power is estimated analytically; physical board current measurement remains future work.",
    "\\fin{The on-chip power of the final design is a Vivado estimate ($0.445\\,$W, \\cref{tab:hw_summary}); the board current was not measured.}")

# ---- 3. old Sec. 3 (mid-term problem + O1-O5) -> appendix, new Sec. 3 in place ----
old3 = cut("% =====================================================================\n\\section{Problem Statement and Formal Engineering Objectives}",
           "% =====================================================================\n\\section{Physiological Signal Model and Dataset}")
old3 = old3.replace("\\label{sec:problem_statement}", "\\label{sec:midterm_problem}")
i = s.index("% =====================================================================\n\\section{Physiological Signal Model and Dataset}")
s = s[:i] + "% =====================================================================\n\\input{sections/ws1_problem}\n\n" + s[i:]

# ---- 4. old Sec. 4: dipole model + data sets rewritten (ws1_dataset); lead selection, filters, split -> appendix ----
old4 = cut("% =====================================================================\n\\section{Physiological Signal Model and Dataset}",
           "% =====================================================================\n\\section{Multi-Channel Signal Processing Architectures}")
old4 = old4.replace("\\label{sec:dataset}", "\\label{sec:midterm_dataset}")
i = s.index("% =====================================================================\n\\section{Multi-Channel Signal Processing Architectures}")
s = s[:i] + "% =====================================================================\n\\input{sections/ws1_dataset}\n\n" + s[i:]

# ---- 5. old Sec. 5 (methods M1-M9, Tab. method_inventory) -> appendix ----
old5 = cut("% =====================================================================\n\\section{Multi-Channel Signal Processing Architectures}",
           "\\begin{finalpart}\n\\section{Final Phase I")

# ---- 6. insert into the appendix right after its intro block ----
k = s.index("\\label{app:midterm}")
k = s.index("\\end{finalpart}\n", k) + len("\\end{finalpart}\n")
block = "\n" + demote(old3) + demote(old4) + demote(old5)
s = s[:k] + block + s[k:]

P.write_text(s, encoding="utf-8", newline="")
print("WS1 applied")

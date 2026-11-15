"""Check that the v7-DL F1 values agree to the digit in the abstract, Tab. v7_results (22) and Tab. final_objectives / v7_literature."""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / "report/final_report/fpr-8.tex"
AUX = ROOT / "report/final_report/fpr-8.aux"
OUT = Path(__file__).resolve().parent / "out/consistency.txt"
s = TEX.read_text(encoding="utf-8")
aux = AUX.read_text(encoding="utf-8", errors="ignore")


def tabnum(lab):
    m = re.search(r"newlabel\{" + re.escape(lab) + r"\}\{\{(\d+)\}", aux)
    return m.group(1) if m else "?"


def block(start, end="\\end{"):
    i = s.index(start)
    return s[i:s.index(end, i + len(start))]


def env(label):
    i = s.index("\\label{" + label + "}")
    j = s.index("\\end{table", i)
    return s[i:j]


abstract = block("\\begin{abstract}", "\\end{abstract}")
b7 = pd.read_csv(ROOT / "report/v61_v7/board_v7/board_cdev_ad_ctest_syn.csv")
syn = pd.read_csv(ROOT / "tools/accuracy/results_v7dl_synall.csv")
UNREL = {"a33", "a38", "a47", "a52", "a54", "a71", "a74"}
truth = {
    "CinC test": b7[b7.set == "ctest"].f1.mean(),
    "CinC test reliable": b7[(b7.set == "ctest") & ~b7.rid.isin(UNREL)].f1.mean(),
    "CinC dev": b7[b7.set == "cdev"].f1.mean(),
    "ADFECGDB": b7[b7.set == "ad"].f1.mean(),
    "FECGSYNDB all": syn.f1.mean(),
}
places = {"abstract": abstract, f"Tab. {tabnum('tab:v7_results')} (v7_results)": env("tab:v7_results"),
          f"Tab. {tabnum('tab:final_objectives')} (final_objectives)": env("tab:final_objectives"),
          f"Tab. {tabnum('tab:v7_literature')} (v7_literature)": env("tab:v7_literature"),
          f"Tab. {tabnum('tab:clinical_specs')} (clinical_specs)": env("tab:clinical_specs")}
lines, bad = [], 0
for nm, v in truth.items():
    val = f"{v:.1f}"
    for pl, txt in places.items():
        present = val in txt
        lines.append(f"{nm:20s} {val:>5s}  {pl:32s} {'found' if present else '-'}")
lines.append("")
# every v7-DL-looking F1 in the abstract must be one of the true values
known = {f"{v:.1f}" for v in truth.values()} | {f"{b7[b7.set.isin(['cdev','ctest'])].f1.mean():.1f}"}
for pl in ["abstract"]:
    for m in re.findall(r"\$(\d\d\.\d)\\%\$", places[pl]):
        if m not in known and m not in {"93.0", "16.7", "87.3", "17.5"}:
            lines.append(f"UNMATCHED value {m}% in {pl}"); bad += 1
# required appearances
need = {"abstract": ["CinC test", "CinC test reliable", "CinC dev", "ADFECGDB", "FECGSYNDB all"],
        f"Tab. {tabnum('tab:v7_results')} (v7_results)": ["CinC test", "CinC test reliable", "CinC dev", "ADFECGDB", "FECGSYNDB all"],
        f"Tab. {tabnum('tab:final_objectives')} (final_objectives)": ["CinC test", "CinC test reliable", "ADFECGDB", "FECGSYNDB all"]}
for pl, keys in need.items():
    for k in keys:
        if f"{truth[k]:.1f}" not in places[pl]:
            lines.append(f"MISSING {k} = {truth[k]:.1f} in {pl}"); bad += 1
lines.append(f"\n{'ALL CONSISTENT' if not bad else str(bad) + ' PROBLEM(S)'}")
OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))

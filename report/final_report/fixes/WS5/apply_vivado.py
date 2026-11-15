#!/usr/bin/env python3
"""WS5 Vivado patch: run AFTER apply.py, once tools/report_stats/out/ws5/vivado_wns.csv exists
(columns strategy,wns_ns; from 'STRATEGY <name> WNS <ns>' lines of tools/report_stats/ws5/vivado/vivado.log;
 python apply_vivado.py --from-log builds the CSV from the log first)."""
import csv
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
ROOT = R.parents[1]
CSV = ROOT / "tools/report_stats/out/ws5/vivado_wns.csv"
LOG = ROOT / "tools/report_stats/ws5/vivado/vivado.log"
if "--from-log" in sys.argv:
    rows = re.findall(r"^STRATEGY (\S+) WNS (-?[\d.]+)", LOG.read_text(errors="ignore"), re.M)
    with open(CSV, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["strategy", "wns_ns"]); w.writerows(rows)
rows = list(csv.DictReader(open(CSV)))
assert rows, "no Vivado results"
wns = [float(r["wns_ns"]) for r in rows]
txt = (rf"\noindent\textbf{{Implementation strategies.}} {len(rows)} placement and routing strategies of v7-DL "
       rf"({', '.join(r['strategy'].replace('_', r'\_') for r in rows)}; same RTL and constraints, "
       r"\texttt{tools/report\_stats/ws5/vivado/strategies\_v7.tcl}) gave worst setup slack "
       + ", ".join(f"${w:+.3f}$" for w in wns) + r"\,ns (\texttt{tools/report\_stats/out/ws5/vivado\_wns.csv}); "
       + ("all meet timing at 50\\,MHz." if min(wns) >= 0 else "not all of them meet timing at 50\\,MHz."))
P = {
 "sections/hardware.tex": [(r"\noindent\textbf{Implementation strategies.} A sweep of three placement and routing strategies for v7-DL "
                            r"(\texttt{tools/report\_stats/ws5/vivado/strategies\_v7.tcl}) was started; its results are not yet available.", txt)],
 "sections/limitations_items.tex": [("Vivado seed sweeps; ", "")],
}
for f, reps in P.items():
    p = R / f
    s = p.read_text(encoding="utf-8")
    for old, new in reps:
        assert s.count(old) == 1, (f, old[:60])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8", newline="")
    print("patched", f)

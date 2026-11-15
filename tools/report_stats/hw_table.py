#!/usr/bin/env python3
"""
Hardware numbers of v6, v6.1 and v7-DL, read from the Vivado reports and board result files on disk.
Writes tools/report_stats/out/hw_table.csv (value + source file per number) and flags differences
from the values quoted in report/final_report/fpr-8.tex (Tabs. final_resources and v7_hw).

    venv/Scripts/python.exe tools/report_stats/hw_table.py
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
B = "fpga_implementation/v6/build"
VER = {"v6": (B, "report/rtl_pc_split/board_umem/board_cdev_ad_ctest_syn.csv"),
       "v6.1": (B + "/v61", "report/v61_v7/board_v61/board_cdev_ad_ctest_syn.csv"),
       "v7-DL": (B + "/v7", "report/v61_v7/board_v7/board_cdev_ad_ctest_syn.csv")}
# values quoted in the report (Tab. v7_hw)
QUOTED = {"v6": dict(lut=18127, ff=10015, dsp=33, bram=60, wns=0.26, power=0.374),
          "v6.1": dict(lut=18986, ff=11179, dsp=33, bram=60, wns=0.41, power=0.386),
          "v7-DL": dict(lut=26701, ff=15970, dsp=43, bram=71, wns=0.05, power=0.445)}


def util(path, name):
    m = re.search(r"\|\s*" + re.escape(name) + r"\s*\|\s*([\d.]+)\s*\|", path.read_text())
    return float(m.group(1))


rows = []
for ver, (bdir, board) in VER.items():
    u, t, pw = ROOT / bdir / "util.rpt", ROOT / bdir / "timing.rpt", ROOT / bdir / "power.rpt"
    tt = t.read_text()
    wns = float(re.search(r"WNS\(ns\).*?\n\s*-+.*?\n\s*([-\d.]+)", tt, re.S).group(1))
    clk = re.search(r"clk50_u\s+\{[^}]*\}\s+([\d.]+)\s+([\d.]+)", tt)
    power = float(re.search(r"Total On-Chip Power \(W\)\s*\|\s*([\d.]+)", pw.read_text()).group(1))
    lines = (ROOT / board).read_text().splitlines()
    hdr = lines[0].split(",")
    i = hdr.index("bit_exact")
    be = sum(1 for l in lines[1:] if l.split(",")[i].strip() == "True")
    vals = dict(lut=util(u, "Slice LUTs"), ff=util(u, "Slice Registers"), dsp=util(u, "DSPs"),
                bram=util(u, "Block RAM Tile"), wns=wns, power=power, clock_mhz=float(clk.group(2)),
                bit_exact=f"{be}/{len(lines) - 1}")
    src = dict(lut=u, ff=u, dsp=u, bram=u, wns=t, power=pw, clock_mhz=t, bit_exact=ROOT / board)
    for k, v in vals.items():
        q = QUOTED[ver].get(k)
        flag = ""
        if q is not None:
            tol = 0.005 if k in ("wns",) else 0.0005 if k == "power" else 0
            flag = "" if abs(float(v) - q) <= tol + 1e-9 else f"DIFF (report {q})"
        rows.append(dict(version=ver, quantity=k, value=v, source=str(src[k].relative_to(ROOT)).replace("\\", "/"), check=flag))

with open(OUT / "hw_table.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["version", "quantity", "value", "source", "check"])
    w.writeheader()
    w.writerows(rows)
for r in rows:
    print(f"{r['version']:6s} {r['quantity']:10s} {str(r['value']):>9s}  {r['check']:18s} {r['source']}")

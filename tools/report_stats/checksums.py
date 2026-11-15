#!/usr/bin/env python3
"""SHA-256 of every result file the final report reads -> tools/report_stats/out/sha256.csv

    venv/Scripts/python.exe tools/report_stats/checksums.py
"""
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out" / "sha256.csv"
ACC = "tools/accuracy/"
FILES = [
    "report/rtl_pc_split/board_umem/board_cdev_ad_ctest_syn.csv",
    "report/v61_v7/board_v61/board_cdev_ad_ctest_syn.csv",
    "report/v61_v7/board_v7/board_cdev_ad_ctest_syn.csv",
    "code/results/metrics.csv",
    "code/results/mega_benchmark_results.csv",
    "code/results/mega_benchmark_summary.csv",
] + [ACC + f for f in [
    "results_adfecgdb.csv", "results_bitaccurate.csv", "results_cinc2013.csv", "results_diag_v5.csv",
    "results_unet_adfecgdb.csv", "results_unet_syn.csv", "results_v5_final_synall.csv", "results_v61_synall.csv",
    "results_v7_delay_sweep.csv", "results_v7dl_synall.csv", "results_v7la_ctest.csv", "results_v7la_dev.csv",
    "results_v7la_synall.csv", "_taps/results.csv", "README.md"]]
FILES += sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "report/final_report/tables").glob("*.csv"))
for d in ["fpga_implementation/v6/build", "fpga_implementation/v6/build/v61", "fpga_implementation/v6/build/v7"]:
    for r in ["util.rpt", "util_hier.rpt", "timing.rpt", "power.rpt"]:
        FILES.append(f"{d}/{r}")
FILES += sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "tools/report_stats/out").glob("*.csv") if p.name != "sha256.csv")

rows = []
for f in FILES:
    p = ROOT / f
    if p.is_file():
        rows.append((f, p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()))
    else:
        rows.append((f, "", "MISSING"))
with open(OUT, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["file", "bytes", "sha256"])
    w.writerows(rows)
print(f"{sum(r[2] != 'MISSING' for r in rows)} files hashed, {sum(r[2] == 'MISSING' for r in rows)} missing -> {OUT}")
for r in rows:
    if r[2] == "MISSING":
        print("missing:", r[0])

#!/usr/bin/env python3
"""
What crosses the PC <-> FPGA link in the final design (v7-DL), per PC decision.

Runs the v7-DL C model (bit-exact with the board) on ADFECGDB r01 (120 s) with V6_DUMP, splits
the uplink stream and the PC answers by message type, groups them by the PC decision they serve
and writes tables/pc_link_traffic.csv (used by Sec. "Why the PC Stays in the Loop").

    venv/Scripts/python.exe report/final_report/tools/pc_link_traffic.py
"""
import csv
import os
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "fpga_implementation/v6/model/v7_sim.exe"
REC = ROOT / "fpga_implementation/v6/sim/r_ad_r01.i16"
OUT = ROOT / "report/final_report/tables/pc_link_traffic.csv"
FRAME = 64                      # samples per SAMPLES frame sent by the host (0.256 s)

# message type -> PC decision it serves (uplink requests/data and downlink answers)
GROUP = {0x84: "template basis", 0x12: "template basis",
         0x87: "track selection", 0x88: "track selection", 0x89: "track selection", 0x8A: "track selection", 0x14: "track selection",
         0x85: "GEVD calibration", 0x86: "GEVD calibration", 0x13: "GEVD calibration",
         0x80: "maternal PCA", 0x10: "maternal PCA",
         0x81: "maternal train", 0x82: "maternal train", 0x83: "maternal train", 0x11: "maternal train"}


def main():
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, V6_DUMP="r")
        subprocess.run([str(MODEL), str(REC)], cwd=tmp, env=env, check=True, capture_output=True)
        up = [int(x, 16) for x in open(Path(tmp) / "r_up.hex") if x.strip()]
        script = open(Path(tmp) / "r_script.txt").read().splitlines()
    n_samples = REC.stat().st_size // 8          # int16, 4 leads
    secs = n_samples / 250
    by = Counter()
    other_up = 0
    i = 0
    while i + 5 <= len(up):                      # A5 5A cmd len_lo len_hi payload xor
        cmd, ln = up[i + 2], up[i + 3] | (up[i + 4] << 8)
        size = 5 + ln + 1
        if cmd in GROUP:
            by[GROUP[cmd]] += size
        else:
            other_up += size                     # beats/FHR output (OUT, OUT7, DONE, END7)
        i += size
    for line in script:
        f = line.split()
        if f and f[0] == "R":
            b = [int(x, 16) for x in f[3:]]
            by[GROUP[b[2]]] += len(b)
    pc_total = sum(by.values())
    samples_down = -(-n_samples // FRAME) * (FRAME * 8 + 6)
    rows = [(k, v, 100.0 * v / pc_total) for k, v in sorted(by.items(), key=lambda kv: -kv[1])]
    up_total = len(up)
    answers = sum(len(l.split()) - 3 for l in script if l.startswith("R "))
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["decision", "bytes", "share_pct"])
        for k, v, s in rows:
            w.writerow([k, v, f"{s:.1f}"])
        w.writerow(["uplink_Bps", f"{up_total / secs:.0f}", ""])
        w.writerow(["answers_Bps", f"{answers / secs:.0f}", ""])
        w.writerow(["samples_down_Bps", f"{samples_down / secs:.0f}", ""])
    for k, v, s in rows:
        print(f"{k:18s} {v:9d} B  {s:5.1f} %")
    print(f"uplink {up_total / secs:.0f} B/s (incl. {other_up / secs:.0f} B/s output), PC answers {answers / secs:.0f} B/s, "
          f"recording {samples_down / secs:.0f} B/s; link capacity 92,160 B/s per direction")
    print("wrote", OUT)


if __name__ == "__main__":
    main()

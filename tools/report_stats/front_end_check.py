"""Cut-off frequencies of the final front end, computed from the Q28 coefficients in
fpga_implementation/v6/model/coef_q28.h and the one-pole high-pass in fpga_model.c (hp_q, shift 6).
Writes tools/report_stats/out/front_end.csv."""
import re
from pathlib import Path

import numpy as np
from scipy.signal import sosfreqz

ROOT = Path(__file__).resolve().parents[2]
H = (ROOT / "fpga_implementation/v6/model/coef_q28.h").read_text()
FS = 250.0
rows = []
for name in ["LP", "BP", "MAT"]:
    body = re.search(name + r"_Q\[\d+\]\[5\] = \{(.*?)\};", H, re.S).group(1)
    sos = np.array([[int(v) for v in re.findall(r"-?\d+", r)] for r in re.findall(r"\{([^}]*)\}", body)], float) / 2 ** 28
    sos = np.hstack([sos[:, :3], np.ones((len(sos), 1)), sos[:, 3:]])
    w, h = sosfreqz(sos, worN=200000, fs=FS)
    mag = np.abs(h) / np.abs(h).max()
    above = w[mag >= 1 / np.sqrt(2)]
    rows.append((name, len(sos), 2 * len(sos), above.min(), above.max(), w[np.argmax(mag)]))
a = 1 / 64                                   # hp_q: B += (x - B) >> 6
fc = -FS / (2 * np.pi) * np.log(1 - a)
out = ROOT / "tools/report_stats/out/front_end.csv"
with open(out, "w") as f:
    f.write("filter,sections,order,f_low_3dB_Hz,f_high_3dB_Hz,peak_Hz\n")
    f.write(f"HP one-pole (shift 6),-,1,{fc:.3f},,\n")
    for r in rows:
        f.write(f"{r[0]},{r[1]},{r[2]},{r[3]:.2f},{r[4]:.2f},{r[5]:.2f}\n")
print(out.read_text())

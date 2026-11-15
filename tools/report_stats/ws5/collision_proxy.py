"""WS5: maternal-fetal QRS collision rate on real data (PROXY).  Real recordings have no maternal annotations, so the
maternal R peaks are the ones the FPGA itself reports (MPK frames of the v7-DL C model, bit-exact with the board).
A fetal reference beat collides if it lies within (w_m + w_f)/2 = 70 ms (17 samples) of such a peak.  Predicted rate:
(w_m + w_f)/T_m with the record's mean FPGA maternal RR.  MPK times include the causal maternal-band filter delay;
for independent rhythms a constant shift does not change the expected rate.  CinC dev and ADFECGDB only."""
import os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "accuracy"))
import v5c
from devbench import _load, items
W = 17  # 70 ms at 250 Hz
rows = []
for item in items(["cdev", "ad"]):
    X, fq = _load(item); rid = item[1] if isinstance(item[1], str) else item[1].rid
    xi = v5c.to_i16(X)
    with tempfile.TemporaryDirectory() as t:
        f = os.path.join(t, "x.i16"); open(f, "wb").write(np.ascontiguousarray(xi).astype("<i2").tobytes())
        subprocess.run([str(ROOT / "fpga_implementation/v6/model/v7_sim.exe"), f], capture_output=True, env=dict(os.environ, V6_DUMP=os.path.join(t, "g")), check=True)
        up = [int(h, 16) for h in open(os.path.join(t, "g_up.hex")).read().split()]
    mp, i = [], 0
    while i + 5 <= len(up):
        cmd, ln = up[i + 2], up[i + 3] | (up[i + 4] << 8)
        if cmd == 0x83:
            mp.append(up[i + 5] | up[i + 6] << 8 | up[i + 7] << 16 | up[i + 8] << 24)
        i += 6 + ln
    mp = np.array(sorted(mp)); fq = np.asarray(fq)
    if len(mp) < 3 or len(fq) == 0:
        continue
    d = np.abs(fq[:, None] - mp[None, :]).min(1)
    tm = np.median(np.diff(mp)) / 250.0
    rows.append(dict(set=item[0], rid=rid, n_fetal=len(fq), n_maternal=len(mp), mean_mat_rr_ms=1000 * np.mean(np.diff(mp)) / 250,
                     measured=100 * np.mean(d <= W), predicted=100 * 0.140 / (np.mean(np.diff(mp)) / 250.0)))
df = pd.DataFrame(rows)
df.to_csv(ROOT / "tools/report_stats/out/ws5/collision_proxy.csv", index=False, float_format="%.2f")
s = df.groupby("set")[["measured", "predicted", "mean_mat_rr_ms"]].mean().round(1)
print(s); print("records", df.groupby("set").size().to_dict())

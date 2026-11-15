"""WS5: clinical agreement (% of reference beats with |device FHR - reference FHR| <= 5 bpm, harness.score
'fhr_within5', same scoring as the board evaluation: from 20 s, +-50 ms) for v6.1 and v7-DL on the 140 board
records.  Beats come from the C model, which is bit-exact with the board on these records; the script checks
that its F1 equals the board CSV F1 for every record.  Scoring only, no decision uses CinC test."""
import os, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "accuracy"))
import harness as H, v5c
from devbench import _load, items
MODEL = ROOT / "fpga_implementation/v6/model"
BOARD = {"v61": ROOT / "report/v61_v7/board_v61/board_cdev_ad_ctest_syn.csv", "v7": ROOT / "report/v61_v7/board_v7/board_cdev_ad_ctest_syn.csv"}

def run(args):
    var, item = args
    d = _load(item)
    X, fq = d; n = len(X); rid = item[1] if isinstance(item[1], str) else item[1].rid
    xi = v5c.to_i16(X)
    with tempfile.TemporaryDirectory() as t:
        f = os.path.join(t, "x.i16"); open(f, "wb").write(np.ascontiguousarray(xi).astype("<i2").tobytes())
        out = subprocess.run([str(MODEL / f"{var}_sim.exe"), f], capture_output=True, text=True, check=True).stdout
    b = np.array([list(map(int, l.split())) for l in out.splitlines() if l.strip()], dtype=np.int64).reshape(-1, 3)
    pk, fhr = v5c.beats_to_stream(b, n)
    r = H.score(fq, pk, fhr, n, 5000)
    return dict(version=var, set=item[0], rid=rid, f1=r["f1"], fhr_within5=r["fhr_within5"], fhr_mae=r["fhr_mae"])

if __name__ == "__main__":
    its = items(["syn", "ad", "cdev", "ctest"])
    jobs = [(v, i) for v in ("v61", "v7") for i in its]
    with ProcessPoolExecutor(8) as ex:
        rows = list(ex.map(run, jobs))
    d = pd.DataFrame(rows)
    chk = []
    for v, p in BOARD.items():
        bd = pd.read_csv(p).set_index("rid")
        x = d[d.version == v].set_index("rid")
        x = x[x.index.isin(bd.index)]
        chk.append(f"{v}: {len(x)} records matched to board CSV, max |F1 model - F1 board| = {np.abs(x.f1 - bd.loc[x.index, 'f1']).max():.2e}")
    d.to_csv(ROOT / "tools/report_stats/out/ws5/agreement_per_record.csv", index=False)
    s = d.groupby(["version", "set"]).agg(n=("rid", "count"), f1=("f1", "mean"), within5=("fhr_within5", "mean"), mae=("fhr_mae", "mean")).round(2)
    s.to_csv(ROOT / "tools/report_stats/out/ws5/agreement.csv")
    print("\n".join(chk)); print(s)

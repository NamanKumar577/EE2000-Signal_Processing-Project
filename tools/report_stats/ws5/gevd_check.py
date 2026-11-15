"""WS5 check of derivation (b): the GEVD step returns w with Rayleigh quotient J(w) = w'Rq w / w'Rx w equal to the
largest generalised eigenvalue lambda_max.  Logging-only copy of the v7-DL model (tools/report_stats/ws5/gevd/model,
-DWS5_LOG prints J, lambda_max, lambda_min to stderr inside gen_top4).  Development sets only (CinC dev, ADFECGDB,
FECGSYNDB subset).  Also checks that the uplink stream of the logging copy is byte-identical to the committed model."""
import hashlib, os, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "accuracy"))
import v5c
from devbench import _load, items
ORIG = ROOT / "fpga_implementation/v6/model/v7_sim.exe"
LOG = ROOT / "tools/report_stats/ws5/gevd/model/v7_sim_log.exe"

def run(item):
    X, fq = _load(item); rid = item[1] if isinstance(item[1], str) else item[1].rid
    xi = v5c.to_i16(X)
    with tempfile.TemporaryDirectory() as t:
        f = os.path.join(t, "x.i16"); open(f, "wb").write(np.ascontiguousarray(xi).astype("<i2").tobytes())
        md5 = {}
        for nm, exe in (("orig", ORIG), ("log", LOG)):
            r = subprocess.run([str(exe), f], capture_output=True, text=True, env=dict(os.environ, V6_DUMP=os.path.join(t, nm)), check=True)
            md5[nm] = hashlib.md5(open(os.path.join(t, nm + "_up.hex"), "rb").read()).hexdigest()
            if nm == "log":
                g = [tuple(map(float, l.split()[1:])) for l in r.stderr.splitlines() if l.startswith("WS5GEVD")]
    return [dict(set=item[0], rid=rid, identical=md5["orig"] == md5["log"], J=a, lam_max=b, lam_min=c) for a, b, c in g] or \
           [dict(set=item[0], rid=rid, identical=md5["orig"] == md5["log"], J=np.nan, lam_max=np.nan, lam_min=np.nan)]

if __name__ == "__main__":
    its = items(["syn", "ad", "cdev"])
    with ProcessPoolExecutor(8) as ex:
        rows = [r for rs in ex.map(run, its) for r in rs]
    d = pd.DataFrame(rows)
    d["rel_err"] = (d.J - d.lam_max).abs() / d.lam_max
    d.to_csv(ROOT / "tools/report_stats/out/ws5/gevd_check.csv", index=False)
    rec = d.groupby("rid").identical.first()
    print(f"records {rec.size}, byte-identical streams {int(rec.sum())}/{rec.size}")
    g = d.dropna(subset=["J"])
    print(f"GEVD solves {len(g)}; max |J - lambda_max|/lambda_max = {g.rel_err.max():.2e}; median {g.rel_err.median():.2e}")
    print(f"lambda_max/lambda_min (generalised SNR gain bound) median {np.median(g.lam_max / g.lam_min):.2f}, "
          f"range {(g.lam_max / g.lam_min).min():.2f}-{(g.lam_max / g.lam_min).max():.2f}; lambda_max median {g.lam_max.median():.3f}")

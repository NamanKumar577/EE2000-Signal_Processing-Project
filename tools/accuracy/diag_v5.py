"""DIAGNOSTIC (uses labels; dev sets only, never drives the deployed logic directly):
selected output vs best single track vs per-5 s-window oracle selection."""
import os
import subprocess
import tempfile
import numpy as np
import pandas as pd
import harness as H
import v5c
from devbench import _load, items


def run_dump(X, cfg=()):
    with tempfile.NamedTemporaryFile(suffix=".i16", delete=False) as f:
        f.write(v5c.to_i16(X).tobytes()); path = f.name
    env = dict(os.environ, FECG_DUMP="1")
    out = subprocess.run([str(v5c.EXE), path, *cfg], capture_output=True, text=True, env=env).stdout
    os.unlink(path)
    tr, sel = {}, []
    for l in out.splitlines():
        if l.startswith("#"):
            _, k, q = l.split(); tr.setdefault(int(k), []).append(int(q))
        elif l.strip():
            sel.append(list(map(int, l.split())))
    return {k: np.array(v) - 13 for k, v in tr.items()}, np.array(sel).reshape(-1, 3)


def one(item):
    d = _load(item)
    if d is None:
        return None
    X, fq = d
    n = len(X)
    tr, sel = run_dump(X)
    pk, fhr = v5c.beats_to_stream(sel, n)
    z = np.zeros(n)
    r = {"set": item[0], "rid": item[1] if isinstance(item[1], str) else item[1].rid,
         "sel": H.score(fq, pk, fhr, n, 5000)["f1"]}
    f1s = {k: H.score(fq, np.sort(v), z, n, 5000)["f1"] for k, v in tr.items()}
    r["best_track"] = max(f1s.values()) if f1s else 0
    r["best_k"] = max(f1s, key=f1s.get) if f1s else -1
    # per-window oracle: in each 5 s window pick the track with most TP - FP
    out = []
    for t in range(4877, n, 1250):
        best, bs = None, -1e9
        for k, v in tr.items():
            w = v[(v >= t) & (v < t + 1250)]
            s = H.score(fq[(fq >= t) & (fq < t + 1250)], w, z, n, 0)
            sc = s["tp"] - s["fp"]
            if sc > bs: best, bs = w, sc
        if best is not None: out.extend(best.tolist())
    r["win_oracle"] = H.score(fq, np.array(sorted(out)), z, n, 5000)["f1"]
    r["sel_k"] = np.bincount(sel[:, 2]).argmax() if len(sel) else -1
    return r


if __name__ == "__main__":
    df = pd.DataFrame([r for r in H.run_parallel(one, items(["cdev", "ad", "syn"]), procs=14) if r])
    df.to_csv("results_diag_v5.csv", index=False)
    print(df.groupby("set")[["sel", "best_track", "win_oracle"]].mean().round(1))
    print(df[df.set == "cdev"].sort_values("sel").head(20).round(1).to_string(index=False))

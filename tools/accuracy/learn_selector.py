#!/usr/bin/env python3
"""
Learned track selector for v6 (idea 2).  Label use: TRAINING ONLY on FECGSYNDB records that
are not in the dev subset; validated on the dev sets (CinC dev, ADFECGDB, FECGSYNDB dev subset).

1. runs the v6 system model with BR_DUMP to get, at every selection time t, the label-free
   features of all 16 tracks (the same numbers the brain uses);
2. label of (t, track) = beat F1 of that track in the output segment [t, t + 625);
3. fits a logistic model on the synthetic training records;
4. replays the selection offline on the dev sets with (a) the brain's own choice and (b) the
   model's choice, so both are scored the same way.

    python learn_selector.py <variant flags...>     (default: detector fix flags)
Writes selector_weights.txt (weights for brain.c) and selector_eval.csv.
"""
import os
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

import harness as H
from devbench import items
from devbench_v6 import CACHE, build, prep
from diag_v6_tracks import frames

HERE = Path(__file__).resolve().parent
SEG = 625
FEATS = ["c", "acc", "lprom", "reg", "prior", "pen", "agr", "valid"]


def run(args):
    exe, key = args
    f = CACHE / f"{key}.i16"
    fq = np.load(CACHE / f"{key}.fq.npy")
    n = f.stat().st_size // 8
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, V6_DUMP=os.path.join(d, "g"), BR_DUMP=os.path.join(d, "feat.txt"))
        subprocess.run([exe, str(f)], capture_output=True, text=True, env=env, check=True)
        up = bytes(int(h, 16) for h in open(os.path.join(d, "g_up.hex")).read().split())
        F = np.loadtxt(os.path.join(d, "feat.txt"), ndmin=2)
    tr = {k: [] for k in range(16)}
    for c, p in frames(up):
        if c == 0x87:
            tr[p[0]].append(int.from_bytes(bytes(p[1:5]), "little") - 13)
    tr = {k: np.array(v, dtype=np.int64) for k, v in tr.items()}
    rows = []
    for r in F:
        t, k = int(r[0]), int(r[1])
        rate = r[6]
        prior = 0.0 if rate <= 0 else min(1.0, max(0.2, (rate - 80) / 40)) if rate < 120 else 1.0
        ref = fq[(fq >= t) & (fq < t + SEG)]
        det = tr[k][(tr[k] >= t) & (tr[k] < t + SEG)]
        tp, fp, fn, _ = H.match(ref, det)
        f1 = 2 * tp / max(2 * tp + fp + fn, 1) if len(ref) else np.nan
        rows.append({"key": key, "t": t, "k": k, "c": r[2], "acc": r[3], "lprom": r[4], "reg": r[5], "rate": rate,
                     "prior": prior, "pen": r[8], "agr": r[9], "q": r[10], "valid": float(r[10] > 0), "f1": f1})
    return rows, key, tr, fq, n


def replay(choice, tracks, fq, n):
    """output beats = chosen track's beats in each segment; score like the device (from 20 s)"""
    out = []
    for t, k in choice:
        q = tracks[k]
        out.append(q[(q >= t) & (q < t + SEG)])
    det = np.unique(np.concatenate(out)) if out else np.zeros(0, np.int64)
    return H.score(fq, det, np.zeros(n), n, 5000)["f1"]


def main(argv):
    flags = " ".join(argv) or "-DMAT_DET_START=256 -DMAT_DECAY=1"
    exe = str(build("dump", flags))
    allsyn = H.list_records()
    train = [("syn", r) for i, r in enumerate(allsyn) if i % 21 in (7, 14)]
    dev = items(["cdev", "ad", "syn"])
    with Pool(12) as p:
        tkeys = [k for k in p.map(prep, train) if k]
        dkeys = [k for k in p.map(prep, dev) if k]
        tres = p.map(run, [(exe, k) for k in tkeys])
        dres = p.map(run, [(exe, k) for k in dkeys])
    T = pd.DataFrame([r for rows, *_ in tres for r in rows]).dropna(subset=["f1"])
    T = T[T.valid > 0]
    X = T[FEATS].values
    y = (T.f1 >= 0.8).astype(float).values
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xs = (X - mu) / sd
    w = np.zeros(Xs.shape[1] + 1)
    for _ in range(3000):                                   # logistic regression, gradient descent + L2
        z = Xs @ w[1:] + w[0]
        p = 1 / (1 + np.exp(-z))
        g = np.r_[np.mean(p - y), Xs.T @ (p - y) / len(y) + 1e-3 * w[1:]]
        w -= 0.5 * g
    print("train windows", len(y), "positives", int(y.sum()))
    print("weights (standardised):", dict(zip(["bias"] + FEATS, np.round(w, 3))))
    # replay on dev
    res = []
    for rows, key, tracks, fq, n in dres:
        D = pd.DataFrame(rows)
        if D.empty:
            continue
        xs = (D[FEATS].values - mu) / sd
        D["p"] = np.where(D.valid > 0, 1 / (1 + np.exp(-(xs @ w[1:] + w[0]))), -1)
        base = [(t, int(g.loc[g.q.idxmax(), "k"])) for t, g in D.groupby("t")]
        lrn = [(t, int(g.loc[g.p.idxmax(), "k"])) for t, g in D.groupby("t")]
        s, rid = key.split("_", 1)
        res.append({"set": s, "rid": rid, "base": replay(base, tracks, fq, n), "learned": replay(lrn, tracks, fq, n)})
    R = pd.DataFrame(res)
    R.to_csv(HERE / "selector_eval.csv", index=False)
    print(R.groupby("set")[["base", "learned"]].mean().round(2).to_string())
    # weights for brain.c: p = sigmoid(b + sum w_i (x_i - mu_i) / sd_i)
    with open(HERE / "selector_weights.txt", "w") as f:
        f.write("feats " + " ".join(FEATS) + "\n")
        f.write("bias %.6f\n" % w[0])
        for nme, wi, m, s_ in zip(FEATS, w[1:], mu, sd):
            f.write(f"{nme} {wi:.6f} {m:.6f} {s_:.6f}\n")


if __name__ == "__main__":
    main(sys.argv[1:])

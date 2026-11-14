#!/usr/bin/env python3
"""
Diagnostic (uses labels, DEV sets only): per-track F1 of the 16 v6 candidate tracks, the
selected output, the best single track and a per-window oracle, for one model variant.

    python diag_v6_tracks.py <variant exe name in _v6build, e.g. det> [--sets cdev,ad,syn]
Writes diag_v6_<variant>.csv.
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
import v5c
from devbench import items

HERE = Path(__file__).resolve().parent
CACHE = HERE.parents[1] / "data" / "_cache_i16"


def frames(up):
    i, out = 0, []
    while i + 5 <= len(up):
        if up[i] != 0xA5 or up[i + 1] != 0x5A:
            i += 1
            continue
        cmd, ln = up[i + 2], up[i + 3] | (up[i + 4] << 8)
        out.append((cmd, up[i + 5:i + 5 + ln]))
        i += 6 + ln
    return out


def one(args):
    exe, key = args
    fq = np.load(CACHE / f"{key}.fq.npy")
    f = CACHE / f"{key}.i16"
    n = f.stat().st_size // 8
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, V6_DUMP=os.path.join(d, "g"))
        out = subprocess.run([exe, str(f)], capture_output=True, text=True, env=env, check=True).stdout
        up = bytes(int(h, 16) for h in open(os.path.join(d, "g_up.hex")).read().split())
    b = np.array([list(map(int, l.split())) for l in out.splitlines() if l.strip()], dtype=np.int64).reshape(-1, 3)
    pk, fhr = v5c.beats_to_stream(b, n)
    sel = H.score(fq, pk, fhr, n, 5000)["f1"]
    tr = {k: [] for k in range(16)}
    for c, p in frames(up):
        if c == 0x87:
            tr[p[0]].append(int.from_bytes(bytes(p[1:5]), "little") - 13)
    f1 = {}
    for k, q in tr.items():
        q = np.array(q, dtype=np.int64)
        f1[k] = H.score(fq, q, np.zeros(n), n, 5000)["f1"] if len(q) else 0.0
    # per 5-s window oracle: best track per window, beats concatenated
    W = 1250
    orc = []
    for w0 in range(5000, n, W):
        best, bv = None, -1
        for k, q in tr.items():
            q = np.array(q, dtype=np.int64)
            r = fq[(fq >= w0) & (fq < w0 + W)]
            d_ = q[(q >= w0) & (q < w0 + W)]
            tp, fp, fn, _ = H.match(r, d_)
            v = 2 * tp / max(2 * tp + fp + fn, 1)
            if v > bv:
                bv, best = v, d_
        orc.append(best)
    orc = np.concatenate(orc) if orc else np.zeros(0, np.int64)
    s, rid = key.split("_", 1)
    row = {"set": s, "rid": rid, "sel": sel, "best_track": max(f1.values()), "best_k": max(f1, key=f1.get),
           "win_oracle": H.score(fq, orc, np.zeros(n), n, 5000)["f1"]}
    row.update({f"t{k}": v for k, v in f1.items()})
    return row


def main(argv):
    v = argv[0]
    sets = ["cdev", "ad", "syn"]
    for a in argv[1:]:
        if a.startswith("--sets="):
            sets = a.split("=", 1)[1].split(",")
    assert "ctest" not in sets, "diagnostics with labels are for DEV sets only"
    exe = str(HERE / "_v6build" / f"v6_sim_{v}.exe")
    keys = [f"{s}_{k if isinstance(k, str) else k.rid}" for s, k in items(sets)]
    keys = [k for k in keys if (CACHE / f"{k}.i16").exists()]
    with Pool(12) as p:
        rows = p.map(one, [(exe, k) for k in keys])
    df = pd.DataFrame(rows)
    df.to_csv(HERE / f"diag_v6_{v}.csv", index=False)
    print(df.groupby("set")[["sel", "best_track", "win_oracle"]].mean().round(2).to_string())
    return df


if __name__ == "__main__":
    main(sys.argv[1:])

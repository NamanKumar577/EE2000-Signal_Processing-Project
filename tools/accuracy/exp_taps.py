#!/usr/bin/env python3
"""
Experiment (DEV sets only): spatio-temporal (delay-tap) GEVD candidates in the v7-DL C model.
Builds variants from the model copy in _taps/model (originals in fpga_implementation/ untouched)
and reports per variant and set: final v7 F1 and FHR MAE (OUT7 beats), and, from the uplink dump
(0x87 track beats; labels used only for this diagnostic), the best single track and a per-5-s oracle.

    python exp_taps.py base="-DV7" k2d1="-DV7 -DTAPS=2 -DTAPD=1" ... [--sets syn,cdev,ad] [--check]

--check also builds the original model (fpga_implementation/v6/model, -DV7) and verifies that every
variant named "base" gives byte-identical OUT7 output on every record.
Writes _taps/results.csv (per record and variant).
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
ROOT = HERE.parents[1]
ORIG = ROOT / "fpga_implementation" / "v6" / "model"
MODEL = HERE / "_taps" / "model"
BUILD = HERE / "_taps" / "build"
CACHE = ROOT / "data" / "_cache_i16"
SRC = ["sim_main.c", "fpga_model.c", "brain.c", "v7_post.c"]


def build(name, flags, model=MODEL):
    BUILD.mkdir(parents=True, exist_ok=True)
    exe = BUILD / f"sim_{name}.exe"
    cmd = ["gcc", "-O2", "-std=gnu99", "-msse2", "-mfpmath=sse", "-ffp-contract=off", f"-I{ORIG}",
           *flags.split(), "-o", str(exe), *SRC, "-lm"]
    subprocess.run(cmd, cwd=model, check=True)
    return exe


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
    name, exe, key = args
    assert not key.startswith("ctest"), "dev sets only"
    fq = np.load(CACHE / f"{key}.fq.npy")
    f = CACHE / f"{key}.i16"
    n = f.stat().st_size // 8
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, V6_DUMP=os.path.join(d, "g"))
        out = subprocess.run([str(exe), str(f)], capture_output=True, text=True, env=env, check=True).stdout
        up = bytes(int(h, 16) for h in open(os.path.join(d, "g_up.hex")).read().split())
    b = np.array([list(map(int, l.split())) for l in out.splitlines() if l.strip()], dtype=np.int64).reshape(-1, 3)
    pk, fhr = v5c.beats_to_stream(b, n)
    r = H.score(fq, pk, fhr, n, 5000)
    tr = {k: [] for k in range(16)}
    for c, p in frames(up):
        if c == 0x87:
            tr[p[0]].append(int.from_bytes(bytes(p[1:5]), "little") - 13)
    tr = {k: np.array(q, dtype=np.int64) for k, q in tr.items()}
    f1 = {k: (H.score(fq, q, np.zeros(n), n, 5000)["f1"] if len(q) else 0.0) for k, q in tr.items()}
    W, orc = 1250, []
    for w0 in range(5000, n, W):
        best, bv = None, -1
        ref = fq[(fq >= w0) & (fq < w0 + W)]
        for k, q in tr.items():
            d_ = q[(q >= w0) & (q < w0 + W)]
            tp, fp, fn, _ = H.match(ref, d_)
            v = 2 * tp / max(2 * tp + fp + fn, 1)
            if v > bv:
                bv, best = v, d_
        orc.append(best)
    orc = np.concatenate(orc) if orc else np.zeros(0, np.int64)
    s, rid = key.split("_", 1)
    row = {"variant": name, "set": s, "rid": rid, "f1": r["f1"], "fhr_mae": r["fhr_mae"],
           "best_track": max(f1.values()), "best_k": max(f1, key=f1.get),
           "win_oracle": H.score(fq, orc, np.zeros(n), n, 5000)["f1"], "out": out}
    row.update({f"t{k}": v for k, v in f1.items()})
    return row


def main(argv):
    sets, variants, check = ["syn", "cdev", "ad"], [], False
    for a in argv:
        if a.startswith("--sets="):
            sets = a.split("=", 1)[1].split(",")
        elif a == "--check":
            check = True
        elif "=" in a:
            variants.append(tuple(a.split("=", 1)))
        else:
            variants.append((a, "-DV7"))
    assert "ctest" not in sets, "dev sets only"
    exes = [(n, build(n, fl)) for n, fl in variants]
    if check:
        exes.append(("orig", build("orig", "-DV7", ORIG)))
    keys = [f"{s}_{k if isinstance(k, str) else k.rid}" for s, k in items(sets)]
    keys = [k for k in keys if (CACHE / f"{k}.i16").exists()]
    with Pool(12) as p:
        rows = p.map(one, [(n, e, k) for n, e in exes for k in keys])
    df = pd.DataFrame(rows)
    if check:
        o = df[df.variant == "orig"].set_index(["set", "rid"]).out
        for n, _ in variants:
            if n.startswith("base"):
                b = df[df.variant == n].set_index(["set", "rid"]).out
                print(f"{n} vs original model: {int((b == o.reindex(b.index)).sum())}/{len(b)} records identical")
    out_csv = HERE / "_taps" / "results.csv"
    old = pd.read_csv(out_csv) if out_csv.exists() else pd.DataFrame()
    df = df.drop(columns="out")
    if len(old):
        old = old[~old.variant.isin(df.variant.unique())]
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(out_csv, index=False)
    names = [n for n, _ in variants] + (["orig"] if check else [])
    cur = df[df.variant.isin(names)]
    piv = cur.pivot_table(index="variant", columns="set", values=["f1", "fhr_mae", "best_track", "win_oracle"],
                          aggfunc="mean").reindex(names)
    print(piv.round(2).to_string())
    return df


if __name__ == "__main__":
    main(sys.argv[1:])

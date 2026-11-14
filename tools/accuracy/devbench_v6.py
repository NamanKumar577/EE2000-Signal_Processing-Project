#!/usr/bin/env python3
"""
Development bench for the v6 system model (fpga_model.c + brain.c): compiles variants
with -D switches and scores them on the DEV sets in parallel.

    python devbench_v6.py base X1=-DMAT_DET_START=256 X2="-DMAT_DECAY=1 -DFOO=2" [--sets syn,cdev,ad] [--test]

  syn : FECGSYNDB, every 21st record (60)   cdev: CinC 2013 odd records (38)   ad: ADFECGDB (5)
  ctest (CinC even records) is only used with --test, once per frozen design; --sets=synall = all FECGSYNDB.
Writes results_devbench_v6.csv (per record and variant).
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
from devbench import _load, items

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "fpga_implementation" / "v6" / "model"
BUILD = ROOT / "tools" / "accuracy" / "_v6build"
CACHE = ROOT / "data" / "_cache_i16"
BUILD.mkdir(exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)


def build(name, flags):
    exe = BUILD / f"v6_sim_{name}.exe"
    cmd = ["gcc", "-O2", "-std=gnu99", "-msse2", "-mfpmath=sse", "-ffp-contract=off", *flags.split(),
           "-o", str(exe), "sim_main.c", "fpga_model.c", "brain.c", "v7_post.c", "-lm"]
    subprocess.run(cmd, cwd=MODEL, check=True)
    return exe


def prep(item):
    """cache int16 input and annotations for one record"""
    key = f"{item[0]}_{item[1] if isinstance(item[1], str) else item[1].rid}"
    f = CACHE / f"{key}.i16"
    q = CACHE / f"{key}.fq.npy"
    if not f.exists() or not q.exists():
        d = _load(item)
        if d is None:
            return None
        X, fq = d
        f.write_bytes(np.ascontiguousarray(v5c.to_i16(X)).tobytes())
        np.save(q, np.asarray(fq, dtype=np.int64))
    return key


def run_one(args):
    name, exe, key = args
    f = CACHE / f"{key}.i16"
    fq = np.load(CACHE / f"{key}.fq.npy")
    n = f.stat().st_size // 8
    out = subprocess.run([str(exe), str(f)], capture_output=True, text=True, check=True).stdout
    b = np.array([list(map(int, l.split())) for l in out.splitlines() if l.strip()], dtype=np.int64).reshape(-1, 3)
    pk, fhr = v5c.beats_to_stream(b, n)
    r = H.score(fq, pk, fhr, n, 5000)
    s, rid = key.split("_", 1)
    return {"variant": name, "set": s, "rid": rid, "f1": r["f1"], "se": r["se"], "ppv": r["ppv"], "fhr_mae": r["fhr_mae"]}


def main(argv):
    sets = ["syn", "cdev", "ad"]
    variants = []
    for a in argv:
        if a.startswith("--sets="):
            sets = a.split("=", 1)[1].split(",")
        elif a == "--test":
            sets = ["ctest"]
        elif "=" in a:
            n, fl = a.split("=", 1)
            variants.append((n, fl))
        else:
            variants.append((a, ""))
    exes = [(n, build(n, fl)) for n, fl in variants]
    its = [("syn", r) for r in H.list_records()] if sets == ["synall"] else items(sets)
    with Pool(12) as p:
        keys = [k for k in p.map(prep, its) if k]
        rows = p.map(run_one, [(n, e, k) for n, e in exes for k in keys])
    df = pd.DataFrame(rows)
    df.to_csv(Path(__file__).parent / "results_devbench_v6.csv", index=False)
    piv = df.pivot_table(index="variant", columns="set", values="f1", aggfunc="mean").reindex([n for n, _ in variants])
    print(piv.round(2).to_string())
    return df


if __name__ == "__main__":
    main(sys.argv[1:])

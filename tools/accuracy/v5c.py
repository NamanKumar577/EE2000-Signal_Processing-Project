"""Run the v5 C algorithm (PC build of the exact firmware source) on dev/test sets.
  python v5c.py [--sets=syn,cdev,ad] [--test] [key=value ...]   (C config overrides)
The input is the recording rounded to int16 (device ADC format); nothing else."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import harness as H

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "v5c"
EXE = ROOT / "fpga_implementation" / "v5" / "algo" / "fecg_v5_host.exe"


def to_i16(X):
    return np.clip(np.round(X), -32768, 32767).astype("<i2")


def run_c(X, cfg=()):
    with tempfile.NamedTemporaryFile(suffix=".i16", delete=False) as f:
        f.write(to_i16(X).tobytes())
        path = f.name
    try:
        out = subprocess.run([str(EXE), path, *cfg], capture_output=True, text=True, check=True).stdout
    finally:
        os.unlink(path)
    rows = [list(map(int, l.split())) for l in out.splitlines() if l.strip()]
    b = np.array(rows, dtype=np.int64).reshape(-1, 3)
    return b


def beats_to_stream(b, n):
    pk = b[:, 0]
    fhr = np.zeros(n)
    for t, f10 in zip(b[:, 0], b[:, 1]):
        if f10 > 0 and t < n:
            fhr[t:] = f10 / 10.0
    return pk, fhr


def one(args):
    item, cfg = args
    from devbench import _load
    d = _load(item)
    if d is None:
        return None
    X, fq = d
    n = len(X)
    b = run_c(X, cfg)
    pk, fhr = beats_to_stream(b, n)
    r = H.score(fq, pk, fhr, n, 5000)
    return {"set": item[0], "rid": item[1] if isinstance(item[1], str) else item[1].rid,
            **{k: r[k] for k in ("f1", "se", "ppv", "fhr_mae")}}


def main(argv):
    from devbench import items
    sets = ["syn", "cdev", "ad"]
    cfg = [a for a in argv if "=" in a and not a.startswith("--")]
    for a in argv:
        if a.startswith("--sets="):
            sets = a.split("=", 1)[1].split(",")
    if "--test" in argv:
        sets = ["ctest"]
    rows = [r for r in H.run_parallel(one, [(it, cfg) for it in items(sets)], procs=14) if r]
    df = pd.DataFrame(rows)
    tag = "_".join(cfg) or "default"
    df.to_csv(Path(__file__).parent / f"results_{PREFIX}_{tag}.csv", index=False)
    print(tag)
    print(df.groupby("set")[["f1", "se", "ppv", "fhr_mae"]].mean().round(2).to_string())
    return df


if __name__ == "__main__":
    main(sys.argv[1:])

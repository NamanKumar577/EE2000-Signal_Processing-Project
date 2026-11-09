"""
Development benchmark for the real-data front end.  Runs named variants of
fe3.system_hybrid on three DEV sets and prints mean F1 per set:
  syn : FECGSYNDB, every 21st record (59 records)
  cdev: CinC 2013 set-a odd records (CINC_DEV)
  ad  : ADFECGDB (5 records; used for tuning before, so it is a dev set now)
CinC even records (CINC_TEST) are only touched by `--test`.

  python devbench.py <variant> [<variant> ...] [--sets syn,cdev,ad] [--test]
"""
import sys

import numpy as np
import pandas as pd

import harness as H
import fe3
import pipeline as P

# name -> (band, system_hybrid kwargs)
VARIANTS = {
    "v3":     (None, {}),
    "band":   (P.V4_BAND, {}),
    "matdyn": (None, {"mat": "dynamic"}),
    "sel":    (None, {"sel": "both"}),
    "v4":     (P.V4_BAND, {"mat": "dynamic", "sel": "both"}),
}


def _load(item):
    kind, key = item
    if kind == "syn":
        d = H.load(key)
        return None if d is None else (d["X"], d["fq"])
    if kind in ("cdev", "ctest"):
        from eval_cinc2013 import load
        return load(key)
    import adfecgdb as A
    return A.load(key)


def one(args):
    item, names = args
    d = _load(item)
    if d is None:
        return None
    X, fq = d
    n = len(X)
    out = {"set": item[0], "rid": item[1] if isinstance(item[1], str) else item[1].rid}
    for name in names:
        band, kw = VARIANTS[name]
        P.set_band(band)
        try:
            (pk, fh), _ = fe3.system_hybrid(X, **kw)
            out[name] = H.score(fq, pk, fh, n, 5000)["f1"]
        except Exception as ex:          # report, don't lose the whole run
            print("FAIL", out["rid"], name, repr(ex), flush=True)
            out[name] = np.nan
    return out


def items(sets):
    import adfecgdb as A
    src = {"syn": lambda: H.list_records()[::21], "cdev": lambda: fe3.CINC_DEV,
           "ctest": lambda: fe3.CINC_TEST, "ad": lambda: A.RECORDS}
    return [(s, k) for s in sets for k in src[s]()]


def main(argv):
    names = [a for a in argv if not a.startswith("--") and a in VARIANTS]
    sets = ["syn", "cdev", "ad"]
    for a in argv:
        if a.startswith("--sets="):
            sets = a.split("=", 1)[1].split(",")
    if "--test" in argv:
        sets = ["ctest"]
    rows = [r for r in H.run_parallel(one, [(it, names) for it in items(sets)], procs=12) if r]
    df = pd.DataFrame(rows)
    df.to_csv("results_devbench_last.csv", index=False)
    print(df.groupby("set")[names].mean().round(2).to_string())
    return df


if __name__ == "__main__":
    main(sys.argv[1:])

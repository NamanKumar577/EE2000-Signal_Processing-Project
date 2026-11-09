"""Simulated output gap-fill on dumped tracks (dev sets): when the selected output has an
RR gap > g * median RR, insert beats of the 2nd-ranked track (by the device's own label-free
quality at that decision) that fall inside the gap.  Labels only score."""
import numpy as np
import pandas as pd
import harness as H
import v5c
import diag_v5 as D
from devbench import _load, items


def fill(sel_beats, tr, q, g=1.5, margin=0.6):
    out = list(sel_beats)
    qa = np.array(q)                         # t, k, wq, pen, q
    times = np.unique(qa[:, 0])
    res = []
    for i in range(len(out) - 1):
        a, b = out[i], out[i + 1]
        res.append(a)
        prev = np.array(out[max(0, i - 5):i + 1])
        R = np.median(np.diff(prev)) if len(prev) > 2 else None
        if R is None or b - a <= g * R:
            continue
        td = times[times <= a + 150]
        if len(td) == 0:
            continue
        rows = qa[qa[:, 0] == td[-1]]
        order = rows[np.argsort(-rows[:, 4])]
        if len(order) < 2 or order[1, 4] <= 0:
            continue
        k2 = int(order[1, 1])
        cand = tr.get(k2, np.array([]))
        ins = cand[(cand > a + margin * R) & (cand < b - margin * R)]
        last = a
        for c in ins:
            if c - last >= margin * R:
                res.append(int(c)); last = c
    if out:
        res.append(out[-1])
    return np.array(sorted(res))


def one(item):
    d = _load(item)
    if d is None:
        return None
    X, fq = d
    n = len(X)
    tr, sel = D.run_dump(X)
    q = D.run_dump.q
    z = np.zeros(n)
    r = {"set": item[0], "rid": item[1] if isinstance(item[1], str) else item[1].rid}
    pk, fhr = v5c.beats_to_stream(sel, n)
    r["sel"] = H.score(fq, pk, fhr, n, 5000)["f1"]
    for g in (1.5, 1.7):
        f = fill(sel[:, 0], tr, q, g=g)
        r[f"fill{g}"] = H.score(fq, f, z, n, 5000)["f1"]
    return r


if __name__ == "__main__":
    df = pd.DataFrame([r for r in H.run_parallel(one, items(["syn", "cdev", "ad"]), procs=14) if r])
    print(df.groupby("set")[[c for c in df.columns if c not in ("set", "rid")]].mean().round(2))

#!/usr/bin/env python3
"""
v7 "Offline Look-Ahead" (v7-LA): a NON-CAUSAL version of the fetal ECG pipeline.

It may use the whole recording (future samples), but still never uses annotations.
Steps:
  1. Front end and candidates: the bit-accurate v6.1 system model (C) is run over the
     recording; its output stream gives, for each of the 16 candidate tracks, every beat,
     the 31-sample beat snapshot and peak energy, the 0.5-s envelope medians, and the
     maternal R peaks.
  2. Track quality in CENTRED windows (past and future): beat-shape consistency,
     completeness, prominence, RR regularity, physiological rate prior, maternal
     coincidence and agreement with the other tracks.
  3. Global track path: Viterbi over 2.5-s segments for the whole recording, with a cost
     for switching tracks (no switch cost when the two tracks agree on the beats).
  4. Beat clean-up with look-ahead: fill a missed beat from another track (or the
     predicted time) when an RR interval is about twice the local rhythm; drop a beat
     that splits an interval.
  5. FHR from a centred 5-beat median.

    python v7_offline.py [--sets cdev,ad,syn] [--test] [--exe v61] [--switch 1.0] [--half 5000]
"""
import argparse
import os
import subprocess
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

import harness as H
from devbench import items
from devbench_v6 import BUILD, CACHE, build, prep
from diag_v6_tracks import frames

HERE = Path(__file__).resolve().parent
LAT = 13            # tracker -> output latency compensation (samples), as in the device
SEG = 625           # 2.5-s segments
FS = 250


def parse(up):
    tr = {k: {"q": [], "snap": [], "pem": []} for k in range(16)}
    bmed = {k: [] for k in range(16)}
    mpk = []
    mdet = {}
    pcfrac = np.ones(4)
    for c, p in frames(up):
        if c == 0x80:                                   # COV: 10 x s64 upper triangle -> maternal PCA energy fractions
            v = np.frombuffer(bytes(p[:80]), dtype="<i8").astype(float)
            C = np.zeros((4, 4))
            i = 0
            for a in range(4):
                for b_ in range(a, 4):
                    C[a, b_] = C[b_, a] = v[i]
                    i += 1
            ev = np.sort(np.clip(np.linalg.eigvalsh(C), 0, None))[::-1]
            pcfrac = ev / max(ev.sum(), 1e-300)
        elif c == 0x81:                                 # MDET k, p
            mdet[int.from_bytes(bytes(p[1:5]), "little")] = p[0]
        if c == 0x87:                                   # BEAT k, q
            tr[p[0]]["q"].append(int.from_bytes(bytes(p[1:5]), "little"))
        elif c == 0x88:                                 # FEAT k, q, 31 x s32, u16 pem(enc)
            k = p[0]
            bp = np.frombuffer(bytes(p[5:5 + 124]), dtype="<i4").astype(float)
            tr[k]["snap"].append((int.from_bytes(bytes(p[1:5]), "little"), bp))
            tr[k]["pem"].append(int.from_bytes(bytes(p[129:131]), "little"))
        elif c == 0x89:                                 # BMED k, u16
            bmed[p[0]].append(int.from_bytes(bytes(p[1:3]), "little"))
        elif c == 0x83:
            q = int.from_bytes(bytes(p[0:4]), "little")
            if pcfrac[mdet.get(q, 0)] >= 0.1:           # trust only maternal peaks from a strong component (as the brain)
                mpk.append(q)
    return tr, bmed, np.array(mpk, dtype=np.int64)


def track_features(tr, k, t0, t1, mpk, allq):
    q = np.array(tr[k]["q"], dtype=np.int64)
    sel = (q >= t0) & (q < t1)
    qq = q[sel]
    if len(qq) < 4:
        return 0.0, 0.0
    rr = np.diff(qq)
    R = np.median(rr)
    rate = 60.0 * FS / R
    if rate < 80 or rate > 220:
        return 0.0, rate
    acc = min(1.0, len(qq) / max((t1 - t0) / R, 1.0))
    reg = np.mean(np.abs(rr - R) <= 0.15 * R)
    snaps = [s for (t, s) in tr[k]["snap"] if t0 <= t < t1]
    if len(snaps) >= 3:
        S = np.array(snaps)
        S = S - S.mean(1, keepdims=True)
        S = S / (np.linalg.norm(S, axis=1, keepdims=True) + 1e-9)
        T = np.median(S, 0)
        T = T / (np.linalg.norm(T) + 1e-9)
        c = max(0.0, float(np.median(S @ T)))
    else:
        c = 0.0
    prior = 1.0 if rate >= 120 else max(0.2, (rate - 80) / 40)
    if len(mpk) > 3:
        m = mpk[(mpk >= t0 - 20) & (mpk < t1 + 20)]
        hit = np.mean(np.min(np.abs(qq[:, None] - m[None, :]), 1) <= 12) if len(m) > 3 else 0.0
        pen = float(np.clip((0.6 - hit) / 0.3, 0, 1)) if len(m) > 3 else 1.0
    else:
        pen = 1.0
    agr = []
    for j, qj in allq.items():
        if j == k or len(qj) == 0:
            continue
        d = np.min(np.abs(qq[:, None] - qj[None, :]), 1) if len(qj) else np.full(len(qq), 99)
        agr.append(np.mean(d <= 8))
    agr = float(np.mean(agr)) if agr else 0.0
    return c * acc * reg ** 2 * prior * pen * (0.5 + agr), rate


def offline(tr, mpk, n, half=3750, switch=1.0, clean=True):
    allq = {k: np.array(v["q"], dtype=np.int64) for k, v in tr.items()}
    segs = list(range(5000 - SEG, n, SEG))
    K = 16
    Q = np.zeros((len(segs), K))
    for i, t in enumerate(segs):
        c = t + SEG // 2
        for k in range(K):
            Q[i, k], _ = track_features(tr, k, c - half, c + half, mpk, allq)
    L = np.log(Q + 1e-3)
    # agreement between tracks per segment: switching between agreeing tracks is free
    D = np.full((len(segs), K, K), switch)
    for i, t in enumerate(segs):
        for a in range(K):
            qa = allq[a][(allq[a] >= t) & (allq[a] < t + SEG)]
            for b in range(K):
                if a == b:
                    D[i, a, b] = 0.0
                    continue
                qb = allq[b][(allq[b] >= t) & (allq[b] < t + SEG)]
                if len(qa) and len(qb) and np.mean(np.min(np.abs(qa[:, None] - qb[None, :]), 1) <= 8) > 0.8:
                    D[i, a, b] = 0.0
    # Viterbi (maximise sum of log-quality minus switch costs)
    V = L[0].copy()
    B = np.zeros((len(segs), K), dtype=int)
    for i in range(1, len(segs)):
        M = V[:, None] - D[i]
        B[i] = np.argmax(M, 0)
        V = M[B[i], np.arange(K)] + L[i]
    path = [int(np.argmax(V))]
    for i in range(len(segs) - 1, 0, -1):
        path.append(int(B[i, path[-1]]))
    path = path[::-1]
    beats = []
    for (t, k) in zip(segs, path):
        q = allq[k]
        beats.append(q[(q >= t) & (q < t + SEG)])
    b = np.unique(np.concatenate(beats)) if beats else np.zeros(0, np.int64)
    if clean:
        b = cleanup(b, allq)
    return b - LAT, path


def cleanup(b, allq, it=2):
    """look-ahead beat clean-up: fill single missed beats, drop beats that split an interval"""
    pool = np.unique(np.concatenate([v for v in allq.values() if len(v)])) if allq else np.zeros(0, np.int64)
    for _ in range(it):
        if len(b) < 6:
            return b
        rr = np.diff(b)
        out = [b[0]]
        for i in range(1, len(b)):
            lo, hi = max(0, i - 5), min(len(rr), i + 4)
            R = np.median(rr[lo:hi])
            gap = b[i] - out[-1]
            if 1.6 * R < gap < 2.5 * R:                          # one beat missed: take the nearest candidate
                exp = out[-1] + gap / 2
                c = pool[np.abs(pool - exp) <= 0.2 * R]
                out.append(int(c[np.argmin(np.abs(c - exp))]) if len(c) else int(round(exp)))
            if gap < 0.55 * R and i + 1 < len(b) and abs((b[i + 1] - out[-1]) - R) < abs((b[i + 1] - b[i]) - R):
                continue                                         # b[i] splits an interval: drop it
            out.append(int(b[i]))
        b = np.array(out, dtype=np.int64)
    return b


def fhr_centred(b, n):
    """FHR stream from a centred 5-beat median of RR (non-causal)"""
    f = np.zeros(n)
    if len(b) < 3:
        return f
    rr = np.diff(b)
    for i in range(1, len(b)):
        lo, hi = max(0, i - 3), min(len(rr), i + 2)
        r = np.median(rr[lo:hi])
        a = b[i - 1]
        e = b[i + 1] if i + 1 < len(b) else n
        if 50 <= r <= 300:
            f[a:e] = 60.0 * FS / r
    return f


def one(args):
    exe, key, half, switch, clean = args
    f = CACHE / f"{key}.i16"
    fq = np.load(CACHE / f"{key}.fq.npy")
    n = f.stat().st_size // 8
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, V6_DUMP=os.path.join(d, "g"))
        out = subprocess.run([exe, str(f)], capture_output=True, text=True, env=env, check=True).stdout
        up = bytes(int(h, 16) for h in open(os.path.join(d, "g_up.hex")).read().split())
    causal = np.array([list(map(int, l.split())) for l in out.splitlines() if l.strip()], dtype=np.int64).reshape(-1, 3)
    tr, bmed, mpk = parse(up)
    b, path = offline(tr, mpk, n, half, switch, clean)
    r = H.score(fq, b, fhr_centred(b, n), n, 5000)
    import v5c
    pk, fh = v5c.beats_to_stream(causal, n)
    rc = H.score(fq, pk, fh, n, 5000)
    s, rid = key.split("_", 1)
    return {"set": s, "rid": rid, "f1_causal": rc["f1"], "f1": r["f1"], "se": r["se"], "ppv": r["ppv"],
            "fhr_mae": r["fhr_mae"], "fhr_mae_causal": rc["fhr_mae"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="cdev,ad,syn")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--exe", default="v61")
    ap.add_argument("--half", type=int, default=3750)
    ap.add_argument("--switch", type=float, default=1.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--noclean", action="store_true")
    a = ap.parse_args()
    sets = ["ctest"] if a.test else a.sets.split(",")
    exe = BUILD / f"v6_sim_{a.exe}.exe"
    if not exe.exists():
        build(a.exe, "-DV61" if a.exe == "v61" else "")
    its = [("syn", r) for r in H.list_records()] if sets == ["synall"] else items(sets)
    with Pool(12) as p:
        keys = [k for k in p.map(prep, its) if k]
        rows = p.map(one, [(str(exe), k, a.half, a.switch, not a.noclean) for k in keys])
    df = pd.DataFrame(rows)
    if a.out:
        df.to_csv(a.out, index=False)
    print(df.groupby("set")[["f1_causal", "f1", "se", "ppv", "fhr_mae_causal", "fhr_mae"]].mean().round(2).to_string())


if __name__ == "__main__":
    main()

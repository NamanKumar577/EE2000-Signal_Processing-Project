#!/usr/bin/env python3
"""
v7-DL design study ("delayed live"): the v7-LA look-ahead run as a STREAM with a fixed delay,
as it would run on the FPGA.  Float reference used to choose the delay and the simplifications.

The input is the v6.1 uplink stream; a frame is "available" at the T of the next DONE frame
(upper bound of the sample at which the device produced it).  Segment i (2.5 s, from 4375) gets
its quality when T reaches  t_i + 312 + HF + M  using beats in [c - HP, c + HF); the Viterbi
decides segment i - LV by backtracking from the best current state; the clean-up and the
centred FHR run on the decided beats as soon as their look-ahead beats exist.  At the end of
the recording (flush) everything left is finished with the data available.

    python v7_live.py [--sets cdev,ad,syn] [--hp 3750] [--hf 2500] [--lv 1] [--m 250]
                      [--shape med|mean] [--it 2] [--noagr]
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

ROOT = Path(__file__).resolve().parents[2]
UPC = ROOT / "data" / "_cache_up_v61"
UPC.mkdir(parents=True, exist_ok=True)
LAT, SEG, FS, S0 = 13, 625, 250, 5000 - 625


def uplink(exe, key):
    f = UPC / f"{key}.bin"
    if f.exists():
        return f.read_bytes()
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, V6_DUMP=os.path.join(d, "g"))
        subprocess.run([exe, str(CACHE / f"{key}.i16")], capture_output=True, env=env, check=True)
        up = bytes(int(h, 16) for h in open(os.path.join(d, "g_up.hex")).read().split())
    f.write_bytes(up)
    return up


def events(up):
    """(avail_T, cmd, payload): avail = T of the next DONE frame"""
    fr = frames(up)
    out, pend = [], []
    for c, p in fr:
        if c == 0x8C:
            T = int.from_bytes(bytes(p[:4]), "little")
            out += [(T, cc, pp) for cc, pp in pend]
            pend = []
        else:
            pend.append((c, p))
    return out


class Rec:
    """all candidate data with availability times"""
    def __init__(self, ev):
        self.q = {k: [] for k in range(16)}
        self.qa = {k: [] for k in range(16)}
        self.snap = {k: [] for k in range(16)}
        mp, ma = [], []
        mdet, pcfrac = {}, np.ones(4)
        for T, c, p in ev:
            if c == 0x80:
                v = np.frombuffer(bytes(p[:80]), dtype="<i8").astype(float)
                C = np.zeros((4, 4)); i = 0
                for a in range(4):
                    for b in range(a, 4):
                        C[a, b] = C[b, a] = v[i]; i += 1
                e = np.sort(np.clip(np.linalg.eigvalsh(C), 0, None))[::-1]
                pcfrac = e / max(e.sum(), 1e-300)
            elif c == 0x81:
                mdet[int.from_bytes(bytes(p[1:5]), "little")] = p[0]
            elif c == 0x87:
                self.q[p[0]].append(int.from_bytes(bytes(p[1:5]), "little")); self.qa[p[0]].append(T)
            elif c == 0x88:
                s = np.frombuffer(bytes(p[5:129]), dtype="<i4").astype(float)
                s = s - s.mean(); s = s / (np.linalg.norm(s) + 1e-9)
                self.snap[p[0]].append((int.from_bytes(bytes(p[1:5]), "little"), T, s))
            elif c == 0x83:
                q = int.from_bytes(bytes(p[:4]), "little")
                if pcfrac[mdet.get(q, 0)] >= 0.1:
                    mp.append(q); ma.append(T)
        self.q = {k: np.array(v, np.int64) for k, v in self.q.items()}
        self.qa = {k: np.array(v, np.int64) for k, v in self.qa.items()}
        self.mp, self.ma = np.array(mp, np.int64), np.array(ma, np.int64)

    def beats(self, k, Tn, t0, t1):
        q = self.q[k]
        return q[(self.qa[k] <= Tn) & (q >= t0) & (q < t1)]


def quality(R, k, Tn, t0, t1, a):
    qq = R.beats(k, Tn, t0, t1)
    if len(qq) < 4:
        return 0.0
    rr = np.diff(qq)
    Rm = np.median(rr)
    rate = 60.0 * FS / Rm
    if rate < 80 or rate > 220:
        return 0.0
    acc = min(1.0, len(qq) / max((t1 - t0) / Rm, 1.0))
    reg = np.mean(np.abs(rr - Rm) <= 0.15 * Rm)
    S = [s for (t, ta, s) in R.snap[k] if ta <= Tn and t0 <= t < t1]
    if len(S) >= 3:
        S = np.array(S)
        if a.shape == "med":
            T = np.median(S, 0); T = T / (np.linalg.norm(T) + 1e-9)
            c = max(0.0, float(np.median(S @ T)))
        else:
            c = float(np.linalg.norm(S.mean(0)))
    else:
        c = 0.0
    prior = 1.0 if rate >= 120 else max(0.2, (rate - 80) / 40)
    m = R.mp[(R.ma <= Tn) & (R.mp >= t0 - 20) & (R.mp < t1 + 20)]
    if len(m) > 3:
        hit = np.mean(np.min(np.abs(qq[:, None] - m[None, :]), 1) <= 12)
        pen = float(np.clip((0.6 - hit) / 0.3, 0, 1))
    else:
        pen = 1.0
    if a.noagr:
        return c * acc * reg ** 2 * prior * pen
    agr = []
    for j in range(16):
        if j == k:
            continue
        qj = R.q[j][R.qa[j] <= Tn]
        if len(qj) == 0:
            continue
        agr.append(np.mean(np.min(np.abs(qq[:, None] - qj[None, :]), 1) <= 8))
    agr = float(np.mean(agr)) if agr else 0.0
    return c * acc * reg ** 2 * prior * pen * (0.5 + agr)


class Clean:
    """streaming version of v7_offline.cleanup (one pass); push raw beats, pop cleaned ones"""
    def __init__(self, pool):
        self.pool = pool          # callable Tn -> all candidate beats available
        self.b, self.out, self.i = [], [], 1

    def run(self, Tn, final):
        b = self.b
        if not self.out and b:
            self.out.append(b[0])
        while self.i < len(b) and (final or self.i + 4 < len(b)):
            i = self.i
            if len(b) >= 6 or not final:
                rr = np.diff(b)
                lo, hi = max(0, i - 5), min(len(rr), i + 4)
                R = np.median(rr[lo:hi])
                gap = b[i] - self.out[-1]
                if 1.6 * R < gap < 2.5 * R:
                    exp = self.out[-1] + gap / 2
                    pool = self.pool(Tn)
                    c = pool[np.abs(pool - exp) <= 0.2 * R]
                    self.out.append(int(c[np.argmin(np.abs(c - exp))]) if len(c) else int(round(exp)))
                if gap < 0.55 * R and i + 1 < len(b) and abs((b[i + 1] - self.out[-1]) - R) < abs((b[i + 1] - b[i]) - R):
                    self.i += 1
                    continue
            self.out.append(int(b[i]))
            self.i += 1


def run(R, n, a):
    K = 16
    nseg = len(range(S0, n, SEG))
    V = None
    Bk = []                      # back-pointers
    decided = {}                 # seg -> (track, decision T)
    raw = []                     # (beat, T) decided raw beats in order

    def pool(Tn):
        return np.unique(np.concatenate([R.q[k][R.qa[k] <= Tn] for k in range(K)]))

    stages = [Clean(pool) for _ in range(a.it)]
    final, emitted = [], []      # cleaned beats; (beat, fhr, T)
    def take(j, k, Tn):
        t = S0 + j * SEG
        decided[j] = k
        for q in R.beats(k, Tn, t, t + SEG):
            raw.append(int(q))

    def flow(Tn, fin):
        src = raw
        for st in stages:
            while len(st.b) < len(src):
                st.b.append(src[len(st.b)])
            st.run(Tn, fin)
            src = st.out
        # centred FHR on the cleaned beats: interval i needs b[i+3]
        b = src
        while len(emitted) + 2 < len(b) or (fin and len(emitted) < len(b)):
            i = len(emitted)
            if i + 1 >= len(b):
                emitted.append((b[i], 0, Tn)); continue
            rr = np.diff(b)
            r = np.median(rr[max(0, i - 2):min(len(rr), i + 3)])
            emitted.append((b[i], 60.0 * FS / r if 50 <= r <= 300 else 0.0, Tn))

    for i in range(nseg):
        t = S0 + i * SEG
        if a.wf >= 0:                    # segment-aligned window [t - wp*SEG, t + (1 + wf)*SEG)
            w0, w1 = t - a.wp * SEG, t + (1 + a.wf) * SEG
        else:                            # centred window
            c = t + SEG // 2
            w0, w1 = c - a.hp, c + a.hf
        Tq = w1 + a.m
        fin = Tq >= n
        Tn = n if fin else Tq
        L = np.log(np.array([quality(R, k, Tn, w0, w1, a) for k in range(K)]) + 1e-3)
        D = np.full((K, K), a.switch)
        bq = [R.beats(k, Tn, t, t + SEG) for k in range(K)]
        for x in range(K):
            D[x, x] = 0.0
            for y in range(K):
                if x != y and len(bq[x]) and len(bq[y]) and np.mean(np.min(np.abs(bq[x][:, None] - bq[y][None, :]), 1) <= 8) > 0.8:
                    D[x, y] = 0.0
        if V is None:
            V = L.copy(); Bk.append(np.zeros(K, int))
        else:
            M = V[:, None] - D
            b = np.argmax(M, 0); Bk.append(b)
            V = M[b, np.arange(K)] + L
        if not fin and i - a.lv >= 0 and (i - a.lv) not in decided:
            k = int(np.argmax(V))
            for x in range(i, i - a.lv, -1):
                k = int(Bk[x][k])
            take(i - a.lv, k, Tn)
            flow(Tn, False)
    # flush: full backtrack over the undecided segments
    k = int(np.argmax(V)) if V is not None else 0
    path = {}
    for x in range(nseg - 1, -1, -1):
        path[x] = k
        k = int(Bk[x][k])
    for j in range(nseg):
        if j not in decided:
            take(j, path[j], n)
    flow(n, True)
    return emitted


def one(args):
    exe, key, a = args
    fq = np.load(CACHE / f"{key}.fq.npy")
    n = (CACHE / f"{key}.i16").stat().st_size // 8
    R = Rec(events(uplink(exe, key)))
    em = run(R, n, a)
    b = np.array([e[0] for e in em], np.int64) - LAT
    fhr = np.zeros(n)
    for (t, f, _) in em:
        if f > 0 and t - LAT < n:
            fhr[max(t - LAT, 0):] = f
    r = H.score(fq, b, fhr, n, 5000)
    dl = [(T - t) / FS for (t, f, T) in em if T < n]
    s, rid = key.split("_", 1)
    return {"set": s, "rid": rid, "f1": r["f1"], "se": r["se"], "ppv": r["ppv"], "fhr_mae": r["fhr_mae"],
            "delay_max": max(dl) if dl else np.nan, "delay_med": float(np.median(dl)) if dl else np.nan}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="cdev,ad,syn")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--hp", type=int, default=3750)
    ap.add_argument("--hf", type=int, default=2500)
    ap.add_argument("--lv", type=int, default=1)
    ap.add_argument("--m", type=int, default=250)
    ap.add_argument("--switch", type=float, default=1.0)
    ap.add_argument("--shape", default="med")
    ap.add_argument("--it", type=int, default=2)
    ap.add_argument("--noagr", action="store_true")
    ap.add_argument("--wp", type=int, default=6)
    ap.add_argument("--wf", type=int, default=-1)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    sets = ["ctest"] if a.test else a.sets.split(",")
    exe = BUILD / "v6_sim_v61.exe"
    if not exe.exists():
        build("v61", "-DV61")
    with Pool(12) as p:
        keys = [k for k in p.map(prep, items(sets)) if k]
        rows = p.map(one, [(str(exe), k, a) for k in keys])
    df = pd.DataFrame(rows)
    if a.out:
        df.to_csv(a.out, index=False)
    print(vars(a))
    print(df.groupby("set")[["f1", "se", "ppv", "fhr_mae", "delay_med", "delay_max"]].agg(
        {"f1": "mean", "se": "mean", "ppv": "mean", "fhr_mae": "mean", "delay_med": "median", "delay_max": "max"}).round(2).to_string())


if __name__ == "__main__":
    main()

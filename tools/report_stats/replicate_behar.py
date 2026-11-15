#!/usr/bin/env python3
"""
R-new-1: re-implementation of template subtraction (TS) and TSpca as described by Behar, Oster and Clifford
(CinC 2013, 40:297-300, Table 1 parameters; same method family as Behar et al. 2014, Physiol. Meas. 35:1569),
scored on PhysioNet/CinC 2013 set-a. A baseline replication only; our own design is not changed.

Protocol (paper, Sec. 2): high-pass 10 Hz + low-pass 99 Hz (zero-phase here, the paper is offline), channel
normalisation, maternal QRS detection on each channel (Pan-Tompkins-like, refractory 250 ms), maternal ECG
cancellation per channel by TS (template = mean of 20 aligned cycles) or TSpca (template = projection on the
first 2 principal components of 20 aligned cycles), fetal QRS detection on each residual (refractory 150 ms),
selection of the channel with the lowest SMI (number of |delta HR| > 30 bpm). Scoring: beat F1, +-50 ms,
2 s to 58 s, the 68 records without the 7 flagged ones; mean over records (preregistered) and pooled.
Details not given in the paper (detector band and threshold, cycle window, template scaling) are our choices.

    venv/Scripts/python.exe tools/report_stats/replicate_behar.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import wfdb
from scipy.signal import butter, filtfilt, find_peaks

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
DATA = next((ROOT / "data").glob("noninvasive-fetal-ecg-the-physionet-computing-in-cardiology-challenge-2013-1.0.0/extracted"))
FLAG = {"a33", "a38", "a47", "a52", "a54", "a71", "a74"}
NCYC, NPC, TOL = 20, 2, 0.05


def bp(x, fs, lo, hi):
    b, a = butter(4, [lo / (fs / 2), hi / (fs / 2)], btype="band")
    return filtfilt(b, a, x, axis=0)


def qrs_detect(x, fs, refr, band):
    """Pan-Tompkins-like: band-pass, derivative, square, 150-ms (mother) / 80-ms (fetus) MWI, adaptive threshold."""
    y = bp(x, fs, *band)
    e = np.gradient(y) ** 2
    w = int((0.15 if refr > 0.2 else 0.08) * fs)
    m = np.convolve(e, np.ones(w) / w, mode="same")
    thr = 0.3 * np.percentile(m, 99)
    pk, _ = find_peaks(m, height=thr, distance=int(refr * fs))
    # refine to the largest |y| within +-50 ms
    r = int(0.05 * fs)
    return np.array([max(p - r, 0) + int(np.argmax(np.abs(y[max(p - r, 0):p + r]))) for p in pk], dtype=int)


def cancel(x, mq, fs, use_pca):
    """subtract a template of the maternal cycle around each maternal R peak"""
    pre, post = int(0.25 * fs), int(0.45 * fs)
    res = x.copy()
    ok = [m for m in mq if m - pre >= 0 and m + post < len(x)]
    if len(ok) < 3:
        return res
    seg = np.array([x[m - pre:m + post] for m in ok])
    taper = np.ones(pre + post)
    k = int(0.03 * fs)
    taper[:k] = np.linspace(0, 1, k); taper[-k:] = np.linspace(1, 0, k)
    for i, m in enumerate(ok):
        lo = max(0, min(i - NCYC // 2, len(ok) - NCYC))
        S = seg[lo:lo + NCYC]
        if use_pca:
            mu = S.mean(0)
            U, s, Vt = np.linalg.svd(S - mu, full_matrices=False)
            B = np.vstack([mu, Vt[:NPC]]).T
        else:
            B = S.mean(0)[:, None]
        c, *_ = np.linalg.lstsq(B, seg[i], rcond=None)
        res[m - pre:m + post] -= taper * (B @ c)
    return res


def smi(fq, fs):
    if len(fq) < 3:
        return 1e9
    hr = 60 * fs / np.diff(fq)
    return int((np.abs(np.diff(hr)) > 30).sum()) + (0 if len(fq) > 60 else 1000)


def f1_score(det, ref, fs, n):
    lo, hi = 2 * fs, n - 2 * fs
    det = np.sort(det[(det >= lo) & (det < hi)]); ref = np.sort(ref[(ref >= lo) & (ref < hi)])
    used = np.zeros(len(det), bool); tp = 0
    for r in ref:
        j = np.searchsorted(det, r)
        best = None
        for k in (j - 1, j):
            if 0 <= k < len(det) and not used[k] and abs(det[k] - r) <= TOL * fs and (best is None or abs(det[k] - r) < abs(det[best] - r)):
                best = k
        if best is not None:
            used[best] = True; tp += 1
    fp, fn = len(det) - tp, len(ref) - tp
    return tp, fp, fn, (200 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0)


rows = []
recs = sorted(p.stem for p in DATA.rglob("a*.hea"))
for rid in recs:
    hea = next(DATA.rglob(rid + ".hea"))
    rec = wfdb.rdrecord(str(hea.with_suffix("")))
    fs = int(rec.fs)
    x = np.nan_to_num(rec.p_signal)
    x = bp(x, fs, 10, 99)
    x = (x - x.mean(0)) / (x.std(0) + 1e-12)
    ref = wfdb.rdann(str(hea.with_suffix("")), "fqrs").sample
    for name, pca in (("TS", False), ("TSpca", True)):
        best = None
        for ch in range(x.shape[1]):
            mq = qrs_detect(x[:, ch], fs, 0.25, (5, 15))
            r = cancel(x[:, ch], mq, fs, pca)
            fq = qrs_detect(r, fs, 0.15, (10, 45))
            s = smi(fq, fs)
            if best is None or s < best[0]:
                best = (s, ch, fq)
        tp, fp, fn, f1 = f1_score(best[2], ref, fs, len(x))
        rows.append(dict(rid=rid, method=name, channel=best[1], tp=tp, fp=fp, fn=fn, f1=f1, flagged=rid in FLAG))
    print(rid, rows[-2]["f1"].__round__(1), rows[-1]["f1"].__round__(1), flush=True)

d = pd.DataFrame(rows)
d.to_csv(OUT / "behar_replication_per_record.csv", index=False, float_format="%.3f")
summ = []
for m, g in d.groupby("method"):
    for nm, h in (("68 records (paper set)", g[~g.flagged]), ("all 75", g)):
        pooled = 200 * h.tp.sum() / (2 * h.tp.sum() + h.fp.sum() + h.fn.sum())
        summ.append(dict(method=m, records=nm, n=len(h), mean_f1=h.f1.mean(), median_f1=h.f1.median(), pooled_f1=pooled))
s = pd.DataFrame(summ)
s.to_csv(OUT / "behar_replication_summary.csv", index=False, float_format="%.2f")
print(s.round(2).to_string(index=False))

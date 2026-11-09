"""
Front end v3 (research): causal maternal cancellation + fetal extraction.

Causality contract: every stage only uses samples up to the current time plus a
fixed look-ahead (output delay).  Maternal cancellation of a beat at p is applied
once samples up to p+L2 have arrived (delay L2 = 0.44 s).  Annotations are only
used in functions whose name starts with `oracle_` (diagnostics).
"""
from __future__ import annotations

import numpy as np
from scipy.signal import sosfilt, butter
from scipy.linalg import eigh

import pipeline as P

FS = 250
CINC_DEV = [f"a{i:02d}" for i in range(1, 76, 2)]    # odd  -> design decisions
CINC_TEST = [f"a{i:02d}" for i in range(2, 76, 2)]   # even -> held out

MAT_SOS = butter(2, [5.0, 25.0], btype="band", fs=FS, output="sos")


def prefilter(X):
    """Per-lead HP1 (0.62 Hz) + LP40: the FPGA's existing front end."""
    return sosfilt(P.LP_SOS, P.hp1(X), axis=0)


# ── 1. causal maternal R-peak detection ───────────────────────────────────────
def maternal_peaks_causal(X, init=2500, refractory=75, mwi_len=38):
    """
    Maternal R peaks, causally.  Maternal reference y = |PC1| projection of the
    5-25 Hz band, where PC1 is estimated on the first `init` samples (2.5x
    longer than any maternal RR).  Detector = FPGA-style adaptive threshold on a
    150 ms energy envelope, 300 ms refractory.  The peak is localised on |y| in
    the 26 samples before the envelope maximum (decision delay <= ~40 samples).
    """
    Y = sosfilt(MAT_SOS, P.hp1(X), axis=0)
    C = Y[256:init].T @ Y[256:init]
    _, V = np.linalg.eigh(C)
    y = Y @ V[:, -1]
    e = P.mwi(y * y, mwi_len)
    comp, raw, _ = P.detect2(np.abs(y), e, 0, 512, refractory, 30, 0, refractory, 625,
                             0, 0.5, 0.6, 1.4, 1.5, 0.0, 0.0)
    return raw, y


# ── 2. causal maternal cancellation (template PCA per lead) ──────────────────
def cancel_maternal(Xf, mpk, L1=40, L2=110, K=20, ncomp=3, search=4, warm=4, subsample=False):
    """
    For each maternal peak p (in time order) and each lead:
      * align p to the running mean template (+-search samples, all leads)
      * basis = mean template + top `ncomp`-1 principal components of the last K
        aligned beats (PAST beats only)
      * least-squares fit of the basis to the current segment, subtract the fit
    The fetal QRS is not time-locked to the mother, so it averages out of the
    basis and survives in the residual.  Segment edges are tapered to avoid
    steps.  Output for samples <= p+L2 is final once x[p+L2] has arrived.
    """
    n, M = Xf.shape
    out = Xf.copy()
    L = L1 + L2
    taper = np.ones(L)
    r = 8
    taper[:r] = np.linspace(0, 1, r)
    taper[-r:] = np.linspace(1, 0, r)
    hist = []                                  # list of (L, M) past aligned beats
    for p in mpk:
        if p - L1 - search < 0 or p + L2 + search > n:
            continue
        frac = 0.0
        if len(hist) >= 1:
            T = np.mean(hist, axis=0)
            cs = []
            for lag in range(-search, search + 1):
                cs.append(np.sum(Xf[p + lag - L1:p + lag + L2] * T))
            k = int(np.argmax(cs))
            if subsample and 0 < k < len(cs) - 1:
                a, b, c = cs[k - 1], cs[k], cs[k + 1]
                den = a - 2 * b + c
                frac = 0.5 * (a - c) / den if den < 0 else 0.0   # peak offset in (-0.5, 0.5)
            p = p + (k - search)
        seg = Xf[p - L1:p + L2]
        if len(hist) >= warm:
            H = np.array(hist[-K:])            # (k, L, M)
            grid = np.arange(L, dtype=float)
            for m in range(M):
                B = H[:, :, m]                 # (k, L)
                mu = B.mean(0)
                if ncomp > 1 and len(B) >= 3:
                    U, S, Vt = np.linalg.svd(B - mu, full_matrices=False)
                    basis = np.vstack([mu, Vt[:ncomp - 1]]).T
                else:
                    basis = mu[:, None]
                if frac != 0.0:                # current beat sits at p+frac: shift the basis
                    basis = np.column_stack([np.interp(grid - frac, grid, basis[:, i]) for i in range(basis.shape[1])])
                coef, *_ = np.linalg.lstsq(basis, seg[:, m], rcond=None)
                fit = basis @ coef
                out[p - L1:p + L2, m] = seg[:, m] - fit * taper
        hist.append(seg.copy())
        if len(hist) > K:
            hist.pop(0)
    return out


# ── diagnostics ───────────────────────────────────────────────────────────────
def band(X):
    return sosfilt(P.BP_SOS, X, axis=0)


def oracle_filter(Xr, fq, shift=14, start=600):
    """DIAGNOSTIC (uses true beats): best single linear filter on residual leads."""
    Y = band(Xr)
    n = len(Y)
    pk = fq + shift
    pk = pk[(pk > start) & (pk < n - 10)]
    idx = (pk[:, None] + np.arange(-4, 5)[None, :]).ravel()
    Cf = Y[idx].T @ Y[idx]
    C = Y[start:].T @ Y[start:]
    C = C + 1e-6 * np.trace(C) / C.shape[0] * np.eye(C.shape[0])
    _, v = eigh(Cf, C)
    return v[:, -1]


def detect_on_lead(y_pref, t_det0=0, latency=13):
    """FPGA detector chain on one already-prefiltered lead (BP -> MWI -> detector)."""
    bp = sosfilt(P.BP_SOS, y_pref)
    e = P.mwi(bp * bp, 30)
    comp, raw, fhr = P.detect2(np.abs(bp), e, t_det0, 512, 50, 26, latency, 50, 300,
                               0, 0.5, 0.6, 1.4, 1.5, 0.0, 0.0)
    return comp, fhr


def maternal_peaks_robust(X, init=2500, refractory=75, mwi_len=38):
    """Like maternal_peaks_causal, but chooses between PC1 and PC2 of the 5-25 Hz
    band (estimated on the first `init` samples): the maternal train is the
    SLOWER of the regular trains (MHR < FHR), rate 40-130 bpm; else PC1."""
    Y = sosfilt(MAT_SOS, P.hp1(X), axis=0)
    C = Y[256:init].T @ Y[256:init]
    _, V = np.linalg.eigh(C)
    best = None
    for j in (1, 2):
        y = Y @ V[:, -j]
        e = P.mwi(y * y, mwi_len)
        comp, raw, _ = P.detect2(np.abs(y), e, 0, 512, refractory, 30, 0, refractory, 625,
                                 0, 0.5, 0.6, 1.4, 1.5, 0.0, 0.0)
        pk = raw[(raw > 512) & (raw < init)]
        if len(pk) >= 4:
            rr = np.diff(pk)
            med = np.median(rr)
            rate = 60 * FS / med
            reg = np.mean(np.abs(rr - med) <= 0.15 * med)
        else:
            rate, reg = 0, 0
        cand = (j, raw, y, rate, reg)
        if j == 1:
            pc1 = cand
        if reg >= 0.6 and 40 <= rate <= 130 and (best is None or rate < best[3] * 0.9):
            best = cand
    c = best or pc1
    return c[1], c[2]


def _train_stats(pk, t0, t1):
    p = pk[(pk >= t0) & (pk < t1)]
    if len(p) < 4:
        return 0.0, 0.0
    rr = np.diff(p)
    med = np.median(rr)
    return 60 * FS / med, float(np.mean(np.abs(rr - med) <= 0.15 * med))


def maternal_peaks_dynamic(X, init=2500, hop=1250, look=5000, refractory=75, mwi_len=38):
    """Causal maternal R peaks with dynamic train selection.  Detectors run in
    parallel on all PCs of the 5-25 Hz band (PCs from the first `init` samples).
    Every `hop` samples the output switches to the train that best fits a mother
    over the trailing `look` samples: the slowest regular (>=60% of RR within
    15% of the median) train at 40-130 bpm; if none is regular, keep the previous
    choice (at start: the most regular).
    Fixes recordings where the fetal or artefact energy dominates PC1 at start."""
    Y = sosfilt(MAT_SOS, P.hp1(X), axis=0)
    C = Y[256:init].T @ Y[256:init]
    _, V = np.linalg.eigh(C)
    n = len(X)
    trains = []
    for j in range(1, V.shape[1] + 1):
        y = Y @ V[:, -j]
        e = P.mwi(y * y, mwi_len)
        comp, raw, _ = P.detect2(np.abs(y), e, 0, 512, refractory, 30, 0, refractory, 625,
                                 0, 0.5, 0.6, 1.4, 1.5, 0.0, 0.0)
        trains.append(raw)

    def choose(t, prev=None):
        st = [_train_stats(pk, max(512, t - look), t) for pk in trains]
        best = None
        for k, (rate, reg) in enumerate(st):
            if reg >= 0.6 and 40 <= rate <= 130 and (best is None or rate < st[best][0] * 0.9):
                best = k
        if best is not None:
            return best
        return prev if prev is not None else int(np.argmax([s[1] for s in st]))

    k = choose(init)
    out = [trains[k][trains[k] < init]]
    t = init
    while t < n:
        k = choose(t, k)
        pk = trains[k]
        out.append(pk[(pk >= t) & (pk < t + hop)])
        t += hop
    pk = np.concatenate(out)
    keep = np.concatenate([[True], np.diff(pk) >= refractory])[:len(pk)]   # drop duplicates at switch points
    return pk[keep], None


def calibrate_residual(Z, mpk, cal_end=3000, start=512, cal_begin=0):
    """Self-referencing GEVD calibration on the maternal-cancelled leads, with the
    known (causal) maternal beats as the exclusion / coincidence reference."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from fecg.host import adaptive_beamformer as AB
    Y = band(Z[cal_begin:cal_end])
    m = mpk[(mpk >= cal_begin + start) & (mpk < cal_end)] - cal_begin
    C = Y[start:].T @ Y[start:] / (len(Y) - start)
    _, V = np.linalg.eigh(C)
    best, bs = None, -1e9
    for j in range(V.shape[1]):
        w = AB._refine(Y, V[:, j], m)
        s = AB._score(Y @ w, m)
        if s > bs:
            best, bs = w, s
    return best / np.linalg.norm(best), bs


def system_v3(X, ncomp=3, robust_mat=True, cal_end=3750, cal_begin=750):
    """End-to-end causal, label-free v3 (float). Returns comp peaks, fhr stream."""
    Xf = prefilter(X)
    mpk, _ = (maternal_peaks_robust if robust_mat else maternal_peaks_causal)(X)
    Z = cancel_maternal(Xf, mpk, ncomp=ncomp)
    w, s = calibrate_residual(Z, mpk, cal_end, cal_begin=cal_begin)
    return detect_on_lead(project(Z, w, cal_end), cal_end + 127)


def project(Z, w, t_apply):
    """FPGA beamformer on the cancelled leads: unity weights [1,0,0,0] until
    t_apply, then 64-sample linear crossfade to unit-norm w."""
    n = len(Z)
    W = np.zeros((n, Z.shape[1]))
    W[:, 0] = 1.0
    w = np.asarray(w, float) / np.linalg.norm(w)
    ramp = np.minimum(np.arange(1, n - t_apply + 1), 64)[:, None] / 64.0
    W[t_apply:] = W[t_apply - 1] + ramp * (w - W[t_apply - 1])
    return np.einsum("nc,nc->n", Z, W)


def blank_maternal(e, mpk, a=0, b=45):
    """Make the MWI envelope flat over [p+a, p+b] for every maternal peak p, so no
    candidate is declared there and the detector levels are not driven by the
    cancellation residual.  Causal under the canceller's fixed output delay."""
    e = e.copy()
    n = len(e)
    for p in mpk:
        lo, hi = p + a, min(n, p + b)
        if 1 <= lo < n:
            e[lo:hi] = e[lo - 1]
    return e


def detect_blanked(y, mpk, t_det0, a=0, b=45, latency=13):
    bp = sosfilt(P.BP_SOS, y)
    e = blank_maternal(P.mwi(bp * bp, 30), mpk, a, b)
    comp, raw, fhr = P.detect2(np.abs(bp), e, t_det0, 512, 50, 26, latency, 50, 300,
                               0, 0.5, 0.6, 1.4, 1.5, 0.0, 0.0)
    return comp, fhr


def system_v3b(X, ncomp=3, cal_end=3750, cal_begin=750, a=0, b=45):
    Xf = prefilter(X)
    mpk, _ = maternal_peaks_robust(X)
    Z = cancel_maternal(Xf, mpk, ncomp=ncomp)
    w, s = calibrate_residual(Z, mpk, cal_end, cal_begin=cal_begin)
    return detect_blanked(project(Z, w, cal_end), mpk, cal_end + 127, a, b), (Z, mpk, w)


def _autocorr_rr(e, lo_bpm=90.0, hi_bpm=200.0):
    x = e - e.mean()
    n = len(x)
    f = np.fft.rfft(x, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    lo, hi = int(FS * 60 / hi_bpm), int(FS * 60 / lo_bpm)
    return lo + int(np.argmax(ac[lo:hi + 1]))


def track_beats(y, t0, init_len=1000, latency=13, mpk=None, blank=(0, 45),
                win=(0.7, 1.3), thr_frac=0.25, miss_reset=4):
    """
    Causal RR-predictive beat tracker (bounded decision delay <= win[1]*RR).
      e  = 120 ms energy envelope of the 12-35 Hz band (optionally maternal-blanked)
      init: RR from autocorrelation of e over [t0, t0+init_len); anchor = max of
            e in the first RR after t0+init_len
      loop: next beat = argmax of e in [t + win0*RR, t + win1*RR]; accepted if
            e > thr_frac * running median of accepted beat energies, else a
            'virtual' beat at t+RR keeps the rhythm (not reported).
            RR <- median of the last 5 accepted intervals.  After `miss_reset`
            consecutive misses the tracker re-initialises from autocorrelation.
    Peak time is localised on |bp| in the 26 samples before the envelope max, and
    reported minus `latency`, exactly like the FPGA localiser.
    """
    bp = sosfilt(P.BP_SOS, y)
    e = P.mwi(bp * bp, 30)
    if mpk is not None:
        e = blank_maternal(e, mpk, *blank)
    absbp = np.abs(bp)
    n = len(e)
    out, fhr = [], np.zeros(n)

    def localise(m):
        lo = max(0, m - 25)
        return lo + int(np.argmax(absbp[lo:m + 1]))

    def init(ts):
        if ts + init_len + 300 >= n:
            return None
        R = _autocorr_rr(e[ts:ts + init_len])
        a = ts + init_len
        m = a + int(np.argmax(e[a:a + R]))
        return m, R

    st = init(t0)
    if st is None:
        return np.array([], np.int64), fhr
    t, R = st
    rrs = [R]
    amps = [e[t]]
    out.append(localise(t))
    misses = 0
    while True:
        lo, hi = t + int(win[0] * R), t + int(win[1] * R)
        if hi >= n:
            break
        m = lo + int(np.argmax(e[lo:hi + 1]))
        if e[m] > thr_frac * np.median(amps[-8:]):
            rr = m - t
            t = m
            out.append(localise(m))
            amps.append(e[m])
            rrs.append(rr)
            R = int(np.clip(np.median(rrs[-5:]), 60, 190))
            misses = 0
            fhr[m:] = 60.0 * FS / R
        else:
            t = t + R
            misses += 1
            if misses >= miss_reset:
                st = init(max(t0, t - init_len))
                if st is None:
                    break
                t, R = st
                R = int(np.clip(R, 60, 190))
                rrs, amps, misses = [R], [e[t]], 0
    peaks = np.maximum(0, np.array(out, np.int64) - latency)
    return peaks, fhr


def tracker_quality(y, mpk, t0, t1):
    """Label-free quality of a projection on [t0, t1): run the tracker there and
    measure (accepted-beat fraction) x (median beat energy / median background)."""
    yy = y[:t1]
    pk, _ = track_beats(yy, t0, init_len=min(1000, (t1 - t0) // 2), mpk=mpk, latency=0)
    pk = pk[pk >= t0]
    if len(pk) < 4:
        return 0.0
    bp = sosfilt(P.BP_SOS, yy)
    e = blank_maternal(P.mwi(bp * bp, 30), mpk)
    seg = e[t0:t1]
    rr = np.diff(pk)
    R = np.median(rr)
    expected = (t1 - pk[0]) / R
    acc = min(1.0, len(pk) / max(expected, 1))
    reg = np.mean(np.abs(rr - R) <= 0.15 * R)
    beat_e = np.median([e[min(len(e) - 1, p + 13):min(len(e), p + 40)].max() for p in pk])
    prom = beat_e / (np.median(seg) + 1e-12)
    rate = 60 * FS / R
    if rate < 80 or rate > 220:
        return 0.0
    return float(acc * reg * np.log1p(prom))


def candidates_residual(Z, mpk, cal_begin, cal_end, start=512):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from fecg.host import adaptive_beamformer as AB
    Y = band(Z[cal_begin:cal_end])
    m = mpk[(mpk >= cal_begin + start) & (mpk < cal_end)] - cal_begin
    C = Y[start:].T @ Y[start:] / (len(Y) - start)
    _, V = np.linalg.eigh(C)
    M = Z.shape[1]
    cands = [np.eye(M)[i] for i in range(M)] + [V[:, j] for j in range(M)]
    cands += [AB._refine(Y, V[:, j], m) for j in range(M)]
    return [c / np.linalg.norm(c) for c in cands]


def system_v3c(X, ncomp=3, cal_end=3750, cal_begin=750):
    Xf = prefilter(X)
    mpk, _ = maternal_peaks_robust(X)
    Z = cancel_maternal(Xf, mpk, ncomp=ncomp)
    best, bq = None, -1
    for w in candidates_residual(Z, mpk, cal_begin, cal_end):
        q = tracker_quality(Z @ w, mpk, cal_begin + 512, cal_end)
        if q > bq:
            best, bq = w, q
    y = project(Z, best, cal_end)
    return track_beats(y, cal_end + 127, mpk=mpk), (Z, mpk, best, bq)


def candidate_features(y, mpk, t0, t1):
    """Label-free features of a projection on the calibration window [t0, t1)."""
    yy = y[:t1]
    pk, _ = track_beats(yy, t0, init_len=min(1000, (t1 - t0) // 2), mpk=mpk, latency=0)
    pk = pk[(pk >= t0 + 20) & (pk < t1 - 20)]
    f = {"n": len(pk), "acc": 0.0, "reg": 0.0, "prom": 0.0, "morph": 0.0, "coinc": 1.0, "rate": 0.0}
    if len(pk) < 4:
        return f
    bp = sosfilt(P.BP_SOS, yy)
    e = blank_maternal(P.mwi(bp * bp, 30), mpk)
    rr = np.diff(pk)
    R = np.median(rr)
    f["rate"] = 60 * FS / R
    f["acc"] = min(1.0, len(pk) / max((t1 - pk[0]) / R, 1))
    f["reg"] = float(np.mean(np.abs(rr - R) <= 0.15 * R))
    f["prom"] = float(np.median([e[p + 13:p + 40].max() for p in pk]) / (np.median(e[t0:t1]) + 1e-12))
    W = np.array([bp[p - 15:p + 16] for p in pk])
    T = np.median(W, axis=0)
    cc = [np.dot(w - w.mean(), T - T.mean()) / (np.linalg.norm(w - w.mean()) * np.linalg.norm(T - T.mean()) + 1e-12) for w in W]
    f["morph"] = float(np.median(cc))
    m = mpk[(mpk >= t0) & (mpk < t1)]
    if len(m):
        j = np.searchsorted(m, pk)
        d = np.minimum(np.abs(pk - m[np.clip(j - 1, 0, len(m) - 1)]), np.abs(pk - m[np.clip(j, 0, len(m) - 1)]))
        f["coinc"] = float(np.mean(d <= 10))
    else:
        f["coinc"] = 0.0
    return f


def window_quality(bp, e, pk, t0, t1):
    """Label-free quality of one candidate's beats in [t0, t1) (morph * acc * log prom)."""
    p = pk[(pk >= t0 + 16) & (pk < t1 - 16)]
    if len(p) < 4:
        return 0.0
    rr = np.diff(p)
    R = np.median(rr)
    rate = 60 * FS / R
    if rate < 80 or rate > 220:
        return 0.0
    acc = min(1.0, len(p) / max((t1 - t0) / R, 1))
    W = np.array([bp[q - 15:q + 16] for q in p])
    T = np.median(W, axis=0)
    Tc = T - T.mean()
    cc = np.median([np.dot(w - w.mean(), Tc) / (np.linalg.norm(w - w.mean()) * np.linalg.norm(Tc) + 1e-12) for w in W])
    prom = np.median([e[min(len(e) - 1, q + 13):min(len(e), q + 40)].max() for q in p]) / (np.median(e[t0:t1]) + 1e-12)
    return float(max(cc, 0) * acc * np.log1p(prom))


def system_v3d(X, ncomp=3, cal_end=3750, cal_begin=750, hop=1250, look=2500):
    """Parallel trackers on all candidate projections; every `hop` samples the
    output switches to the candidate with the best quality over the trailing
    `look` samples (causal dynamic selection)."""
    Xf = prefilter(X)
    mpk, _ = maternal_peaks_robust(X)
    Z = cancel_maternal(Xf, mpk, ncomp=ncomp)
    cands = candidates_residual(Z, mpk, cal_begin, cal_end)
    n = len(Z)
    tracks = []
    for w in cands:
        y = project(Z, w, cal_end)
        pk, _ = track_beats(y, cal_end + 127, mpk=mpk, latency=0)
        bp = sosfilt(P.BP_SOS, y)
        e = blank_maternal(P.mwi(bp * bp, 30), mpk)
        tracks.append((pk, bp, e))
    out = []
    t = cal_end + 127 + 1000
    choice = []
    while t < n:
        qs = [window_quality(bp, e, pk, max(0, t - look), t) for pk, bp, e in tracks]
        k = int(np.argmax(qs))
        choice.append(k)
        pk = tracks[k][0]
        out.extend(pk[(pk >= t) & (pk < t + hop)].tolist())
        t += hop
    peaks = np.maximum(0, np.array(sorted(out), np.int64) - 13)
    return (peaks, fhr_median5(peaks, n)), choice


def fhr_median5(peaks, n):
    """FPGA-style FHR: median of the last 5 valid RR (50..300 samples)."""
    fhr = np.zeros(n)
    buf = []
    for i in range(1, len(peaks)):
        rr = peaks[i] - peaks[i - 1]
        if 50 <= rr <= 300:
            buf = (buf + [rr])[-5:]
            fhr[peaks[i]:] = 60.0 * FS / np.median(buf)
    return fhr


def v2_track(X, Xf):
    """v2 path as a candidate track: host beamformer on raw leads + FPGA threshold
    detector (raw peaks, latency 0)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from fecg.host import adaptive_beamformer as AB
    cmds = AB.plan_schedule(X)
    n = len(X)
    W = np.zeros((n, X.shape[1]))
    W[:, 0] = 1.0
    for c in cmds:
        w = np.asarray(c.w_q15, float) / 32768
        ramp = np.minimum(np.arange(1, n - c.t + 1), 64)[:, None] / 64.0
        W[c.t:] = W[c.t - 1] + ramp * (w - W[c.t - 1])
    y = np.einsum("nc,nc->n", Xf, W)
    bp = sosfilt(P.BP_SOS, y)
    e = P.mwi(bp * bp, 30)
    comp, raw, _ = P.detect2(np.abs(bp), e, cmds[0].t + 127 if cmds else 0, 512, 50, 26, 0, 50, 300,
                             0, 0.5, 0.6, 1.4, 1.5, 0.0, 0.0)
    return raw, bp, e


from numba import njit  # noqa: E402


@njit(cache=True)
def _nlms(D, r, taps, delay, mu):
    n, M = D.shape
    out = D.copy()
    w = np.zeros((M, taps))
    for t in range(taps, n - delay):
        x = r[t + delay - taps + 1:t + delay + 1]
        p = np.dot(x, x) + 1e-6
        for m in range(M):
            err = D[t, m] - np.dot(w[m], x)
            out[t, m] = err
            w[m] += mu * err * x / p
    return out


def window_agreement(tracks, k, t0, t1, tol=8):
    """Label-free cross-candidate agreement of candidate k on [t0, t1): mean over
    its beats of the fraction of the other candidates with a beat within +-tol.
    The fetal train is shared by many projections; spurious beats are not."""
    p = tracks[k][0]
    p = p[(p >= t0) & (p < t1)]
    if len(p) < 4:
        return 0.0
    ag = np.zeros(len(p))
    for j, tr in enumerate(tracks):
        if j == k:
            continue
        q = tr[0][(tr[0] >= t0 - tol) & (tr[0] < t1 + tol)]
        if len(q) == 0:
            continue
        i = np.clip(np.searchsorted(q, p), 1, len(q) - 1) if len(q) > 1 else np.zeros(len(p), int)
        d = np.minimum(np.abs(q[i] - p), np.abs(q[np.maximum(i - 1, 0)] - p))
        ag += d <= tol
    return float(np.mean(ag) / (len(tracks) - 1))


# ── maternal chest-lead reference (optional hardware channel) ───────────────
def maternal_peaks_chest(thor, refractory=75, mwi_len=38):
    """Maternal R peaks from a thoracic (chest) lead: 5-25 Hz band, FPGA-style
    adaptive threshold detector, 300 ms refractory.  Causal."""
    y = sosfilt(MAT_SOS, P.hp1(thor[:, None])[:, 0])
    e = P.mwi(y * y, mwi_len)
    comp, raw, _ = P.detect2(np.abs(y), e, 0, 512, refractory, 30, 0, refractory, 625,
                             0, 0.5, 0.6, 1.4, 1.5, 0.0, 0.0)
    return raw


def nlms_cancel(D, r, taps=17, delay=8, mu=0.02):
    """Causal NLMS: predict each abdominal lead from the chest reference
    r[t+delay-taps+1 .. t+delay] and subtract.  Output delayed by `delay` samples
    relative to r is avoided by delaying D instead (the output at t is final once
    r[t+delay] has arrived: fixed 32 ms look-ahead)."""
    return _nlms(np.ascontiguousarray(D, float), np.ascontiguousarray(r, float), taps, delay, mu)


def hybrid_tracks(X, ncomp=3, cal_end=3750, cal_begin=750, mat="robust", thor=None, chest="template"):
    """All candidate beat tracks of the hybrid: [v2 path] + 12 cancelled-lead trackers.
    thor: optional chest-lead signal; chest = 'template' (maternal peaks from the
    chest lead), 'nlms' (adaptive cancellation only) or 'both'."""
    Xf = prefilter(X)
    if thor is not None and chest in ("template", "both"):
        mpk = maternal_peaks_chest(thor)
    else:
        mpk, _ = (maternal_peaks_dynamic if mat == "dynamic" else maternal_peaks_robust)(X)
    Z = cancel_maternal(Xf, mpk, ncomp=ncomp) if (thor is None or chest != "nlms") else Xf
    if thor is not None and chest in ("nlms", "both"):
        Z = nlms_cancel(Z, prefilter(thor[:, None])[:, 0])
    tracks = [v2_track(X, Xf)]
    for w in candidates_residual(Z, mpk, cal_begin, cal_end):
        y = project(Z, w, cal_end)
        pk, _ = track_beats(y, cal_end + 127, mpk=mpk, latency=0)
        bp = sosfilt(P.BP_SOS, y)
        tracks.append((pk, bp, blank_maternal(P.mwi(bp * bp, 30), mpk)))
    return tracks


def select_tracks(tracks, n, t_start, hop=1250, look=2500, v2_bonus=1.0, sel="quality", agr_floor=0.0):
    """Every `hop` samples output the candidate with the best trailing-window score.
    sel: 'quality' = morph*acc*log(prom); 'agree' = cross-candidate agreement x
    acceptance; 'both' = product of the two.  agr_floor softens the agreement
    term: (agr_floor + agreement)."""
    out, choice = [], []
    t = t_start
    while t < n:
        t0 = max(0, t - look)
        qs = []
        for k, (pk, bp, e) in enumerate(tracks):
            q = window_quality(bp, e, pk, t0, t) if sel in ("quality", "both") else 1.0
            if sel in ("agree", "both"):
                p = pk[(pk >= t0) & (pk < t)]
                R = np.median(np.diff(p)) if len(p) > 3 else 1e9
                acc = min(1.0, len(p) / max((t - t0) / R, 1)) if 60 * FS / R >= 80 else 0.0
                q *= (agr_floor + window_agreement(tracks, k, t0, t)) * acc
            qs.append(q)
        qs[0] *= v2_bonus
        k = int(np.argmax(qs))
        choice.append(k)
        pk = tracks[k][0]
        out.extend(pk[(pk >= t) & (pk < t + hop)].tolist())
        t += hop
    peaks = np.maximum(0, np.array(sorted(out), np.int64) - 13)
    return (peaks, fhr_median5(peaks, n)), choice


def system_hybrid(X, ncomp=3, cal_end=3750, cal_begin=750, hop=1250, look=2500, v2_bonus=1.0,
                  mat="robust", sel="quality", thor=None, chest="template"):
    tracks = hybrid_tracks(X, ncomp, cal_end, cal_begin, mat, thor, chest)
    return select_tracks(tracks, len(X), cal_end + 127 + 1000, hop, look, v2_bonus, sel)

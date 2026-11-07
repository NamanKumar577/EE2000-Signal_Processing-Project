"""
Label-free causal spatial calibrators (host side).

All functions only look at the data buffer they are given (samples the host has
already received) and at the pipeline's OWN detections on that buffer.  No
annotation is ever used.
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import eigh
from scipy.signal import sosfilt

import pipeline as P

FS = 250
RIDGE = 1e-6
FHR_LO, FHR_HI = 80.0, 220.0   # physiological fetal range (bradycardia included)


def band(X):
    """Same front end as the FPGA (HP1 + LP40 + detector band-pass), per channel."""
    return sosfilt(P.BP_SOS, sosfilt(P.LP_SOS, P.hp1(X), axis=0), axis=0)


def detect_on(y, det_start=0, warmup=512):
    """Run the frozen detector on a 1-D detector-band signal; return RAW peak indices."""
    e = P.mwi(y * y, 30)
    comp, raw, fhr = P.detect(np.abs(y), e, det_start, warmup, 50, 26, 18, 50, 300, 0, 1.66)
    return raw


def autocorr_score(y, lo_bpm=83.0, hi_bpm=200.0, warmup=512):
    e = P.mwi(y * y, 30)[warmup:]
    e = e - e.mean()
    n = len(e)
    f = np.fft.rfft(e, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    if ac[0] <= 0:
        return 0.0
    ac /= ac[0]
    lo = int(FS * 60 / hi_bpm)
    hi = int(FS * 60 / lo_bpm)
    return float(ac[lo:hi + 1].max())


def rr_regularity(peaks, n_span):
    """Label-free quality of a beat train: fraction of RR within 15% of median RR,
    penalised if the rate is implausible for a fetus (< 100 or > 200 bpm)."""
    if len(peaks) < 6:
        return 0.0
    rr = np.diff(peaks)
    med = np.median(rr)
    bpm = 60 * FS / med
    if bpm < FHR_LO or bpm > FHR_HI:
        return 0.0
    reg = np.mean(np.abs(rr - med) <= 0.15 * med)
    return float(reg)


def rr_regularity_any(peaks):
    """Regularity without a rate window (for judging a competing source)."""
    if len(peaks) < 6:
        return 0.0
    rr = np.diff(peaks)
    med = np.median(rr)
    return float(np.mean(np.abs(rr - med) <= 0.15 * med))


def qrs_cov(Y, peaks, half=4):
    idx = (peaks[:, None] + np.arange(-half, half + 1)[None, :]).ravel()
    idx = idx[(idx >= 0) & (idx < len(Y))]
    Z = Y[idx]
    return Z.T @ Z / max(len(Z), 1)


def unit(w):
    w = np.asarray(w, float)
    k = np.argmax(np.abs(w))
    if w[k] < 0:
        w = -w
    return w / np.linalg.norm(w)


def pca_dirs(Y):
    C = Y.T @ Y / len(Y)
    vals, vecs = np.linalg.eigh(C)
    return vecs[:, ::-1]  # descending


def maternal_peaks(y, start=512):
    """Host-side maternal R-peak picker on the dominant (maternal) component of the
    received buffer: peaks of the 120 ms energy envelope above 30% of its robust
    maximum, >= 300 ms apart (maternal HR <= 200 bpm).  Any maternal rate down to
    ~20 bpm is handled because there is no RR upper limit."""
    from scipy.signal import find_peaks
    e = P.mwi(y * y, 30)
    e[:start] = 0
    thr = 0.3 * np.percentile(e[start:], 99.5)
    pk, _ = find_peaks(e, height=thr, distance=75)
    # MWI peak lags the R wave; localise on |y| in the preceding 26 samples (like the FPGA)
    out = np.array([max(0, p - 25) + int(np.argmax(np.abs(y[max(0, p - 25):p + 1]))) for p in pk], dtype=np.int64)
    return out


def coincidence(pk, mpk, tol=10):
    """Fraction of beats in pk lying within +-tol samples of a beat in mpk."""
    if len(pk) == 0 or len(mpk) == 0:
        return 0.0
    j = np.searchsorted(mpk, pk)
    d1 = np.abs(pk - mpk[np.clip(j - 1, 0, len(mpk) - 1)])
    d2 = np.abs(pk - mpk[np.clip(j, 0, len(mpk) - 1)])
    return float(np.mean(np.minimum(d1, d2) <= tol))


def drop_near(pk, mpk, tol=6):
    if len(pk) == 0 or len(mpk) == 0:
        return pk
    j = np.searchsorted(mpk, pk)
    d1 = np.abs(pk - mpk[np.clip(j - 1, 0, len(mpk) - 1)])
    d2 = np.abs(pk - mpk[np.clip(j, 0, len(mpk) - 1)])
    return pk[np.minimum(d1, d2) > tol]


def refine(Y, w0, iters=3, half=4, ridge=RIDGE, start=512, mpk=None):
    """Self-referencing GEVD beamformer: fetal-QRS covariance from own detections
    (maternal-coincident detections excluded) vs total covariance."""
    w = unit(w0)
    C = Y[start:].T @ Y[start:] / max(len(Y) - start, 1)
    C = C + ridge * np.trace(C) / C.shape[0] * np.eye(C.shape[0])
    lam = 0.0
    for _ in range(iters):
        pk = detect_on(Y @ w)
        pk = pk[pk >= start]
        if mpk is not None:
            pk = drop_near(pk, mpk)
        if len(pk) < 4:
            break
        Cf = qrs_cov(Y, pk, half)
        vals, vecs = eigh(Cf, C)
        w = unit(vecs[:, -1])
        lam = float(vals[-1])
    return w, lam


def train_rate(y, start=512):
    pk = detect_on(y)
    pk = pk[pk >= start]
    if len(pk) < 3:
        return 0.0
    return 60.0 * FS / float(np.median(np.diff(pk)))


def candidate_score(y, start, mpk):
    pk = detect_on(y)
    pk = pk[pk >= start]
    reg = rr_regularity(pk, len(y) - start)
    ac = autocorr_score(y)
    co = coincidence(pk, mpk) if mpk is not None else 0.0
    return reg + 0.5 * ac - 3.0 * max(0.0, co - 0.3), co


def calib_selfref(Xbuf, start=512, iters=3, use_maternal=True, extra_seeds=True):
    """
    Host calibration on the received buffer Xbuf (N,C) raw counts.
    1. detector-band filter each channel (same filters as FPGA)
    2. maternal beats from PC1 (dominant source) -> label-free maternal reference
    3. candidate seeds: PCA directions 2..C, maternal-nulling GEVD directions
    4. refine each seed with the self-referencing GEVD loop
    5. choose the refined filter whose beat train is regular, periodic and NOT
       time-locked to the maternal beats
    """
    Y = band(Xbuf)
    V = pca_dirs(Y[start:])
    mpk = None
    seeds = [V[:, j] for j in range(1, V.shape[1])]
    if use_maternal:
        mpk = maternal_peaks(Y @ V[:, 0], start)
        if extra_seeds and len(mpk) >= 4:
            C = Y[start:].T @ Y[start:] / (len(Y) - start)
            Cm = qrs_cov(Y, mpk, 8) + 1e-3 * np.trace(C) / C.shape[0] * np.eye(C.shape[0])
            vals, vecs = eigh(C, Cm)              # max total power per unit maternal-QRS power
            seeds += [vecs[:, -1], vecs[:, -2]]
    best, best_s, info = None, -1e9, []
    for s0 in seeds:
        w, lam = refine(Y, s0, iters=iters, start=start, mpk=mpk)
        s, co = candidate_score(Y @ w, start, mpk)
        info.append((round(s, 3), round(co, 2), round(lam, 2)))
        if s > best_s:
            best, best_s = w, s
    # Fallback: no good candidate orthogonal to the dominant source, but the dominant
    # source itself is a regular beat train at a fetal-plausible rate -> the dominant
    # source IS the fetus (weak maternal ECG).  Use it, refined without exclusion.
    if use_maternal and best_s < FALLBACK_SCORE:
        w1, lam1 = refine(Y, V[:, 0], iters=iters, start=start, mpk=None)
        s1, _ = candidate_score(Y @ w1, start, None)
        r1 = train_rate(Y @ w1, start)
        pkb = detect_on(Y @ best)
        pkb = pkb[pkb >= start]
        rb = train_rate(Y @ best, start) if rr_regularity_any(pkb) >= 0.5 else 0.0
        info.append(("pc1", round(s1, 3), round(r1, 1), round(rb, 1)))
        # FHR > MHR: the dominant source can only be the fetus if it is the faster one
        if s1 > best_s + FALLBACK_SCORE and r1 > 1.05 * rb:
            best, best_s = w1, s1
    return best, best_s, info


FALLBACK_SCORE = 0.5


def subspace2(Xbuf, w, start=512, half=4, ridge=1e-3, k=2):
    """Given the chosen fetal filter w, return the top-k self-referencing GEVD
    directions normalised to unit total (C-weighted) power, so that sum of squares
    of the k projections is a fetal-energy detector statistic."""
    Y = band(Xbuf)
    V = pca_dirs(Y[start:])
    mpk = maternal_peaks(Y @ V[:, 0], start)
    C = Y[start:].T @ Y[start:] / (len(Y) - start)
    C = C + ridge * np.trace(C) / C.shape[0] * np.eye(C.shape[0])
    pk = detect_on(Y @ w)
    pk = pk[pk >= start]
    pk2 = drop_near(pk, mpk)
    if len(pk2) >= 4:
        pk = pk2
    Cf = qrs_cov(Y, pk, half)
    vals, vecs = eigh(Cf, C)          # vecs normalised: v^T C v = 1
    Wk = vecs[:, ::-1][:, :k]
    if np.dot(Wk[:, 0], w) < 0:
        Wk[:, 0] = -Wk[:, 0]
    return Wk, vals[::-1][:k]


def fetal_cov(Xbuf, w, start=512, half=4):
    """Fetal-QRS covariance (detector band) from the pipeline's own detections with
    filter w on the calibration buffer, maternal-coincident detections excluded."""
    Y = band(Xbuf)
    V = pca_dirs(Y[start:])
    mpk = maternal_peaks(Y @ V[:, 0], start)
    pk = detect_on(Y @ w)
    pk = pk[pk >= start]
    pk2 = drop_near(pk, mpk)
    if len(pk2) >= 4:
        pk = pk2
    return qrs_cov(Y, pk, half)


def adaptive_schedule(X, cal_end=3000, every=500, win=1250, ridge=1e-6, n=None, beta=1.0):
    """
    Causal adaptive beamformer schedule.
      t = cal_end : self-referencing calibration -> w0, fetal covariance Cf and
                    calibration interference covariance C0
      every `every` samples: C = C0 + beta * C_recent (last `win` samples), so new
      interference (e.g. contractions) is nulled while the calibration solution is
      kept when nothing changes.  w = top GEVD(Cf, C), rescaled so that the fetal
      QRS response w'Cf w stays equal to the calibration value (keeps the detector
      threshold meaningful across updates).
    Only samples < t are used to compute the weights applied from t.
    """
    n = n or len(X)
    w0, s, _ = calib_selfref(X[:cal_end])
    Cf = fetal_cov(X[:cal_end], w0)
    Y = band(X)                       # causal filter; Y[:t] depends only on X[:t]
    Zc = Y[512:cal_end]
    C0 = Zc.T @ Zc / len(Zc)
    resp0 = float(w0 @ Cf @ w0)
    sched = [(cal_end, w0)]
    t = cal_end + every
    while t < n:
        Z = Y[max(0, t - win):t]
        C = C0 + beta * (Z.T @ Z / len(Z))
        C = C + ridge * np.trace(C) / C.shape[0] * np.eye(C.shape[0])
        vals, vecs = eigh(Cf, C)
        w = vecs[:, -1]
        w = w * np.sqrt(resp0 / max(float(w @ Cf @ w), 1e-30))
        if np.max(np.abs(w)) > 0.999:
            w = w * 0.999 / np.max(np.abs(w))
        if np.dot(w, sched[-1][1]) < 0:
            w = -w
        sched.append((t, w))
        t += every
    return sched


def adaptive_schedule2(X, cal_end=3000, every=500, win=1250, fwin=2500, alpha=0.3,
                       reg_min=0.7, beta=1.0, ridge=RIDGE, n=None):
    """
    adaptive_schedule + fetal-signature tracking.
    At each update the host also runs the detector with the CURRENT weights on the
    last `fwin` samples (exactly what the FPGA does), drops maternal-coincident
    beats, and - only if that beat train is regular (rr_regularity >= reg_min) -
    blends the fetal-QRS covariance of those beats into Cf (trace-normalised).
    """
    n = n or len(X)
    w0, s, _ = calib_selfref(X[:cal_end])
    Cf = fetal_cov(X[:cal_end], w0)
    trf = np.trace(Cf)
    Y = band(X)
    Zc = Y[512:cal_end]
    C0 = Zc.T @ Zc / len(Zc)
    V0 = pca_dirs(Zc)
    resp0 = float(w0 @ Cf @ w0)
    sched = [(cal_end, w0)]
    t = cal_end + every
    while t < n:
        w_cur = sched[-1][1]
        lo = max(0, t - fwin)
        Yw = Y[lo:t]
        pk = detect_on(Yw @ w_cur, 0, 256)
        pk = pk[pk >= 256]
        if len(pk) >= 6 and rr_regularity(pk, len(Yw)) >= reg_min:
            mpk = maternal_peaks(Yw @ V0[:, 0], 256)
            pk2 = drop_near(pk, mpk)
            if len(pk2) >= 6:
                Cn = qrs_cov(Yw, pk2, 4)
                Cn = Cn * (trf / max(np.trace(Cn), 1e-30))
                Cf = (1 - alpha) * Cf + alpha * Cn
        Z = Y[max(0, t - win):t]
        C = C0 + beta * (Z.T @ Z / len(Z))
        C = C + ridge * np.trace(C) / C.shape[0] * np.eye(C.shape[0])
        vals, vecs = eigh(Cf, C)
        w = vecs[:, -1]
        w = w * np.sqrt(resp0 / max(float(w @ Cf @ w), 1e-30))
        if np.max(np.abs(w)) > 0.999:
            w = w * 0.999 / np.max(np.abs(w))
        if np.dot(w, w_cur) < 0:
            w = -w
        sched.append((t, w))
        t += every
    return sched


def gated_schedule(X, cal_end=3000, every=500, win=1250, gate=2.0, beta=1.0, ridge=RIDGE, n=None):
    """
    Static self-referencing calibration, plus interference nulling that switches on
    only when new interference appears.  rho = tr(C0^-1 C_recent)/M is the recent
    detector-band power relative to the calibration covariance (whitened); rho ~ 1
    when nothing changed.  If rho > gate: w = GEVD(Cf, C0 + beta*C_recent) with the
    fetal response held constant; else w = w0.
    """
    n = n or len(X)
    w0, s, _ = calib_selfref(X[:cal_end])
    Cf = fetal_cov(X[:cal_end], w0)
    Y = band(X)
    Zc = Y[512:cal_end]
    C0 = Zc.T @ Zc / len(Zc)
    M = C0.shape[0]
    C0i = np.linalg.inv(C0 + ridge * np.trace(C0) / M * np.eye(M))
    resp0 = float(w0 @ Cf @ w0)
    sched = [(cal_end, w0)]
    t = cal_end + every
    while t < n:
        Z = Y[max(0, t - win):t]
        Cr = Z.T @ Z / len(Z)
        rho = float(np.trace(C0i @ Cr)) / M
        if rho > gate:
            C = C0 + beta * Cr
            C = C + ridge * np.trace(C) / M * np.eye(M)
            vals, vecs = eigh(Cf, C)
            w = vecs[:, -1]
            w = w * np.sqrt(resp0 / max(float(w @ Cf @ w), 1e-30))
            if np.max(np.abs(w)) > 0.999:
                w = w * 0.999 / np.max(np.abs(w))
            if np.dot(w, sched[-1][1]) < 0:
                w = -w
        else:
            w = w0
        if not np.allclose(w, sched[-1][1]):
            sched.append((t, w))
        t += every
    return sched


def _anchor(Xbuf, w):
    """Calibration anchor from a raw buffer and chosen fetal filter w."""
    Cf = fetal_cov(Xbuf, w)
    Zc = band(Xbuf)[512:]
    C0 = Zc.T @ Zc / len(Zc)
    M = C0.shape[0]
    C0i = np.linalg.inv(C0 + RIDGE * np.trace(C0) / M * np.eye(M))
    return Cf, C0, C0i, float(w @ Cf @ w)


def robust_schedule(X, cal_end=3000, every=500, win=1250, gate=4.0, beta=1.0,
                    qwin=2500, q_min=0.6, q_bad_n=2, recal_len=3000, margin=0.1, n=None):
    """
    gated_schedule + lock-loss recovery.
    Every update the host checks the beat train the detector produces with the
    current weights over the last `qwin` samples.  After `q_bad_n` consecutive
    checks with regularity < q_min it re-runs the self-referencing calibration on
    the last `recal_len` samples and adopts it if it scores better (+margin) on
    that buffer than the current weights.  Everything uses only past samples.
    """
    n = n or len(X)
    w0, s, _ = calib_selfref(X[:cal_end])
    Cf, C0, C0i, resp0 = _anchor(X[:cal_end], w0)
    M = C0.shape[0]
    Y = band(X)
    sched = [(cal_end, w0)]
    bad = 0
    t = cal_end + every
    while t < n:
        w_cur = sched[-1][1]
        # ---- lock-loss monitor (same detector as the FPGA) ----
        Yq = Y[max(0, t - qwin):t]
        pk = detect_on(Yq @ w_cur, 0, 256)
        pk = pk[pk >= 256]
        q = rr_regularity(pk, len(Yq))
        bad = bad + 1 if q < q_min else 0
        if bad >= q_bad_n and t >= recal_len:
            Xb = X[t - recal_len:t]
            w_new, s_new, _ = calib_selfref(Xb)
            Yb = band(Xb)
            Vb = pca_dirs(Yb[512:])
            mpk = maternal_peaks(Yb @ Vb[:, 0])
            s_cur, _ = candidate_score(Yb @ w0, 512, mpk)
            s_n, _ = candidate_score(Yb @ w_new, 512, mpk)
            if s_n > s_cur + margin:
                w0 = w_new
                Cf, C0, C0i, resp0 = _anchor(Xb, w0)
            bad = 0
        # ---- gated interference nulling ----
        Z = Y[max(0, t - win):t]
        Cr = Z.T @ Z / len(Z)
        rho = float(np.trace(C0i @ Cr)) / M
        if rho > gate:
            C = C0 + beta * Cr
            C = C + RIDGE * np.trace(C) / M * np.eye(M)
            vals, vecs = eigh(Cf, C)
            w = vecs[:, -1]
            w = w * np.sqrt(resp0 / max(float(w @ Cf @ w), 1e-30))
            if np.max(np.abs(w)) > 0.999:
                w = w * 0.999 / np.max(np.abs(w))
            if np.dot(w, w_cur) < 0:
                w = -w
        else:
            w = w0
        if not np.allclose(w, w_cur):
            sched.append((t, w))
        t += every
    return sched

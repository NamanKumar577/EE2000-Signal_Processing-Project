"""
src/fecg/host/adaptive_beamformer.py
────────────────────────────────────────────────────────────────────────────
Host-side causal, label-free spatial calibration for the Spartan-7 FECG
pipeline ("self-referencing gated beamformer").

The FPGA projects the 4 abdominal leads with Q1.15 weights w (y = w^T x).  The
host chooses w.  Everything here uses ONLY samples the host has already
streamed to the FPGA, and the pipeline's own beat detections on them; reference
annotations are never used.

Algorithm
  1. Initial calibration on the first CAL_LEN samples (12 s):
     a. Filter each lead with the FPGA front end (HP1 + LP40 + 12-35 Hz band).
     b. Maternal reference: R peaks of the dominant principal component.
     c. Seeds: PCA directions 2..4 and two maternal-nulling GEVD directions.
     d. Self-referencing refinement of every seed (3 iterations):
          detect beats on y = w^T x  ->  drop beats coincident with maternal R
          peaks  ->  Cf = covariance of the leads around those beats
          (fetal-QRS covariance)  ->  w = top generalised eigenvector of
          (Cf, C), C = total covariance.  This maximises fetal-QRS power
          relative to everything else (an estimate of the max-SINR filter).
     e. Choose the refined filter whose beat train is regular, periodic, at a
        fetal-plausible rate and NOT time-locked to the maternal beats.  If no
        candidate is acceptable but the dominant component is itself a regular
        train FASTER than the competing one (FHR > MHR) and >= 110 bpm, the
        dominant component is the fetus (weak maternal ECG).
     -> sent as a 0xC4 packet (weights + detector warm-up restart).
  2. Every UPDATE_EVERY samples (2 s): rho = tr(C0^-1 C_recent)/4 compares the
     last 5 s with the calibration covariance C0.  If rho > GATE (new strong
     interference, e.g. a uterine contraction) the weights become
     GEVD(Cf, C0 + C_recent) with the fetal response held constant; otherwise
     the calibration weights are (re)used.  -> 0xC3 packets.

Measured on FECGSYNDB (1,248 single-fetus records, see
tools/accuracy/README.md) with the frozen detector: F1 82.2% -> 95.2%,
FHR MAE 18.8 -> 2.6 bpm.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from scipy.linalg import eigh
from scipy.signal import find_peaks, lfilter, sosfilt

from fecg.hardware.bit_accurate_reference import (
    DET_BP_CONFIG_C_COEFFS_Q15,
    LP40_COEFFS_Q15,
)

FS = 250
WARMUP = 512             # detector warm-up used inside calibration buffers
CAL_LEN = 3000           # initial calibration buffer (12 s)
UPDATE_EVERY = 500       # 2 s
RECENT_WIN = 1250        # 5 s
GATE = 4.0               # whitened power ratio that switches nulling on
RIDGE = 1e-6             # relative diagonal loading (must stay tiny: the trace
                         # is dominated by the maternal ECG)
FHR_LO, FHR_HI = 80.0, 220.0
FALLBACK_SCORE = 0.5
FALLBACK_MIN_BPM = 110.0
WEIGHT_MAX = 0.999


# ──────────────────────────────────────────────────────────────────────────────
# FPGA front end (float) and detector
# ──────────────────────────────────────────────────────────────────────────────

def _q15_to_sos(coeffs):
    return np.array([[b0 / 32768, b1 / 32768, b2 / 32768, 1.0, -a1n / 32768, -a2n / 32768]
                     for b0, b1, b2, a1n, a2n in coeffs])


LP_SOS = _q15_to_sos(LP40_COEFFS_Q15)
BP_SOS = _q15_to_sos(DET_BP_CONFIG_C_COEFFS_Q15)


def hp1(x: np.ndarray, k: int = 6) -> np.ndarray:
    a = 2.0 ** -k
    return x - lfilter([0.0, a], [1.0, -(1 - a)], x, axis=0)


def band(X: np.ndarray) -> np.ndarray:
    """Per-lead FPGA front end: HP1 -> LP40 -> 12-35 Hz band-pass (causal)."""
    return sosfilt(BP_SOS, sosfilt(LP_SOS, hp1(X), axis=0), axis=0)


def mwi(sq: np.ndarray, w: int = 30) -> np.ndarray:
    c = np.cumsum(sq)
    out = c.copy()
    out[w:] = c[w:] - c[:-w]
    return out


def _detect_py(absy, e, warmup):
    """Float copy of the FPGA detector (warm-up, 1/8 EMA levels, 50-sample
    refractory, 26-sample localisation, RR<50 fusion). Returns raw peaks."""
    n = len(e)
    raw: List[int] = []
    peak = noise = wmax = wsum = 0.0
    enabled = False
    last = -10 ** 9
    for t in range(n):
        if t < warmup:
            wmax = max(wmax, e[t])
            wsum += e[t]
            if t == warmup - 1:
                peak, noise = wmax, wsum / warmup
                enabled = peak > noise
            continue
        if not enabled or t < 2:
            continue
        m = t - 1
        v = e[m]
        if e[m - 1] < v and v >= e[t]:
            thr = 0.25 * peak + 0.75 * noise
            if v > thr:
                if m - last >= 50:
                    lo = max(0, t - 25)
                    best = lo + int(np.argmax(absy[lo:t + 1]))
                    if raw and best - raw[-1] < 50:
                        if absy[best] > absy[raw[-1]]:
                            raw[-1] = best
                    else:
                        raw.append(best)
                    last = m
                    peak += (v - peak) / 8.0
            else:
                noise += (v - noise) / 8.0
    return np.asarray(raw, dtype=np.int64)


try:  # numba makes calibration ~50x faster; the algorithm is identical without it
    from numba import njit as _njit

    @_njit(cache=True)
    def _detect_nb(absy, e, warmup):
        n = len(e)
        raw = np.empty(n // 20 + 10, np.int64)
        k = 0
        peak = 0.0
        noise = 0.0
        wmax = 0.0
        wsum = 0.0
        enabled = False
        last = -10 ** 9
        for t in range(n):
            if t < warmup:
                if e[t] > wmax:
                    wmax = e[t]
                wsum += e[t]
                if t == warmup - 1:
                    peak = wmax
                    noise = wsum / warmup
                    enabled = peak > noise
                continue
            if (not enabled) or t < 2:
                continue
            m = t - 1
            v = e[m]
            if e[m - 1] < v and v >= e[t]:
                thr = 0.25 * peak + 0.75 * noise
                if v > thr:
                    if m - last >= 50:
                        lo = max(0, t - 25)
                        best = lo
                        for i in range(lo + 1, t + 1):
                            if absy[i] > absy[best]:
                                best = i
                        if k > 0 and best - raw[k - 1] < 50:
                            if absy[best] > absy[raw[k - 1]]:
                                raw[k - 1] = best
                        else:
                            raw[k] = best
                            k += 1
                        last = m
                        peak += (v - peak) / 8.0
                else:
                    noise += (v - noise) / 8.0
        return raw[:k]

    def detect(y: np.ndarray, warmup: int = WARMUP) -> np.ndarray:
        y = np.ascontiguousarray(y, dtype=np.float64)
        return _detect_nb(np.abs(y), mwi(y * y), warmup)
except ImportError:  # pragma: no cover
    def detect(y: np.ndarray, warmup: int = WARMUP) -> np.ndarray:
        y = np.asarray(y, dtype=np.float64)
        return _detect_py(np.abs(y), mwi(y * y), warmup)


# ──────────────────────────────────────────────────────────────────────────────
# Label-free beat-train statistics
# ──────────────────────────────────────────────────────────────────────────────

def _regularity(peaks: np.ndarray, lo: float = FHR_LO, hi: float = FHR_HI) -> float:
    """Fraction of RR within 15% of the median RR; 0 if rate outside [lo, hi] bpm."""
    if len(peaks) < 6:
        return 0.0
    rr = np.diff(peaks)
    med = np.median(rr)
    bpm = 60.0 * FS / med
    if bpm < lo or bpm > hi:
        return 0.0
    return float(np.mean(np.abs(rr - med) <= 0.15 * med))


def _autocorr(y: np.ndarray, lo_bpm: float = 83.0, hi_bpm: float = 200.0) -> float:
    e = mwi(y * y)[WARMUP:]
    e = e - e.mean()
    n = len(e)
    if n < 300:
        return 0.0
    f = np.fft.rfft(e, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    if ac[0] <= 0:
        return 0.0
    ac = ac / ac[0]
    return float(ac[int(FS * 60 / hi_bpm):int(FS * 60 / lo_bpm) + 1].max())


def _nearest_dist(pk: np.ndarray, ref: np.ndarray) -> np.ndarray:
    j = np.searchsorted(ref, pk)
    d1 = np.abs(pk - ref[np.clip(j - 1, 0, len(ref) - 1)])
    d2 = np.abs(pk - ref[np.clip(j, 0, len(ref) - 1)])
    return np.minimum(d1, d2)


def _coincidence(pk, mpk, tol=10) -> float:
    if len(pk) == 0 or len(mpk) == 0:
        return 0.0
    return float(np.mean(_nearest_dist(pk, mpk) <= tol))


def _drop_near(pk, mpk, tol=6):
    if len(pk) == 0 or len(mpk) == 0:
        return pk
    return pk[_nearest_dist(pk, mpk) > tol]


def _peaks_after(y, start=WARMUP):
    pk = detect(y)
    return pk[pk >= start]


def _rate(pk) -> float:
    return 0.0 if len(pk) < 3 else 60.0 * FS / float(np.median(np.diff(pk)))


def _score(y, mpk) -> float:
    pk = _peaks_after(y)
    co = _coincidence(pk, mpk) if mpk is not None else 0.0
    return _regularity(pk) + 0.5 * _autocorr(y) - 3.0 * max(0.0, co - 0.3)


def maternal_peaks(y: np.ndarray, start: int = WARMUP) -> np.ndarray:
    """R peaks of the dominant component: 120 ms energy peaks above 30% of the
    robust maximum, >= 300 ms apart; localised on |y| like the FPGA."""
    e = mwi(y * y)
    e[:start] = 0
    pk, _ = find_peaks(e, height=0.3 * np.percentile(e[start:], 99.5), distance=75)
    return np.array([max(0, p - 25) + int(np.argmax(np.abs(y[max(0, p - 25):p + 1]))) for p in pk],
                    dtype=np.int64)


def _qrs_cov(Y, pk, half=4):
    idx = (pk[:, None] + np.arange(-half, half + 1)[None, :]).ravel()
    idx = idx[(idx >= 0) & (idx < len(Y))]
    Z = Y[idx]
    return Z.T @ Z / max(len(Z), 1)


def _unit(w):
    w = np.asarray(w, dtype=np.float64)
    if w[np.argmax(np.abs(w))] < 0:
        w = -w
    return w / np.linalg.norm(w)


def _loaded(C):
    M = C.shape[0]
    return C + RIDGE * np.trace(C) / M * np.eye(M)


# ──────────────────────────────────────────────────────────────────────────────
# Calibration
# ──────────────────────────────────────────────────────────────────────────────

def _refine(Y, w0, mpk, iters=3):
    w = _unit(w0)
    C = _loaded(Y[WARMUP:].T @ Y[WARMUP:] / (len(Y) - WARMUP))
    for _ in range(iters):
        pk = _peaks_after(Y @ w)
        if mpk is not None:
            pk = _drop_near(pk, mpk)
        if len(pk) < 4:
            break
        vals, vecs = eigh(_qrs_cov(Y, pk), C)
        w = _unit(vecs[:, -1])
    return w


def calibrate(Xbuf: np.ndarray) -> Tuple[np.ndarray, dict]:
    """Self-referencing calibration on a raw (N, 4) buffer. Returns unit-norm w."""
    Y = band(np.asarray(Xbuf, dtype=np.float64))
    C = Y[WARMUP:].T @ Y[WARMUP:] / (len(Y) - WARMUP)
    vals, V = np.linalg.eigh(C)
    V = V[:, ::-1]
    mpk = maternal_peaks(Y @ V[:, 0])
    seeds = [V[:, j] for j in range(1, V.shape[1])]
    if len(mpk) >= 4:
        Cm = _loaded(_qrs_cov(Y, mpk, 8) + 1e-3 * np.trace(C) / C.shape[0] * np.eye(C.shape[0]))
        _, mv = eigh(C, Cm)
        seeds += [mv[:, -1], mv[:, -2]]
    best, best_s = None, -1e9
    for s0 in seeds:
        w = _refine(Y, s0, mpk)
        s = _score(Y @ w, mpk)
        if s > best_s:
            best, best_s = w, s
    info = {"score": best_s, "fallback": False}
    if best_s < FALLBACK_SCORE:
        w1 = _refine(Y, V[:, 0], None)
        s1 = _score(Y @ w1, None)
        pkb = _peaks_after(Y @ best)
        rb = _rate(pkb) if _regularity(pkb, 0.0, 1e9) >= 0.5 else 0.0
        r1 = _rate(_peaks_after(Y @ w1))
        # FHR > MHR, and a dominant source slower than normal FHR (110 bpm) is taken
        # to be the mother: on real abdominal recordings the maternal ECG dominates.
        if s1 > best_s + FALLBACK_SCORE and r1 > 1.05 * rb and r1 >= FALLBACK_MIN_BPM:
            best, best_s = w1, s1
            info.update(score=s1, fallback=True)
    return best, info


def fetal_covariance(Xbuf: np.ndarray, w: np.ndarray) -> np.ndarray:
    Y = band(np.asarray(Xbuf, dtype=np.float64))
    C = Y[WARMUP:].T @ Y[WARMUP:]
    _, V = np.linalg.eigh(C)
    mpk = maternal_peaks(Y @ V[:, -1])
    pk = _peaks_after(Y @ w)
    pk2 = _drop_near(pk, mpk)
    return _qrs_cov(Y, pk2 if len(pk2) >= 4 else pk)


def to_q15(w: np.ndarray) -> List[int]:
    return [int(v) for v in np.clip(np.round(np.asarray(w) * 32768.0), -32768, 32767)]


# ──────────────────────────────────────────────────────────────────────────────
# Streaming host controller
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class WeightCommand:
    t: int                 # sample index from which the FPGA applies the weights
    w_q15: List[int]
    restart: bool          # True -> send as 0xC4 (restart detector warm-up)


@dataclass
class AdaptiveBeamformerHost:
    """
    Feed raw samples as they are streamed; returns the weight packets to send.
    A command returned by push() at sample t must be sent before sample t.
    """
    cal_len: int = CAL_LEN
    every: int = UPDATE_EVERY
    win: int = RECENT_WIN
    gate: float = GATE
    _buf: List[np.ndarray] = field(default_factory=list)
    _n: int = 0
    _w0: Optional[np.ndarray] = None
    _w_cur: Optional[np.ndarray] = None
    _Cf: Optional[np.ndarray] = None
    _C0: Optional[np.ndarray] = None
    _C0i: Optional[np.ndarray] = None
    _resp0: float = 0.0
    _next: int = 0
    _zi: Optional[list] = None
    _Ytail: Optional[np.ndarray] = None

    def push(self, x: np.ndarray) -> List[WeightCommand]:
        x = np.atleast_2d(np.asarray(x, dtype=np.float64))
        cmds: List[WeightCommand] = []
        for row in x:
            self._buf.append(row)
            self._n += 1
            if self._w0 is None:
                if self._n == self.cal_len:
                    cmds.append(self._initial())
            elif self._n == self._next:
                c = self._update()
                if c is not None:
                    cmds.append(c)
                self._next += self.every
        return cmds

    def _initial(self) -> WeightCommand:
        X = np.array(self._buf)
        w0, _ = calibrate(X)
        self._w0 = self._w_cur = w0
        self._Cf = fetal_covariance(X, w0)
        Zc = band(X)[WARMUP:]
        self._C0 = Zc.T @ Zc / len(Zc)
        self._C0i = np.linalg.inv(_loaded(self._C0))
        self._resp0 = float(w0 @ self._Cf @ w0)
        self._next = self._n + self.every
        return WeightCommand(self._n, to_q15(w0), True)

    def _update(self) -> Optional[WeightCommand]:
        # causal band filtering of the recent window (warm-start with 4x context)
        Z = band(np.array(self._buf[-4 * self.win:]))[-self.win:]
        Cr = Z.T @ Z / len(Z)
        M = Cr.shape[0]
        rho = float(np.trace(self._C0i @ Cr)) / M
        if rho > self.gate:
            _, vecs = eigh(self._Cf, _loaded(self._C0 + Cr))
            w = vecs[:, -1]
            w = w * np.sqrt(self._resp0 / max(float(w @ self._Cf @ w), 1e-30))
            if np.max(np.abs(w)) > WEIGHT_MAX:
                w = w * WEIGHT_MAX / np.max(np.abs(w))
            if np.dot(w, self._w_cur) < 0:
                w = -w
        else:
            w = self._w0
        if len(self._buf) > 8 * self.win + self.cal_len:   # bound memory
            del self._buf[: len(self._buf) - 8 * self.win]
        if np.allclose(w, self._w_cur):
            return None
        self._w_cur = w
        return WeightCommand(self._n, to_q15(w), False)


def plan_schedule(X: np.ndarray, **kw) -> List[WeightCommand]:
    """Run the streaming controller over a whole record (offline evaluation).
    Identical decisions to live use: each command depends only on X[:t]."""
    host = AdaptiveBeamformerHost(**kw)
    cmds: List[WeightCommand] = []
    step = 250
    for i in range(0, len(X), step):
        cmds += host.push(X[i:i + step])
    return cmds

"""
tools/accuracy/pipeline.py
Float mirror of the frozen FPGA datapath (same filters, same detector logic as
src/fecg/hardware/bit_accurate_reference.py) with switches for the candidate
causal improvements.  Detector loop compiled with numba.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from numba import njit
from scipy.signal import sosfilt, lfilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fecg.hardware.bit_accurate_reference import (  # noqa: E402
    LP40_COEFFS_Q15, DET_BP_CONFIG_C_COEFFS_Q15,
)

FS = 250


def q15_to_sos(coeffs):
    return np.array([[b0 / 32768, b1 / 32768, b2 / 32768, 1.0, -a1n / 32768, -a2n / 32768]
                     for b0, b1, b2, a1n, a2n in coeffs])


LP_SOS = q15_to_sos(LP40_COEFFS_Q15)
BP_SOS = q15_to_sos(DET_BP_CONFIG_C_COEFFS_Q15)
LP0_SOS, BP0_SOS = LP_SOS, BP_SOS
V4_BAND = (60, 15, 40)          # wider detection band adopted for v4 (LP60, BP 15-40 Hz)


def set_band(spec):
    """Swap the float front-end/detector filters. None = deployed FPGA filters
    (LP40, BP 12-35); (lp_hz, bp_lo, bp_hi[, notch_hz]) = Butterworth LP4 and BP4."""
    global LP_SOS, BP_SOS
    if spec is None:
        LP_SOS, BP_SOS = LP0_SOS, BP0_SOS
        return
    from scipy.signal import butter, iirnotch, tf2sos
    LP_SOS = butter(4, spec[0], fs=FS, output="sos")
    BP_SOS = butter(4, [spec[1], spec[2]], btype="band", fs=FS, output="sos")
    if len(spec) > 3 and spec[3]:
        b, a = iirnotch(spec[3], 10, fs=FS)
        BP_SOS = np.vstack([BP_SOS, tf2sos(b, a)])


def hp1(x: np.ndarray, k: int = 6) -> np.ndarray:
    """y[n] = x[n] - B[n-1];  B[n] = B[n-1] + 2^-k * y[n]  (works on 1-D or (N,C))."""
    a = 2.0 ** -k
    # B[n] = (1-a) B[n-1] + a x[n]  -> y = x - B[n-1]
    b_num = [0.0, a]          # B[n-1] as function of x: z^-1 * a / (1 - (1-a) z^-1)
    b_den = [1.0, -(1 - a)]
    Bm1 = lfilter(b_num, b_den, x, axis=0)
    return x - Bm1


def front_end(x: np.ndarray):
    """x: 1-D projected signal. Returns fecg (LP40 out) and detector band signal."""
    h = hp1(x)
    fe = sosfilt(LP_SOS, h)
    bp = sosfilt(BP_SOS, fe)
    return fe, bp


def mwi(sq: np.ndarray, w: int = 30) -> np.ndarray:
    c = np.cumsum(sq)
    out = c.copy()
    out[w:] = c[w:] - c[:-w]
    return out


@njit(cache=True)
def detect(absbp, e, det_start, warmup, refractory, loc, latency, rr_min, rr_max,
           searchback, sb_factor):
    """
    Mirror of the frozen detector.  det_start: sample at which the detector
    (re)starts its warm-up.  searchback=1 enables the causal search-back
    extension (see below); 0 = frozen behaviour.
    Returns compensated peaks, raw peaks, per-sample FHR (bpm).
    """
    n = len(e)
    comp = np.empty(n // 20 + 10, np.int64)
    raw = np.empty(n // 20 + 10, np.int64)
    np_ = 0
    fhr = np.zeros(n)
    medbuf = np.zeros(5, np.int64)
    nmed = 0
    fhr_cur = 0.0
    peak_level = 0.0
    noise_level = 0.0
    wmax = 0.0
    wsum = 0.0
    enabled = False
    last = -10 ** 9
    for t in range(det_start, n):
        if t < det_start + warmup:
            if e[t] > wmax:
                wmax = e[t]
            wsum += e[t]
            if t == det_start + warmup - 1:
                peak_level = wmax
                noise_level = wsum / warmup
                enabled = peak_level > noise_level
            continue
        if enabled and t >= 2:
            m = t - 1
            v = e[m]
            vp = e[m - 1]
            if vp < v and v >= e[t]:
                thr = 0.25 * peak_level + 0.75 * noise_level
                if v > thr:
                    if m - last >= refractory:
                        lo = max(0, t - (loc - 1))
                        best = lo
                        bv = absbp[lo]
                        for i in range(lo + 1, t + 1):
                            if absbp[i] > bv:
                                bv = absbp[i]
                                best = i
                        cidx = max(0, best - latency)
                        if np_ > 0:
                            rr = best - raw[np_ - 1]
                            if rr < rr_min:
                                if bv > absbp[raw[np_ - 1]]:
                                    raw[np_ - 1] = best
                                    comp[np_ - 1] = cidx
                            elif rr <= rr_max:
                                raw[np_] = best
                                comp[np_] = cidx
                                np_ += 1
                                # median-5
                                if nmed < 5:
                                    medbuf[nmed] = rr
                                    nmed += 1
                                else:
                                    for q in range(4):
                                        medbuf[q] = medbuf[q + 1]
                                    medbuf[4] = rr
                                s = np.sort(medbuf[:nmed])
                                if nmed % 2 == 1:
                                    med = s[nmed // 2]
                                else:
                                    med = (s[nmed // 2 - 1] + s[nmed // 2] + 1) // 2
                                fhr_cur = 15000.0 / med
                            else:
                                raw[np_] = best
                                comp[np_] = cidx
                                np_ += 1
                        else:
                            raw[np_] = best
                            comp[np_] = cidx
                            np_ += 1
                        last = m
                        peak_level += (v - peak_level) / 8.0
                else:
                    noise_level += (v - noise_level) / 8.0
        fhr[t] = fhr_cur
    return comp[:np_], raw[:np_], fhr


@njit(cache=True)
def _commit(best, bv, absbp, raw, comp, np_, medbuf, nmed, fhr_cur, latency, rr_min, rr_max):
    """Frozen interval-fusion + median-5 FHR logic for one accepted beat."""
    cidx = max(0, best - latency)
    if np_ > 0:
        rr = best - raw[np_ - 1]
        if rr < rr_min:
            if bv > absbp[raw[np_ - 1]]:
                raw[np_ - 1] = best
                comp[np_ - 1] = cidx
            return np_, nmed, fhr_cur
        raw[np_] = best
        comp[np_] = cidx
        np_ += 1
        if rr <= rr_max:
            if nmed < 5:
                medbuf[nmed] = rr
                nmed += 1
            else:
                for q in range(4):
                    medbuf[q] = medbuf[q + 1]
                medbuf[4] = rr
            s = np.sort(medbuf[:nmed])
            if nmed % 2 == 1:
                med = s[nmed // 2]
            else:
                med = (s[nmed // 2 - 1] + s[nmed // 2] + 1) // 2
            fhr_cur = 15000.0 / med
        return np_, nmed, fhr_cur
    raw[np_] = best
    comp[np_] = cidx
    return np_ + 1, nmed, fhr_cur


@njit(cache=True)
def _localize(absbp, t, loc):
    lo = max(0, t - (loc - 1))
    best = lo
    bv = absbp[lo]
    for i in range(lo + 1, t + 1):
        if absbp[i] > bv:
            bv = absbp[i]
            best = i
    return best, bv


@njit(cache=True)
def _median_rr(medbuf, nmed):
    s = np.sort(medbuf[:nmed])
    if nmed % 2 == 1:
        return s[nmed // 2]
    return (s[nmed // 2 - 1] + s[nmed // 2] + 1) // 2


@njit(cache=True)
def detect2(absbp, e, det_start, warmup, refractory, loc, latency, rr_min, rr_max,
            sb_on, sb_frac, sb_lo, sb_hi, sb_wait, clamp_k=0.0, art_k=0.0):
    """
    Frozen detector + causal search-back.
    While waiting for the next beat, remember the strongest sub-threshold MWI peak
    (v > sb_frac * thr) located in [sb_lo, sb_hi] x RRmed after the last beat.
    If no beat is accepted by sb_wait x RRmed after the last beat, accept the
    remembered candidate.  Decision delay <= sb_wait x RR (~0.6 s at 140 bpm).
    """
    n = len(e)
    comp = np.empty(n // 20 + 10, np.int64)
    raw = np.empty(n // 20 + 10, np.int64)
    np_ = 0
    fhr = np.zeros(n)
    medbuf = np.zeros(5, np.int64)
    nmed = 0
    fhr_cur = 0.0
    peak_level = 0.0
    noise_level = 0.0
    wmax = 0.0
    wsum = 0.0
    enabled = False
    last = -10 ** 9
    sb_v = 0.0
    sb_best = -1
    sb_bv = 0.0
    sb_m = -1
    for t in range(det_start, n):
        if t < det_start + warmup:
            if e[t] > wmax:
                wmax = e[t]
            wsum += e[t]
            if t == det_start + warmup - 1:
                peak_level = wmax
                noise_level = wsum / warmup
                enabled = peak_level > noise_level
            continue
        if enabled and t >= 2:
            m = t - 1
            v = e[m]
            vp = e[m - 1]
            rrmed = _median_rr(medbuf, nmed) if nmed >= 3 else 0
            if vp < v and v >= e[t]:
                thr = 0.25 * peak_level + 0.75 * noise_level
                if art_k > 0 and v > art_k * peak_level:
                    pass                      # artifact: no beat, no level update
                elif v > thr and m - last >= refractory:
                    best, bv = _localize(absbp, t, loc)
                    np_, nmed, fhr_cur = _commit(best, bv, absbp, raw, comp, np_, medbuf, nmed,
                                                 fhr_cur, latency, rr_min, rr_max)
                    last = m
                    vu = min(v, clamp_k * peak_level) if clamp_k > 0 else v
                    peak_level += (vu - peak_level) / 8.0
                    sb_v = 0.0
                    sb_best = -1
                elif v <= thr:
                    noise_level += (v - noise_level) / 8.0
                    if sb_on and rrmed > 0:
                        dt = m - last
                        if dt >= sb_lo * rrmed and dt <= sb_hi * rrmed and dt >= refractory \
                                and v > sb_frac * thr and v > sb_v:
                            best, bv = _localize(absbp, t, loc)
                            sb_v = v
                            sb_best = best
                            sb_bv = bv
                            sb_m = m
            if sb_on and sb_best >= 0 and rrmed > 0 and (t - last) > sb_wait * rrmed:
                np_, nmed, fhr_cur = _commit(sb_best, sb_bv, absbp, raw, comp, np_, medbuf, nmed,
                                             fhr_cur, latency, rr_min, rr_max)
                last = sb_m
                peak_level += (sb_v - peak_level) / 4.0
                sb_v = 0.0
                sb_best = -1
        fhr[t] = fhr_cur
    return comp[:np_], raw[:np_], fhr

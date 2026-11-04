"""
src/causal_pipeline.py
──────────────────────────────────────────────────────────────────────────────
Causal (sample-by-sample) floating-point reference for the FPGA pipeline.

This implements FPGA_SPEC.md (v0.2).  Everything here only uses samples that
have already arrived, so it can be mapped to hardware.  It is deliberately
SEPARATE from preprocessing.py / qrs_detector.py, which are zero-phase
(non-causal) and are kept untouched so the old benchmark stays reproducible.

Pipeline (per sample)
---------------------
    raw 4-channel mixture  --(w . x)-->  projection
        --> HP1   : 1st-order baseline remover, shift-only (fc ~ 0.62 Hz at k=6)
        --> LP40  : 4th-order Butterworth low-pass 40 Hz (2 biquads)      = fecg_out
        --> BP    : 4th-order Butterworth band-pass 8-30 Hz (4 biquads)
        --> square --> trailing moving-window sum (20 samples)
        --> adaptive threshold + 200 ms refractory --> R-peak localisation
        --> fixed latency compensation

Why project first: all filters are linear and time-invariant and the weights
are constant, so filter(w.x) == w.filter(x).  One filter chain instead of four.

Calibration (weights) is done once by the host from the first T seconds and is
NOT part of the sample-by-sample path.  Component selection must not use
ground truth ("label-free"); the 'oracle' rule exists only to measure the
upper bound and is clearly labelled wherever it is reported.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.signal import butter, freqz, lfilter, sosfilt, sosfreqz

FS = 250

RULES_FIXED = ("pc1", "pc2", "pc3", "pc4")
RULES_LABEL_FREE = ("pc2", "pc3", "periodic_rr", "autocorr")
RULES_ALL = ("pc1", "pc2", "pc3", "pc4", "periodic_rr", "autocorr", "oracle")


# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CausalConfig:
    fs: int = FS
    hp_shift_k: int = 6            # baseline remover: fc ~ fs / (2*pi*2**k) = 0.62 Hz
    lp_hz: float = 40.0
    lp_order: int = 4
    det_low_hz: float = 8.0
    det_high_hz: float = 30.0
    det_order: int = 4
    mwi_len: int = 20              # 80 ms trailing sum
    refractory: int = 50           # 200 ms
    warmup: int = 512              # ~2.05 s; power of two so the mean is a shift
    level_shift: int = 3           # EMA 1/8 for peak and noise levels
    loc_window: int = 26           # R-peak search over the last 26 samples
    latency_comp: Optional[int] = None   # None -> computed from filter group delay
    latency_freq_hz: float = 15.0  # frequency at which delay is evaluated

    def latency(self) -> int:
        if self.latency_comp is not None:
            return int(self.latency_comp)
        return int(round(group_delay_samples(self, self.latency_freq_hz)))


DEFAULT_CONFIG = CausalConfig()


# ──────────────────────────────────────────────────────────────────────────────
# Filters
# ──────────────────────────────────────────────────────────────────────────────

def lp_sos(cfg: CausalConfig = DEFAULT_CONFIG) -> np.ndarray:
    return butter(cfg.lp_order, cfg.lp_hz / (cfg.fs / 2.0), btype="low", output="sos")


def det_sos(cfg: CausalConfig = DEFAULT_CONFIG) -> np.ndarray:
    nyq = cfg.fs / 2.0
    return butter(cfg.det_order, [cfg.det_low_hz / nyq, cfg.det_high_hz / nyq],
                  btype="band", output="sos")


def hp1_coeffs(cfg: CausalConfig = DEFAULT_CONFIG) -> Tuple[List[float], List[float]]:
    """y[n] = x[n] - B[n-1];  B[n] = B[n-1] + 2**-k (x[n] - B[n-1])."""
    beta = 2.0 ** -cfg.hp_shift_k
    return [1.0, -1.0], [1.0, -(1.0 - beta)]


def hp1_filter(x: np.ndarray, cfg: CausalConfig = DEFAULT_CONFIG) -> np.ndarray:
    b, a = hp1_coeffs(cfg)
    return lfilter(b, a, x, axis=0)


def preprocess_causal(x: np.ndarray, cfg: CausalConfig = DEFAULT_CONFIG) -> np.ndarray:
    """HP1 then LP40, causal.  Works on (n,) or (n, channels) arrays."""
    y = hp1_filter(np.asarray(x, dtype=np.float64), cfg)
    return sosfilt(lp_sos(cfg), y, axis=0)


def group_delay_samples(cfg: CausalConfig, f_hz: float) -> float:
    """Group delay (samples) of HP1 + LP40 + detector BP at f_hz."""
    w = 2.0 * np.pi * np.array([f_hz - 0.05, f_hz + 0.05]) / cfg.fs
    phase = np.zeros(2)
    b, a = hp1_coeffs(cfg)
    _, h = freqz(b, a, worN=w)
    phase += np.unwrap(np.angle(h))
    for sos in (lp_sos(cfg), det_sos(cfg)):
        _, h = sosfreqz(sos, worN=w)
        phase += np.unwrap(np.angle(h))
    return float(-(phase[1] - phase[0]) / (w[1] - w[0]))


# ──────────────────────────────────────────────────────────────────────────────
# Causal fetal QRS detector (FPGA_SPEC.md section 5)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class DetectionResult:
    peaks: np.ndarray        # latency-compensated R-peak sample indices
    raw_peaks: np.ndarray    # R-peak index in the detector-filter timeline
    decl_idx: np.ndarray     # sample index at which each beat was declared
    x_bp: Optional[np.ndarray] = None
    x_int: Optional[np.ndarray] = None


def _empty_detection() -> DetectionResult:
    e = np.array([], dtype=int)
    return DetectionResult(peaks=e, raw_peaks=e, decl_idx=e)


def moving_sum_trailing(x: np.ndarray, w: int) -> np.ndarray:
    """out[n] = sum(x[n-w+1 .. n]), zero before the start."""
    c = np.cumsum(x)
    out = c.copy()
    out[w:] -= c[:-w]
    return out


def detect_causal(
    fecg: np.ndarray,
    cfg: CausalConfig = DEFAULT_CONFIG,
    keep_debug: bool = False,
) -> DetectionResult:
    """
    Detect fetal R-peaks in `fecg` (output of preprocess_causal on the projection)
    using only past samples (plus one sample of lookahead for the local-maximum test).
    """
    x = np.asarray(fecg, dtype=np.float64)
    n = len(x)
    warm = cfg.warmup
    if n < warm + 4 or not np.all(np.isfinite(x)):
        return _empty_detection()

    x_bp = sosfilt(det_sos(cfg), x)
    x_int = moving_sum_trailing(x_bp * x_bp, cfg.mwi_len)

    peak = float(np.max(x_int[:warm]))
    noise = float(np.mean(x_int[:warm]))
    if peak <= noise:
        return _empty_detection()

    # candidate m: x_int[m-1] < x_int[m] >= x_int[m+1]; declared at n = m + 1
    a, b, c = x_int[:-2], x_int[1:-1], x_int[2:]
    cand = np.nonzero((a < b) & (b >= c))[0] + 1
    cand = cand[cand >= warm - 1]

    gain = 2.0 ** -cfg.level_shift
    abs_bp = np.abs(x_bp)
    raw_peaks: List[int] = []
    decl: List[int] = []
    last_m = -(10 ** 9)

    for m in cand:
        v = x_int[m]
        thr = 0.25 * peak + 0.75 * noise
        if v > thr:
            if m - last_m >= cfg.refractory:
                n_decl = m + 1
                lo = max(0, n_decl - (cfg.loc_window - 1))
                r = lo + int(np.argmax(abs_bp[lo:n_decl + 1]))
                raw_peaks.append(r)
                decl.append(n_decl)
                last_m = m
                peak += (v - peak) * gain
        else:
            noise += (v - noise) * gain

    raw = np.array(raw_peaks, dtype=int)
    comp = np.maximum(raw - cfg.latency(), 0)
    return DetectionResult(
        peaks=comp, raw_peaks=raw, decl_idx=np.array(decl, dtype=int),
        x_bp=x_bp if keep_debug else None, x_int=x_int if keep_debug else None,
    )


def run_causal(
    X_raw: np.ndarray,
    w: np.ndarray,
    cfg: CausalConfig = DEFAULT_CONFIG,
    keep_debug: bool = False,
) -> Tuple[np.ndarray, DetectionResult]:
    """Project -> preprocess -> detect.  X_raw is (n, channels) in physical units."""
    proj = np.asarray(X_raw, dtype=np.float64) @ np.asarray(w, dtype=np.float64)
    fecg = preprocess_causal(proj, cfg)
    return fecg, detect_causal(fecg, cfg, keep_debug=keep_debug)


# ──────────────────────────────────────────────────────────────────────────────
# Calibration: PCA weights and LABEL-FREE component selection
# ──────────────────────────────────────────────────────────────────────────────

def pca_components(Xf_window: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Eigen-decomposition of the channel covariance.  Returns (W, eigvals) with
    columns sorted by DESCENDING variance.  Each column is unit-norm with its
    largest-magnitude entry made positive (deterministic sign for hex dumps).
    """
    if Xf_window.shape[0] < 100:
        raise ValueError("calibration window too short (need >= 100 samples)")
    cov = np.cov(Xf_window, rowvar=False)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    W = evecs[:, order].copy()
    for j in range(W.shape[1]):
        if W[np.argmax(np.abs(W[:, j])), j] < 0:
            W[:, j] = -W[:, j]
    return W, evals[order]


def score_periodic_rr(
    peaks: np.ndarray, n_after_warm: int, cfg: CausalConfig,
    rate_lo: float = 100.0, rate_hi: float = 200.0,
) -> float:
    """
    Label-free score in [0, 1]: how much do the detected beats look like a regular
    fetal heartbeat?  Zero unless the median rate is inside [rate_lo, rate_hi] bpm.
    """
    if len(peaks) < 4:
        return 0.0
    rr = np.diff(peaks).astype(float)
    med = float(np.median(rr))
    if med <= 0:
        return 0.0
    rate = 60.0 * cfg.fs / med
    if not (rate_lo <= rate <= rate_hi):
        return 0.0
    regular = float(np.mean(np.abs(rr - med) <= 0.2 * med))
    expected = (n_after_warm / cfg.fs) * rate / 60.0
    coverage = min(1.0, len(peaks) / max(expected, 1.0))
    return regular * coverage


def score_autocorr(
    x_int: np.ndarray, cfg: CausalConfig,
    rate_lo: float = 100.0, rate_hi: float = 200.0,
) -> float:
    """
    Label-free score: strongest normalised autocorrelation of the detector energy
    envelope at lags corresponding to [rate_lo, rate_hi] bpm.
    """
    e = np.asarray(x_int[cfg.warmup:], dtype=float)
    n = len(e)
    lag_lo = int(cfg.fs * 60.0 / rate_hi)
    lag_hi = int(cfg.fs * 60.0 / rate_lo)
    if n <= lag_hi + 2:
        return 0.0
    e = e - e.mean()
    f = np.fft.rfft(e, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    if ac[0] <= 0:
        return 0.0
    ac = ac / ac[0]
    return float(np.max(ac[lag_lo:lag_hi + 1]))


class CalibrationBank:
    """
    Everything derived from one calibration window of one record.

    cal_seconds counts AFTER the first `cfg.warmup` samples (filter settling and
    detector warm-up); cal_seconds in (0, None) means "use the whole record".
    pca_on: "detector" (covariance on the 8-30 Hz band, default) or "preprocessed"
    (covariance on the HP1 + LP40 output, like the old benchmark).
    Component j of the bank is Xf_full @ W[:, j], i.e. filter(projection j).
    """

    def __init__(
        self,
        X_raw: np.ndarray,
        cfg: CausalConfig = DEFAULT_CONFIG,
        cal_seconds: Optional[float] = None,
        Xf_full: Optional[np.ndarray] = None,
        pca_on: str = "detector",
    ):
        if pca_on not in ("detector", "preprocessed"):
            raise ValueError("pca_on must be 'detector' or 'preprocessed'")
        self.cfg = cfg
        X_raw = np.asarray(X_raw, dtype=np.float64)
        n = X_raw.shape[0]
        self.Xf_full = preprocess_causal(X_raw, cfg) if Xf_full is None else Xf_full
        settle = cfg.warmup
        if cal_seconds in (None, 0):
            end = n
        else:
            end = min(n, settle + int(round(cal_seconds * cfg.fs)))
        self.end = end
        # The covariance is estimated on the detector band (8-30 Hz) by default: slow
        # baseline wander that survives the 0.6 Hz remover would otherwise take a
        # principal component.  This only affects the host-side weights; the weights
        # are applied to the normal HP1 + LP40 chain, so it costs nothing in hardware.
        Xp = sosfilt(det_sos(cfg), self.Xf_full, axis=0) if pca_on == "detector" else self.Xf_full
        self.W, self.eigvals = pca_components(Xp[settle:end])
        self.comps_full = self.Xf_full @ self.W
        self._prefix: Dict[int, DetectionResult] = {}
        self._full: Dict[int, DetectionResult] = {}

    def det_prefix(self, j: int) -> DetectionResult:
        """Detection using ONLY the calibration prefix (what the host can see)."""
        if j not in self._prefix:
            self._prefix[j] = detect_causal(self.comps_full[:self.end, j], self.cfg, keep_debug=True)
        return self._prefix[j]

    def det_full(self, j: int) -> DetectionResult:
        """Detection over the whole record with component j."""
        if j not in self._full:
            self._full[j] = detect_causal(self.comps_full[:, j], self.cfg)
        return self._full[j]

    def select(
        self,
        rule: str,
        ref_qrs: Optional[np.ndarray] = None,
        candidates: Sequence[int] = (1, 2, 3),
    ) -> Tuple[int, Dict[int, float]]:
        """Return (component index, per-candidate scores).  'oracle' needs ref_qrs."""
        if rule in RULES_FIXED:
            return int(rule[2:]) - 1, {}

        if rule == "periodic_rr":
            n_after = max(self.end - self.cfg.warmup, 1)
            scores = {j: score_periodic_rr(self.det_prefix(j).peaks, n_after, self.cfg)
                      for j in candidates}
            best = max(scores, key=lambda j: scores[j])
            return (best if scores[best] > 0.0 else 1), scores   # fallback: PC2

        if rule == "autocorr":
            scores = {j: score_autocorr(self.det_prefix(j).x_int, self.cfg) for j in candidates}
            best = max(scores, key=lambda j: scores[j])
            return (best if scores[best] >= 0.1 else 1), scores  # fallback: PC2

        if rule == "oracle":
            if ref_qrs is None:
                raise ValueError("oracle rule needs ref_qrs (upper bound only, NOT deployable)")
            from fecg.core.evaluation import compute_beat_metrics
            scores = {}
            for j in range(self.W.shape[1]):
                m = compute_beat_metrics(ref_qrs, self.det_full(j).peaks, fs=self.cfg.fs)
                scores[j] = float(m.f1 or 0.0)
            return max(scores, key=lambda j: scores[j]), scores

        raise ValueError(f"unknown rule '{rule}' (choose from {RULES_ALL})")

    def weights(self, j: int) -> np.ndarray:
        return self.W[:, j].copy()


def fit_weights(
    X_raw: np.ndarray,
    cfg: CausalConfig = DEFAULT_CONFIG,
    cal_seconds: Optional[float] = None,
    rule: str = "pc2",
    ref_qrs: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, int, CalibrationBank]:
    """Convenience wrapper: returns (unit-norm weights, component index, bank)."""
    bank = CalibrationBank(X_raw, cfg, cal_seconds)
    j, _ = bank.select(rule, ref_qrs=ref_qrs)
    return bank.weights(j), j, bank

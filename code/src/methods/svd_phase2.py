"""
src/methods/svd.py
──────────────────────────────────────────────────────────────────────────────
SVD-based fetal ECG extraction — all three variants from Kanjilal et al. (1997).

Role     : Integration & SVD Extraction Lead
Primary paper : Fetal_ECG_extraction_from_single-channel_maternal_ECG_using_
                singular_value_decomposition.pdf
                (Kanjilal, Palit & Saha, IEEE TBME, Vol. 44 No. 1, Jan 1997)

Three variants implemented
--------------------------
Variant 1 — Fixed-period / linear interpolation
    Matrix A: rows = consecutive maternal cycles, aligned at R-peak.
    Cycles shorter than the modal period n are linearly interpolated to n.
    SVD of A → dominant dyad A_M = u1·σ1·v1ᵀ → subtract to get residual.
    Residual re-segmented by fetal cycles → matrix B → SVD → fetal estimate.

Variant 2 — SVR spectrum + time-resampling (Equation 3 from the paper)
    Use the Singular Value Ratio (SVR) spectrum to find the most likely
    period length n for maternal cycles.  All beats are dynamically
    compressed/expanded to length n (interpolation/extrapolation in time).
    SVD extracts maternal pattern; inverse-resampling reconstructs the series.
    Residual processed similarly for fetal ECG.

Variant 3 — Moving-window (block-adaptive) SVD
    Slide a submatrix window of size m1 × n (m1 < m) row-by-row over A.
    SVD on each sub-window; last row of dominant dyad = local maternal beat.
    Subtract to form residual, then extract fetal ECG from residual matrix B.

Usage
-----
    from src.methods.svd import SVDExtractorV1, SVDExtractorV2, SVDExtractorV3

    extractor = SVDExtractorV1(fs=250)
    fecg_est, meta = extractor.run(mixture_signal)

NOTE
----
Phase 2 numerical implementations are included. This remains an offline,
research implementation; extraction quality must be validated on the team's
frozen TC1–TC5 test matrix before making performance claims.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import numpy as np
from scipy.interpolate import interp1d

from src.methods.base import BaseExtractor


# ──────────────────────────────────────────────────────────────────────────────
# Shared configuration defaults
# ──────────────────────────────────────────────────────────────────────────────

_SVD_DEFAULT_CONFIG = {
    # R-peak detection for maternal segmentation (simple threshold-based)
    "maternal_rpeak_min_distance_ms": 400,   # minimum maternal RR (150 BPM max)
    "maternal_rpeak_height_fraction": 0.5,   # fraction of signal max for R-peak threshold

    # Matrix construction
    "n_svd_components_maternal": 1,          # number of dominant components to subtract (maternal)
    "n_svd_components_fetal": 1,             # number of dominant components to keep (fetal)

    # Variant 1 / 2: period handling
    "period_mode": "modal",                  # 'modal' (Variant 1) or 'svr' (Variant 2)

    # Variant 3: moving window
    "window_rows": 5,                        # m1 — sub-window row count for Method 3

    # SVR spectrum (Variant 2)
    "svr_period_range": (50, 200),           # search range in samples
}


# ──────────────────────────────────────────────────────────────────────────────
# Variant 1 — Fixed period / linear interpolation
# ──────────────────────────────────────────────────────────────────────────────

class SVDExtractorV1(BaseExtractor):
    """
    SVD Variant 1: Fixed-period matrix, linear interpolation for short cycles.

    Corresponds to Method 1 in Section III-B of Kanjilal et al. (1997).
    """

    DESCRIPTION = "SVD extraction — Variant 1: fixed modal period + linear interpolation"
    INPUT_SIGNALS = "Single-channel abdominal mixture (preprocessed)"
    REFERENCE_NEEDED = False
    IS_CAUSAL = False

    def extract(
        self,
        mixture: np.ndarray,
        **kwargs: Any,
    ) -> tuple[np.ndarray, dict]:
        """
        Parameters
        ----------
        mixture : np.ndarray, shape (n_samples,)
            Preprocessed single-channel abdominal ECG mixture.
        **kwargs : unused for this variant.

        Returns
        -------
        fecg_est : np.ndarray, shape (n_samples,)
        metadata : dict
        """
        t0 = time.perf_counter()
        fs = self.fs
        cfg = {**_SVD_DEFAULT_CONFIG, **self.config}

        # ── Step 1: Detect maternal R-peaks from mixture ──────────────────────
        m_peaks = _detect_rpeaks(
            mixture, fs,
            min_distance_ms=cfg["maternal_rpeak_min_distance_ms"],
            height_fraction=cfg["maternal_rpeak_height_fraction"],
        )

        # ── Step 2: Segment mixture into maternal cycles, pad to modal period ─
        A, period_n, cycle_info = _build_matrix_fixed_period(mixture, m_peaks)

        # ── Step 3: SVD of A → subtract dominant maternal component ──────────
        mecg_est, residual = _svd_subtract(mixture, A, cycle_info, cfg["n_svd_components_maternal"])

        # ── Step 4: Detect fetal R-peaks in residual ──────────────────────────
        f_peaks = _detect_rpeaks(
            residual, fs,
            min_distance_ms=150,      # fetal HR up to 200 BPM → min RR 300 ms
            height_fraction=0.3,
        )

        # ── Step 5: Segment residual into fetal cycles, build matrix B ────────
        B, fetal_period_n, fetal_cycle_info = _build_matrix_fixed_period(residual, f_peaks)

        # ── Step 6: SVD of B → dominant fetal component ───────────────────────
        fecg_est = _svd_extract(residual, B, fetal_cycle_info, cfg["n_svd_components_fetal"])

        runtime = time.perf_counter() - t0

        metadata = {
            "method_name": "SVD",
            "variant": "variant_1_fixed_period",
            "input_condition": "single_channel",
            "runtime_s": runtime,
            "parameter_notes": (
                f"Modal period n={period_n} samples, "
                f"n_maternal_peaks={len(m_peaks)}, "
                f"n_fetal_peaks={len(f_peaks)}, "
                f"n_svd_maternal={cfg['n_svd_components_maternal']}, "
                f"n_svd_fetal={cfg['n_svd_components_fetal']}"
            ),
            "is_causal": self.IS_CAUSAL,
        }
        return fecg_est, metadata


# ──────────────────────────────────────────────────────────────────────────────
# Variant 2 — SVR spectrum + time-resampling
# ──────────────────────────────────────────────────────────────────────────────

class SVDExtractorV2(BaseExtractor):
    """
    SVD Variant 2: SVR spectrum used to find dominant cycle length; cycles are
    resampled (compressed/expanded) to that length before matrix construction.

    Corresponds to Method 2 in Section III-B of Kanjilal et al. (1997).
    """

    DESCRIPTION = "SVD extraction — Variant 2: SVR spectrum + time-resampling"
    INPUT_SIGNALS = "Single-channel abdominal mixture (preprocessed)"
    REFERENCE_NEEDED = False
    IS_CAUSAL = False

    def extract(
        self,
        mixture: np.ndarray,
        **kwargs: Any,
    ) -> tuple[np.ndarray, dict]:
        t0 = time.perf_counter()
        fs = self.fs
        cfg = {**_SVD_DEFAULT_CONFIG, **self.config}

        # ── Step 1: Detect maternal R-peaks ───────────────────────────────────
        m_peaks = _detect_rpeaks(mixture, fs,
                                 min_distance_ms=cfg["maternal_rpeak_min_distance_ms"],
                                 height_fraction=cfg["maternal_rpeak_height_fraction"])

        # ── Step 2: Compute SVR spectrum → find dominant period n ─────────────
        period_n = _svr_dominant_period(
            mixture,
            search_range=cfg["svr_period_range"],
        )

        # ── Step 3: Build matrix A with time-resampling ───────────────────────
        A, cycle_info = _build_matrix_resampled(mixture, m_peaks, period_n)

        # ── Step 4: SVD subtract maternal ─────────────────────────────────────
        mecg_est, residual = _svd_subtract(mixture, A, cycle_info, cfg["n_svd_components_maternal"])

        # ── Step 5: SVR for fetal period, build B, extract fetal ──────────────
        f_peaks = _detect_rpeaks(residual, fs, min_distance_ms=150, height_fraction=0.3)
        fetal_period_n = _svr_dominant_period(residual, search_range=(30, 150))
        B, fetal_cycle_info = _build_matrix_resampled(residual, f_peaks, fetal_period_n)
        fecg_est = _svd_extract(residual, B, fetal_cycle_info, cfg["n_svd_components_fetal"])

        runtime = time.perf_counter() - t0

        metadata = {
            "method_name": "SVD",
            "variant": "variant_2_svr_resampling",
            "input_condition": "single_channel",
            "runtime_s": runtime,
            "parameter_notes": (
                f"SVR period n={period_n} samples, fetal period={fetal_period_n} samples, "
                f"n_maternal_peaks={len(m_peaks)}, n_fetal_peaks={len(f_peaks)}"
            ),
            "is_causal": self.IS_CAUSAL,
        }
        return fecg_est, metadata


# ──────────────────────────────────────────────────────────────────────────────
# Variant 3 — Moving-window (block-adaptive) SVD
# ──────────────────────────────────────────────────────────────────────────────

class SVDExtractorV3(BaseExtractor):
    """
    SVD Variant 3: Sliding sub-matrix window over A; adapts to morphology shifts.

    Corresponds to Method 3 in Section III-B of Kanjilal et al. (1997).
    """

    DESCRIPTION = "SVD extraction — Variant 3: moving-window (block-adaptive) SVD"
    INPUT_SIGNALS = "Single-channel abdominal mixture (preprocessed)"
    REFERENCE_NEEDED = False
    IS_CAUSAL = False   # windowed but still offline

    def extract(
        self,
        mixture: np.ndarray,
        **kwargs: Any,
    ) -> tuple[np.ndarray, dict]:
        t0 = time.perf_counter()
        fs = self.fs
        cfg = {**_SVD_DEFAULT_CONFIG, **self.config}

        # ── Step 1: Detect maternal R-peaks ───────────────────────────────────
        m_peaks = _detect_rpeaks(mixture, fs,
                                 min_distance_ms=cfg["maternal_rpeak_min_distance_ms"],
                                 height_fraction=cfg["maternal_rpeak_height_fraction"])

        # ── Step 2: Build full matrix A (fixed period / modal) ─────────────────
        A, period_n, cycle_info = _build_matrix_fixed_period(mixture, m_peaks)

        # ── Step 3: Moving-window SVD ─────────────────────────────────────────
        m1 = cfg["window_rows"]
        mecg_est, residual = _moving_window_svd_subtract(
            mixture, A, cycle_info, window_rows=m1,
            n_components=cfg["n_svd_components_maternal"],
        )

        # ── Step 4: Extract fetal from residual ───────────────────────────────
        f_peaks = _detect_rpeaks(residual, fs, min_distance_ms=150, height_fraction=0.3)
        B, fetal_period_n, fetal_cycle_info = _build_matrix_fixed_period(residual, f_peaks)
        fecg_est = _svd_extract(residual, B, fetal_cycle_info, cfg["n_svd_components_fetal"])

        runtime = time.perf_counter() - t0

        metadata = {
            "method_name": "SVD",
            "variant": "variant_3_moving_window",
            "input_condition": "single_channel",
            "runtime_s": runtime,
            "parameter_notes": (
                f"Window rows m1={m1}, period n={period_n} samples, "
                f"n_maternal_peaks={len(m_peaks)}, n_fetal_peaks={len(f_peaks)}"
            ),
            "is_causal": self.IS_CAUSAL,
        }
        return fecg_est, metadata


# ──────────────────────────────────────────────────────────────────────────────
# Stub placeholder files for teammate methods (outside primary workstream)
# ──────────────────────────────────────────────────────────────────────────────
# See src/methods/template_subtraction.py  (Template Subtraction)
#     src/methods/swt_lms_ssnf.py          (Astitva)
#     src/methods/alternative.py            (Wavelet-Threshold Hybrid)


# ──────────────────────────────────────────────────────────────────────────────
# Internal algorithm helpers (Phase 2: implement full bodies here)
# ──────────────────────────────────────────────────────────────────────────────

def _detect_rpeaks(
    signal: np.ndarray,
    fs: int,
    min_distance_ms: float = 400,
    height_fraction: float = 0.5,
) -> np.ndarray:
    """
    Simple R-peak detector for matrix segmentation (NOT the shared QRS detector).
    Uses scipy.signal.find_peaks with a height threshold and minimum distance.

    This is used INTERNALLY to build SVD matrices; the shared QRS detector
    (src/qrs_detector.py) is used for final evaluation beat detection.
    """
    from scipy.signal import find_peaks

    signal = np.asarray(signal, dtype=np.float64).reshape(-1)
    if fs <= 0 or signal.size < 3 or not np.all(np.isfinite(signal)):
        return np.array([], dtype=int)
    min_dist_samples = max(1, int(round(min_distance_ms * fs / 1000.0)))
    centered = signal - np.median(signal)
    height = max(height_fraction * float(np.max(np.abs(centered))), np.finfo(float).eps)

    # Detect on positive signal (handles inverted leads too by checking negative)
    pos_peaks, _ = find_peaks(centered, height=height, distance=min_dist_samples)
    neg_peaks, _ = find_peaks(-centered, height=height, distance=min_dist_samples)

    all_peaks = np.sort(np.concatenate([pos_peaks, neg_peaks]))
    # Remove any that are too close after merging
    if len(all_peaks) > 1:
        keep = [all_peaks[0]]
        for p in all_peaks[1:]:
            if p - keep[-1] >= min_dist_samples:
                keep.append(p)
        all_peaks = np.array(keep, dtype=int)

    return all_peaks


def _build_matrix_fixed_period(
    signal: np.ndarray,
    r_peaks: np.ndarray,
) -> tuple[np.ndarray, int, list[dict]]:
    """
    Build matrix A where each row contains one beat cycle.
    Cycles are linearly interpolated to the modal period length.

    Returns
    -------
    A          : np.ndarray, shape (n_cycles, n)
    period_n   : int — modal period length
    cycle_info : list of dicts — start/end/original_length per cycle
    """
    if len(r_peaks) < 2:
        return np.zeros((0, 1)), 1, []

    # Compute inter-peak intervals
    intervals = np.diff(r_peaks)
    unique, counts = np.unique(intervals, return_counts=True)
    modes = unique[counts == counts.max()]
    period_n = int(modes[np.argmin(np.abs(modes - np.median(intervals)))])

    cycles = []
    cycle_info = []
    for i in range(len(r_peaks) - 1):
        start = r_peaks[i]
        end = r_peaks[i + 1]
        seg = signal[start:end].astype(np.float64)
        orig_len = len(seg)

        # Resample segment to period_n via linear interpolation
        if orig_len != period_n:
            x_old = np.linspace(0, 1, orig_len)
            x_new = np.linspace(0, 1, period_n)
            seg_resampled = np.interp(x_new, x_old, seg)
        else:
            seg_resampled = seg

        cycles.append(seg_resampled)
        cycle_info.append({
            "start": start, "end": end,
            "orig_len": orig_len, "resampled_len": period_n,
        })

    A = np.vstack(cycles)
    return A, period_n, cycle_info


def _build_matrix_resampled(
    signal: np.ndarray,
    r_peaks: np.ndarray,
    period_n: int,
) -> tuple[np.ndarray, list[dict]]:
    """
    Build matrix where each row contains one beat cycle dynamically resampled
    to length period_n (Kanjilal Method 2).

    Returns
    -------
    A          : np.ndarray, shape (n_cycles, period_n)
    cycle_info : list of dicts — metadata per cycle for inverse mapping
    """
    if len(r_peaks) < 2 or period_n <= 1:
        return np.zeros((0, max(1, period_n))), []

    cycles = []
    cycle_info = []
    for i in range(len(r_peaks) - 1):
        start = r_peaks[i]
        end = r_peaks[i + 1]
        seg = signal[start:end].astype(np.float64)
        orig_len = len(seg)

        if orig_len != period_n and orig_len > 1:
            x_old = np.linspace(0, 1, orig_len)
            x_new = np.linspace(0, 1, period_n)
            seg_resampled = np.interp(x_new, x_old, seg)
        elif orig_len == period_n:
            seg_resampled = seg
        else:
            seg_resampled = np.zeros(period_n)

        cycles.append(seg_resampled)
        cycle_info.append({
            "start": start, "end": end,
            "orig_len": orig_len, "resampled_len": period_n,
        })

    if cycles:
        A = np.vstack(cycles)
    else:
        A = np.zeros((0, period_n))
    return A, cycle_info


def _svd_subtract(
    signal: np.ndarray,
    A: np.ndarray,
    cycle_info: list[dict],
    n_components: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Perform SVD on A, reconstruct the dominant maternal signal, subtract.

    Returns
    -------
    mecg_est : np.ndarray — reconstructed maternal ECG estimate
    residual : np.ndarray — signal with maternal component subtracted
    """
    x = np.asarray(signal, dtype=np.float64).reshape(-1)
    if A.ndim != 2 or A.shape[0] == 0 or not cycle_info:
        return np.zeros_like(x), x.copy()
    if n_components < 1:
        raise ValueError("n_components must be >= 1")
    try:
        U, S, Vt = np.linalg.svd(A, full_matrices=False)
    except np.linalg.LinAlgError:
        return np.zeros_like(x), x.copy()
    k = min(int(n_components), len(S))
    A_maternal = (U[:, :k] * S[:k]) @ Vt[:k, :]
    mecg_est = _matrix_to_signal(A_maternal, cycle_info, x.size)
    return mecg_est, x - mecg_est


def _svd_extract(
    signal: np.ndarray,
    B: np.ndarray,
    cycle_info: list[dict],
    n_components: int = 1,
) -> np.ndarray:
    """
    SVD of matrix B; retain dominant fetal components and reconstruct.

    Returns estimated fetal ECG of the same length as signal.
    """
    x = np.asarray(signal, dtype=np.float64).reshape(-1)
    if B.ndim != 2 or B.shape[0] == 0 or not cycle_info:
        return np.zeros_like(x)
    if n_components < 1:
        raise ValueError("n_components must be >= 1")
    try:
        U, S, Vt = np.linalg.svd(B, full_matrices=False)
    except np.linalg.LinAlgError:
        return np.zeros_like(x)
    k = min(int(n_components), len(S))
    B_fetal = (U[:, :k] * S[:k]) @ Vt[:k, :]
    return _matrix_to_signal(B_fetal, cycle_info, x.size)


def _matrix_to_signal(
    M: np.ndarray,
    cycle_info: list[dict],
    n_total: int,
) -> np.ndarray:
    """
    Reconstruct a time-domain signal from a cycle matrix by inverse-resampling
    each row back to its original length and placing it at the correct position.
    """
    out = np.zeros(n_total, dtype=np.float64)
    cnt = np.zeros(n_total, dtype=np.float64)  # accumulate overlapping contributions

    for i, info in enumerate(cycle_info):
        row = M[i, :]
        orig_len = info["orig_len"]
        start = info["start"]
        end = info["end"]

        # Inverse-resample back to original length
        if len(row) != orig_len:
            x_old = np.linspace(0, 1, len(row))
            x_new = np.linspace(0, 1, orig_len)
            row = np.interp(x_new, x_old, row)

        actual_end = min(end, start + orig_len, n_total)
        actual_len = actual_end - start
        out[start:actual_end] += row[:actual_len]
        cnt[start:actual_end] += 1.0

    # Average overlapping regions (should be minimal with non-overlapping cycles)
    mask = cnt > 0
    out[mask] /= cnt[mask]
    return out


def _svr_dominant_period(
    signal: np.ndarray,
    search_range: tuple[int, int] = (50, 200),
) -> int:
    """
    Compute the Singular Value Ratio (SVR) spectrum to identify the dominant
    periodic component length.

    SVR(n) = σ₁(A_n)² / σ₂(A_n)²  where A_n is the matrix formed
    by folding signal into rows of length n.

    The period with the largest SVR is the dominant one.

    Returns
    -------
    best_period : int
        Period length (samples) with maximum SVR.
    """
    x = np.asarray(signal, dtype=np.float64).reshape(-1)
    n_min, n_max = map(int, search_range)
    if n_min < 2 or n_max < n_min:
        raise ValueError("search_range must satisfy 2 <= min <= max")
    best_period, best_svr = n_min, -np.inf
    for n in range(n_min, min(n_max, x.size // 2) + 1):
        rows = x.size // n
        if rows < 2:
            continue
        folded = x[:rows * n].reshape(rows, n)
        try:
            singular = np.linalg.svd(folded, compute_uv=False, full_matrices=False)
        except np.linalg.LinAlgError:
            continue
        if singular.size < 2:
            continue
        den = float(singular[1] ** 2)
        svr = float(singular[0] ** 2) / den if den > np.finfo(float).eps else np.finfo(float).max
        if svr > best_svr:
            best_svr, best_period = svr, n
    return int(best_period)


def _moving_window_svd_subtract(
    signal: np.ndarray,
    A: np.ndarray,
    cycle_info: list[dict],
    window_rows: int = 5,
    n_components: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Moving-window SVD subtraction (Method 3).
    Slides an m1 × n window over matrix A row-by-row.
    For each window position, SVD is computed and the last row of the
    dominant dyad is the estimated maternal beat at that cycle.

    Returns mecg_est, residual.
    """
    x = np.asarray(signal, dtype=np.float64).reshape(-1)
    if A.ndim != 2 or A.shape[0] == 0 or not cycle_info:
        return np.zeros_like(x), x.copy()
    window_rows = max(1, int(window_rows))
    local = np.zeros_like(A, dtype=np.float64)
    for i in range(A.shape[0]):
        window = A[max(0, i - window_rows + 1):i + 1]
        try:
            U, S, Vt = np.linalg.svd(window, full_matrices=False)
            k = min(max(1, int(n_components)), len(S))
            reconstructed = (U[:, :k] * S[:k]) @ Vt[:k, :]
            local[i] = reconstructed[-1]
        except np.linalg.LinAlgError:
            local[i] = window[-1]
    mecg_est = _matrix_to_signal(local, cycle_info, x.size)
    return mecg_est, x - mecg_est

"""
src/methods/svd.py
──────────────────────────────────────────────────────────────────────────────
SVD-based fetal ECG extraction — all three variants from Kanjilal et al. (1997).

Owner         : Naman (Primary Extraction Workstream)
Primary paper : Fetal_ECG_extraction_from_single-channel_maternal_ECG_using_
                singular_value_decomposition.pdf
                (Kanjilal, Palit & Saha, IEEE TBME, Vol. 44 No. 1, Jan 1997)

Three variants implemented
--------------------------
Variant 1 — Fixed-period / linear interpolation
    Matrix A: rows = consecutive maternal cycles, aligned at R-peak.
    Cycles are resampled / linearly interpolated to modal period n.
    SVD of A -> dominant dyad A_M = u1·sigma1·v1^T -> subtract to get residual.
    Residual re-segmented by fetal cycles -> matrix B -> SVD -> fetal estimate.

Variant 2 — SVR spectrum + time-resampling (Equation 3 from Kanjilal et al.)
    Use the Singular Value Ratio (SVR) spectrum to find the most likely
    period length n for maternal cycles. All beats are dynamically
    compressed/expanded to length n (interpolation/extrapolation in time).
    SVD extracts maternal pattern; inverse-resampling reconstructs the series.
    Residual processed similarly for fetal ECG.

Variant 3 — Moving-window (block-adaptive) SVD
    Slide a submatrix window of size m1 x n (m1 < m) row-by-row over A.
    SVD on each sub-window; last row of dominant dyad = local maternal beat.
    Subtract to form residual, then extract fetal ECG from residual matrix B.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import numpy as np
from scipy.signal import find_peaks

from src.methods.base import BaseExtractor


# ──────────────────────────────────────────────────────────────────────────────
# Shared configuration defaults
# ──────────────────────────────────────────────────────────────────────────────

_SVD_DEFAULT_CONFIG = {
    # Maternal R-peak detection
    "maternal_rpeak_min_distance_ms": 400,   # minimum maternal RR interval (<= 150 BPM)
    "maternal_rpeak_height_fraction": 0.45,  # fraction of robust amplitude scale

    # Fetal R-peak detection in residual
    "fetal_rpeak_min_distance_ms": 280,      # minimum fetal RR interval (<= 214 BPM)
    "fetal_rpeak_height_fraction": 0.35,     # fraction of robust amplitude scale in residual

    # SVD component counts
    "n_svd_components_maternal": 1,          # dominant maternal dyads to eliminate
    "n_svd_components_fetal": 1,             # dominant fetal dyads to retain

    # Variant 2: SVR spectrum
    "svr_period_range": (50, 200),           # period search range in samples (250 Hz)

    # Variant 3: moving window
    "window_rows": 5,                        # m1 sub-window row count for block-adaptive SVD
}


# ──────────────────────────────────────────────────────────────────────────────
# Variant 1 — Fixed period / linear interpolation
# ──────────────────────────────────────────────────────────────────────────────

class SVDExtractorV1(BaseExtractor):
    """
    SVD Variant 1: Fixed-period matrix, linear interpolation for short/long cycles.

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
        t0 = time.perf_counter()
        fs = self.fs
        cfg = {**_SVD_DEFAULT_CONFIG, **self.config}

        # ── Step 1: Detect maternal R-peaks from mixture ──────────────────────
        m_peaks = _detect_rpeaks(
            mixture, fs,
            min_distance_ms=cfg["maternal_rpeak_min_distance_ms"],
            height_fraction=cfg["maternal_rpeak_height_fraction"],
            use_percentile=True,
        )

        # ── Step 2: Segment mixture into maternal cycles, pad to modal period ─
        A, period_n, cycle_info = _build_matrix_fixed_period(mixture, m_peaks)

        # ── Step 3: SVD of A -> subtract dominant maternal component ──────────
        mecg_est, residual = _svd_subtract(
            mixture, A, cycle_info,
            n_components=cfg["n_svd_components_maternal"],
        )

        # ── Step 4: Detect fetal R-peaks in residual ──────────────────────────
        f_peaks = _detect_rpeaks(
            residual, fs,
            min_distance_ms=cfg["fetal_rpeak_min_distance_ms"],
            height_fraction=cfg["fetal_rpeak_height_fraction"],
            use_percentile=True,
        )

        # ── Step 5: Segment residual into fetal cycles, build matrix B ────────
        B, fetal_period_n, fetal_cycle_info = _build_matrix_fixed_period(residual, f_peaks)

        # ── Step 6: SVD of B -> dominant fetal component ───────────────────────
        fecg_est = _svd_extract(
            residual, B, fetal_cycle_info,
            n_components=cfg["n_svd_components_fetal"],
        )

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
                f"fetal_period_n={fetal_period_n} samples, "
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
        m_peaks = _detect_rpeaks(
            mixture, fs,
            min_distance_ms=cfg["maternal_rpeak_min_distance_ms"],
            height_fraction=cfg["maternal_rpeak_height_fraction"],
            use_percentile=True,
        )

        # ── Step 2: Compute SVR spectrum -> find dominant maternal period n ───
        period_n = _svr_dominant_period(
            mixture,
            search_range=cfg["svr_period_range"],
        )

        # ── Step 3: Build matrix A with time-resampling ───────────────────────
        A, cycle_info = _build_matrix_resampled(mixture, m_peaks, period_n)

        # ── Step 4: SVD subtract maternal component ───────────────────────────
        mecg_est, residual = _svd_subtract(
            mixture, A, cycle_info,
            n_components=cfg["n_svd_components_maternal"],
        )

        # ── Step 5: SVR for fetal period, build B, extract fetal ──────────────
        f_peaks = _detect_rpeaks(
            residual, fs,
            min_distance_ms=cfg["fetal_rpeak_min_distance_ms"],
            height_fraction=cfg["fetal_rpeak_height_fraction"],
            use_percentile=True,
        )
        fetal_period_n = _svr_dominant_period(residual, search_range=(50, 150))
        B, fetal_cycle_info = _build_matrix_resampled(residual, f_peaks, fetal_period_n)
        fecg_est = _svd_extract(
            residual, B, fetal_cycle_info,
            n_components=cfg["n_svd_components_fetal"],
        )

        runtime = time.perf_counter() - t0

        metadata = {
            "method_name": "SVD",
            "variant": "variant_2_svr_resampling",
            "input_condition": "single_channel",
            "runtime_s": runtime,
            "parameter_notes": (
                f"SVR maternal period n={period_n} samples, "
                f"fetal period={fetal_period_n} samples, "
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
        m_peaks = _detect_rpeaks(
            mixture, fs,
            min_distance_ms=cfg["maternal_rpeak_min_distance_ms"],
            height_fraction=cfg["maternal_rpeak_height_fraction"],
            use_percentile=True,
        )

        # ── Step 2: Build full matrix A (fixed period / modal) ─────────────────
        A, period_n, cycle_info = _build_matrix_fixed_period(mixture, m_peaks)

        # ── Step 3: Moving-window SVD ─────────────────────────────────────────
        m1 = cfg["window_rows"]
        mecg_est, residual = _moving_window_svd_subtract(
            mixture, A, cycle_info, window_rows=m1,
            n_components=cfg["n_svd_components_maternal"],
        )

        # ── Step 4: Extract fetal from residual ───────────────────────────────
        f_peaks = _detect_rpeaks(
            residual, fs,
            min_distance_ms=cfg["fetal_rpeak_min_distance_ms"],
            height_fraction=cfg["fetal_rpeak_height_fraction"],
            use_percentile=True,
        )
        B, fetal_period_n, fetal_cycle_info = _build_matrix_fixed_period(residual, f_peaks)
        fecg_est = _svd_extract(
            residual, B, fetal_cycle_info,
            n_components=cfg["n_svd_components_fetal"],
        )

        runtime = time.perf_counter() - t0

        metadata = {
            "method_name": "SVD",
            "variant": "variant_3_moving_window",
            "input_condition": "single_channel",
            "runtime_s": runtime,
            "parameter_notes": (
                f"Window rows m1={m1}, modal period n={period_n} samples, "
                f"n_maternal_peaks={len(m_peaks)}, n_fetal_peaks={len(f_peaks)}"
            ),
            "is_causal": self.IS_CAUSAL,
        }
        return fecg_est, metadata


# ──────────────────────────────────────────────────────────────────────────────
# Core Algorithm Helpers (Phase 2 Implementation)
# ──────────────────────────────────────────────────────────────────────────────

def _detect_rpeaks(
    signal: np.ndarray,
    fs: int,
    min_distance_ms: float = 400,
    height_fraction: float = 0.5,
    use_percentile: bool = True,
) -> np.ndarray:
    """
    R-peak detector used internally for matrix segmentation.
    Uses robust percentile-based amplitude scaling to reject outlier boundary spikes.
    """
    x = np.asarray(signal, dtype=np.float64).reshape(-1)
    if fs <= 0 or x.size < 3 or not np.all(np.isfinite(x)):
        return np.array([], dtype=int)

    min_dist_samples = max(1, int(round(min_distance_ms * fs / 1000.0)))
    centered = x - np.median(x)

    if use_percentile:
        # 98th percentile rejects edge transients / un-subtracted spikes
        scale = float(np.percentile(np.abs(centered), 98))
    else:
        scale = float(np.max(np.abs(centered)))

    height = max(height_fraction * scale, np.finfo(float).eps)

    pos_peaks, _ = find_peaks(centered, height=height, distance=min_dist_samples)
    neg_peaks, _ = find_peaks(-centered, height=height, distance=min_dist_samples)

    all_peaks = np.sort(np.concatenate([pos_peaks, neg_peaks]))
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
    Build matrix A where each row contains one beat cycle, linearly interpolated
    to the modal period length n (Kanjilal Method 1).
    """
    if len(r_peaks) < 2:
        return np.zeros((0, 1)), 1, []

    intervals = np.diff(r_peaks)
    unique, counts = np.unique(intervals, return_counts=True)
    modes = unique[counts == counts.max()]
    period_n = int(modes[np.argmin(np.abs(modes - np.median(intervals)))])
    period_n = max(2, period_n)

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

    A = np.vstack(cycles) if cycles else np.zeros((0, period_n))
    return A, period_n, cycle_info


def _build_matrix_resampled(
    signal: np.ndarray,
    r_peaks: np.ndarray,
    period_n: int,
) -> tuple[np.ndarray, list[dict]]:
    """
    Build matrix where each row contains one beat cycle dynamically resampled
    to length period_n determined by SVR (Kanjilal Method 2).
    """
    period_n = max(2, int(period_n))
    if len(r_peaks) < 2:
        return np.zeros((0, period_n)), []

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

    A = np.vstack(cycles) if cycles else np.zeros((0, period_n))
    return A, cycle_info


def _matrix_to_signal(
    M: np.ndarray,
    cycle_info: list[dict],
    n_total: int,
    extrapolate_edges: bool = True,
) -> np.ndarray:
    """
    Reconstruct time-domain signal from cycle matrix M.
    Performs inverse-resampling per beat, averages overlaps, and smoothly
    extrapolates boundary edges so no step discontinuities occur at signal borders.
    """
    out = np.zeros(n_total, dtype=np.float64)
    cnt = np.zeros(n_total, dtype=np.float64)

    if not cycle_info or M.shape[0] == 0:
        return out

    for i, info in enumerate(cycle_info):
        row = M[i, :]
        orig_len = info["orig_len"]
        start = info["start"]
        end = info["end"]

        if len(row) != orig_len:
            x_old = np.linspace(0, 1, len(row))
            x_new = np.linspace(0, 1, orig_len)
            row = np.interp(x_new, x_old, row)

        actual_end = min(end, start + orig_len, n_total)
        actual_len = actual_end - start
        out[start:actual_end] += row[:actual_len]
        cnt[start:actual_end] += 1.0

    mask = cnt > 0
    out[mask] /= cnt[mask]

    # Edge extrapolation prevents severe step artifacts at borders
    if extrapolate_edges and len(cycle_info) > 0:
        first_start = cycle_info[0]["start"]
        if first_start > 0:
            first_cycle = out[first_start:first_start + cycle_info[0]["orig_len"]]
            k = first_start
            while k > 0:
                chunk = min(k, len(first_cycle))
                out[k - chunk:k] = first_cycle[-chunk:]
                k -= chunk

        last_end = cycle_info[-1]["end"]
        if last_end < n_total:
            last_cycle = out[cycle_info[-1]["start"]:last_end]
            k = last_end
            while k < n_total:
                chunk = min(n_total - k, len(last_cycle))
                out[k:k + chunk] = last_cycle[:chunk]
                k += chunk

    return out


def _svd_subtract(
    signal: np.ndarray,
    A: np.ndarray,
    cycle_info: list[dict],
    n_components: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    SVD of matrix A; eliminate dominant maternal components and subtract from mixture.
    """
    x = np.asarray(signal, dtype=np.float64).reshape(-1)
    if A.ndim != 2 or A.shape[0] == 0 or not cycle_info:
        return np.zeros_like(x), x.copy()

    try:
        U, S, Vt = np.linalg.svd(A, full_matrices=False)
    except np.linalg.LinAlgError:
        return np.zeros_like(x), x.copy()

    k = min(max(1, int(n_components)), len(S))
    A_maternal = (U[:, :k] * S[:k]) @ Vt[:k, :]
    mecg_est = _matrix_to_signal(A_maternal, cycle_info, x.size, extrapolate_edges=True)
    return mecg_est, x - mecg_est


def _svd_extract(
    signal: np.ndarray,
    B: np.ndarray,
    cycle_info: list[dict],
    n_components: int = 1,
) -> np.ndarray:
    """
    SVD of matrix B; retain dominant fetal components and reconstruct.
    If matrix B has insufficient cycles, falls back cleanly to the maternal-subtracted residual.
    """
    x = np.asarray(signal, dtype=np.float64).reshape(-1)
    if B.ndim != 2 or B.shape[0] < 2 or not cycle_info:
        return x.copy()

    try:
        U, S, Vt = np.linalg.svd(B, full_matrices=False)
    except np.linalg.LinAlgError:
        return x.copy()

    k = min(max(1, int(n_components)), len(S))
    B_fetal = (U[:, :k] * S[:k]) @ Vt[:k, :]
    fecg_est = _matrix_to_signal(B_fetal, cycle_info, x.size, extrapolate_edges=False)

    # For regions where fetal beat reconstruction had no coverage, retain residual
    uncovered = (fecg_est == 0.0)
    fecg_est[uncovered] = x[uncovered]
    return fecg_est


def _svr_dominant_period(
    signal: np.ndarray,
    search_range: tuple[int, int] = (50, 200),
) -> int:
    """
    Compute Singular Value Ratio (SVR) spectrum to identify dominant period length.
    SVR(n) = sigma1(A_n)^2 / sigma2(A_n)^2
    """
    x = np.asarray(signal, dtype=np.float64).reshape(-1)
    n_min, n_max = map(int, search_range)
    n_min = max(2, n_min)
    n_max = max(n_min, n_max)

    best_period = n_min
    best_svr = -np.inf

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
            best_svr = svr
            best_period = n

    return int(best_period)


def _moving_window_svd_subtract(
    signal: np.ndarray,
    A: np.ndarray,
    cycle_info: list[dict],
    window_rows: int = 5,
    n_components: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Moving-window (block-adaptive) SVD subtraction (Method 3).
    Slides an m1 x n sub-window over matrix A row-by-row.
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

    mecg_est = _matrix_to_signal(local, cycle_info, x.size, extrapolate_edges=True)
    return mecg_est, x - mecg_est

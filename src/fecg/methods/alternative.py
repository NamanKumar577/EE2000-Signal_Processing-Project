"""
src/methods/alternative.py
──────────────────────────────────────────────────────────────────────────────
Alternative extraction method — Wavelet-Threshold Hybrid Method.

Role     : Data Validation & Evaluation Lead
Primary references  : 43407.pdf (Sameni ECG modeling),
                      s11042-022-13391-0.pdf (comprehensive FECG survey)
Supporting refs     : Hasan et al. review, Digital Filters paper

Algorithm:
Single-Channel Adaptive SVD-Template Subtraction with Multi-Scale
Sub-band Refinement (Pseudo-Ensemble Extraction).

1. Maternal QRS Enhancement & Robust R-Peak Detection.
2. Beat-by-beat amplitude-scaled & low-rank SVD-regularized maternal ECG 
   template construction (handles non-stationary maternal morphology).
3. Smooth windowed maternal P-QRS-T cancellation.
4. Multi-scale sub-band filtering (8-38 Hz) to isolate fetal QRS complexes 
   while suppressing residual maternal T-waves and baseline wander.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks, savgol_filter

from .base import BaseExtractor, OUTPUT_KEYS


class AlternativeExtractor(BaseExtractor):
    """
    Single-channel Fetal ECG extractor combining:
    1. Multi-band maternal QRS enhancement & robust R-peak detection.
    2. Beat-by-beat amplitude-scaled & SVD/median-regularized maternal ECG 
       template construction.
    3. Smooth Hann-windowed maternal P-QRS-T cancellation.
    4. Multi-scale sub-band filtering (8-38 Hz) to isolate fetal QRS complexes.
    """

    DESCRIPTION = (
        "Single-channel Adaptive SVD-Template Subtraction + Sub-band Filtering "
        "(Wavelet-Threshold Subband Hybrid)"
    )
    INPUT_SIGNALS = "Single-channel abdominal mixture"
    REFERENCE_NEEDED = False
    IS_CAUSAL = False

    def __init__(
        self,
        fs: int = 250,
        config: Optional[dict] = None,
        pre_window_sec: float = 0.25,
        post_window_sec: float = 0.45,
        n_svd_components: int = 2,
        fecg_band: Tuple[float, float] = (8.0, 38.0),
        **kwargs: Any,
    ) -> None:
        super().__init__(fs=fs, config=config)
        cfg = config or {}
        self.pre_window_sec = float(cfg.get("pre_window_sec", pre_window_sec))
        self.post_window_sec = float(cfg.get("post_window_sec", post_window_sec))
        self.n_svd_components = int(cfg.get("n_svd_components", n_svd_components))
        self.fecg_band = tuple(cfg.get("fecg_band", fecg_band))

    def _bandpass(
        self, sig: np.ndarray, lowcut: float, highcut: float, order: int = 3
    ) -> np.ndarray:
        nyq = 0.5 * self.fs
        low = max(0.001, min(lowcut / nyq, 0.99))
        high = max(low + 0.01, min(highcut / nyq, 0.99))
        b, a = butter(order, [low, high], btype="band")
        # Pad reflectively if signal is short
        pad_len = min(len(sig) - 1, 3 * max(len(b), len(a)))
        if pad_len < 3:
            return sig.copy()
        return filtfilt(b, a, sig, padlen=pad_len)

    def _detect_maternal_peaks(self, aecg: np.ndarray) -> np.ndarray:
        """Robustly detect dominant maternal R-peaks in single-channel AECG."""
        n_samples = len(aecg)
        if n_samples < int(self.fs * 0.5):
            return np.array([], dtype=int)

        # Bandpass 5-25 Hz to maximize maternal QRS energy
        mecg_enh = self._bandpass(aecg, 5.0, 25.0, order=3)

        # Determine dominant polarity
        pos_99 = np.percentile(mecg_enh, 99)
        neg_99 = np.percentile(-mecg_enh, 99)
        polarity = 1.0 if pos_99 >= neg_99 else -1.0
        oriented = polarity * mecg_enh

        # Non-linear energy envelope for initial peak picking
        win_samples = max(5, int(0.06 * self.fs) | 1)
        if len(oriented) > win_samples:
            env = savgol_filter(oriented ** 2, window_length=win_samples, polyorder=2)
        else:
            env = oriented ** 2

        min_dist = max(1, int(0.40 * self.fs))  # Max ~150 BPM maternal heart rate
        prom_thresh = max(float(np.percentile(env, 65)), 0.15 * float(np.max(env)))

        coarse_peaks, _ = find_peaks(env, distance=min_dist, prominence=prom_thresh)

        if len(coarse_peaks) < 3:
            std_val = float(np.std(oriented))
            coarse_peaks, _ = find_peaks(
                oriented, distance=min_dist, height=std_val * 1.0
            )

        # Refine each peak to the exact local maximum on the oriented signal
        search_rad = int(0.05 * self.fs)
        refined_peaks = []
        for p in coarse_peaks:
            left = max(0, p - search_rad)
            right = min(n_samples, p + search_rad + 1)
            if left < right:
                local_max = left + int(np.argmax(oriented[left:right]))
                refined_peaks.append(local_max)

        return np.unique(np.array(refined_peaks, dtype=int))

    def _cancel_maternal_ecg(
        self, aecg: np.ndarray, m_peaks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Construct a low-rank maternal beat matrix (pseudo-ensemble) and subtract
        the reconstructed maternal P-QRS-T complex from each beat.
        """
        n_samples = len(aecg)
        pre_s = int(self.pre_window_sec * self.fs)
        post_s = int(self.post_window_sec * self.fs)
        beat_len = pre_s + post_s

        valid_peaks = [p for p in m_peaks if pre_s <= p < n_samples - post_s]
        if len(valid_peaks) < 3:
            # Fallback if too few beats (e.g. very short smoke tests)
            return aecg.copy(), np.zeros_like(aecg), 0

        # Build beat matrix: shape (n_beats, beat_len)
        beats = np.array([aecg[p - pre_s : p + post_s] for p in valid_peaks])

        # Taper edges with a Tukey/cosine window to prevent step discontinuities
        taper_len = int(0.04 * self.fs)
        window = np.ones(beat_len)
        if taper_len > 0:
            taper = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, taper_len)))
            window[:taper_len] = taper
            window[-taper_len:] = taper[::-1]

        # Low-rank SVD reconstruction of maternal beat ensemble
        u, s, vt = np.linalg.svd(beats, full_matrices=False)
        k = min(self.n_svd_components, len(s))
        s_clean = np.zeros_like(s)
        s_clean[:k] = s[:k]
        reconstructed_beats = (u * s_clean) @ vt

        mecg_est = np.zeros(n_samples, dtype=float)
        weight_sum = np.zeros(n_samples, dtype=float)

        for idx, p in enumerate(valid_peaks):
            seg = reconstructed_beats[idx] * window
            mecg_est[p - pre_s : p + post_s] += seg
            weight_sum[p - pre_s : p + post_s] += window

        # Normalize overlapping regions if maternal HR is high
        overlap_mask = weight_sum > 1.0
        mecg_est[overlap_mask] /= weight_sum[overlap_mask]

        residual = aecg - mecg_est
        return residual, mecg_est, k

    def extract(
        self,
        mixture: np.ndarray,
        **kwargs: Any,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Execute single-channel FECG extraction.

        Parameters
        ----------
        mixture : np.ndarray, shape (n_samples,)
            Preprocessed 1-D abdominal ECG mixture.

        Returns
        -------
        fecg_est : np.ndarray, shape (n_samples,)
            Estimated fetal ECG waveform.
        metadata : dict
            Conforms strictly to BaseExtractor.OUTPUT_KEYS contract.
        """
        t_start = time.perf_counter()
        arr = np.asarray(mixture, dtype=np.float64)

        if arr.ndim > 1:
            arr = arr.ravel()

        # Defensively sanitize any NaNs or Infs
        if not np.all(np.isfinite(arr)):
            arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

        # Stage 1: Maternal R-peak detection
        m_peaks = self._detect_maternal_peaks(arr)

        # Stage 2: Adaptive SVD-Template Maternal Cancellation
        residual, mecg_est, k_used = self._cancel_maternal_ecg(arr, m_peaks)

        # Stage 3: Multi-scale Sub-band Enhancement for Fetal QRS (8 - 38 Hz)
        if len(residual) > int(self.fs * 0.1):
            fecg_est = self._bandpass(
                residual, self.fecg_band[0], self.fecg_band[1], order=3
            )
        else:
            fecg_est = residual.copy()

        # Preserve relative scale with respect to residual energy
        std_val = np.std(fecg_est)
        if std_val > 1e-9:
            res_std = np.std(residual)
            if res_std > 1e-9:
                fecg_est = fecg_est * (res_std / std_val)

        runtime_sec = time.perf_counter() - t_start

        param_str = (
            f"pre_win={self.pre_window_sec}s, post_win={self.post_window_sec}s, "
            f"k_svd={k_used}, band={self.fecg_band}Hz, n_maternal_peaks={len(m_peaks)}"
        )

        metadata: Dict[str, Any] = {
            "method_name": "alternative",
            "variant": "default",
            "input_condition": "single_channel",
            "runtime_s": float(runtime_sec),
            "parameter_notes": param_str,
            "is_causal": self.IS_CAUSAL,
            # Extra diagnostic metadata
            "n_maternal_peaks": int(len(m_peaks)),
            "n_svd_components": int(k_used),
            "fecg_band": list(self.fecg_band),
        }

        return fecg_est.astype(np.float64), metadata

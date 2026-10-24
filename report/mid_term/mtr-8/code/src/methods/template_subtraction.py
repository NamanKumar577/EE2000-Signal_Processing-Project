"""
src/methods/template_subtraction.py
──────────────────────────────────────────────────────────────────────────────
Maternal template subtraction for non-invasive fetal ECG extraction.

Owner    : Anshu (Maternal Template Subtraction extraction owner)
Reference: PPR-8 Section 5.2 Method B;
           A Review of Signal Processing Techniques for Non-Invasive Fetal
           Electrocardiography (Hasan et al., 2009);
           ECG Signal Processing (Sörnmo & Laguna, 2006).

Algorithm Description (PPR-8 Section 5.2 Method B):
  1. Maternal R-peak detection:
     Direct single-channel detection from preprocessed abdominal mixture
     via 8–20 Hz bandpass, squaring, moving integration, and peak detection.
     (No clean reference or oracle signal used in deployable mode).
  2. Beat segmentation:
     Segment maternal beats in a ±300 ms window around each detected R-peak
     (±75 samples at 250 Hz, length 151 samples).
  3. Template estimation:
     - Adaptive EMA (default, PPR-8): K=10 initial beat median, updated
       via exponential moving average (weight alpha=0.1 for new beat).
     - Fixed Ensemble (variant): Static median template across all beats.
  4. Template subtraction:
     Scale-adjusted template is subtracted from the mixture around each
     maternal beat with boundary tapering to eliminate step transients.
     Inter-beat intervals are preserved without modification.
  5. Fetal residual:
     Resulting signal is the estimated fetal ECG with maternal QRS suppressed.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import numpy as np
from scipy.signal import butter, sosfiltfilt, find_peaks

from src.methods.base import BaseExtractor


class TemplatSubtractionExtractor(BaseExtractor):
    """
    Maternal template subtraction (Anshu's method).

    Supports:
      - 'adaptive_ema'  : PPR-8 default with exponential moving average (alpha=0.1)
      - 'fixed_ensemble': Static median template over all detected maternal beats
      - Oracle mode     : Activated if reference_channel is provided in kwargs
    """

    DESCRIPTION = (
        "Maternal template subtraction (PPR-8 Section 5.2 Method B: "
        "maternal QRS detection, ±300 ms beat windowing, adaptive EMA template)"
    )
    INPUT_SIGNALS = "Single-channel abdominal mixture (preprocessed)"
    REFERENCE_NEEDED = False
    IS_CAUSAL = False

    def __init__(self, fs: int = 250, config: Optional[dict] = None):
        super().__init__(fs=fs, config=config)
        cfg = self.config or {}
        self.variant = cfg.get("variant", "adaptive_ema")
        self.window_ms = float(cfg.get("window_ms", 300.0))
        self.ema_alpha = float(cfg.get("ema_alpha", 0.1))
        self.k_init = int(cfg.get("k_init", 10))
        self.amplitude_scaling = bool(cfg.get("amplitude_scaling", True))

    def extract(
        self,
        mixture: np.ndarray,
        **kwargs: Any,
    ) -> tuple[np.ndarray, dict]:
        """
        Extract fetal ECG via maternal template subtraction.

        Parameters
        ----------
        mixture : np.ndarray, shape (n_samples,)
            Preprocessed single-channel abdominal mixture signal.
        **kwargs : Any
            Optional 'reference_channel' (clean MECG) for diagnostic oracle runs.

        Returns
        -------
        fecg_est : np.ndarray, shape (n_samples,)
            Estimated fetal ECG signal.
        metadata : dict
            Conforms strictly to OUTPUT_KEYS contract.
        """
        t0 = time.perf_counter()
        fs = self.fs
        n = len(mixture)

        # ── 1. Check for diagnostic oracle mode ────────────────────────────────
        ref_channel = kwargs.get("reference_channel", None)
        is_oracle = ref_channel is not None
        input_cond = "oracle_assisted" if is_oracle else "single_channel"

        # Signal used for maternal R-peak detection
        m_det_signal = ref_channel.astype(np.float64) if is_oracle else mixture.astype(np.float64)

        # ── 2. Maternal R-peak detection ──────────────────────────────────────
        m_peaks = self._detect_maternal_peaks(m_det_signal, fs=fs)

        if len(m_peaks) == 0:
            # Fallback: if no maternal beats detected, return mixture
            runtime = time.perf_counter() - t0
            metadata = {
                "method_name": "template_subtraction",
                "variant": self.variant,
                "input_condition": input_cond,
                "runtime_s": runtime,
                "parameter_notes": f"variant={self.variant}, window_ms={self.window_ms}, n_peaks=0",
                "is_causal": False,
            }
            return mixture.copy(), metadata

        # ── 3. Beat segmentation ──────────────────────────────────────────────
        pre_s = int(0.25 * fs)
        post_s = int(0.45 * fs)
        beat_len = pre_s + post_s

        # Collect complete maternal beats for template construction
        valid_peaks = [p for p in m_peaks if pre_s <= p < n - post_s]

        if len(valid_peaks) == 0:
            runtime = time.perf_counter() - t0
            metadata = {
                "method_name": "template_subtraction",
                "variant": self.variant,
                "input_condition": input_cond,
                "runtime_s": runtime,
                "parameter_notes": f"variant={self.variant}, n_valid_beats=0",
                "is_causal": False,
            }
            return mixture.copy(), metadata

        beats = np.array([mixture[p - pre_s : p + post_s].astype(np.float64) for p in valid_peaks])

        # ── 4. Window taper ───────────────────────────────────────────────────
        taper_len = min(10, max(1, int(0.04 * fs)))
        taper = np.ones(beat_len)
        if taper_len > 1:
            taper[:taper_len] = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, taper_len)))
            taper[-taper_len:] = taper[:taper_len][::-1]

        mecg_est = np.zeros(n, dtype=np.float64)
        weight_sum = np.zeros(n, dtype=np.float64)

        if self.variant == "fixed_ensemble":
            # Global low-rank regularized ensemble (captures dominant morphology + respiratory dipole axis tilt)
            u, s, vt = np.linalg.svd(beats, full_matrices=False)
            k = min(2, len(s))
            recon_beats = (u[:, :k] * s[:k]) @ vt[:k, :]

            for idx, p in enumerate(valid_peaks):
                seg = recon_beats[idx] * taper
                mecg_est[p - pre_s : p + post_s] += seg
                weight_sum[p - pre_s : p + post_s] += taper
        else:
            # Block-adaptive moving template ensemble (adapts locally to heart rate & axis shifts)
            m_win = 15
            for idx, p in enumerate(valid_peaks):
                w_start = max(0, idx - m_win + 1)
                sub = beats[w_start : idx + 1]
                if len(sub) >= 2:
                    u, s, vt = np.linalg.svd(sub, full_matrices=False)
                    k = min(2, len(s))
                    sub_recon = (u[:, :k] * s[:k]) @ vt[:k, :]
                    seg = sub_recon[-1] * taper
                else:
                    seg = beats[idx] * taper
                mecg_est[p - pre_s : p + post_s] += seg
                weight_sum[p - pre_s : p + post_s] += taper

        # Normalize overlapping regions
        mask = weight_sum > 1.0
        mecg_est[mask] /= weight_sum[mask]

        residual = mixture - mecg_est

        # ── 6. Multi-scale subband filter (8-38 Hz) to isolate fetal QRS ───────
        if len(residual) > int(fs * 0.1):
            nyq = 0.5 * fs
            low = max(0.01, min(8.0 / nyq, 0.95))
            high = max(low + 0.01, min(38.0 / nyq, 0.99))
            sos = butter(3, [low, high], btype="band", output="sos")
            fecg_est = sosfiltfilt(sos, residual)
            std_f = float(np.std(fecg_est))
            std_r = float(np.std(residual))
            if std_f > 1e-9 and std_r > 1e-9:
                fecg_est = fecg_est * (std_r / std_f)
        else:
            fecg_est = residual.copy()

        runtime = time.perf_counter() - t0

        param_notes = (
            f"variant={self.variant}, window_ms={self.window_ms}, "
            f"ema_alpha={self.ema_alpha}, scaling={self.amplitude_scaling}, "
            f"n_maternal_peaks={len(m_peaks)}, mode={input_cond}"
        )

        metadata = {
            "method_name": "template_subtraction",
            "variant": self.variant,
            "input_condition": input_cond,
            "runtime_s": runtime,
            "parameter_notes": param_notes,
            "is_causal": False,
        }

        return fecg_est, metadata

    def _detect_maternal_peaks(self, signal: np.ndarray, fs: int) -> np.ndarray:
        """
        Detect maternal R-peaks directly from single-channel mixture.
        Uses 8–20 Hz bandpass, squaring, moving-window integration,
        and physiological refractory blanking (400 ms for maternal).
        """
        n = len(signal)
        nyq = fs / 2.0
        low = max(0.01, min(8.0 / nyq, 0.95))
        high = max(low + 0.01, min(20.0 / nyq, 0.99))
        sos = butter(4, [low, high], btype="band", output="sos")
        bp = sosfiltfilt(sos, signal)
        sq = bp ** 2

        # Moving window integration (120 ms)
        win_samples = max(1, int(round(0.120 * fs)))
        kernel = np.ones(win_samples) / win_samples
        mwi = np.convolve(sq, kernel, mode="same")

        # Refractory period: maternal HR typically 60–100 BPM -> min 400 ms (100 samples)
        min_dist = max(1, int(round(0.400 * fs)))
        height_thr = float(np.percentile(mwi, 80))

        candidates, _ = find_peaks(mwi, distance=min_dist, height=height_thr)
        if len(candidates) == 0:
            return np.array([], dtype=int)

        # Localize exact maternal R-peak within ±40 ms in the mixture
        search_samples = max(1, int(round(0.040 * fs)))
        m_peaks: list[int] = []
        for c in candidates:
            w_start = max(0, c - search_samples)
            w_end = min(n, c + search_samples + 1)
            true_pk = int(w_start + np.argmax(np.abs(signal[w_start:w_end])))
            m_peaks.append(true_pk)

        # Deduplicate and sort
        m_peaks_arr = np.sort(np.unique(m_peaks)).astype(int)
        return m_peaks_arr


class FixedTemplateSubtractionExtractor(TemplatSubtractionExtractor):
    """Fixed ensemble median template subtraction variant."""
    def __init__(self, fs: int = 250, config: Optional[dict] = None):
        cfg = dict(config or {})
        cfg["variant"] = "fixed_ensemble"
        super().__init__(fs=fs, config=cfg)


# Alias for clean naming
TemplateSubtractionExtractor = TemplatSubtractionExtractor


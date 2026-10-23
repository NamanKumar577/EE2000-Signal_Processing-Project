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
        half_win = max(1, int(round(self.window_ms * fs / 1000.0)))
        win_len = 2 * half_win + 1

        # Collect complete maternal beats for template initialization
        valid_beats: list[np.ndarray] = []
        for p in m_peaks:
            if p - half_win >= 0 and p + half_win < n:
                valid_beats.append(mixture[p - half_win : p + half_win + 1])

        if len(valid_beats) == 0:
            # All peaks too close to boundary
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

        valid_beats_arr = np.array(valid_beats)

        # ── 4. Template initialization ────────────────────────────────────────
        # Window taper (10-sample Tukey-style transition at flanks)
        taper = np.ones(win_len)
        n_taper = min(10, half_win // 4)
        if n_taper > 1:
            taper[:n_taper] = np.linspace(0.0, 1.0, n_taper)
            taper[-n_taper:] = np.linspace(1.0, 0.0, n_taper)

        k_init = min(len(valid_beats_arr), self.k_init)
        if self.variant == "fixed_ensemble":
            # Static median template across entire recording
            template = np.median(valid_beats_arr, axis=0)
        else:
            # Adaptive EMA template initialized from first K beats
            template = np.median(valid_beats_arr[:k_init], axis=0)

        alpha = self.ema_alpha
        fecg_est = mixture.copy().astype(np.float64)

        # ── 5. Template subtraction & dynamic adaptation ──────────────────────
        for p in m_peaks:
            start = max(0, p - half_win)
            end = min(n, p + half_win + 1)
            t_start = start - (p - half_win)
            t_end = t_start + (end - start)

            curr_beat = mixture[start:end]
            curr_template = template[t_start:t_end]
            curr_taper = taper[t_start:t_end]

            # Amplitude scaling factor (least-squares fit to accommodate respiration)
            scale = 1.0
            if self.amplitude_scaling:
                denom = np.dot(curr_template, curr_template)
                if denom > 1e-8:
                    scale = float(np.dot(curr_beat, curr_template) / denom)
                    scale = float(np.clip(scale, 0.6, 1.5))

            # Subtract scaled, tapered maternal template
            fecg_est[start:end] -= scale * curr_template * curr_taper

            # Adaptive EMA update (only for full beats in adaptive mode)
            if self.variant != "fixed_ensemble" and t_start == 0 and t_end == win_len:
                normalized_beat = curr_beat / scale if scale > 1e-3 else curr_beat
                template = (1.0 - alpha) * template + alpha * normalized_beat

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


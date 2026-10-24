"""
code/tests/test_preprocessing.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for shared baseline preprocessing module (Astitva's module).
Tests baseline wander removal, bandpass filtering, zero-phase response,
edge padding, and config immutability.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest
import numpy as np

# Ensure code/ is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.preprocessing import preprocess, get_config_summary, _DEFAULT_CONFIG


def test_preprocess_output_shape_and_type():
    """Preprocessing should preserve input length and return float ndarray."""
    signal = np.random.randn(5000)
    out = preprocess(signal, fs=250)
    assert isinstance(out, np.ndarray)
    assert out.shape == signal.shape
    assert not np.any(np.isnan(out))
    assert not np.any(np.isinf(out))


def test_dc_rejection():
    """A pure DC offset signal must be suppressed to near zero."""
    fs = 250
    t = np.linspace(0, 10, 10 * fs, endpoint=False)
    # DC offset of 5.0 V + tiny noise
    signal = 5.0 * np.ones_like(t)
    filtered = preprocess(signal, fs=fs)
    # Discard boundary edges to avoid edge transients and measure steady-state
    steady_state = filtered[250:-250]
    assert np.max(np.abs(steady_state)) < 0.05, f"DC offset not suppressed: max={np.max(np.abs(steady_state))}"


def test_slow_baseline_wander_suppression():
    """Slow 0.1 Hz drift (respiratory band) should be strongly attenuated."""
    fs = 250
    t = np.arange(10 * fs) / fs
    drift = 2.0 * np.sin(2 * np.pi * 0.1 * t)
    filtered = preprocess(drift, fs=fs)
    # The 0.1 Hz signal should be attenuated by at least 15 dB
    amp_in = np.max(np.abs(drift))
    amp_out = np.max(np.abs(filtered[250:-250]))
    attenuation_db = 20 * np.log10(amp_out / amp_in)
    assert attenuation_db < -15.0, f"Drift attenuation insufficient: {attenuation_db:.2f} dB"


def test_passband_preservation():
    """QRS band frequencies (e.g. 10 Hz) should be preserved with near unity gain."""
    fs = 250
    t = np.arange(10 * fs) / fs
    pure_tone = 1.0 * np.sin(2 * np.pi * 10.0 * t)
    filtered = preprocess(pure_tone, fs=fs)
    # Check amplitude in central portion
    steady_in = pure_tone[fs * 2: -fs * 2]
    steady_out = filtered[fs * 2: -fs * 2]
    gain = np.max(np.abs(steady_out)) / np.max(np.abs(steady_in))
    assert 0.95 <= gain <= 1.05, f"Passband gain deviant at 10 Hz: {gain:.4f}"


def test_high_frequency_suppression():
    """Frequencies above 50 Hz (e.g. 80 Hz noise) should be significantly attenuated."""
    fs = 250
    t = np.arange(10 * fs) / fs
    hf_noise = 1.0 * np.sin(2 * np.pi * 80.0 * t)
    filtered = preprocess(hf_noise, fs=fs)
    steady_out = filtered[fs * 2: -fs * 2]
    gain = np.max(np.abs(steady_out))
    attenuation_db = 20 * np.log10(gain)
    assert attenuation_db < -20.0, f"High frequency (80 Hz) not suppressed: {attenuation_db:.2f} dB"


def test_zero_phase_no_delay():
    """Zero-phase filtfilt must not shift the timing of QRS-like peaks."""
    fs = 250
    t = np.arange(10 * fs) / fs
    # Construct a synthetic isolated spike (simulating R-peak)
    signal = np.zeros_like(t)
    peak_idx = 5 * fs
    signal[peak_idx] = 10.0  # isolated impulse
    filtered = preprocess(signal, fs=fs)
    # Peak index of filtered response should align with peak_idx
    filt_peak_idx = np.argmax(filtered)
    assert filt_peak_idx == peak_idx, f"Phase delay introduced! Peak at {filt_peak_idx}, expected {peak_idx}"


def test_config_summary_string():
    """Summary string should contain key filter parameters."""
    summary = get_config_summary()
    assert "250 Hz" in summary
    assert "0.5" in summary
    assert "40.0" in summary
    assert "Zero-phase" in summary

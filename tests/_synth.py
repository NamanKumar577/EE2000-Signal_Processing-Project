"""
tests/_synth.py
Synthetic 4-channel abdominal ECG mixture for dataset-free unit tests.

  maternal : 70 bpm, 1.0 mV peak, wide QRS
  fetal    : 140 bpm, 0.05 mV peak (20x weaker), narrow QRS
  baseline : DC offset + 0.3 Hz wander, white noise
Each source reaches the 4 electrodes through a different mixing vector, so the
maternal signal occupies one spatial direction and the fetal signal another.
"""

import numpy as np

FS = 250


def ricker_train(n, rate_bpm, amp, sigma_s, rng, jitter=0.02, first_s=0.3, fs=FS):
    """Train of Ricker (Mexican-hat) pulses; returns (signal, peak sample indices)."""
    sig = np.zeros(n)
    peaks = []
    t = first_s
    rr0 = 60.0 / rate_bpm
    half = int(5 * sigma_s * fs)
    k = np.arange(-half, half + 1)
    tt = k / fs
    shape = (1 - (tt / sigma_s) ** 2) * np.exp(-(tt ** 2) / (2 * sigma_s ** 2))
    while True:
        c = int(round(t * fs))
        if c + half >= n:
            break
        sig[c - half:c + half + 1] += amp * shape
        peaks.append(c)
        t += rr0 * (1.0 + jitter * rng.standard_normal())
    return sig, np.array(peaks, dtype=int)


def make_mixture(seconds=60, seed=0, fetal_amp=0.05, maternal_amp=1.0, noise=0.01):
    rng = np.random.default_rng(seed)
    n = int(seconds * FS)
    mat, mat_peaks = ricker_train(n, 70, maternal_amp, 0.020, rng)
    fet, fet_peaks = ricker_train(n, 140, fetal_amp, 0.010, rng, first_s=0.45)
    a = np.array([1.0, 0.8, 0.6, 0.9])
    b = np.array([0.3, -0.5, 0.7, 0.1])
    t = np.arange(n) / FS
    wander = 0.5 * np.sin(2 * np.pi * 0.3 * t)
    X = (np.outer(mat, a) + np.outer(fet, b) + 0.2 + np.outer(wander, [1.0, 0.9, 1.1, 1.0])
         + noise * rng.standard_normal((n, 4)))
    return X, fet_peaks, mat_peaks

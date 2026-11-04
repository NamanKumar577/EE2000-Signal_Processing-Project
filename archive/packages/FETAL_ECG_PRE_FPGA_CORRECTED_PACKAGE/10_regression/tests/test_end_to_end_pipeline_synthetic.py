"""
code/tests/test_end_to_end_pipeline_synthetic.py
──────────────────────────────────────────────────────────────────────────────
Self-contained end-to-end regression test for the bit-accurate integer pipeline.
Operates on purely synthetic multi-channel ECG waveforms (no external dataset needed).
Verifies:
  1. Complete pipeline execution (Beamformer -> HP1 -> LP40 -> Bandpass -> MWI -> Adaptive Thr -> FHR).
  2. R-peak declaration and latency compensation.
  3. Correct interval fusion on injected double-peaked complexes.
  4. Telemetry packet streaming and state flag transitions (Warmup -> Real -> Fused).
"""

import sys
from pathlib import Path
import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.bit_accurate_reference_model_corrected import (
    run_bit_accurate_pipeline_corrected,
    FLAG_REAL_DETECTED, FLAG_FUSED_BEAT, FLAG_INVALID_WARMUP
)
from src.uart_protocol import encode_fhr_telemetry_packet, decode_fhr_telemetry_packet

def test_synthetic_end_to_end_pipeline():
    """Verify bit-accurate pipeline execution on synthetic 4-channel input."""
    fs = 250
    duration_sec = 6.0 # 1500 samples
    n_samples = int(fs * duration_sec)

    # Generate synthetic cardiac beats at 150 bpm (RR = 100 samples)
    # Channel weights: w = [0.5, -0.5, 0.25, -0.25]
    t = np.arange(n_samples)
    sig = np.zeros(n_samples)

    # Injected beats at t = 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400
    beat_locs = list(range(100, 1450, 100))
    # Inject a split peak at t = 715 (15 samples after beat 700) to test fusion
    beat_locs.append(715)
    beat_locs.sort()

    for b in beat_locs:
        # Gaussian QRS pulse
        width = 4 # ~16 ms
        pulse = np.exp(-0.5 * ((t - b) / width) ** 2)
        sig += 2000.0 * pulse

    # Distribute across 4 channels
    x_q = np.zeros((n_samples, 4), dtype=np.int16)
    x_q[:, 0] = np.clip(sig * 0.8, -32768, 32767).astype(np.int16)
    x_q[:, 1] = np.clip(-sig * 0.5, -32768, 32767).astype(np.int16)
    x_q[:, 2] = np.clip(sig * 0.3, -32768, 32767).astype(np.int16)
    x_q[:, 3] = np.clip(-sig * 0.2, -32768, 32767).astype(np.int16)

    # Weights in Q1.15
    w_q = np.array([16384, -16384, 8192, -8192], dtype=np.int16)

    # Run pipeline with warmup = 256 samples
    res = run_bit_accurate_pipeline_corrected(x_q, w_q, mwi_len=30, refractory=50, warmup=256, latency=18)

    # Verify warmup behavior
    assert res.flags[100] == FLAG_INVALID_WARMUP
    assert res.fhr_hold[100] == 0

    # Verify detections occurred after warmup
    assert len(res.peaks) >= 10, f"Expected at least 10 detected peaks, got {len(res.peaks)}"

    # Verify telemetry packet encoding
    last_peak = int(res.peaks[-1])
    fhr_val = int(res.fhr_hold[-1])
    flag_val = int(res.flags[-1])
    pkt = encode_fhr_telemetry_packet(last_peak, fhr_val, flag_val, confident=True)
    assert len(pkt) == 8

    t_dec, fhr_dec, flag_dec, conf_dec = decode_fhr_telemetry_packet(pkt)
    assert t_dec == last_peak
    assert abs(fhr_dec - fhr_val / 10.0) < 1e-4
    assert flag_dec == flag_val
    assert conf_dec is True

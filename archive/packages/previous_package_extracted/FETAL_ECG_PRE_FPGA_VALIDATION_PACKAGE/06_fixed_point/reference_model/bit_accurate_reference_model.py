"""
code/src/bit_accurate_reference_model.py
──────────────────────────────────────────────────────────────────────────────
Pure Bit-Accurate Fixed-Point Integer Golden Reference Model for Spartan-7 FPGA.

Target FPGA: AMD/Xilinx Spartan-7 XC7S50-1CSGA324C
Operating Clock: 100 MHz, Sample Rate: 250 Hz (Ts = 4.0 ms)
Pipeline:
  1. Input ADC: 4 channels, Signed 16-bit Q1.15
  2. Spatial Beamformer: Dot-product with 4x Signed 16-bit Q1.15 weights -> 32-bit Q2.30 accumulator -> Shift >>> 7, Sat s24 (Q1.23)
  3. HP1 Baseline Filter: Recursive shift-only (k=6) in Signed 24-bit (Q1.23)
  4. LP40 Filter: 4th-order Butterworth (40 Hz), 2 biquads (DF2T) with Signed 18-bit Q3.15 coefficients and 48-bit states -> Sat s24
  5. Detector Bandpass Filter: 4th-order Butterworth (12-35 Hz, Config C), 4 biquads with Signed 18-bit Q3.15 coefficients -> Shift >>> 8, Sat s16
  6. Squarer: Signed 16-bit squared -> Unsigned 32-bit product (u32)
  7. Moving Window Integrator (MWI): Trailing ring buffer (W=30 samples = 120 ms) -> Unsigned 36-bit accumulator (u36)
  8. Adaptive Threshold FSM: Dual-threshold EMA tracking with 1/8 shifts
  9. Peak Detector & Localizer: Trailing 26-sample window for R-peak timestamp
  10. Latency Compensation: Subtractor (-12 samples @ 250 Hz)
  11. Beat Quality & FHR Engine: Safe interval fusion (RR < 60) + Causal Median5 + 2-bit state flags

All arithmetic is strictly integer-only. No floating-point operations in data path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np

# Numerical Wordlengths & Binary Positions
ADC_BITS = 16
ADC_FRAC = 15       # Q1.15

WEIGHT_BITS = 16
WEIGHT_FRAC = 15    # Q1.15

PROJ_ACC_BITS = 32  # Q2.30 internal DSP accumulator
PROJ_SHIFT = 7      # Q2.30 >>> 7 -> Q1.23 (s24)

DATA_BITS = 24
DATA_FRAC = 23      # Q1.23 internal datapath

COEF_BITS = 18
COEF_FRAC = 15      # Q3.15 (allows representation of +2.0 exactly)

BIQUAD_STATE_BITS = 48 # Fits 48-bit DSP48 accumulator

DET_SHIFT = 8       # Q1.23 >>> 8 -> Q1.15 (s16)
DET_BITS = 16
DET_FRAC = 15       # Q1.15 detector input

MWI_ACC_BITS = 36   # Unsigned 36-bit accumulator for 30x squared s16 samples

RR_MIN = 60         # 250 bpm @ 250 Hz
RR_MAX = 300        # 50 bpm @ 250 Hz

# Telemetry 2-bit Status Flags
FLAG_REAL_DETECTED    = 0b00
FLAG_FUSED_BEAT       = 0b01
FLAG_HELD_FHR         = 0b10
FLAG_INVALID_WARMUP   = 0b11

def sat(v: int, bits: int) -> int:
    """Two-level symmetric saturation clamp to signed [-(1<<(bits-1)), (1<<(bits-1))-1]."""
    lim = 1 << (bits - 1)
    if v >= lim:
        return lim - 1
    elif v < -lim:
        return -lim
    return int(v)

def sat_u(v: int, bits: int) -> int:
    """Saturation clamp to unsigned [0, (1<<bits)-1]."""
    lim = (1 << bits) - 1
    if v >= lim:
        return lim
    elif v < 0:
        return 0
    return int(v)

def rshift_round(v: int, shift: int) -> int:
    """Symmetric round-half-up integer shift: (v + (1 << (shift - 1))) >> shift."""
    if shift <= 0:
        return int(v)
    return int((v + (1 << (shift - 1))) >> shift)

def quantize_biquad_sos(sos: np.ndarray, coef_frac: int = COEF_FRAC) -> List[Tuple[int, int, int, int, int]]:
    """Convert floating-point SOS matrix to integer Q3.15 coefficients."""
    out = []
    scale = 1 << coef_frac
    for row in sos:
        b0, b1, b2, a0, a1, a2 = row
        # Normalize by a0
        b0_q = sat(int(round(b0 / a0 * scale)), COEF_BITS)
        b1_q = sat(int(round(b1 / a0 * scale)), COEF_BITS)
        b2_q = sat(int(round(b2 / a0 * scale)), COEF_BITS)
        # Direct Form II Transposed uses negative feedback (-a1, -a2)
        a1_neg_q = sat(int(round(-a1 / a0 * scale)), COEF_BITS)
        a2_neg_q = sat(int(round(-a2 / a0 * scale)), COEF_BITS)
        out.append((b0_q, b1_q, b2_q, a1_neg_q, a2_neg_q))
    return out

class BiquadDF2TInt:
    """
    Direct Form II Transposed Biquad Section with 48-bit State Accumulators.
    Hardware equations (DSP48E1 pipelined MAC):
      y[n]  = sat_s24((b0_q * x[n] + s1) >>> COEF_FRAC)
      s1[n] = b1_q * x[n] + a1_neg_q * y[n] + s2
      s2[n] = b2_q * x[n] + a2_neg_q * y[n]
    """
    def __init__(self, coeffs: Tuple[int, int, int, int, int], out_bits: int = DATA_BITS):
        self.b0, self.b1, self.b2, self.a1_neg, self.a2_neg = coeffs
        self.out_bits = out_bits
        self.s1 = 0
        self.s2 = 0
        self.max_s1 = 0
        self.max_s2 = 0

    def step(self, x: int) -> int:
        # Accumulator 1: b0 * x + s1
        acc = int(self.b0 * x + self.s1)
        y = sat(rshift_round(acc, COEF_FRAC), self.out_bits)

        # Update delay state 1: b1 * x + a1_neg * y + s2
        self.s1 = int(self.b1 * x + self.a1_neg * y + self.s2)
        # Update delay state 2: b2 * x + a2_neg * y
        self.s2 = int(self.b2 * x + self.a2_neg * y)

        self.max_s1 = max(self.max_s1, abs(self.s1))
        self.max_s2 = max(self.max_s2, abs(self.s2))
        return y

@dataclass
class BitAccurateResult:
    proj: np.ndarray        # Signed 24-bit
    hp: np.ndarray          # Signed 24-bit
    fecg: np.ndarray        # Signed 24-bit
    det_bp: np.ndarray      # Signed 16-bit
    x_int: np.ndarray       # Unsigned 36-bit
    peaks: np.ndarray       # Latency compensated sample timestamps
    raw_peaks: np.ndarray   # Uncompensated detector timestamps
    fhr_hold: np.ndarray    # Instantaneous FHR stream in bpm x 10
    flags: np.ndarray       # 2-bit state classification flags
    rr: np.ndarray          # Validated RR intervals
    max_ranges: Dict[str, int]

def run_bit_accurate_pipeline(
    x_q: np.ndarray,        # (N, 4) Signed 16-bit samples
    w_q: np.ndarray,        # (4,) Signed 16-bit weights
    lp_sos_float: np.ndarray,
    bp_sos_float: np.ndarray,
    mwi_len: int = 30,      # Config C: 30 samples (120 ms)
    refractory: int = 50,   # Config C: 50 samples (200 ms)
    warmup: int = 512,      # 512 samples (~2.05 s)
    loc_window: int = 26,   # 26 samples (104 ms)
    latency: int = 12       # 12 samples compensation
) -> BitAccurateResult:
    x_q = np.asarray(x_q, dtype=np.int64)
    n, n_ch = x_q.shape
    w = [int(v) for v in w_q]

    # Initialize Integer Biquad Cascades
    lp_biquads = [BiquadDF2TInt(c, out_bits=DATA_BITS) for c in quantize_biquad_sos(lp_sos_float)]
    bp_biquads = [BiquadDF2TInt(c, out_bits=DATA_BITS) for c in quantize_biquad_sos(bp_sos_float)]

    # State variables
    k = 6 # HP1 shift
    hp_acc = 0
    mwi_ring = [0] * mwi_len
    mwi_sum = 0
    abs_hist: List[int] = []

    peak_level = 0
    noise_level = 0
    warm_max = 0
    warm_sum = 0
    detector_enabled = False
    last_cand_m = -(10 ** 9)

    # Output arrays
    proj_arr = np.zeros(n, dtype=np.int64)
    hp_arr = np.zeros(n, dtype=np.int64)
    fecg_arr = np.zeros(n, dtype=np.int64)
    det_bp_arr = np.zeros(n, dtype=np.int64)
    xint_arr = np.zeros(n, dtype=np.int64)
    fhr_stream = np.zeros(n, dtype=np.int64)
    flags_arr = np.zeros(n, dtype=np.uint8)

    raw_peaks_list: List[int] = []
    comp_peaks_list: List[int] = []
    rr_list: List[int] = []

    fhr_current = 1400 # 140.0 bpm
    current_flag = FLAG_INVALID_WARMUP

    # Range and overflow tracking
    max_proj_acc = 0
    max_hp_acc = 0
    max_mwi_acc = 0

    # FHR LUT (150,000 / RR in bpm x 10)
    fhr_lut = [round(150000.0 / r) for r in range(RR_MIN, RR_MAX + 1)]

    for t in range(n):
        # ── 1. Spatial Beamformer (4x s16 x s16 -> s32 -> s24) ─────────────
        acc = 0
        for c in range(n_ch):
            acc += w[c] * int(x_q[t, c])
        max_proj_acc = max(max_proj_acc, abs(acc))
        # Symmetric round-half-up shift >>> 7, saturate to 24 bits
        proj_val = sat(rshift_round(acc, PROJ_SHIFT), DATA_BITS)
        proj_arr[t] = proj_val

        # ── 2. HP1 Baseline Remover (Recursive shift-only in s24) ──────────
        # base = hp_acc >>> 6;  y = proj - base;  hp_acc += proj - base
        base = hp_acc >> k
        hp_val = sat(proj_val - base, DATA_BITS)
        hp_acc = hp_acc + proj_val - base
        max_hp_acc = max(max_hp_acc, abs(hp_acc))
        hp_arr[t] = hp_val

        # ── 3. LP40 Filter (2 Biquads in s24) = FECG Clean Output ──────────
        fecg_val = hp_val
        for s in lp_biquads:
            fecg_val = s.step(fecg_val)
        fecg_arr[t] = fecg_val

        # ── 4. Detector Bandpass Filter (4 Biquads in s24 -> s16) ──────────
        bp_val = fecg_val
        for s in bp_biquads:
            bp_val = s.step(bp_val)
        # Shift >>> 8 to fit 16-bit multiplier input
        bp16 = sat(rshift_round(bp_val, DET_SHIFT), DET_BITS)
        det_bp_arr[t] = bp16
        abs_hist.append(abs(bp16))

        # ── 5. Squaring & Moving Window Integration (u36) ──────────────────
        sq = bp16 * bp16 # Unsigned 32-bit product
        mwi_sum += sq - mwi_ring[t % mwi_len]
        mwi_ring[t % mwi_len] = sq
        max_mwi_acc = max(max_mwi_acc, mwi_sum)
        xint_arr[t] = mwi_sum

        # ── 6. Warm-up Initialization ──────────────────────────────────────
        if t < warmup:
            flags_arr[t] = FLAG_INVALID_WARMUP
            fhr_stream[t] = 0
            warm_max = max(warm_max, mwi_sum)
            warm_sum += mwi_sum
            if t == warmup - 1:
                peak_level = warm_max
                noise_level = warm_sum >> 9 # Divide by 512 via shift
                detector_enabled = (peak_level > noise_level)
            continue

        current_flag = FLAG_REAL_DETECTED

        # ── 7. Adaptive Threshold & Peak Detection at m = t - 1 ────────────
        if detector_enabled and t >= 2:
            m = t - 1
            v = int(xint_arr[m])
            # Local maximum test: x_int[m-1] < x_int[m] >= x_int[t]
            if int(xint_arr[m - 1]) < v and v >= mwi_sum and m >= warmup - 1:
                # Dual threshold: thr = 1/4 peak + 3/4 noise
                thr = (peak_level >> 2) + noise_level - (noise_level >> 2)
                if v > thr:
                    if (m - last_cand_m) >= refractory:
                        # Localize true R-peak in the trailing search window
                        lo = max(0, t - (loc_window - 1))
                        best_idx = lo
                        best_val = abs_hist[lo]
                        for i in range(lo + 1, t + 1):
                            if abs_hist[i] > best_val:
                                best_val = abs_hist[i]
                                best_idx = i

                        # RR and Interval Fusion Logic
                        if raw_peaks_list:
                            raw_rr = best_idx - raw_peaks_list[-1]
                            if raw_rr < RR_MIN:
                                current_flag = FLAG_FUSED_BEAT
                            elif raw_rr <= RR_MAX:
                                fhr_current = fhr_lut[raw_rr - RR_MIN]
                                current_flag = FLAG_REAL_DETECTED
                            else:
                                current_flag = FLAG_HELD_FHR # Keep previous FHR
                        else:
                            raw_rr = 0

                        rr_list.append(raw_rr)
                        raw_peaks_list.append(best_idx)
                        comp_peaks_list.append(max(0, best_idx - latency))
                        last_cand_m = m
                        peak_level += (v - peak_level) >> 3 # EMA with 1/8 factor
                else:
                    noise_level += (v - noise_level) >> 3

        fhr_stream[t] = fhr_current
        flags_arr[t] = current_flag

    max_ranges = {
        "max_proj_acc_bits": int(max_proj_acc).bit_length() + 1,
        "max_hp_acc_bits": int(max_hp_acc).bit_length() + 1,
        "max_lp_biquad_state_bits": max(s.max_s1 for s in lp_biquads).bit_length() + 1,
        "max_bp_biquad_state_bits": max(s.max_s1 for s in bp_biquads).bit_length() + 1,
        "max_mwi_acc_bits": int(max_mwi_acc).bit_length()
    }

    return BitAccurateResult(
        proj=proj_arr,
        hp=hp_arr,
        fecg=fecg_arr,
        det_bp=det_bp_arr,
        x_int=xint_arr,
        peaks=np.array(comp_peaks_list, dtype=np.int64),
        raw_peaks=np.array(raw_peaks_list, dtype=np.int64),
        fhr_hold=fhr_stream,
        flags=flags_arr,
        rr=np.array(rr_list, dtype=np.int64),
        max_ranges=max_ranges
    )

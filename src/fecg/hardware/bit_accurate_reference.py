"""
code/src/bit_accurate_reference_model_final.py
────────────────────────────────────────────────────────────────────────────
Final Bit-Accurate Fixed-Point Integer Golden Reference Model for Spartan-7.

Target FPGA: AMD/Xilinx Spartan-7 XC7S50-1CSGA324C
Operating Clock: 100 MHz, Sample Rate: 250 Hz (Ts = 4.0 ms)

Strict Hardware Arithmetic Constraints:
  1. Priority A: Exact scaling chain derived:
     - Input ADC: Signed 16-bit, scale = 4096 LSB/mV (12-bit ADC in 16-bit word, Q12).
     - Weights: Signed 16-bit Q1.15 (scale = 32768 LSB/unit).
     - Multiplier: Signed 16x16 -> 32-bit product (Q27).
     - Projection Accumulator: Constrained to 32 bits (PROJ_ACC_BITS = 32).
     - Projection Shift: >>> 7 with Convergent Rounding -> Q20 (2^20 LSB/mV).
     - Int to physical conversion: x_mV = proj_q / (2^20).
  2. Priority B: Enforced Exact Hardware Arithmetic:
     - Projection Accumulator: Explicit signed 32-bit clamping sat(acc, 32).
     - MWI Accumulator: Explicit unsigned 36-bit clamping sat_u(acc, 36).
     - Zero np.median(): Pure integer median-5 algorithm with deterministic rounding.
     - Frozen Integer FHR LUT: Precomputed 251-word table in 0.1 bpm units.
     - 64-sample linear crossfade slew engine for dynamic weight transitions.
     - Per-stage saturation and overflow accounting.
  3. Priority E: Empirically verified 18-sample group delay latency compensation.
  4. Priority G: Telemetry status byte with bits 1:0 (class), bit 2 (conf), bit 3 (sat), bits 7:4 (res).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np

# Master Numerical Wordlengths & Binary Positions
ADC_BITS = 16
ADC_SCALE_LSB_PER_MV = 4096.0  # Q12 representation of 12-bit ADC in 16-bit word

WEIGHT_BITS = 16
WEIGHT_SCALE = 32768.0        # Q1.15

PROJ_ACC_BITS = 32            # Signed 32-bit internal DSP accumulator
PROJ_SHIFT = 7                # Q27 >>> 7 -> Q20 in 24-bit word
PHYSICAL_SCALE_Q20 = 1048576.0 # 2^20 LSB/mV

DATA_BITS = 24                # Signed 24-bit internal datapath (Q20)

COEF_BITS = 18
COEF_FRAC = 15                # Q3.15 (scale = 32768)
COEF_SCALE = 32768

BIQUAD_STATE_BITS = 48        # Enforces 48-bit DSP48 accumulator width

DET_SHIFT = 8                 # Q20 >>> 8 -> Q12 (Signed 16-bit detector input)
DET_BITS = 16

MWI_ACC_BITS = 36             # Unsigned 36-bit accumulator for 30x squared s16 samples
MWI_WINDOW_LEN = 30           # 120 ms window

REFRACTORY_SAMPLES = 50       # 200 ms -> 300 bpm max physical firing rate
RR_MIN = 50                   # 300 bpm @ 250 Hz (50 samples = 200 ms)
RR_MAX = 300                  # 50 bpm @ 250 Hz (300 samples = 1200 ms)
FHR_MIN_BPM = 50.0
FHR_MAX_BPM = 300.0

WEIGHT_CROSSFADE_STEPS = 64   # 64-sample linear crossfade slew engine

LATENCY_COMPENSATION_SAMPLES = 18  # Group delay compensation at 15 Hz for Config C

# Telemetry Status Flags (Byte 6)
FLAG_REAL_DETECTED    = 0b00
FLAG_FUSED_BEAT       = 0b01
FLAG_HELD_FHR         = 0b10
FLAG_INVALID_WARMUP   = 0b11

# Frozen Static Integer Coefficients in Signed 18-bit Q3.15 (Scale = 32768)
# LP40 Filter (4th-order Butterworth lowpass, 40 Hz @ 250 Hz, 2 biquads)
LP40_COEFFS_Q15: Tuple[Tuple[int, int, int, int, int], ...] = (
    (749, 1499, 749, 19727, -4049),      # Section 0: b0, b1, b2, a1_neg, a2_neg
    (32768, 65536, 32768, 26540, -16764) # Section 1
)

# Config C Bandpass Filter (8th-order Butterworth bandpass, 12-35 Hz @ 250 Hz, 4 biquads)
DET_BP_CONFIG_C_COEFFS_Q15: Tuple[Tuple[int, int, int, int, int], ...] = (
    (119, 238, 119, 38563, -16484),       # Section 0
    (32768, 65536, 32768, 49834, -21435), # Section 1
    (32768, -65536, 32768, 37298, -24206),# Section 2
    (32768, -65536, 32768, 58829, -29016) # Section 3
)

# Frozen Integer FHR LUT (251 entries, RR = 50 to 300 samples, units = 0.1 bpm)
# Formally generated: round(150000.0 / rr)
FHR_FROZEN_INTEGER_LUT: Tuple[int, ...] = tuple(
    round(150000.0 / r) for r in range(RR_MIN, RR_MAX + 1)
)

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

def rshift_round_nearest_even(v: int, shift: int) -> int:
    """
    Bit-accurate Convergent Rounding (Round-to-Nearest-Even).
    Eliminates systematic DC offset accumulation in recursive filter paths.
    """
    if shift <= 0:
        return int(v)
    q = v >> shift
    r = v & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    if r > half:
        return q + 1
    elif r < half:
        return q
    else:  # Exact halfway: round to nearest even quotient
        return q + (q & 1)

def integer_median(values: Sequence[int]) -> int:
    """
    Pure integer median for 1 to 5 values with deterministic integer rounding for even counts.
    For even counts [a, b], rounds average: (a + b + 1) // 2.
    Zero floating point operations.
    """
    k = len(values)
    if k == 0:
        return 0
    s = sorted(values)
    if k == 1:
        return s[0]
    elif k == 2:
        return (s[0] + s[1] + 1) // 2
    elif k == 3:
        return s[1]
    elif k == 4:
        return (s[1] + s[2] + 1) // 2
    else:  # k == 5 (or odd)
        return s[k // 2]

@dataclass
class StageOverflowAccounting:
    proj_mult_overflow: int = 0
    proj_acc_overflow: int = 0
    proj_sat_count: int = 0
    hp_acc_overflow: int = 0
    hp_sat_count: int = 0
    lp_biquad_state_overflow: int = 0
    lp_biquad_out_sat: int = 0
    bp_biquad_state_overflow: int = 0
    bp_biquad_out_sat: int = 0
    det_shift_sat_count: int = 0
    squaring_overflow: int = 0
    mwi_acc_overflow: int = 0
    threshold_overflow: int = 0
    rr_overflow: int = 0
    fhr_lut_overflow: int = 0

    def total_overflows(self) -> int:
        return (
            self.proj_mult_overflow
            + self.proj_acc_overflow
            + self.hp_acc_overflow
            + self.lp_biquad_state_overflow
            + self.bp_biquad_state_overflow
            + self.squaring_overflow
            + self.mwi_acc_overflow
            + self.threshold_overflow
            + self.rr_overflow
            + self.fhr_lut_overflow
        )

    def total_saturations(self) -> int:
        return (
            self.proj_sat_count
            + self.hp_sat_count
            + self.lp_biquad_out_sat
            + self.bp_biquad_out_sat
            + self.det_shift_sat_count
        )

class BiquadDF2TIntFinal:
    """
    Final Direct Form II Transposed Biquad with Enforced 48-bit State Saturation
    and Per-Stage Saturation Tracking.
    """
    def __init__(self, coeffs: Tuple[int, int, int, int, int], out_bits: int = DATA_BITS):
        self.b0, self.b1, self.b2, self.a1_neg, self.a2_neg = coeffs
        self.out_bits = out_bits
        self.s1 = 0
        self.s2 = 0
        self.max_s1 = 0
        self.max_s2 = 0
        self.state_overflow_count = 0
        self.out_sat_count = 0

    def step(self, x: int) -> int:
        acc = self.b0 * x + self.s1
        y_rounded = rshift_round_nearest_even(acc, COEF_FRAC)
        y = sat(y_rounded, self.out_bits)
        if y != y_rounded:
            self.out_sat_count += 1

        next_s1_raw = self.b1 * x + self.a1_neg * y + self.s2
        next_s2_raw = self.b2 * x + self.a2_neg * y

        next_s1 = sat(next_s1_raw, BIQUAD_STATE_BITS)
        next_s2 = sat(next_s2_raw, BIQUAD_STATE_BITS)

        if next_s1 != next_s1_raw or next_s2 != next_s2_raw:
            self.state_overflow_count += 1

        self.s1 = next_s1
        self.s2 = next_s2

        self.max_s1 = max(self.max_s1, abs(self.s1))
        self.max_s2 = max(self.max_s2, abs(self.s2))
        return y

@dataclass
class BitAccurateFinalResult:
    proj: np.ndarray             # Signed 24-bit (scale 2^20 LSB/mV)
    hp: np.ndarray               # Signed 24-bit (scale 2^20 LSB/mV)
    fecg: np.ndarray             # Signed 24-bit (scale 2^20 LSB/mV)
    det_bp: np.ndarray           # Signed 16-bit (scale 2^12 LSB/mV)
    x_int: np.ndarray            # Unsigned 36-bit
    peaks: np.ndarray            # 18-sample latency-compensated sample timestamps (fused)
    raw_peaks: np.ndarray        # Uncompensated detector timestamps (fused)
    fhr_hold: np.ndarray         # Causal Median-5 FHR stream in 0.1 bpm units
    flags: np.ndarray            # 8-bit Telemetry Status Bytes
    rr: np.ndarray               # Validated RR intervals
    accounting: StageOverflowAccounting
    max_ranges: Dict[str, int]
    n_fused_events: int

def run_bit_accurate_pipeline_final(
    x_q: np.ndarray,                 # (N, 4) Signed 16-bit samples (Q12)
    w_q: np.ndarray,                 # (4,) Signed 16-bit weights (Q1.15)
    mwi_len: int = MWI_WINDOW_LEN,   # 30 samples (120 ms)
    refractory: int = REFRACTORY_SAMPLES, # 50 samples (200 ms)
    warmup: int = 512,               # 512 samples (~2.05 s)
    loc_window: int = 26,            # 26 samples (104 ms)
    latency: int = LATENCY_COMPENSATION_SAMPLES, # 18 samples
    target_weights: Optional[Sequence[Tuple[int, Sequence[int]]]] = None # List of (sample_idx, new_weights)
) -> BitAccurateFinalResult:
    """
    Final Pre-RTL Bit-Accurate Execution Reference Model.
    Strictly adheres to hardware arithmetic wordlengths:
      - 32-bit projection accumulation
      - 48-bit biquad state clamping
      - 36-bit MWI accumulation
      - Pure integer median-5
      - 64-sample linear weight crossfade
      - Per-stage saturation and overflow instrumentation
    """
    x_q = np.asarray(x_q, dtype=np.int64)
    n, n_ch = x_q.shape
    w_curr = [int(v) for v in w_q]
    w_old = list(w_curr)
    w_target = list(w_curr)
    crossfade_step = WEIGHT_CROSSFADE_STEPS  # Start fully settled

    # Parse scheduled weight updates if provided
    update_dict: Dict[int, List[int]] = {}
    if target_weights is not None:
        for t_up, w_up in target_weights:
            update_dict[int(t_up)] = [int(v) for v in w_up]

    # Initialize Integer Biquads
    lp_biquads = [BiquadDF2TIntFinal(c, out_bits=DATA_BITS) for c in LP40_COEFFS_Q15]
    bp_biquads = [BiquadDF2TIntFinal(c, out_bits=DATA_BITS) for c in DET_BP_CONFIG_C_COEFFS_Q15]

    acc_tracker = StageOverflowAccounting()

    # State variables
    k_hp = 6  # HP1 shift (fc ~ 0.62 Hz)
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

    # Causal Median5 RR Buffer
    median5_rr_buf: List[int] = []
    fhr_current = 1400  # 140.0 bpm
    current_flag_2bit = FLAG_INVALID_WARMUP
    is_confident_flag = True
    n_fused = 0

    max_proj_acc = 0
    max_hp_acc = 0
    max_mwi_acc = 0

    for t in range(n):
        # ── 0. Dynamic Weight Slew Engine (64-Sample Crossfade) ───────────
        if t in update_dict:
            # New calibration packet arrived: latch current active weights as old base
            w_old = list(w_curr)
            w_target = list(update_dict[t])
            crossfade_step = 1
        elif crossfade_step < WEIGHT_CROSSFADE_STEPS:
            crossfade_step += 1
            for c in range(n_ch):
                delta = w_target[c] - w_old[c]
                step = rshift_round_nearest_even(crossfade_step * delta, 6) # Divide by 64
                w_curr[c] = sat(w_old[c] + step, WEIGHT_BITS)
        elif crossfade_step == WEIGHT_CROSSFADE_STEPS:
            w_curr = list(w_target)

        # ── 1. Spatial Beamformer (Enforced 32-bit Accumulator) ───────────
        raw_acc = 0
        for c in range(n_ch):
            prod = w_curr[c] * int(x_q[t, c])
            if prod >= (1 << 31) or prod < -(1 << 31):
                acc_tracker.proj_mult_overflow += 1
            raw_acc += prod

        acc_clamped = sat(raw_acc, PROJ_ACC_BITS)
        if acc_clamped != raw_acc:
            acc_tracker.proj_acc_overflow += 1

        max_proj_acc = max(max_proj_acc, abs(acc_clamped))
        proj_rounded = rshift_round_nearest_even(acc_clamped, PROJ_SHIFT)
        proj_val = sat(proj_rounded, DATA_BITS)
        if proj_val != proj_rounded:
            acc_tracker.proj_sat_count += 1
        proj_arr[t] = proj_val

        # ── 2. HP1 Baseline Remover (Signed 32-bit Accumulator) ──────────
        base = hp_acc >> k_hp
        hp_sub = proj_val - base
        hp_val = sat(hp_sub, DATA_BITS)
        if hp_val != hp_sub:
            acc_tracker.hp_sat_count += 1

        hp_acc_next = hp_acc + hp_sub
        hp_acc_clamped = sat(hp_acc_next, 32)
        if hp_acc_clamped != hp_acc_next:
            acc_tracker.hp_acc_overflow += 1
        hp_acc = hp_acc_clamped

        max_hp_acc = max(max_hp_acc, abs(hp_acc))
        hp_arr[t] = hp_val

        # ── 3. LP40 Filter (2 Biquads, 48-bit State Saturation) ──────────
        fecg_val = hp_val
        for s in lp_biquads:
            fecg_val = s.step(fecg_val)
        fecg_arr[t] = fecg_val

        # ── 4. Detector Bandpass Filter (4 Biquads, 48-bit States) ───────
        bp_val = fecg_val
        for s in bp_biquads:
            bp_val = s.step(bp_val)
        bp_rounded = rshift_round_nearest_even(bp_val, DET_SHIFT)
        bp16 = sat(bp_rounded, DET_BITS)
        if bp16 != bp_rounded:
            acc_tracker.det_shift_sat_count += 1
        det_bp_arr[t] = bp16
        abs_hist.append(abs(bp16))

        # ── 5. Squaring & Moving Window Integration (36-bit Constrained) ─
        sq = bp16 * bp16  # Unsigned 32-bit product
        if sq >= (1 << 32):
            acc_tracker.squaring_overflow += 1

        mwi_sub = mwi_sum + sq - mwi_ring[t % mwi_len]
        mwi_clamped = sat_u(mwi_sub, MWI_ACC_BITS)
        if mwi_clamped != mwi_sub:
            acc_tracker.mwi_acc_overflow += 1
        mwi_sum = mwi_clamped

        mwi_ring[t % mwi_len] = sq
        max_mwi_acc = max(max_mwi_acc, mwi_sum)
        xint_arr[t] = mwi_sum

        # ── 6. Warm-up Initialization ────────────────────────────────────
        if t < warmup:
            current_flag_2bit = FLAG_INVALID_WARMUP
            flags_arr[t] = (current_flag_2bit & 0x03) | ((1 if is_confident_flag else 0) << 2)
            fhr_stream[t] = 0
            warm_max = max(warm_max, mwi_sum)
            warm_sum += mwi_sum
            if t == warmup - 1:
                peak_level = warm_max
                noise_level = warm_sum >> 9  # Mean over 512 samples
                detector_enabled = (peak_level > noise_level)
            continue

        # ── 7. Adaptive Threshold & Local Peak Search at m = t - 1 ───────
        if detector_enabled and t >= 2:
            m = t - 1
            v = int(xint_arr[m])
            if int(xint_arr[m - 1]) < v and v >= mwi_sum and m >= warmup - 1:
                thr = (peak_level >> 2) + noise_level - (noise_level >> 2)
                if thr >= (1 << 36):
                    acc_tracker.threshold_overflow += 1

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

                        # ── 8. Corrected Interval Fusion & Integer Median5
                        if raw_peaks_list:
                            raw_rr = best_idx - raw_peaks_list[-1]

                            if raw_rr < RR_MIN:
                                # TRUE INTERVAL FUSION: Merge split peak into previous beat
                                n_fused += 1
                                current_flag_2bit = FLAG_FUSED_BEAT
                                if best_val > abs_hist[raw_peaks_list[-1]]:
                                    raw_peaks_list[-1] = best_idx
                                    comp_peaks_list[-1] = max(0, best_idx - latency)
                                # Do NOT append new beat!

                            elif raw_rr <= RR_MAX:
                                # Normal Physiological Beat: Push to Median5 FIFO
                                current_flag_2bit = FLAG_REAL_DETECTED
                                raw_peaks_list.append(best_idx)
                                comp_peaks_list.append(max(0, best_idx - latency))
                                rr_list.append(raw_rr)

                                median5_rr_buf.append(raw_rr)
                                if len(median5_rr_buf) > 5:
                                    median5_rr_buf.pop(0)

                                # PURE INTEGER MEDIAN (Zero float, zero np.median)
                                med_rr = integer_median(median5_rr_buf)
                                lut_addr = min(max(med_rr - RR_MIN, 0), len(FHR_FROZEN_INTEGER_LUT) - 1)
                                if med_rr < RR_MIN or med_rr > RR_MAX:
                                    acc_tracker.fhr_lut_overflow += 1
                                fhr_current = FHR_FROZEN_INTEGER_LUT[lut_addr]

                            else:
                                # Isolated Dropout / Bradycardia (> 1.2 s)
                                current_flag_2bit = FLAG_HELD_FHR
                                raw_peaks_list.append(best_idx)
                                comp_peaks_list.append(max(0, best_idx - latency))
                                rr_list.append(raw_rr)
                                # Hold previous valid FHR; do not corrupt median buffer
                        else:
                            # First detected beat
                            current_flag_2bit = FLAG_REAL_DETECTED
                            raw_peaks_list.append(best_idx)
                            comp_peaks_list.append(max(0, best_idx - latency))
                            rr_list.append(0)

                        last_cand_m = m
                        peak_level += (v - peak_level) >> 3  # EMA 1/8
                else:
                    noise_level += (v - noise_level) >> 3

        fhr_stream[t] = fhr_current
        # Telemetry Status Byte (Byte 6): bits 1:0 = class, bit 2 = conf, bit 3 = sat, bits 7:4 = 0
        has_sat = int(acc_tracker.total_saturations() > 0)
        flags_arr[t] = (current_flag_2bit & 0x03) | ((1 if is_confident_flag else 0) << 2) | (has_sat << 3)

    # Accumulate biquad internal stats
    for s in lp_biquads:
        acc_tracker.lp_biquad_state_overflow += s.state_overflow_count
        acc_tracker.lp_biquad_out_sat += s.out_sat_count
    for s in bp_biquads:
        acc_tracker.bp_biquad_state_overflow += s.state_overflow_count
        acc_tracker.bp_biquad_out_sat += s.out_sat_count

    max_ranges = {
        "max_proj_acc_bits": int(max_proj_acc).bit_length() + 1,
        "max_hp_acc_bits": int(max_hp_acc).bit_length() + 1,
        "max_lp_biquad_state_bits": max(s.max_s1 for s in lp_biquads).bit_length() + 1,
        "max_bp_biquad_state_bits": max(s.max_s1 for s in bp_biquads).bit_length() + 1,
        "max_mwi_acc_bits": int(max_mwi_acc).bit_length(),
        "total_state_overflows": acc_tracker.total_overflows(),
        "total_saturations": acc_tracker.total_saturations()
    }

    return BitAccurateFinalResult(
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
        accounting=acc_tracker,
        max_ranges=max_ranges,
        n_fused_events=n_fused
    )

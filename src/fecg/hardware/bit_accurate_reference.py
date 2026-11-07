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
  3. Priority E: 13-sample group delay latency compensation (filter group delay at 20-30 Hz).
  5. Detector warm-up restart on 0xC4 calibration packets (DET_RESTART_DELAY after the weights).
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

# Group delay compensation.  The HP1+LP40+Config-C chain has a group delay of
# 12.0 samples at 20 Hz, 11.2 at 25 Hz and 12.9 at 30 Hz (where the band-limited
# fetal QRS energy lies) but 17.9 at 15 Hz.  The old value 18 was evaluated at
# 15 Hz and left detections ~4.3 samples early on all 1,248 FECGSYNDB records.
LATENCY_COMPENSATION_SAMPLES = 13

# Detector warm-up restart: a 0xC4 calibration packet (weights + restart) re-runs
# the 512-sample warm-up DET_RESTART_DELAY samples after the new weights arrive
# (64-sample crossfade + filter settling).  Without it the detector keeps the
# peak/noise levels learned on the power-up (unity) weights and can stay locked
# out after the real calibration arrives.
DET_RESTART_DELAY = 128

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
    peaks: np.ndarray            # latency-compensated sample timestamps (fused)
    raw_peaks: np.ndarray        # Uncompensated detector timestamps (fused)
    fhr_hold: np.ndarray         # Causal Median-5 FHR stream in 0.1 bpm units
    flags: np.ndarray            # 8-bit Telemetry Status Bytes
    rr: np.ndarray               # Validated RR intervals
    accounting: StageOverflowAccounting
    max_ranges: Dict[str, int]
    n_fused_events: int
    telemetry_peaks: Optional[np.ndarray] = None  # compensated timestamps as transmitted in 0xAA
                                                  # (first accepted value; not rewritten by RR<50 fusion)

class BitAccuratePipelineRunner:
    """
    Stateful Pre-RTL Bit-Accurate Execution Reference Model for Spartan-7.
    
    Preserves internal filter states (HP1, LP40, Bandpass biquads), slew engine
    registers, MWI ring buffer, and adaptive threshold detector across sequential
    recordings or streaming blocks to maintain 100% bit-exact parity with physical
    FPGA hardware runtime semantics.
    """
    def __init__(
        self,
        w_initial: Optional[Sequence[int]] = None,
        mwi_len: int = MWI_WINDOW_LEN,
        refractory: int = REFRACTORY_SAMPLES,
        warmup: int = 512,
        loc_window: int = 26,
        latency: int = LATENCY_COMPENSATION_SAMPLES
    ):
        self.mwi_len = mwi_len
        self.refractory = refractory
        self.warmup = warmup
        self.loc_window = loc_window
        self.latency = latency
        self.reset(w_initial=w_initial)

    def reset(self, w_initial: Optional[Sequence[int]] = None) -> None:
        """Resets all pipeline registers to initial state (equivalent to FPGA hardware reset)."""
        if w_initial is not None:
            self.w_curr = [int(v) for v in w_initial]
            self.w_old = list(self.w_curr)
            self.w_target = list(self.w_curr)
            self.crossfade_step = WEIGHT_CROSSFADE_STEPS
        else:
            self.w_curr = [32768, 0, 0, 0]  # Default hardware unity bypass
            self.w_old = list(self.w_curr)
            self.w_target = list(self.w_curr)
            self.crossfade_step = WEIGHT_CROSSFADE_STEPS

        self.lp_biquads = [BiquadDF2TIntFinal(c, out_bits=DATA_BITS) for c in LP40_COEFFS_Q15]
        self.bp_biquads = [BiquadDF2TIntFinal(c, out_bits=DATA_BITS) for c in DET_BP_CONFIG_C_COEFFS_Q15]
        self.acc_tracker = StageOverflowAccounting()

        self.k_hp = 6  # HP1 shift (fc ~ 0.62 Hz)
        self.hp_acc = 0

        self.mwi_ring = [0] * self.mwi_len
        self.mwi_sum = 0
        self.abs_hist: List[int] = []

        self.peak_level = 0
        self.noise_level = 0
        self.warm_max = 0
        self.warm_sum = 0
        self.warm_cnt = 0              # samples seen in the current warm-up
        self.warm_done_t = -1          # global t of the last warm-up sample
        self.restart_countdown = 0     # >0: warm-up restart pending
        self.detector_enabled = False
        self.last_cand_m = -(10 ** 9)

        self.raw_peaks_list: List[int] = []
        self.comp_peaks_list: List[int] = []
        self.rr_list: List[int] = []

        self.median5_rr_buf: List[int] = []
        self.fhr_current = 1400  # 140.0 bpm
        self.current_flag_2bit = FLAG_INVALID_WARMUP
        self.is_confident_flag = True
        self.n_fused = 0

        self.max_proj_acc = 0
        self.max_hp_acc = 0
        self.max_mwi_acc = 0

        self.t_global = 0
        self.prev_mwi = 0
        self.prev_prev_mwi = 0

    def process_block(
        self,
        x_q: np.ndarray,
        new_weights: Optional[Sequence[int]] = None,
        target_weights: Optional[Sequence[Tuple]] = None,
        restart_detector: bool = False
    ) -> BitAccurateFinalResult:
        """
        Processes a block of signed 16-bit Q12 samples through the pipeline.
        Maintains all filter accumulators, biquad delays, and detector thresholds.
        """
        x_q = np.asarray(x_q, dtype=np.int64)
        n, n_ch = x_q.shape

        update_dict: Dict[int, List[int]] = {}
        restart_set = set()
        if new_weights is not None:
            update_dict[0] = [int(v) for v in new_weights]
            if restart_detector:
                restart_set.add(0)
        if target_weights is not None:
            for entry in target_weights:
                t_up, w_up = entry[0], entry[1]
                update_dict[int(t_up)] = [int(v) for v in w_up]
                if len(entry) > 2 and entry[2]:
                    restart_set.add(int(t_up))

        proj_arr = np.zeros(n, dtype=np.int64)
        hp_arr = np.zeros(n, dtype=np.int64)
        fecg_arr = np.zeros(n, dtype=np.int64)
        det_bp_arr = np.zeros(n, dtype=np.int64)
        xint_arr = np.zeros(n, dtype=np.int64)
        fhr_stream = np.zeros(n, dtype=np.int64)
        flags_arr = np.zeros(n, dtype=np.uint8)

        block_raw_peaks: List[int] = []
        block_comp_peaks: List[int] = []
        block_rr: List[int] = []
        block_telem: List[int] = []
        t_block_start = self.t_global

        for t_rel in range(n):
            t = self.t_global

            # ── 0. Dynamic Weight Slew Engine (64-Sample Crossfade) ───────────
            if t_rel in restart_set:
                self.restart_countdown = DET_RESTART_DELAY
            if self.restart_countdown > 0:
                self.restart_countdown -= 1
                if self.restart_countdown == 0:
                    # 0xC4: restart the detector warm-up (levels relearned on new weights)
                    self.warm_cnt = 0
                    self.warm_max = 0
                    self.warm_sum = 0
                    self.detector_enabled = False

            if t_rel in update_dict:
                self.w_old = list(self.w_curr)
                self.w_target = list(update_dict[t_rel])
                self.crossfade_step = 1
            elif self.crossfade_step < WEIGHT_CROSSFADE_STEPS:
                self.crossfade_step += 1
                for c in range(n_ch):
                    delta = self.w_target[c] - self.w_old[c]
                    step = rshift_round_nearest_even(self.crossfade_step * delta, 6)
                    self.w_curr[c] = sat(self.w_old[c] + step, WEIGHT_BITS)
            elif self.crossfade_step == WEIGHT_CROSSFADE_STEPS:
                self.w_curr = list(self.w_target)

            # ── 1. Spatial Beamformer (Enforced 32-bit Accumulator) ───────────
            raw_acc = 0
            for c in range(n_ch):
                prod = self.w_curr[c] * int(x_q[t_rel, c])
                if prod >= (1 << 31) or prod < -(1 << 31):
                    self.acc_tracker.proj_mult_overflow += 1
                raw_acc += prod

            acc_clamped = sat(raw_acc, PROJ_ACC_BITS)
            if acc_clamped != raw_acc:
                self.acc_tracker.proj_acc_overflow += 1

            self.max_proj_acc = max(self.max_proj_acc, abs(acc_clamped))
            proj_rounded = rshift_round_nearest_even(acc_clamped, PROJ_SHIFT)
            proj_val = sat(proj_rounded, DATA_BITS)
            if proj_val != proj_rounded:
                self.acc_tracker.proj_sat_count += 1
            proj_arr[t_rel] = proj_val

            # ── 2. HP1 Baseline Remover (Signed 32-bit Accumulator) ──────────
            base = self.hp_acc >> self.k_hp
            hp_sub = proj_val - base
            hp_val = sat(hp_sub, DATA_BITS)
            if hp_val != hp_sub:
                self.acc_tracker.hp_sat_count += 1

            hp_acc_next = self.hp_acc + hp_sub
            hp_acc_clamped = sat(hp_acc_next, 32)
            if hp_acc_clamped != hp_acc_next:
                self.acc_tracker.hp_acc_overflow += 1
            self.hp_acc = hp_acc_clamped

            self.max_hp_acc = max(self.max_hp_acc, abs(self.hp_acc))
            hp_arr[t_rel] = hp_val

            # ── 3. LP40 Filter (2 Biquads, 48-bit State Saturation) ──────────
            fecg_val = hp_val
            for s in self.lp_biquads:
                fecg_val = s.step(fecg_val)
            fecg_arr[t_rel] = fecg_val

            # ── 4. Detector Bandpass Filter (4 Biquads, 48-bit States) ───────
            bp_val = fecg_val
            for s in self.bp_biquads:
                bp_val = s.step(bp_val)
            bp_rounded = rshift_round_nearest_even(bp_val, DET_SHIFT)
            bp16 = sat(bp_rounded, DET_BITS)
            if bp16 != bp_rounded:
                self.acc_tracker.det_shift_sat_count += 1
            det_bp_arr[t_rel] = bp16
            self.abs_hist.append(abs(bp16))

            # ── 5. Squaring & Moving Window Integration (36-bit Constrained) ─
            sq = bp16 * bp16
            if sq >= (1 << 32):
                self.acc_tracker.squaring_overflow += 1

            mwi_sub = self.mwi_sum + sq - self.mwi_ring[self.t_global % self.mwi_len]
            mwi_clamped = sat_u(mwi_sub, MWI_ACC_BITS)
            if mwi_clamped != mwi_sub:
                self.acc_tracker.mwi_acc_overflow += 1
            self.mwi_sum = mwi_clamped

            self.mwi_ring[self.t_global % self.mwi_len] = sq
            self.max_mwi_acc = max(self.max_mwi_acc, self.mwi_sum)
            xint_arr[t_rel] = self.mwi_sum

            # ── 6. Warm-up Initialization (restartable via 0xC4) ─────────────
            if self.warm_cnt < self.warmup:
                self.current_flag_2bit = FLAG_INVALID_WARMUP
                flags_arr[t_rel] = (self.current_flag_2bit & 0x03) | ((1 if self.is_confident_flag else 0) << 2)
                fhr_stream[t_rel] = 0
                self.warm_max = max(self.warm_max, self.mwi_sum)
                self.warm_sum += self.mwi_sum
                self.warm_cnt += 1
                if self.warm_cnt == self.warmup:
                    self.peak_level = self.warm_max
                    self.noise_level = self.warm_sum >> 9  # Mean over 512 samples
                    self.detector_enabled = (self.peak_level > self.noise_level)
                    self.warm_done_t = t
                self._advance_sample(xint_arr, t_rel)
                continue

            # ── 7. Adaptive Threshold & Local Peak Search at m = t - 1 ───────
            if self.detector_enabled and t >= 2:
                m = t - 1
                v = int(xint_arr[t_rel - 1] if t_rel >= 1 else self.prev_mwi)
                v_prev = int(xint_arr[t_rel - 2] if t_rel >= 2 else (self.prev_mwi if t_rel == 1 else self.prev_prev_mwi))
                if v_prev < v and v >= self.mwi_sum and m >= self.warm_done_t:
                    thr = (self.peak_level >> 2) + self.noise_level - (self.noise_level >> 2)
                    if thr >= (1 << 36):
                        self.acc_tracker.threshold_overflow += 1

                    if v > thr:
                        if (m - self.last_cand_m) >= self.refractory:
                            lo = max(0, t - (self.loc_window - 1))
                            best_idx = lo
                            best_val = self.abs_hist[lo]
                            for i in range(lo + 1, t + 1):
                                if self.abs_hist[i] > best_val:
                                    best_val = self.abs_hist[i]
                                    best_idx = i

                            # ── 8. Corrected Interval Fusion & Integer Median5
                            comp_idx = max(0, best_idx - self.latency)
                            rel_comp_idx = comp_idx - t_block_start
                            rel_raw_idx = best_idx - t_block_start

                            if self.raw_peaks_list:
                                raw_rr = best_idx - self.raw_peaks_list[-1]
                                if raw_rr < RR_MIN:
                                    self.n_fused += 1
                                    self.current_flag_2bit = FLAG_FUSED_BEAT
                                    if best_val > self.abs_hist[self.raw_peaks_list[-1]]:
                                        self.raw_peaks_list[-1] = best_idx
                                        self.comp_peaks_list[-1] = comp_idx
                                        if block_comp_peaks:
                                            block_comp_peaks[-1] = rel_comp_idx
                                            block_raw_peaks[-1] = rel_raw_idx
                                elif raw_rr <= RR_MAX:
                                    self.current_flag_2bit = FLAG_REAL_DETECTED
                                    self.raw_peaks_list.append(best_idx)
                                    self.comp_peaks_list.append(comp_idx)
                                    self.rr_list.append(raw_rr)
                                    block_comp_peaks.append(rel_comp_idx)
                                    block_telem.append(rel_comp_idx)
                                    block_raw_peaks.append(rel_raw_idx)
                                    block_rr.append(raw_rr)

                                    self.median5_rr_buf.append(raw_rr)
                                    if len(self.median5_rr_buf) > 5:
                                        self.median5_rr_buf.pop(0)

                                    med_rr = integer_median(self.median5_rr_buf)
                                    lut_addr = min(max(med_rr - RR_MIN, 0), len(FHR_FROZEN_INTEGER_LUT) - 1)
                                    if med_rr < RR_MIN or med_rr > RR_MAX:
                                        self.acc_tracker.fhr_lut_overflow += 1
                                    self.fhr_current = FHR_FROZEN_INTEGER_LUT[lut_addr]
                                else:
                                    self.current_flag_2bit = FLAG_HELD_FHR
                                    self.raw_peaks_list.append(best_idx)
                                    self.comp_peaks_list.append(comp_idx)
                                    self.rr_list.append(raw_rr)
                                    block_comp_peaks.append(rel_comp_idx)
                                    block_telem.append(rel_comp_idx)
                                    block_raw_peaks.append(rel_raw_idx)
                                    block_rr.append(raw_rr)
                            else:
                                self.current_flag_2bit = FLAG_REAL_DETECTED
                                self.raw_peaks_list.append(best_idx)
                                self.comp_peaks_list.append(comp_idx)
                                self.rr_list.append(0)
                                block_comp_peaks.append(rel_comp_idx)
                                block_telem.append(rel_comp_idx)
                                block_raw_peaks.append(rel_raw_idx)
                                block_rr.append(0)

                            self.last_cand_m = m
                            self.peak_level += (v - self.peak_level) >> 3
                    else:
                        self.noise_level += (v - self.noise_level) >> 3

            fhr_stream[t_rel] = self.fhr_current
            has_sat = int(self.acc_tracker.total_saturations() > 0)
            flags_arr[t_rel] = (self.current_flag_2bit & 0x03) | ((1 if self.is_confident_flag else 0) << 2) | (has_sat << 3)
            self._advance_sample(xint_arr, t_rel)

        total_lp_state_ovf = sum(s.state_overflow_count for s in self.lp_biquads) + self.acc_tracker.lp_biquad_state_overflow
        total_lp_out_sat = sum(s.out_sat_count for s in self.lp_biquads) + self.acc_tracker.lp_biquad_out_sat
        total_bp_state_ovf = sum(s.state_overflow_count for s in self.bp_biquads) + self.acc_tracker.bp_biquad_state_overflow
        total_bp_out_sat = sum(s.out_sat_count for s in self.bp_biquads) + self.acc_tracker.bp_biquad_out_sat

        max_ranges = {
            "max_proj_acc_bits": int(self.max_proj_acc).bit_length() + 1,
            "max_hp_acc_bits": int(self.max_hp_acc).bit_length() + 1,
            "max_lp_biquad_state_bits": max(s.max_s1 for s in self.lp_biquads).bit_length() + 1,
            "max_bp_biquad_state_bits": max(s.max_s1 for s in self.bp_biquads).bit_length() + 1,
            "max_mwi_acc_bits": int(self.max_mwi_acc).bit_length(),
            "total_state_overflows": self.acc_tracker.total_overflows(),
            "total_saturations": self.acc_tracker.total_saturations()
        }

        return BitAccurateFinalResult(
            proj=proj_arr,
            hp=hp_arr,
            fecg=fecg_arr,
            det_bp=det_bp_arr,
            x_int=xint_arr,
            peaks=np.array(block_comp_peaks, dtype=np.int64),
            raw_peaks=np.array(block_raw_peaks, dtype=np.int64),
            fhr_hold=fhr_stream,
            flags=flags_arr,
            rr=np.array(block_rr, dtype=np.int64),
            accounting=self.acc_tracker,
            max_ranges=max_ranges,
            n_fused_events=self.n_fused,
            telemetry_peaks=np.array(block_telem, dtype=np.int64)
        )

    def _advance_sample(self, xint_arr: np.ndarray, t_rel: int) -> None:
        if t_rel >= 1:
            self.prev_prev_mwi = int(xint_arr[t_rel - 1])
        self.prev_mwi = self.mwi_sum
        self.t_global += 1

    def flush_zeros(self, n_zeros: int = 512, new_weights: Optional[Sequence[int]] = None) -> None:
        """Streams n_zeros samples of [0, 0, 0, 0] to allow filter state decay."""
        zeros = np.zeros((n_zeros, 4), dtype=np.int64)
        self.process_block(zeros, new_weights=new_weights)




def run_bit_accurate_pipeline_final(
    x_q: np.ndarray,                 # (N, 4) Signed 16-bit samples (Q12)
    w_q: np.ndarray,                 # (4,) Signed 16-bit weights (Q1.15)
    mwi_len: int = MWI_WINDOW_LEN,   # 30 samples (120 ms)
    refractory: int = REFRACTORY_SAMPLES, # 50 samples (200 ms)
    warmup: int = 512,               # 512 samples (~2.05 s)
    loc_window: int = 26,            # 26 samples (104 ms)
    latency: int = LATENCY_COMPENSATION_SAMPLES, # 13 samples
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
    runner = BitAccuratePipelineRunner(
        w_initial=w_q,
        mwi_len=mwi_len,
        refractory=refractory,
        warmup=warmup,
        loc_window=loc_window,
        latency=latency
    )
    return runner.process_block(x_q, target_weights=target_weights)

"""
src/fpga_int_model.py
──────────────────────────────────────────────────────────────────────────────
Integer-only golden model of the FPGA pipeline (FPGA_SPEC.md v0.2).

The sample loop uses ONLY Python integers (no floats).  The RTL must match the
stage dumps written by dump_stages() bit for bit.

Formats
-------
  input sample        s16  Q1.15   full scale +-5 mV  (0.1526 uV / LSB)
  weights             s16  Q1.15
  projection          s24  Q1.23   (same 5 mV full scale, 8 extra fractional bits)
  biquad coefficients s18  Q3.15   (Q3.15 so that a numerator coefficient of 2.0 is exact)
  biquad states       full-precision accumulators (< s48)
  detector input      s16  (= s24 >> 8, saturated)
  square              u32
  moving-window sum   u36  (20 x u30), NOT divided by 20
  threshold levels    same width as the sum
  thr = peak/4 + noise - noise/4,  EMA update: level += (v - level) >> 3

Usage (golden vectors from a real record; needs wfdb and the dataset):
  python src/fpga_int_model.py --record data/FECGSD/DESTINATION/sub01/snr12dB/sub01_snr12dB_l1_c0 \
      --cal-seconds 60 --rule pc2 --n-samples 20000 --out-dir code/results/fpga_golden/sub01_snr12_c0
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from src.causal_pipeline import (
    CausalConfig, DEFAULT_CONFIG, RULES_ALL, CalibrationBank, det_sos, lp_sos, run_causal,
)

# ──────────────────────────────────────────────────────────────────────────────
# Fixed-point constants
# ──────────────────────────────────────────────────────────────────────────────

FULL_SCALE_MV = 5.0
IN_BITS, IN_FRAC = 16, 15
DATA_BITS, DATA_FRAC = 24, 23
COEF_BITS, COEF_FRAC = 18, 15
PROJ_SHIFT = 2 * IN_FRAC - DATA_FRAC          # 30 - 23 = 7
DET_SHIFT = DATA_BITS - IN_BITS                # 8 (s24 -> s16)

RR_MIN, RR_MAX = 60, 300                       # 250 .. 50 bpm at 250 Hz
FHR_NUMERATOR = 150000                         # bpm x10 = 60 * 250 * 10 / RR


def sat(v: int, bits: int) -> int:
    hi = (1 << (bits - 1)) - 1
    lo = -(1 << (bits - 1))
    return hi if v > hi else lo if v < lo else v


def rshift_round(v: int, s: int) -> int:
    """Round-half-up arithmetic right shift (what a DSP48 + constant does)."""
    return (v + (1 << (s - 1))) >> s


def fhr_lut() -> List[int]:
    """ROM contents: index RR-60 -> round(150000 / RR), 241 entries, 12-bit words."""
    return [(2 * FHR_NUMERATOR + rr) // (2 * rr) for rr in range(RR_MIN, RR_MAX + 1)]


# ──────────────────────────────────────────────────────────────────────────────
# Quantisers
# ──────────────────────────────────────────────────────────────────────────────

def quantize_input(x_mv: np.ndarray) -> np.ndarray:
    q = np.round(np.asarray(x_mv, dtype=np.float64) / FULL_SCALE_MV * (1 << IN_FRAC))
    return np.clip(q, -(1 << (IN_BITS - 1)), (1 << (IN_BITS - 1)) - 1).astype(np.int64)


def dequantize_input(q: np.ndarray) -> np.ndarray:
    return np.asarray(q, dtype=np.float64) / (1 << IN_FRAC) * FULL_SCALE_MV


def quantize_weights(w: np.ndarray) -> np.ndarray:
    q = np.round(np.asarray(w, dtype=np.float64) * (1 << IN_FRAC))
    return np.clip(q, -(1 << (IN_BITS - 1)), (1 << (IN_BITS - 1)) - 1).astype(np.int64)


def quantize_sos(sos: np.ndarray) -> List[tuple]:
    """scipy SOS -> list of (b0, b1, b2, a1, a2) ints in Q3.15 (a0 is 1)."""
    out = []
    lo, hi = -(1 << (COEF_BITS - 1)), (1 << (COEF_BITS - 1)) - 1
    for row in sos:
        assert abs(row[3] - 1.0) < 1e-12, "scipy SOS rows have a0 == 1"
        q = [int(np.clip(round(float(c) * (1 << COEF_FRAC)), lo, hi))
             for c in (row[0], row[1], row[2], row[4], row[5])]
        out.append(tuple(q))
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Building blocks
# ──────────────────────────────────────────────────────────────────────────────

class BiquadInt:
    """Transposed direct form II, integer, saturating s24 output."""

    def __init__(self, coefs: tuple):
        self.b0, self.b1, self.b2, self.a1, self.a2 = coefs
        self.s1 = 0
        self.s2 = 0
        self.max_state = 0

    def step(self, x: int) -> int:
        y = sat(rshift_round(self.b0 * x + self.s1, COEF_FRAC), DATA_BITS)
        self.s1 = self.b1 * x - self.a1 * y + self.s2
        self.s2 = self.b2 * x - self.a2 * y
        m = max(abs(self.s1), abs(self.s2))
        if m > self.max_state:
            self.max_state = m
        return y


@dataclass
class IntResult:
    proj: np.ndarray            # s24
    hp: np.ndarray              # s24
    fecg: np.ndarray            # s24  (LP40 output, = fecg_out before the >>8)
    det_bp: np.ndarray          # s16  (detector band-pass output, saturated)
    x_int: np.ndarray           # u36  (moving-window sum)
    beat_flag: np.ndarray       # 1 on the sample where a beat is declared
    warmup_flag: np.ndarray     # 1 during the warm-up
    fhr_hold: np.ndarray        # bpm x10, held between beats (0 = none/invalid)
    fhr_valid: np.ndarray       # 1 if the last RR was inside 60..300
    raw_peaks: np.ndarray       # R index in the detector timeline
    peaks: np.ndarray           # raw_peaks - latency, clipped at 0
    decl_idx: np.ndarray
    rr: np.ndarray              # per beat (0 for the first)
    fhr_beat: np.ndarray        # per beat bpm x10 (0 if invalid / first)
    latency: int
    stats: Dict[str, int] = field(default_factory=dict)

    def fecg_out_s16(self) -> np.ndarray:
        out = [sat(rshift_round(int(v), DET_SHIFT), IN_BITS) for v in self.fecg]
        return np.array(out, dtype=np.int64)


# ──────────────────────────────────────────────────────────────────────────────
# Full pipeline
# ──────────────────────────────────────────────────────────────────────────────

def run_int_pipeline(
    x_q: np.ndarray,
    w_q: np.ndarray,
    cfg: CausalConfig = DEFAULT_CONFIG,
) -> IntResult:
    """
    x_q : (n, 4) int array of s16 samples;  w_q : (4,) int array of s16 weights.
    """
    x_q = np.asarray(x_q, dtype=np.int64)
    n, n_ch = x_q.shape
    w = [int(v) for v in w_q]
    assert len(w) == n_ch

    lp = [BiquadInt(c) for c in quantize_sos(lp_sos(cfg))]
    bp = [BiquadInt(c) for c in quantize_sos(det_sos(cfg))]
    latency = cfg.latency()

    k = cfg.hp_shift_k
    hp_acc = 0
    warm = cfg.warmup
    W = cfg.mwi_len
    lut = fhr_lut()

    proj_a = np.zeros(n, dtype=np.int64)
    hp_a = np.zeros(n, dtype=np.int64)
    fecg_a = np.zeros(n, dtype=np.int64)
    bp16_a = np.zeros(n, dtype=np.int64)
    xint_a = np.zeros(n, dtype=np.int64)
    flag_a = np.zeros(n, dtype=np.int64)
    warm_a = np.zeros(n, dtype=np.int64)
    fhr_hold_a = np.zeros(n, dtype=np.int64)
    fhr_valid_a = np.zeros(n, dtype=np.int64)

    sq_ring = [0] * W
    run_sum = 0
    abs_hist: List[int] = []

    peak = noise = 0
    warm_max = 0
    warm_sum = 0
    detector_on = False
    last_m = -(10 ** 9)

    raw_peaks: List[int] = []
    decl: List[int] = []
    rr_list: List[int] = []
    fhr_beat: List[int] = []
    fhr_now = 0
    fhr_ok = 0
    max_hp_acc = 0
    max_proj_acc = 0

    row = x_q.tolist()
    for t in range(n):
        # 1. projection  (4 products of s16 x s16, accumulate, round >> 7, saturate s24)
        acc = 0
        for c in range(n_ch):
            acc += w[c] * row[t][c]
        max_proj_acc = max(max_proj_acc, abs(acc))
        x = sat(rshift_round(acc, PROJ_SHIFT), DATA_BITS)
        proj_a[t] = x

        # 2. HP1 baseline remover (shift only)
        base = hp_acc >> k
        y = sat(x - base, DATA_BITS)
        hp_acc = hp_acc + x - base
        max_hp_acc = max(max_hp_acc, abs(hp_acc))
        hp_a[t] = y

        # 3. LP40 (two biquads)
        for s in lp:
            y = s.step(y)
        fecg_a[t] = y

        # 4. detector band-pass (four biquads), then s24 -> s16
        z = y
        for s in bp:
            z = s.step(z)
        z16 = sat(rshift_round(z, DET_SHIFT), IN_BITS)
        bp16_a[t] = z16
        abs_hist.append(abs(z16))

        # 5. square and trailing 20-sample sum (add newest, drop the one leaving)
        sq = z16 * z16
        run_sum += sq - sq_ring[t % W]
        sq_ring[t % W] = sq
        xint_a[t] = run_sum

        # 6. warm-up accumulation / finalisation
        if t < warm:
            warm_a[t] = 1
            warm_max = max(warm_max, run_sum)
            warm_sum += run_sum
            if t == warm - 1:
                peak = warm_max
                noise = warm_sum >> (warm.bit_length() - 1)   # warm is a power of two
                detector_on = peak > noise
            fhr_hold_a[t] = 0
            continue

        # 7. candidate test at m = t-1:  x_int[m-1] < x_int[m] >= x_int[t]
        if detector_on and t >= 2:
            m = t - 1
            v = int(xint_a[m])
            if int(xint_a[m - 1]) < v >= run_sum and m >= warm - 1:
                thr = (peak >> 2) + noise - (noise >> 2)
                if v > thr:
                    if m - last_m >= cfg.refractory:
                        lo = max(0, t - (cfg.loc_window - 1))
                        best = lo
                        best_v = abs_hist[lo]
                        for i in range(lo + 1, t + 1):
                            if abs_hist[i] > best_v:
                                best_v = abs_hist[i]
                                best = i
                        # RR / FHR from consecutive raw peaks
                        if raw_peaks:
                            rr = best - raw_peaks[-1]
                            if RR_MIN <= rr <= RR_MAX:
                                fhr_now = lut[rr - RR_MIN]
                                fhr_ok = 1
                            else:
                                fhr_now = 0
                                fhr_ok = 0
                        else:
                            rr = 0
                        rr_list.append(rr)
                        fhr_beat.append(fhr_now if raw_peaks else 0)
                        raw_peaks.append(best)
                        decl.append(t)
                        flag_a[t] = 1
                        last_m = m
                        peak += (v - peak) >> cfg.level_shift
                else:
                    noise += (v - noise) >> cfg.level_shift

        fhr_hold_a[t] = fhr_now
        fhr_valid_a[t] = fhr_ok

    raw = np.array(raw_peaks, dtype=np.int64)
    stats = {
        "max_proj_acc_bits": int(max_proj_acc).bit_length() + 1,
        "max_hp_acc_bits": int(max_hp_acc).bit_length() + 1,
        "max_biquad_state_bits": max(s.max_state for s in lp + bp).bit_length() + 1,
        "max_xint_bits": int(np.max(xint_a)).bit_length() if n else 0,
    }
    return IntResult(
        proj=proj_a, hp=hp_a, fecg=fecg_a, det_bp=bp16_a, x_int=xint_a,
        beat_flag=flag_a, warmup_flag=warm_a, fhr_hold=fhr_hold_a, fhr_valid=fhr_valid_a,
        raw_peaks=raw, peaks=np.maximum(raw - latency, 0), decl_idx=np.array(decl, dtype=np.int64),
        rr=np.array(rr_list, dtype=np.int64), fhr_beat=np.array(fhr_beat, dtype=np.int64),
        latency=latency, stats=stats,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Comparison with the float causal reference
# ──────────────────────────────────────────────────────────────────────────────

def compare_with_float(
    x_mv: np.ndarray,
    w_float: np.ndarray,
    cfg: CausalConfig = DEFAULT_CONFIG,
) -> Dict[str, float]:
    """
    Run both models on the SAME quantised input and weights so that only the
    arithmetic (filters, shifts, integer detector) differs.
    """
    from src.evaluation import match_beats

    x_q = quantize_input(x_mv)
    w_q = quantize_weights(w_float)
    res = run_int_pipeline(x_q, w_q, cfg)

    fecg_f, det_f = run_causal(dequantize_input(x_q), w_q / float(1 << IN_FRAC), cfg)
    fecg_i = res.fecg.astype(np.float64) / (1 << DATA_FRAC) * FULL_SCALE_MV
    err = fecg_f - fecg_i
    sqnr = 10.0 * np.log10(np.sum(fecg_f ** 2) / max(np.sum(err ** 2), 1e-30))

    tol_ms = 2 * 1000.0 / cfg.fs                     # +-2 samples
    tp, fp, fn = match_beats(det_f.peaks, res.peaks, fs=cfg.fs, tolerance_ms=tol_ms)
    return {
        "sqnr_db": float(sqnr),
        "n_float_beats": int(len(det_f.peaks)),
        "n_int_beats": int(len(res.peaks)),
        "tp": tp, "fp": fp, "fn": fn,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Hex dumps for $readmemh
# ──────────────────────────────────────────────────────────────────────────────

def to_hex(v: int, bits: int) -> str:
    digits = (bits + 3) // 4
    return f"{int(v) & ((1 << bits) - 1):0{digits}x}"


def write_hex(path: Path, values: Sequence[int], bits: int) -> None:
    path.write_text("\n".join(to_hex(v, bits) for v in values) + "\n")


def read_hex(path: Path, bits: int, signed: bool = True) -> np.ndarray:
    out = []
    for line in path.read_text().split():
        v = int(line, 16)
        if signed and v >= (1 << (bits - 1)):
            v -= 1 << bits
        out.append(v)
    return np.array(out, dtype=np.int64)


def dump_stages(out_dir: Path, x_q: np.ndarray, w_q: np.ndarray, res: IntResult) -> List[str]:
    """Write stimulus, weights and every stage as one-word-per-line hex files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []

    def put(name: str, vals, bits: int):
        write_hex(out_dir / name, vals, bits)
        files.append(name)

    for c in range(x_q.shape[1]):
        put(f"stimulus_ch{c}_s16.hex", x_q[:, c], 16)
    put("weights_s16.hex", w_q, 16)
    put("proj_s24.hex", res.proj, 24)
    put("hp_s24.hex", res.hp, 24)
    put("fecg_s24.hex", res.fecg, 24)
    put("fecg_out_s16.hex", res.fecg_out_s16(), 16)
    put("det_bp_s16.hex", res.det_bp, 16)
    put("x_int_u40.hex", res.x_int, 40)
    put("beat_flag.hex", res.beat_flag, 4)
    put("fhr_x10_hold_u16.hex", res.fhr_hold, 16)
    put("fhr_lut_u16.hex", fhr_lut(), 16)
    (out_dir / "peaks.txt").write_text("\n".join(str(int(p)) for p in res.peaks) + "\n")
    (out_dir / "raw_peaks.txt").write_text("\n".join(str(int(p)) for p in res.raw_peaks) + "\n")
    files += ["peaks.txt", "raw_peaks.txt"]
    return files


# ──────────────────────────────────────────────────────────────────────────────
# CLI: golden vectors from a real FECGSYNDB record
# ──────────────────────────────────────────────────────────────────────────────

def _load_mixture(record_base: str, channels: Sequence[int]):
    import wfdb  # imported lazily so the module works without wfdb installed
    fecg = wfdb.rdrecord(record_base + "_fecg1").p_signal
    mecg = wfdb.rdrecord(record_base + "_mecg").p_signal
    n1 = wfdb.rdrecord(record_base + "_noise1").p_signal
    n2 = wfdb.rdrecord(record_base + "_noise2").p_signal
    ref = np.sort(wfdb.rdann(record_base + "_fecg1", "qrs").sample)
    return (mecg + fecg + n1 + n2)[:, list(channels)], ref


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--record", required=True, help="record prefix, e.g. .../sub01_snr12dB_l1_c0")
    ap.add_argument("--channels", nargs="+", type=int, default=[27, 26, 28, 25])
    ap.add_argument("--cal-seconds", type=float, default=60.0, help="0 = whole record")
    ap.add_argument("--rule", default="pc2", choices=RULES_ALL)
    ap.add_argument("--n-samples", type=int, default=20000)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    X, ref = _load_mixture(args.record, args.channels)
    bank = CalibrationBank(X, DEFAULT_CONFIG, args.cal_seconds)
    j, scores = bank.select(args.rule, ref_qrs=ref)
    w = bank.weights(j)
    if args.rule == "oracle":
        print("WARNING: oracle rule uses ground truth; golden vectors are NOT deployable.")

    x_q = quantize_input(X[: args.n_samples])
    w_q = quantize_weights(w)
    res = run_int_pipeline(x_q, w_q)
    cmp_ = compare_with_float(X[: args.n_samples], w)

    out = Path(args.out_dir)
    files = dump_stages(out, x_q, w_q, res)
    summary = {
        "record": args.record, "channels": list(args.channels), "rule": args.rule,
        "cal_seconds": args.cal_seconds, "component_index": int(j),
        "scores": {str(k): float(v) for k, v in scores.items()},
        "weights_float": [float(v) for v in w], "weights_s16": [int(v) for v in w_q],
        "latency_samples": res.latency, "n_samples": int(x_q.shape[0]),
        "n_beats": int(len(res.peaks)), "int_vs_float": cmp_, "widths": res.stats, "files": files,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("component_index", "n_beats", "int_vs_float", "widths")}, indent=2))
    print(f"golden files written to {out}")


if __name__ == "__main__":
    main()

from __future__ import annotations
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / 'src'
for _p in [str(_SRC_DIR), str(_REPO_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
"""
src/run_causal_benchmark.py
──────────────────────────────────────────────────────────────────────────────
Benchmark of the CAUSAL, label-free FPGA pipeline (FPGA_SPEC.md v0.2) on
PhysioNet FECGSYNDB, sweeping

    component-selection rule  x  calibration window length

and (optionally) running the old zero-phase + oracle-selected Spatial PCA on the
same records for a side-by-side comparison.

Rules
-----
  pc2, pc3          fixed principal component (label-free)
  periodic_rr       label-free: most regular beat train in 100-200 bpm
  autocorr          label-free: strongest envelope autocorrelation at 100-200 bpm lags
  oracle            picks the component with the best F1 against ground truth.
                    UPPER BOUND ONLY -- cannot be built in hardware.
  legacy_zero_phase_oracle (--with-legacy)
                    the existing method: zero-phase filters + oracle selection.

Choosing the rule honestly
--------------------------
Pick the rule / window using the TRAIN partition (sub01-sub07) only, with the
validation subject (sub08) as a sanity check.  Report the held-out subjects
(sub09-sub10) once, for the chosen configuration.  The summary prints them in a
separate block for that reason.

Usage
-----
  python src/run_causal_benchmark.py --data-dir data/FECGSD/DESTINATION
  python src/run_causal_benchmark.py --subs sub01 --snrs snr12dB --cases c0 --max-cases 3   # smoke test
"""
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / 'src'
for p in [str(_SRC_DIR), str(_REPO_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)



import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

_CODE_DIR = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _CODE_DIR.parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from src.causal_pipeline import (
    DEFAULT_CONFIG, RULES_LABEL_FREE, CalibrationBank, CausalConfig,
)
from src.evaluation import compute_beat_metrics
from src.fhr import compare_fhr, compute_fhr

ALL_SUBS = [f"sub{i:02d}" for i in range(1, 11)]
ALL_SNRS = ["snr00dB", "snr03dB", "snr06dB", "snr09dB", "snr12dB"]
ALL_CASES = ["c0", "c1", "c2", "c3", "c4"]
SNR_DB = {"snr00dB": 0, "snr03dB": 3, "snr06dB": 6, "snr09dB": 9, "snr12dB": 12}
DEFAULT_CHANNELS = [27, 26, 28, 25]
DEFAULT_RULES = ["pc2", "pc3", "periodic_rr", "autocorr", "oracle"]
DEFAULT_CAL_SECONDS = [3, 10, 30, 60, 0]          # 0 = whole record

PARTITIONS = {
    "train": {f"sub{i:02d}" for i in range(1, 8)},
    "val": {"sub08"},
    "test": {"sub09", "sub10"},
}

FIELDS = [
    "sub_id", "snr_db", "case_id", "rule", "cal_s", "causal", "label_free", "sel_pc",
    "tp", "fp", "fn", "n_ref", "n_det", "sensitivity", "ppv", "f1", "fhr_mae_bpm",
    "median_offset", "runtime_s",
]


# ──────────────────────────────────────────────────────────────────────────────
# Per-record processing (pure function, no file I/O -> testable with synthetic data)
# ──────────────────────────────────────────────────────────────────────────────

def median_offset(ref: np.ndarray, det: np.ndarray, tol: int = 25) -> Optional[float]:
    """Median of (detected - nearest reference) over detections within +-tol samples."""
    ref = np.asarray(ref)
    if len(ref) == 0 or len(det) == 0:
        return None
    offs = []
    for p in det:
        d = int(p) - ref
        i = int(np.argmin(np.abs(d)))
        if abs(int(d[i])) <= tol:
            offs.append(int(d[i]))
    return float(np.median(offs)) if offs else None


def _row(ref_qrs, det, fs, **meta) -> dict:
    m = compute_beat_metrics(ref_qrs, det, fs=fs)
    fc = compare_fhr(compute_fhr(det, fs=fs), ref_qrs, fs=fs)
    off = median_offset(ref_qrs, det)
    row = dict(meta)
    row.update(
        tp=m.tp, fp=m.fp, fn=m.fn, n_ref=len(ref_qrs), n_det=len(det),
        sensitivity=round(m.sensitivity or 0.0, 4), ppv=round(m.ppv or 0.0, 4),
        f1=round(m.f1 or 0.0, 4),
        fhr_mae_bpm=None if fc.mean_abs_error_bpm != fc.mean_abs_error_bpm else round(fc.mean_abs_error_bpm, 2),
        median_offset=off,
    )
    return row


def legacy_zero_phase_oracle(X_raw: np.ndarray, ref_qrs: np.ndarray, fs: int) -> np.ndarray:
    """The existing method: zero-phase filtering, PCA on the whole record, oracle component."""
    from src.preprocessing import preprocess
    from src.qrs_detector import detect_fetal_qrs

    prep = np.column_stack([preprocess(X_raw[:, c], fs=fs) for c in range(X_raw.shape[1])])
    _, evecs = np.linalg.eigh(np.cov(prep, rowvar=False))
    comps = prep @ evecs[:, ::-1]
    best_f1, best = -1.0, np.array([], dtype=int)
    for j in range(min(4, comps.shape[1])):
        det, _ = detect_fetal_qrs(comps[:, j], fs=fs)
        f1 = compute_beat_metrics(ref_qrs, det, fs=fs).f1 or 0.0
        if f1 > best_f1:
            best_f1, best = f1, det
    return best


def process_record(
    X_raw: np.ndarray,
    ref_qrs: np.ndarray,
    meta: dict,
    cfg: CausalConfig = DEFAULT_CONFIG,
    rules: Sequence[str] = tuple(DEFAULT_RULES),
    cal_seconds: Sequence[float] = tuple(DEFAULT_CAL_SECONDS),
    with_legacy: bool = False,
) -> List[dict]:
    """Return one row per (rule, calibration window) for a single record."""
    rows: List[dict] = []
    Xf_full = None
    for cal in cal_seconds:
        t0 = time.time()
        bank = CalibrationBank(X_raw, cfg, cal, Xf_full=Xf_full)
        Xf_full = bank.Xf_full                      # causal filtering is shared by all windows
        for rule in rules:
            t1 = time.time()
            j, _ = bank.select(rule, ref_qrs=ref_qrs if rule == "oracle" else None)
            det = bank.det_full(j).peaks
            rows.append(_row(
                ref_qrs, det, cfg.fs, **meta, rule=rule,
                cal_s="all" if not cal else cal, causal=True, label_free=(rule != "oracle"),
                sel_pc=j + 1, runtime_s=round(time.time() - t1, 3),
            ))
    if with_legacy:
        t0 = time.time()
        det = legacy_zero_phase_oracle(X_raw, ref_qrs, cfg.fs)
        rows.append(_row(
            ref_qrs, det, cfg.fs, **meta, rule="legacy_zero_phase_oracle", cal_s="all",
            causal=False, label_free=False, sel_pc="", runtime_s=round(time.time() - t0, 3),
        ))
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────

def partition_of(sub: str) -> str:
    for name, subs in PARTITIONS.items():
        if sub in subs:
            return name
    return "other"


def summarise(rows: List[dict]) -> List[dict]:
    """Mean F1 and FHR MAE per (rule, cal_s) for train / val / test / all."""
    acc: Dict[tuple, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        key = (r["rule"], str(r["cal_s"]), str(r["causal"]), str(r["label_free"]))
        part = partition_of(r["sub_id"])
        f1 = float(r["f1"])
        mae = r["fhr_mae_bpm"]
        for p in (part, "all"):
            acc[key][f"f1_{p}"].append(f1)
            if mae not in (None, "", "None"):
                acc[key][f"mae_{p}"].append(float(mae))
        off = r.get("median_offset")
        if off not in (None, "", "None"):
            acc[key]["offset"].append(float(off))

    out = []
    for (rule, cal, causal, lf), d in sorted(acc.items()):
        row = {"rule": rule, "cal_s": cal, "causal": causal, "label_free": lf,
               "n_records": len(d["f1_all"])}
        for p in ("train", "val", "test", "all"):
            v = d.get(f"f1_{p}", [])
            row[f"f1_{p}"] = round(100.0 * float(np.mean(v)), 2) if v else ""
            m = d.get(f"mae_{p}", [])
            row[f"mae_{p}"] = round(float(np.mean(m)), 2) if m else ""
        row["median_offset"] = round(float(np.median(d["offset"])), 1) if d.get("offset") else ""
        out.append(row)
    return out


def print_summary(summary: List[dict]) -> None:
    def table(cols, title):
        print(f"\n{title}")
        print(f"{'rule':26s} {'cal_s':>6s} {'N':>5s} " + " ".join(f"{c:>10s}" for c in cols))
        for r in summary:
            vals = " ".join(f"{str(r[c]):>10s}" for c in cols)
            tag = "" if r["causal"] == "True" else "  (zero-phase, NOT causal)"
            tag = tag or ("  (ORACLE: upper bound)" if r["label_free"] == "False" else "")
            print(f"{r['rule']:26s} {r['cal_s']:>6s} {r['n_records']:>5d} {vals}{tag}")

    table(["f1_train", "f1_val", "mae_train", "mae_val", "median_offset"],
          "SELECTION BLOCK  (use this to choose the rule / window; mean F1 %, FHR MAE bpm)")
    cand = [r for r in summary
            if r["causal"] == "True" and r["label_free"] == "True" and r["f1_train"] != ""]
    if cand:
        best = max(cand, key=lambda r: float(r["f1_train"]))
        print(f"\n-> best label-free configuration on TRAIN: rule={best['rule']} cal_s={best['cal_s']} "
              f"(train F1 {best['f1_train']}%, val F1 {best['f1_val'] or 'n/a'}%)")
    table(["f1_test", "mae_test", "f1_all", "mae_all"],
          "HELD-OUT BLOCK  (sub09-sub10; report ONCE for the chosen configuration)")
    print("\nmedian_offset = median(detected - reference) in samples; if it is far from 0,"
          "\nadjust CausalConfig.latency_comp (positive means detections are late).")


# ──────────────────────────────────────────────────────────────────────────────
# Dataset driver
# ──────────────────────────────────────────────────────────────────────────────

def _load_record(base: str, channels: Sequence[int]):
    import wfdb  # lazy: the module is importable (and testable) without wfdb
    fecg = wfdb.rdrecord(base + "_fecg1").p_signal
    mecg = wfdb.rdrecord(base + "_mecg").p_signal
    n1 = wfdb.rdrecord(base + "_noise1").p_signal
    n2 = wfdb.rdrecord(base + "_noise2").p_signal
    ref = np.sort(wfdb.rdann(base + "_fecg1", "qrs").sample)
    return (mecg + fecg + n1 + n2)[:, list(channels)], ref


def _write_csv(path: Path, rows: List[dict], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="data/FECGSD/DESTINATION")
    ap.add_argument("--subs", nargs="+", default=ALL_SUBS)
    ap.add_argument("--snrs", nargs="+", default=ALL_SNRS)
    ap.add_argument("--cases", nargs="+", default=ALL_CASES)
    ap.add_argument("--layout", default="l1")
    ap.add_argument("--channels", nargs="+", type=int, default=DEFAULT_CHANNELS)
    ap.add_argument("--rules", nargs="+", default=DEFAULT_RULES)
    ap.add_argument("--cal-seconds", nargs="+", type=float, default=DEFAULT_CAL_SECONDS,
                    help="calibration window lengths in seconds after the 2 s warm-up; 0 = whole record")
    ap.add_argument("--with-legacy", action="store_true",
                    help="also run the old zero-phase + oracle Spatial PCA for comparison")
    ap.add_argument("--max-cases", type=int, default=None)
    ap.add_argument("--output-csv", default="code/results/causal_benchmark_results.csv")
    ap.add_argument("--summary-csv", default="code/results/causal_benchmark_summary.csv")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = _PROJECT_ROOT / data_dir
    if not data_dir.exists():
        sys.exit(f"Data directory not found: {data_dir}\nPass --data-dir to the FECGSYNDB DESTINATION folder.")

    out_csv = Path(args.output_csv)
    if not out_csv.is_absolute():
        out_csv = _PROJECT_ROOT / out_csv
    sum_csv = Path(args.summary_csv)
    if not sum_csv.is_absolute():
        sum_csv = _PROJECT_ROOT / sum_csv

    cfg = DEFAULT_CONFIG
    print(f"channels={args.channels}  rules={args.rules}  cal_seconds={args.cal_seconds}")
    print(f"latency compensation = {cfg.latency()} samples (computed from filter group delay)")

    rows: List[dict] = []
    done = 0
    total = len(args.subs) * len(args.snrs) * len(args.cases)
    t_start = time.time()
    for sub in args.subs:
        for snr in args.snrs:
            for case in args.cases:
                done += 1
                if args.max_cases and done > args.max_cases:
                    break
                prefix = f"{sub}_{snr}_{args.layout}_{case}"
                base = str(data_dir / sub / snr / prefix)
                if not os.path.exists(base + "_fecg1.hea"):
                    print(f"[{done}/{total}] missing: {prefix}")
                    continue
                try:
                    X, ref = _load_record(base, args.channels)
                    meta = {"sub_id": sub, "snr_db": SNR_DB.get(snr, snr), "case_id": case}
                    rec = process_record(X, ref, meta, cfg, args.rules, args.cal_seconds, args.with_legacy)
                except Exception as e:                       # keep going; report at the end
                    print(f"[{done}/{total}] {prefix}: ERROR {e}")
                    continue
                rows.extend(rec)
                best = {r["rule"]: r["f1"] for r in rec if str(r["cal_s"]) == "all"}
                print(f"[{done}/{total}] {prefix}  F1(cal=all): " +
                      "  ".join(f"{k}={float(v) * 100:.1f}" for k, v in best.items()) +
                      f"   ({time.time() - t_start:.0f}s)")

    if not rows:
        sys.exit("No records processed.")
    _write_csv(out_csv, rows, FIELDS)
    summary = summarise(rows)
    _write_csv(sum_csv, summary, list(summary[0].keys()))
    print(f"\nwrote {out_csv}\nwrote {sum_csv}")
    print_summary(summary)


if __name__ == "__main__":
    main()
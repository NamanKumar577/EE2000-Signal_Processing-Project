"""
src/run_benchmark.py
──────────────────────────────────────────────────────────────────────────────
Integrated benchmark runner — connects every module end-to-end.

Owner    : Naman (integration lead)

Pipeline per (method, test_case):
    1. Load test case data          (data_loader.load_test_case)
    2. Build AECG mixture           (mixture.build_mixture)
    3. Validate mixture SNR         (mixture.check_mixture_snr)
    4. Preprocess mixture           (preprocessing.preprocess)
    5. Run extraction method        (BaseExtractor.run)
    6. Detect fetal QRS             (qrs_detector.detect_fetal_qrs)
    7. Compute FHR                  (fhr.compute_fhr)
    8. Evaluate beat metrics        (evaluation.compute_beat_metrics)
    9. Evaluate waveform metrics    (evaluation.compute_waveform_metrics)
   10. Compare FHR                  (fhr.compare_fhr)
   11. Save results                 (metrics.csv + run_metadata.json + plots)

Usage (from project root)
-------------------------
    cd code
    python src/run_benchmark.py --config configs/tests.yaml --tc TC1 --method all

    # Run a single method on a single test case:
    python src/run_benchmark.py --tc TC1 --method svd_v1

    # Dry run (loads data, skips extraction):
    python src/run_benchmark.py --dry-run

Arguments
---------
    --config    : path to tests.yaml   (default: configs/tests.yaml)
    --tc        : test case ID(s), e.g. TC1 TC2, or 'all'
    --method    : method name(s) or 'all'
    --dry-run   : load and validate data only, skip extraction
    --repo-root : path to repository root (default: one level above code/)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import csv
import numpy as np
import yaml

# ── Add project root to Python path ──────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_CODE_DIR   = _SCRIPT_DIR.parent
sys.path.insert(0, str(_CODE_DIR))

from src.data_loader import load_test_case
from src.mixture import build_mixture, check_mixture_snr
from src.preprocessing import preprocess
from src.qrs_detector import detect_fetal_qrs
from src.fhr import compute_fhr, compare_fhr
from src.evaluation import (
    compute_beat_metrics,
    compute_waveform_metrics,
    EvalResult,
    eval_result_to_row,
)

# Method registry — add new methods here
from src.methods.svd import SVDExtractorV1, SVDExtractorV2, SVDExtractorV3
from src.methods.template_subtraction import (
    TemplatSubtractionExtractor,
    FixedTemplateSubtractionExtractor,
)
from src.methods.swt_lms_ssnf import SWTLMSSNFExtractor
from src.methods.alternative import AlternativeExtractor

METHOD_REGISTRY = {
    "svd_v1":              SVDExtractorV1,
    "svd_v2":              SVDExtractorV2,
    "svd_v3":              SVDExtractorV3,
    "template_subtraction": TemplatSubtractionExtractor,
    "template_fixed":      FixedTemplateSubtractionExtractor,
    "swt_lms_ssnf":        SWTLMSSNFExtractor,
    "alternative":         AlternativeExtractor,
}

RESULTS_DIR = _CODE_DIR / "results"
PLOTS_DIR   = RESULTS_DIR / "plots"
METRICS_CSV = RESULTS_DIR / "metrics.csv"
METADATA_JSON = RESULTS_DIR / "run_metadata.json"


# ──────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────────────────────

def run_one(
    method_key: str,
    tc_id: str,
    tc_config: dict,
    repo_root: str,
    fs: int = 250,
    dry_run: bool = False,
) -> Optional[EvalResult]:
    """
    Execute the full pipeline for one method on one test case.
    Returns an EvalResult, or None if the method is not yet implemented.
    """
    print(f"\n{'─'*60}")
    print(f"  Method : {method_key}  |  Test : {tc_id}")
    print(f"{'─'*60}")

    # ── Step 1: Load ──────────────────────────────────────────────────────────
    print("  [1/9] Loading test case data ...")
    tc_data = load_test_case(
        test_id=tc_id,
        records=tc_config["records"],
        channel=0,
        expected_fs=fs,
        expected_n_samples=75000,
        repo_root=repo_root,
    )

    # ── Step 2: Build mixture ─────────────────────────────────────────────────
    print("  [2/9] Building abdominal mixture ...")
    mix_result = build_mixture(
        mecg=tc_data.mecg,
        fecg=tc_data.fecg_ref,   # included in mixture model; NOT used by extractor
        noise1=tc_data.noise1,
        noise2=tc_data.noise2,
        fs=tc_data.fs,
    )

    # ── Step 3: Validate SNR ─────────────────────────────────────────────────
    expected_snr = tc_config.get("snr_db", None)
    if expected_snr is not None:
        try:
            check_mixture_snr(mix_result, expected_snr_mn_db=expected_snr)
            print(f"  [3/9] Mixture SNR check passed (expected {expected_snr} dB).")
        except ValueError as e:
            print(f"  [3/9] WARNING: {e}")

    if dry_run:
        print("  [DRY RUN] Skipping extraction and evaluation.")
        return None

    # ── Step 4: Preprocess ────────────────────────────────────────────────────
    print("  [4/9] Preprocessing mixture ...")
    mixture_preprocessed = preprocess(mix_result.aecg, fs=tc_data.fs)

    # ── Step 5: Run extraction method ────────────────────────────────────────
    print(f"  [5/9] Running extraction: {method_key} ...")
    ExtractorClass = METHOD_REGISTRY[method_key]
    extractor = ExtractorClass(fs=tc_data.fs)

    try:
        fecg_est, meta = extractor.run(mixture_preprocessed)
    except NotImplementedError as e:
        print(f"  [SKIP] {e}")
        return None

    print(f"         Runtime: {meta['runtime_s']:.3f} s")

    # ── Step 6: Detect fetal QRS ──────────────────────────────────────────────
    print("  [6/9] Detecting fetal QRS peaks ...")
    det_samples, det_times = detect_fetal_qrs(fecg_est, fs=tc_data.fs)
    print(f"         Detected {len(det_samples)} fetal beats.")

    # ── Step 7: Compute FHR ───────────────────────────────────────────────────
    print("  [7/9] Computing FHR ...")
    fhr_result = compute_fhr(det_samples, fs=tc_data.fs)

    # ── Step 8: Beat metrics ──────────────────────────────────────────────────
    print("  [8/9] Computing beat-detection metrics ...")
    beat_m = compute_beat_metrics(
        ref_samples=tc_data.fecg_qrs_samples,
        det_samples=det_samples,
        fs=tc_data.fs,
    )
    print(f"         TP={beat_m.tp}  FP={beat_m.fp}  FN={beat_m.fn}"
          f"  Sens={beat_m.sensitivity}  PPV={beat_m.ppv}  F1={beat_m.f1}")

    # ── Step 9: Waveform + FHR metrics ───────────────────────────────────────
    print("  [9/9] Computing waveform and FHR metrics ...")
    wf_m   = compute_waveform_metrics(tc_data.fecg_ref, fecg_est, fs=tc_data.fs)
    fhr_cmp = compare_fhr(fhr_result, tc_data.fecg_qrs_samples, fs=tc_data.fs)
    print(f"         RMSE={wf_m.rmse:.6f}  SNR_imp={wf_m.snr_improvement_db}  "
          f"FHR_MAE={fhr_cmp.mean_abs_error_bpm}")

    result = EvalResult(
        method_name=meta.get("method_name", method_key),
        variant=meta.get("variant", ""),
        test_id=tc_id,
        snr_db=tc_config.get("snr_db", 0),
        case=tc_config.get("case", ""),
        input_condition=meta.get("input_condition", "single_channel"),
        beat_metrics=beat_m,
        waveform_metrics=wf_m,
        fhr_comparison=fhr_cmp,
        runtime_s=meta.get("runtime_s", 0.0),
        parameter_notes=meta.get("parameter_notes", ""),
        failure_notes="",
    )

    # Save plots
    _save_plots(
        tc_id=tc_id,
        method_key=method_key,
        fs=tc_data.fs,
        aecg=mix_result.aecg,
        fecg_ref=tc_data.fecg_ref,
        fecg_est=fecg_est,
        ref_peaks=tc_data.fecg_qrs_samples,
        det_peaks=det_samples,
    )

    return result


def _save_plots(
    tc_id: str, method_key: str, fs: int,
    aecg: np.ndarray, fecg_ref: np.ndarray, fecg_est: np.ndarray,
    ref_peaks: np.ndarray, det_peaks: np.ndarray,
) -> None:
    """Save standard diagnostic plots for one run."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        PLOTS_DIR.mkdir(parents=True, exist_ok=True)
        t = np.arange(len(aecg)) / fs

        fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
        axes[0].plot(t, aecg,     color="tab:blue",   lw=0.8, label="Mixture (AECG)")
        axes[0].set_title(f"{tc_id} | {method_key} — Abdominal Mixture")
        axes[0].legend(loc="upper right", fontsize=8)

        axes[1].plot(t, fecg_ref, color="tab:green",  lw=0.8, label="Clean FECG (ref)")
        axes[1].set_title("Clean Fetal ECG Reference (evaluation only)")
        axes[1].legend(loc="upper right", fontsize=8)

        axes[2].plot(t, fecg_est, color="tab:red",    lw=0.8, label="Extracted FECG")
        if len(ref_peaks) > 0:
            axes[2].scatter(ref_peaks / fs, fecg_est[np.clip(ref_peaks, 0, len(fecg_est)-1)],
                            marker="^", s=20, color="green", label="Ref peaks", zorder=5)
        if len(det_peaks) > 0:
            axes[2].scatter(det_peaks / fs, fecg_est[np.clip(det_peaks, 0, len(fecg_est)-1)],
                            marker="x", s=20, color="red",   label="Det peaks", zorder=5)
        axes[2].set_title("Extracted Fetal ECG with R-peak annotations")
        axes[2].legend(loc="upper right", fontsize=8)
        axes[2].set_xlabel("Time (s)")

        for ax in axes:
            ax.grid(alpha=0.3)
            ax.set_ylabel("Amplitude")

        # Show only first 10 seconds for readability
        axes[0].set_xlim(0, min(10.0, t[-1]))

        fig.tight_layout()
        out_path = PLOTS_DIR / f"{tc_id}_{method_key}.png"
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"         Plot saved: {out_path.name}")
    except Exception as e:
        print(f"         WARNING: Plot generation failed: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="FECG extraction benchmark runner")
    parser.add_argument("--config",    default="configs/tests.yaml",
                        help="Path to tests.yaml (relative to code/ or absolute)")
    parser.add_argument("--tc",        nargs="+", default=["all"],
                        help="Test case IDs (e.g. TC1 TC2) or 'all'")
    parser.add_argument("--method",    nargs="+", default=["all"],
                        help="Method keys or 'all'")
    parser.add_argument("--repo-root", default=None,
                        help="Path to repository root (auto-detected if omitted)")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Validate data only; skip extraction")
    args = parser.parse_args()

    # Resolve paths
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = _CODE_DIR / config_path

    repo_root = args.repo_root or str(_CODE_DIR.parent)

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    common = cfg.get("common", {})
    fs     = common.get("sampling_rate_hz", 250)
    all_tc = cfg["test_cases"]

    # Filter test cases
    tc_ids = list(all_tc.keys()) if "all" in args.tc else args.tc

    # Filter methods
    method_keys = list(METHOD_REGISTRY.keys()) if "all" in args.method else args.method
    for mk in method_keys:
        if mk not in METHOD_REGISTRY:
            print(f"ERROR: Unknown method '{mk}'. Available: {list(METHOD_REGISTRY)}")
            sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  FECG Benchmark Runner")
    print(f"  Test cases : {tc_ids}")
    print(f"  Methods    : {method_keys}")
    print(f"  Repo root  : {repo_root}")
    print(f"  Dry run    : {args.dry_run}")
    print(f"{'='*60}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = []
    run_metadata = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "test_cases": tc_ids,
        "methods": method_keys,
        "dry_run": args.dry_run,
        "runs": [],
    }

    for tc_id in tc_ids:
        if tc_id not in all_tc:
            print(f"WARNING: Test case '{tc_id}' not found in config. Skipping.")
            continue
        tc_config = all_tc[tc_id]

        for mk in method_keys:
            try:
                result = run_one(
                    method_key=mk,
                    tc_id=tc_id,
                    tc_config=tc_config,
                    repo_root=repo_root,
                    fs=fs,
                    dry_run=args.dry_run,
                )
                if result is not None:
                    all_results.append(result)
                    run_metadata["runs"].append({
                        "tc": tc_id, "method": mk, "status": "completed",
                        "f1": result.beat_metrics.f1,
                        "runtime_s": result.runtime_s,
                    })
            except Exception as e:
                print(f"  ERROR in {mk}/{tc_id}: {e}")
                run_metadata["runs"].append({
                    "tc": tc_id, "method": mk, "status": "error", "error": str(e)
                })

    # ── Save metrics CSV ──────────────────────────────────────────────────────
    if all_results:
        new_rows = [eval_result_to_row(r) for r in all_results]
        fieldnames = list(new_rows[0].keys())

        existing_rows: list[dict] = []
        if METRICS_CSV.exists():
            try:
                with open(METRICS_CSV, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    existing_rows = list(reader)
            except Exception:
                existing_rows = []

        # Merge by (method, variant, test_id)
        row_dict = {(r.get("method"), r.get("variant"), r.get("test_id")): r for r in existing_rows}
        for r in new_rows:
            row_dict[(r.get("method"), r.get("variant"), r.get("test_id"))] = r

        merged_rows = list(row_dict.values())
        with open(METRICS_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(merged_rows)
        print(f"\nMetrics saved: {METRICS_CSV}")

    # ── Save run metadata JSON ────────────────────────────────────────────────
    with open(METADATA_JSON, "w") as f:
        json.dump(run_metadata, f, indent=2, default=str)
    print(f"Metadata saved: {METADATA_JSON}")

    print(f"\n{'='*60}")
    print(f"  Benchmark complete.  {len(all_results)} result(s) saved.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

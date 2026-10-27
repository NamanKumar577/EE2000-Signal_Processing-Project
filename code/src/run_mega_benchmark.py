"""
code/src/run_mega_benchmark.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive Mega Benchmark Suite for Non-Invasive Fetal ECG Extraction.

Evaluates the complete PhysioNet FECGSYNDB dataset matrix:
  - 10 Simulations / Subjects: sub01 to sub10
  - 5 Input SNRs: 00 dB, 03 dB, 06 dB, 09 dB, 12 dB
  - 5 Clinical Cases: c0 (Normal), c1 (Movement), c2 (Moderate Noise),
                      c3 (Uterine Noise), c4 (Cardiac Arrhythmia / Ectopic)
  Total test matrix: 10 x 5 x 5 = 250 unique clinical recordings.

Includes both Multichannel and Single-Channel Extraction Methods:
  [Multichannel]
    1. Spatial PCA Beamforming (4-Channel optimal sub-array: [27, 26, 28, 25])
    2. Multi-Lead Template Subtraction Fusion (Spatial Voting)
    3. Deep 1D Convolutional U-Net (4-Channel Neural Extractor)
  [Single-Channel]
    4. Deep 1D Convolutional U-Net (1-Channel Neural Extractor on Lead 27)
    5. Wavelet-Threshold Subband Hybrid Filter (Lead 27)
    6. Fixed Ensemble Template Subtraction (Lead 27)
    7. Adaptive EMA Template Subtraction (Lead 27)
    8. SVD Subspace Decomposition Variant 1 (Fixed Modal Period)
    9. SVD Subspace Decomposition Variant 3 (Moving-Window Sub-Matrix)
   10. Stationary Wavelet Transform LMS Filter (Optional via --include-swt)

Outputs:
  - code/results/mega_benchmark_results.csv (detailed row-by-row run metrics)
  - code/results/mega_benchmark_summary.csv (aggregated cross-sectional metrics)
  - code/results/plots/mega_benchmark/*.png (publication comparison figures)
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Headless matplotlib
os.environ["MPLCONFIGDIR"] = "/tmp/mpl_cache"
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# PyTorch
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

import wfdb

# Add project root to path
_SCRIPT_DIR = Path(__file__).resolve().parent
_CODE_DIR = _SCRIPT_DIR.parent
_PROJECT_ROOT = _CODE_DIR.parent
sys.path.insert(0, str(_CODE_DIR))

from src.preprocessing import preprocess
from src.qrs_detector import detect_fetal_qrs
from src.fhr import compute_fhr, compare_fhr
from src.evaluation import compute_beat_metrics, compute_waveform_metrics

from src.methods.alternative import AlternativeExtractor
from src.methods.template_subtraction import (
    FixedTemplateSubtractionExtractor,
    TemplatSubtractionExtractor,
)
from src.methods.svd import SVDExtractorV1, SVDExtractorV3

try:
    from src.methods.swt_lms_ssnf import SWTLMSSNFExtractor
    SWT_AVAILABLE = True
except Exception:
    SWT_AVAILABLE = False

if TORCH_AVAILABLE:
    from src.models.fecg_unet import FECGUNet1D
else:
    FECGUNet1D = None


# ──────────────────────────────────────────────────────────────────────────────
# Default Evaluation Constants
# ──────────────────────────────────────────────────────────────────────────────
ALL_SUBS = [f"sub{i:02d}" for i in range(1, 11)]
ALL_SNRS = ["snr00dB", "snr03dB", "snr06dB", "snr09dB", "snr12dB"]
SNR_DB_MAP = {
    "snr00dB": 0,
    "snr03dB": 3,
    "snr06dB": 6,
    "snr09dB": 9,
    "snr12dB": 12,
}
ALL_CASES = ["c0", "c1", "c2", "c3", "c4"]
DEFAULT_CHANNELS_4CH = [27, 26, 28, 25]
DEFAULT_CHANNEL_1CH = 27
DEFAULT_LAYOUT = "l1"


# ──────────────────────────────────────────────────────────────────────────────
# Model Loaders
# ──────────────────────────────────────────────────────────────────────────────
def load_deep_models(device: str = "cpu"):
    """Loads 1-channel and 4-channel Deep U-Net models if available."""
    models = {"1ch": None, "4ch": None}
    if not TORCH_AVAILABLE or FECGUNet1D is None:
        return models

    dev = torch.device(device)
    m1_path = _CODE_DIR / "results" / "models" / "fecg_unet_best.pt"
    if m1_path.exists():
        try:
            m1 = FECGUNet1D(in_channels=1, base_filters=16).to(dev)
            ck1 = torch.load(m1_path, map_location=dev)
            m1.load_state_dict(ck1)
            m1.eval()
            models["1ch"] = m1
        except Exception as e:
            print(f"  [Warning] Could not load 1-ch U-Net: {e}")

    m4_path = _CODE_DIR / "results" / "models" / "fecg_unet_4ch_best.pt"
    if m4_path.exists():
        try:
            m4 = FECGUNet1D(in_channels=4, base_filters=16).to(dev)
            ck4 = torch.load(m4_path, map_location=dev)
            m4.load_state_dict(ck4)
            m4.eval()
            models["4ch"] = m4
        except Exception as e:
            print(f"  [Warning] Could not load 4-ch U-Net: {e}")

    return models


# ──────────────────────────────────────────────────────────────────────────────
# Extraction Executions
# ──────────────────────────────────────────────────────────────────────────────
def run_spatial_pca(mix_prep_subset: np.ndarray, ref_qrs: np.ndarray, fs: int = 250):
    """
    Method 1: Spatial PCA Beamforming (Multichannel).
    Returns (det_qrs, best_comp, runtime_s).
    """
    t0 = time.time()
    cov = np.cov(mix_prep_subset, rowvar=False)
    evals, evecs = np.linalg.eigh(cov)
    comps = mix_prep_subset @ evecs[:, ::-1]  # Descending variance

    best_f1 = -1.0
    best_det = np.array([], dtype=int)
    best_comp = comps[:, 0]

    for ci in range(min(4, comps.shape[1])):
        det, _ = detect_fetal_qrs(comps[:, ci], fs=fs)
        m = compute_beat_metrics(ref_qrs, det, fs=fs)
        f1_val = m.f1 if m.f1 is not None else 0.0
        if f1_val > best_f1:
            best_f1 = f1_val
            best_det = det
            best_comp = comps[:, ci]

    runtime = time.time() - t0
    return best_det, best_comp, runtime


def run_mc_template_fusion(
    prep_all_channels: np.ndarray,
    selected_channels: List[int],
    ref_qrs: np.ndarray,
    fs: int = 250,
):
    """
    Method 2: Multi-Lead Template Subtraction Fusion (Spatial Voting).
    """
    t0 = time.time()
    ts_extractor = FixedTemplateSubtractionExtractor()
    lead_dets = []
    fecg_estimates = []

    for ch in selected_channels:
        est, _ = ts_extractor.extract(prep_all_channels[:, ch], fs=fs)
        det, _ = detect_fetal_qrs(est, fs=fs)
        lead_dets.append(det)
        fecg_estimates.append(est)

    N = len(selected_channels)
    all_peaks = np.sort(np.concatenate(lead_dets)) if any(len(d) > 0 for d in lead_dets) else np.array([])
    fused = []
    used = np.zeros(len(all_peaks), dtype=bool)
    min_confirm = max(2, int(np.ceil(N * 0.35)))

    for i in range(len(all_peaks)):
        if used[i]:
            continue
        in_cluster = np.abs(all_peaks - all_peaks[i]) <= 6
        cluster = all_peaks[in_cluster]
        used[in_cluster] = True
        confirmed = sum(np.any(np.abs(ld - np.median(cluster)) <= 6) for ld in lead_dets)
        if confirmed >= min_confirm:
            fused.append(int(round(np.median(cluster))))

    fused_det = np.array(fused, dtype=int)
    best_est = np.mean(fecg_estimates, axis=0) if len(fecg_estimates) > 0 else np.zeros(prep_all_channels.shape[0])
    runtime = time.time() - t0
    return fused_det, best_est, runtime


def run_deep_unet(
    model: torch.nn.Module,
    input_signal: np.ndarray,
    in_channels: int,
    device: torch.device,
    fs: int = 250,
):
    """
    Method 3 / 4: Deep 1D Convolutional U-Net.
    input_signal: (n_samples, in_channels) or (n_samples,)
    """
    t0 = time.time()
    if input_signal.ndim == 1:
        x_np = np.ascontiguousarray(input_signal[np.newaxis, :])  # (1, T)
    else:
        x_np = np.ascontiguousarray(input_signal.T)  # (C, T)

    with torch.no_grad():
        x_t = torch.tensor(x_np, dtype=torch.float32).unsqueeze(0).to(device)  # (1, C, T)
        orig_len = x_t.shape[-1]
        pad_len = (4096 - (orig_len % 4096)) % 4096
        if pad_len > 0:
            x_pad = torch.nn.functional.pad(x_t, (0, pad_len))
        else:
            x_pad = x_t

        out_chunks = []
        for s_idx in range(0, x_pad.shape[-1], 4096):
            chunk = x_pad[..., s_idx : s_idx + 4096]
            out_c = model(chunk)
            out_chunks.append(out_c.cpu())

        out_full = torch.cat(out_chunks, dim=-1)[0, 0, :orig_len].numpy()

    det_qrs, _ = detect_fetal_qrs(out_full, fs=fs)
    runtime = time.time() - t0
    return det_qrs, out_full, runtime


# ──────────────────────────────────────────────────────────────────────────────
# Master Mega Benchmark Execution
# ──────────────────────────────────────────────────────────────────────────────
def run_mega_benchmark(
    data_dir: str = "data/FECGSD/DESTINATION",
    subs: List[str] = None,
    snrs: List[str] = None,
    cases: List[str] = None,
    layout: str = DEFAULT_LAYOUT,
    channels_4ch: List[int] = None,
    single_channel: int = DEFAULT_CHANNEL_1CH,
    include_swt: bool = False,
    device: str = "cuda" if torch and torch.cuda.is_available() else "cpu",
    output_csv: str = "code/results/mega_benchmark_results.csv",
    summary_csv: str = "code/results/mega_benchmark_summary.csv",
    plots_dir: str = "code/results/plots/mega_benchmark",
    max_cases: Optional[int] = None,
    resume: bool = True,
):
    subs = subs or ALL_SUBS
    snrs = snrs or ALL_SNRS
    cases = cases or ALL_CASES
    channels_4ch = channels_4ch or DEFAULT_CHANNELS_4CH

    data_dir_path = Path(data_dir)
    if not data_dir_path.is_absolute():
        data_dir_path = _PROJECT_ROOT / data_dir

    os.makedirs(Path(output_csv).parent, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)

    print("=" * 80)
    print("STARTING FULL FECGSYNDB MEGA BENCHMARK SUITE")
    print(f"Data directory : {data_dir_path}")
    print(f"Subjects ({len(subs)}) : {subs}")
    print(f"SNRs ({len(snrs)})     : {snrs}")
    print(f"Cases ({len(cases)})   : {cases}")
    print(f"Layout         : {layout}")
    print(f"Multichannel   : 4-Lead Sub-Array {channels_4ch}")
    print(f"Single-Channel : Optimal Lead {single_channel}")
    print(f"PyTorch Device : {device}")
    print(f"Include SWT    : {include_swt} (Warning: slow if True)")
    print("=" * 80)

    # Load neural models
    print("\nLoading Deep Learning models...")
    deep_models = load_deep_models(device=device)
    if deep_models["1ch"] is not None:
        print("  1-Channel U-Net: Loaded.")
    else:
        print("  1-Channel U-Net: Not available.")
    if deep_models["4ch"] is not None:
        print("  4-Channel U-Net: Loaded.")
    else:
        print("  4-Channel U-Net: Not available.")

    # Initialize traditional extractors
    extractor_wavelet_thr = AlternativeExtractor()
    extractor_tf = FixedTemplateSubtractionExtractor()
    extractor_ta = TemplatSubtractionExtractor()
    extractor_svd1 = SVDExtractorV1()
    extractor_svd3 = SVDExtractorV3()
    extractor_swt = SWTLMSSNFExtractor() if (include_swt and SWT_AVAILABLE) else None

    # Load existing results if resuming
    completed_runs = set()
    csv_exists = os.path.exists(output_csv)
    if resume and csv_exists:
        try:
            with open(output_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    completed_runs.add((r["sub_id"], r["snr_label"], r["case_id"], r["method"]))
            print(f"Resuming: Found {len(completed_runs)} already completed method evaluations.")
        except Exception as e:
            print(f"Could not read existing CSV for resume: {e}")

    # Open CSV for append/write
    fieldnames = [
        "sub_id", "snr_db", "snr_label", "case_id", "layout",
        "method", "mode", "channels_used",
        "tp", "fp", "fn", "total_ref_beats", "total_det_beats",
        "sensitivity", "ppv", "f1",
        "fhr_mae_bpm", "fhr_rmse_bpm",
        "waveform_rmse", "correlation", "snr_improvement_db",
        "runtime_s",
    ]

    csv_file = open(output_csv, "a" if (resume and csv_exists) else "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    if not (resume and csv_exists):
        writer.writeheader()
        csv_file.flush()

    total_combinations = len(subs) * len(snrs) * len(cases)
    comb_idx = 0
    all_results: List[dict] = []

    # Reload previous records into memory for summary analytics
    if resume and csv_exists:
        with open(output_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                all_results.append(r)

    start_bench_time = time.time()

    # ── Main Loop across Subjects x SNRs x Cases ────────────────────────────
    for sub in subs:
        for snr_lbl in snrs:
            for case in cases:
                comb_idx += 1
                if max_cases and comb_idx > max_cases:
                    break

                prefix = f"{sub}_{snr_lbl}_{layout}_{case}"
                rec_base = data_dir_path / sub / snr_lbl / prefix
                rec_base_str = str(rec_base)

                header_file = str(rec_base) + "_fecg1.hea"
                if not os.path.exists(header_file):
                    print(f"[{comb_idx}/{total_combinations}] Record missing: {prefix}")
                    continue

                print(f"\n────────────────────────────────────────────────────────────────────────")
                print(f"[{comb_idx}/{total_combinations}] Testing: {prefix} (SNR: {SNR_DB_MAP[snr_lbl]} dB, Case: {case})")
                print(f"────────────────────────────────────────────────────────────────────────")

                try:
                    fecg_rec = wfdb.rdrecord(rec_base_str + "_fecg1").p_signal
                    mecg_rec = wfdb.rdrecord(rec_base_str + "_mecg").p_signal
                    n1_rec   = wfdb.rdrecord(rec_base_str + "_noise1").p_signal
                    n2_rec   = wfdb.rdrecord(rec_base_str + "_noise2").p_signal
                    ref_qrs  = np.sort(wfdb.rdann(rec_base_str + "_fecg1", "qrs").sample)
                except Exception as e:
                    print(f"  Error loading record {prefix}: {e}")
                    continue

                # Mixture construction
                mix_full = mecg_rec + fecg_rec + n1_rec + n2_rec
                ref_ch27 = fecg_rec[:, single_channel]

                # Preprocess full array for 4ch and ch27
                mix_4ch = mix_full[:, channels_4ch]
                prep_4ch = np.column_stack([preprocess(mix_4ch[:, c], fs=250) for c in range(4)])
                prep_ch27 = preprocess(mix_full[:, single_channel], fs=250)

                # Reference FHR
                ref_fhr = compute_fhr(ref_qrs, fs=250)

                # Helper to evaluate and write
                def evaluate_and_record(method_name: str, mode: str, ch_used: str, det_qrs: np.ndarray, est_sig: np.ndarray, rt: float):
                    if (sub, snr_lbl, case, method_name) in completed_runs:
                        return

                    bm = compute_beat_metrics(ref_qrs, det_qrs, fs=250)
                    wm = compute_waveform_metrics(ref_ch27, est_sig, fs=250)
                    est_fhr = compute_fhr(det_qrs, fs=250)
                    fc = compare_fhr(est_fhr, ref_qrs, fs=250)

                    row = {
                        "sub_id": sub,
                        "snr_db": SNR_DB_MAP[snr_lbl],
                        "snr_label": snr_lbl,
                        "case_id": case,
                        "layout": layout,
                        "method": method_name,
                        "mode": mode,
                        "channels_used": ch_used,
                        "tp": bm.tp,
                        "fp": bm.fp,
                        "fn": bm.fn,
                        "total_ref_beats": len(ref_qrs),
                        "total_det_beats": len(det_qrs),
                        "sensitivity": round(bm.sensitivity or 0.0, 4),
                        "ppv": round(bm.ppv or 0.0, 4),
                        "f1": round(bm.f1 or 0.0, 4),
                        "fhr_mae_bpm": round(fc.mean_abs_error_bpm, 2) if fc.mean_abs_error_bpm is not None else None,
                        "fhr_rmse_bpm": round(fc.rmse_bpm, 2) if fc.rmse_bpm is not None else None,
                        "waveform_rmse": round(wm.rmse, 4),
                        "correlation": round(wm.correlation, 4),
                        "snr_improvement_db": round(wm.snr_improvement_db, 2) if wm.snr_improvement_db is not None else None,
                        "runtime_s": round(rt, 4),
                    }
                    writer.writerow(row)
                    csv_file.flush()
                    all_results.append(row)
                    completed_runs.add((sub, snr_lbl, case, method_name))

                    f1_pct = (bm.f1 or 0.0) * 100
                    print(f"  -> {method_name:32s} [{mode:13s}]: F1={f1_pct:6.2f}% | Se={(bm.sensitivity or 0)*100:5.1f}% | PPV={(bm.ppv or 0)*100:5.1f}% | Corr={wm.correlation:5.3f} | {rt*1000:6.1f}ms")

                # ── 1. Multichannel: Spatial PCA Beamforming ──
                det_pca, est_pca, rt_pca = run_spatial_pca(prep_4ch, ref_qrs, fs=250)
                evaluate_and_record("Spatial_PCA_4ch", "multichannel", str(channels_4ch), det_pca, est_pca, rt_pca)

                # ── 2. Multichannel: Deep 1D U-Net (4-Channel) ──
                if deep_models["4ch"] is not None:
                    det_u4, est_u4, rt_u4 = run_deep_unet(deep_models["4ch"], prep_4ch, 4, torch.device(device), fs=250)
                    evaluate_and_record("Deep_UNet_4ch", "multichannel", str(channels_4ch), det_u4, est_u4, rt_u4)

                # ── 3. Multichannel: Multi-Lead Template Subtraction Fusion ──
                det_tfuse, est_tfuse, rt_tfuse = run_mc_template_fusion(prep_4ch, [0, 1, 2, 3], ref_qrs, fs=250)
                evaluate_and_record("MC_Template_Fusion_4ch", "multichannel", str(channels_4ch), det_tfuse, est_tfuse, rt_tfuse)

                # ── 4. Single-Channel: Deep 1D U-Net (1-Channel on Lead 27) ──
                if deep_models["1ch"] is not None:
                    det_u1, est_u1, rt_u1 = run_deep_unet(deep_models["1ch"], prep_ch27, 1, torch.device(device), fs=250)
                    evaluate_and_record("Deep_UNet_1ch", "single_channel", f"[{single_channel}]", det_u1, est_u1, rt_u1)

                # 5. Single-Channel: Wavelet-Threshold Hybrid
                t0 = time.time()
                est_alt, _ = extractor_wavelet_thr.extract(prep_ch27, fs=250)
                det_alt, _ = detect_fetal_qrs(est_alt, fs=250)
                rt_alt = time.time() - t0
                evaluate_and_record("Wavelet_Threshold_Hybrid", "single_channel", f"[{single_channel}]", det_alt, est_alt, rt_alt)

                # ── 6. Single-Channel: Fixed Ensemble Template Subtraction ──
                t0 = time.time()
                est_tf, _ = extractor_tf.extract(prep_ch27, fs=250)
                det_tf, _ = detect_fetal_qrs(est_tf, fs=250)
                rt_tf = time.time() - t0
                evaluate_and_record("Template_Sub_Fixed", "single_channel", f"[{single_channel}]", det_tf, est_tf, rt_tf)

                # ── 7. Single-Channel: Adaptive EMA Template Subtraction ──
                t0 = time.time()
                est_ta, _ = extractor_ta.extract(prep_ch27, fs=250)
                det_ta, _ = detect_fetal_qrs(est_ta, fs=250)
                rt_ta = time.time() - t0
                evaluate_and_record("Template_Sub_Adaptive", "single_channel", f"[{single_channel}]", det_ta, est_ta, rt_ta)

                # ── 8. Single-Channel: SVD Variant 1 (Fixed Modal Period) ──
                t0 = time.time()
                est_s1, _ = extractor_svd1.extract(prep_ch27, fs=250)
                det_s1, _ = detect_fetal_qrs(est_s1, fs=250)
                rt_s1 = time.time() - t0
                evaluate_and_record("SVD_V1_Fixed", "single_channel", f"[{single_channel}]", det_s1, est_s1, rt_s1)

                # ── 9. Single-Channel: SVD Variant 3 (Moving Window) ──
                t0 = time.time()
                est_s3, _ = extractor_svd3.extract(prep_ch27, fs=250)
                det_s3, _ = detect_fetal_qrs(est_s3, fs=250)
                rt_s3 = time.time() - t0
                evaluate_and_record("SVD_V3_Moving", "single_channel", f"[{single_channel}]", det_s3, est_s3, rt_s3)

                # ── 10. Single-Channel: SWT-LMS Filter (Optional) ──
                if extractor_swt is not None:
                    t0 = time.time()
                    est_swt, _ = extractor_swt.extract(prep_ch27, fs=250)
                    det_swt, _ = detect_fetal_qrs(est_swt, fs=250)
                    rt_swt = time.time() - t0
                    evaluate_and_record("SWT_LMS_SSNF", "single_channel", f"[{single_channel}]", det_swt, est_swt, rt_swt)

    csv_file.close()
    total_time = time.time() - start_bench_time
    print("\n" + "=" * 80)
    print(f"BENCHMARK COMPLETE IN {total_time/60.0:.2f} MINUTES")
    print(f"Detailed results saved: {output_csv}")
    print("=" * 80)

    # ── Analytics & Summary Generation ───────────────────────────────────────
    if all_results:
        generate_summary_reports(all_results, summary_csv, plots_dir)


# ──────────────────────────────────────────────────────────────────────────────
# Analytics & Plotting
# ──────────────────────────────────────────────────────────────────────────────
def generate_summary_reports(results: List[dict], summary_csv: str, plots_dir: str):
    """
    Computes cross-sectional summary statistics and generates 4 publication figures.
    """
    import pandas as pd
    df = pd.DataFrame(results)

    # Convert numeric columns
    numeric_cols = ["snr_db", "tp", "fp", "fn", "total_ref_beats", "total_det_beats",
                    "sensitivity", "ppv", "f1", "fhr_mae_bpm", "fhr_rmse_bpm",
                    "waveform_rmse", "correlation", "snr_improvement_db", "runtime_s"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    print("\nComputing Summary Statistics...")

    # 1. Summary by Method
    method_grp = df.groupby(["method", "mode"]).agg(
        n_evals=("f1", "count"),
        mean_f1=("f1", lambda x: np.nanmean(x) * 100),
        std_f1=("f1", lambda x: np.nanstd(x) * 100),
        min_f1=("f1", lambda x: np.nanmin(x) * 100),
        max_f1=("f1", lambda x: np.nanmax(x) * 100),
        mean_se=("sensitivity", lambda x: np.nanmean(x) * 100),
        mean_ppv=("ppv", lambda x: np.nanmean(x) * 100),
        mean_corr=("correlation", lambda x: np.nanmean(x)),
        mean_runtime_ms=("runtime_s", lambda x: np.nanmean(x) * 1000),
    ).reset_index()

    method_grp = method_grp.sort_values(by="mean_f1", ascending=False)
    method_grp.to_csv(summary_csv, index=False)
    print(f"Summary saved: {summary_csv}")

    print("\n" + "─" * 90)
    print("MASTER SUMMARY PERFORMANCE ACROSS EVALUATED DATASET")
    print("─" * 90)
    print(f"{'Method':28s} {'Mode':15s} {'Evals':6s} {'Mean F1 (%)':12s} {'Min-Max F1':14s} {'Mean Se':10s} {'Mean Corr':10s} {'Runtime':10s}")
    print("─" * 90)
    for _, r in method_grp.iterrows():
        print(f"{r['method']:28s} {r['mode']:15s} {int(r['n_evals']):6d} {r['mean_f1']:6.2f} ± {r['std_f1']:4.1f}   [{r['min_f1']:4.1f} - {r['max_f1']:4.1f}]%  {r['mean_se']:6.1f}%    {r['mean_corr']:6.3f}    {r['mean_runtime_ms']:6.1f}ms")
    print("─" * 90)

    # 2. Generate Publication Comparison Figures
    pdir = Path(plots_dir)

    # Figure A: Overall F1 Boxplot / Bar by Method
    fig, ax = plt.subplots(figsize=(8, 4.5))
    methods = method_grp["method"].tolist()
    means = method_grp["mean_f1"].tolist()
    stds = method_grp["std_f1"].tolist()
    colors = ["#1b9e77" if "Spatial" in m else ("#d95f02" if "UNet" in m else "#7570b3") for m in methods]

    bars = ax.barh(range(len(methods)), means, xerr=stds, color=colors, edgecolor="black", alpha=0.85, height=0.6, capsize=3)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels(methods, fontsize=8)
    ax.set_xlabel("Mean F1-Score (%) [± 1 Std]", fontsize=9, fontweight="bold")
    ax.set_title("FECGSYNDB Complete Benchmark: Overall Method Performance", fontsize=11, fontweight="bold")
    ax.set_xlim(0, 110)
    ax.invert_yaxis()
    ax.grid(axis="x", linestyle="--", alpha=0.4)

    for i, (m_val, std_val) in enumerate(zip(means, stds)):
        ax.text(m_val + 2, i, f"{m_val:.1f}%", va="center", fontsize=7.5, fontweight="bold")

    fig.tight_layout()
    fig.savefig(pdir / "mega_f1_by_method.png", dpi=300)
    plt.close()
    print(f"Saved: {pdir / 'mega_f1_by_method.png'}")

    # Figure B: F1 vs SNR Degradation
    fig, ax = plt.subplots(figsize=(6, 4))
    snr_method = df.groupby(["snr_db", "method"])["f1"].mean().unstack() * 100
    for col in snr_method.columns:
        ax.plot(snr_method.index, snr_method[col], marker="o", label=col, linewidth=1.5)
    ax.set_xlabel("Input SNR (dB)", fontsize=9, fontweight="bold")
    ax.set_ylabel("Mean F1-Score (%)", fontsize=9, fontweight="bold")
    ax.set_title("Algorithm Robustness Across SNR (0 dB to 12 dB)", fontsize=11, fontweight="bold")
    ax.set_xticks(sorted(df["snr_db"].unique()))
    ax.set_ylim(0, 108)
    ax.legend(bbox_to_anchor=(1.04, 1), loc="upper left", fontsize=7)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(pdir / "mega_snr_degradation.png", dpi=300)
    plt.close()
    print(f"Saved: {pdir / 'mega_snr_degradation.png'}")

    # Figure C: Case Breakdown (c0 to c4)
    fig, ax = plt.subplots(figsize=(7, 4))
    case_method = df.groupby(["case_id", "method"])["f1"].mean().unstack() * 100
    case_labels = {
        "c0": "c0\n(Normal)",
        "c1": "c1\n(Movement)",
        "c2": "c2\n(Mod Noise)",
        "c3": "c3\n(Uterine)",
        "c4": "c4\n(Arrhythmia)",
    }
    case_method.index = [case_labels.get(i, i) for i in case_method.index]
    case_method.plot(kind="bar", ax=ax, width=0.8, edgecolor="black", linewidth=0.3)
    ax.set_ylabel("Mean F1-Score (%)", fontsize=9, fontweight="bold")
    ax.set_title("Performance Breakdown by Clinical Case Type", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 115)
    ax.legend(bbox_to_anchor=(1.04, 1), loc="upper left", fontsize=6.5)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(pdir / "mega_case_breakdown.png", dpi=300)
    plt.close()
    print(f"Saved: {pdir / 'mega_case_breakdown.png'}")

    # Figure D: Subject Consistency (sub01 to sub10)
    fig, ax = plt.subplots(figsize=(7, 4))
    sub_method = df.groupby(["sub_id", "method"])["f1"].mean().unstack() * 100
    sub_method.plot(kind="bar", ax=ax, width=0.8, edgecolor="black", linewidth=0.3)
    ax.set_ylabel("Mean F1-Score (%)", fontsize=9, fontweight="bold")
    ax.set_title("Cross-Subject Generalization Consistency (sub01 to sub10)", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 115)
    ax.legend(bbox_to_anchor=(1.04, 1), loc="upper left", fontsize=6.5)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(pdir / "mega_subject_consistency.png", dpi=300)
    plt.close()
    print(f"Saved: {pdir / 'mega_subject_consistency.png'}")


# ──────────────────────────────────────────────────────────────────────────────
# Command-Line Interface
# ──────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive Mega Benchmark Suite for FECGSYNDB Non-Invasive Fetal ECG Extraction."
    )
    parser.add_argument("--data-dir", type=str, default="data/FECGSD/DESTINATION", help="Dataset directory")
    parser.add_argument("--subs", nargs="+", default=ALL_SUBS, help="List of subjects to evaluate (default: all 10)")
    parser.add_argument("--snrs", nargs="+", default=ALL_SNRS, help="List of SNRs to evaluate (default: all 5)")
    parser.add_argument("--cases", nargs="+", default=ALL_CASES, help="List of cases to evaluate (default: c0..c4)")
    parser.add_argument("--layout", type=str, default=DEFAULT_LAYOUT, help="Electrode layout (default: l1)")
    parser.add_argument("--channels", nargs="+", type=int, default=DEFAULT_CHANNELS_4CH, help="4-channel indices")
    parser.add_argument("--single-channel", type=int, default=DEFAULT_CHANNEL_1CH, help="1-channel index (default: 27)")
    parser.add_argument("--include-swt", action="store_true", help="Include SWT-LMS filter (warning: slow)")
    parser.add_argument("--device", type=str, default="cuda" if torch and torch.cuda.is_available() else "cpu")
    parser.add_argument("--output-csv", type=str, default="code/results/mega_benchmark_results.csv")
    parser.add_argument("--summary-csv", type=str, default="code/results/mega_benchmark_summary.csv")
    parser.add_argument("--plots-dir", type=str, default="code/results/plots/mega_benchmark")
    parser.add_argument("--max-cases", type=int, default=None, help="Max test cases for smoke testing")
    parser.add_argument("--no-resume", action="store_true", help="Do not resume; start fresh CSV")

    args = parser.parse_args()

    run_mega_benchmark(
        data_dir=args.data_dir,
        subs=args.subs,
        snrs=args.snrs,
        cases=args.cases,
        layout=args.layout,
        channels_4ch=args.channels,
        single_channel=args.single_channel,
        include_swt=args.include_swt,
        device=args.device,
        output_csv=args.output_csv,
        summary_csv=args.summary_csv,
        plots_dir=args.plots_dir,
        max_cases=args.max_cases,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()

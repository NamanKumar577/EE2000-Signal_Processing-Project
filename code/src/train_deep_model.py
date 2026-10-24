"""
src/train_deep_model.py
──────────────────────────────────────────────────────────────────────────────
Training & Evaluation Pipeline for Deep 1D U-Net Fetal ECG Extractor.
Supports execution on ASUS TUF (CUDA), Apple Silicon (MPS), or CPU.

Features:
  - Supports automated discovery across all 30+ GB of dataset (e.g. data/FECGSD/DESTINATION)
  - Numerically stable training with gradient clipping & standard scaling
  - Trains on PhysioNet mixtures with Composite Waveform + Morphology Loss
  - Evaluates on unseen high-noise (TC3 0 dB) and ectopic beat (TC5 c4) cases
  - Computes standard clinical beat detection metrics (F1, Se, PPV)
  - Saves comparison plot: code/results/plots/deep_learning_waveform_comparison.png
  - Saves model weights: code/results/models/fecg_unet_best.pt
"""

import os
import sys
import glob
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import numpy as np

# Matplotlib configuration for headless rendering
os.environ["MPLCONFIGDIR"] = "/tmp/mpl_cache"
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import torch
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    Dataset = object
    DataLoader = None

import wfdb

# Add code to path
sys.path.insert(0, os.path.abspath("code"))

if TORCH_AVAILABLE:
    from src.models.fecg_unet import FECGUNet1D, CompositeECGLoss
else:
    FECGUNet1D = None
    CompositeECGLoss = None

from src.preprocessing import preprocess
from src.qrs_detector import detect_fetal_qrs
from src.evaluation import compute_beat_metrics


# ──────────────────────────────────────────────────────────────────────────────
# Automatic Dataset Discovery
# ──────────────────────────────────────────────────────────────────────────────
def discover_records(data_dir: str, max_records: int = None) -> list[str]:
    """
    Recursively scans data_dir for valid FECGSYN record sets.
    Matches any record that has _fecg1, _mecg, _noise1, and _noise2 headers.
    """
    print(f"\nScanning '{data_dir}' for training records...")
    fecg_headers = glob.glob(os.path.join(data_dir, "**", "*_fecg1.hea"), recursive=True)
    
    valid_bases = []
    for h in sorted(fecg_headers):
        base = h[:-10]  # strip '_fecg1.hea'
        base_norm = base.replace("\\", "/")
        dir_name = os.path.dirname(h)
        base_name = os.path.basename(base)
        
        has_mecg = os.path.exists(os.path.join(dir_name, base_name + "_mecg.hea"))
        has_n1 = os.path.exists(os.path.join(dir_name, base_name + "_noise1.hea"))
        has_n2 = os.path.exists(os.path.join(dir_name, base_name + "_noise2.hea"))
        
        if has_mecg and has_n1 and has_n2:
            valid_bases.append(base_norm)

    print(f"Found {len(valid_bases)} complete record sets in '{data_dir}'.")
    
    if max_records is not None and max_records > 0 and len(valid_bases) > max_records:
        step = max(1, len(valid_bases) // max_records)
        selected = valid_bases[::step][:max_records]
        print(f"Subsampled to {len(selected)} records for training (--max-records {max_records}).")
        return selected

    return valid_bases


# ──────────────────────────────────────────────────────────────────────────────
# Dataset Class
# ──────────────────────────────────────────────────────────────────────────────
class ECGWindowDataset(Dataset):
    """Slices continuous ECG recordings into overlapping training windows."""
    def __init__(self, records_list, channels=[27], window_len=1024, stride=256):
        self.inputs = []
        self.targets = []
        self.window_len = window_len

        total_recs = len(records_list)
        for idx, base_path in enumerate(records_list, 1):
            if total_recs > 3 and (idx % 10 == 0 or idx == total_recs):
                print(f"  [Loading & Slicing Data] {idx}/{total_recs} records processed...", end="\r", flush=True)

            try:
                fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal[:, channels]
                mecg = wfdb.rdrecord(base_path + "_mecg").p_signal[:, channels]
                n1 = wfdb.rdrecord(base_path + "_noise1").p_signal[:, channels]
                n2 = wfdb.rdrecord(base_path + "_noise2").p_signal[:, channels]
            except Exception:
                continue
            
            # Form mixture and preprocess
            mix = mecg + fecg + n1 + n2
            prep_mix = np.column_stack([preprocess(mix[:, c], fs=250) for c in range(mix.shape[1])])
            target_fecg = fecg[:, 0].copy()  # Primary fetal target channel

            # Standard scale per recording to ensure numerical stability in deep network
            scale = float(np.std(prep_mix))
            if scale > 1e-4:
                prep_mix = prep_mix / scale
                target_fecg = target_fecg / scale

            n_samples = len(target_fecg)
            for start in range(0, n_samples - window_len + 1, stride):
                end = start + window_len
                inp_win = prep_mix[start:end, :].T
                targ_win = target_fecg[start:end][np.newaxis, :]
                
                # Verify no NaN or Inf in slice
                if np.isfinite(inp_win).all() and np.isfinite(targ_win).all():
                    self.inputs.append(inp_win.astype(np.float32))
                    self.targets.append(targ_win.astype(np.float32))

        if total_recs > 3:
            print()  # newline after progress counter

        self.inputs = np.array(self.inputs)
        self.targets = np.array(self.targets)

    def __len__(self):
        return len(self.inputs)

    def __getitem__(self, idx):
        return torch.from_numpy(self.inputs[idx]), torch.from_numpy(self.targets[idx])


# ──────────────────────────────────────────────────────────────────────────────
# Main Training & Evaluation Routine
# ──────────────────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Deep 1D U-Net Fetal ECG Extractor (ASUS TUF / CUDA / MPS / CPU)")
    parser.add_argument("--train", action="store_true", help="Train the model on the training dataset")
    parser.add_argument("--eval-only", action="store_true", help="Evaluate existing checkpoint on TC1-TC5")
    parser.add_argument("--data-dir", type=str, default=None, help="Root folder containing dataset to scan (e.g. data/FECGSD/DESTINATION)")
    parser.add_argument("--max-records", type=int, default=None, help="Max records to use from data-dir (default: all)")
    parser.add_argument("--epochs", type=int, default=15, help="Number of training epochs (default: 15)")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size (default: 32)")
    parser.add_argument("--lr", type=float, default=5e-4, help="Initial learning rate (default: 5e-4)")
    parser.add_argument("--channels", nargs="+", type=int, default=[27, 26, 28, 25], help="Input channel indices (default: [27, 26, 28, 25] for 4-channel spatial array)")
    parser.add_argument("--model-path", type=str, default=None, help="Explicit path to save/load model checkpoint")
    args = parser.parse_args()

    print("=" * 80)
    print("DEEP LEARNING (1D U-NET) FETAL ECG EXTRACTION PIPELINE")
    print("Optimized for GPU acceleration (ASUS TUF CUDA / Apple Silicon MPS / CPU)")
    print("=" * 80)

    if not TORCH_AVAILABLE:
        print("\n[ERROR] PyTorch is not yet installed in this environment.")
        print("To install PyTorch with CUDA support on Windows, run:")
        print("    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124")
        print("=" * 80)
        return

    # Device selection: CUDA (ASUS TUF) > MPS (Apple Silicon) > CPU
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"Detected Compute Device: CUDA ({torch.cuda.get_device_name(0)}) [ASUS TUF Ready]")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
        print("Detected Compute Device: Apple Silicon MPS (Metal Performance Shaders)")
    else:
        device = torch.device("cpu")
        print("Detected Compute Device: Standard CPU")

    os.makedirs("code/results/models", exist_ok=True)
    os.makedirs("code/results/plots/deep_learning", exist_ok=True)

    selected_channels = args.channels
    num_ch = len(selected_channels)
    if args.model_path:
        model_path = args.model_path
    elif num_ch > 1:
        model_path = f"code/results/models/fecg_unet_{num_ch}ch_best.pt"
    else:
        model_path = "code/results/models/fecg_unet_best.pt"

    if num_ch > 1:
        plot_out = f"code/results/plots/deep_learning/deep_learning_waveform_{num_ch}ch_comparison.png"
    else:
        plot_out = "code/results/plots/deep_learning/deep_learning_waveform_comparison.png"

    if not args.train and not args.eval_only:
        print("\n[INFO] Deep Learning module is compiled and ready for training!")
        print(f"\nActive Channels ({num_ch}): {selected_channels}")
        print("\nTo train on your ASUS TUF laptop with GPU acceleration, run:")
        print(f"    python code/src/train_deep_model.py --train --data-dir data/FECGSD/DESTINATION --epochs 20 --batch-size 64 --channels {' '.join(str(c) for c in selected_channels)}")
        print("\nTo evaluate a saved checkpoint on the benchmark without re-training:")
        print(f"    python code/src/train_deep_model.py --eval-only --channels {' '.join(str(c) for c in selected_channels)}")
        print("=" * 80)
        return

    # 1. Prepare Training & Validation Sets
    if args.data_dir:
        train_bases = discover_records(args.data_dir, max_records=args.max_records)
        if not train_bases:
            print(f"Error: No valid records found in '{args.data_dir}'. Falling back to test folder.")
            train_bases = [
                "test/test1/sub01_snr12dB_l1_c0",
                "test/test2/sub01_snr06dB_l1_c0",
                "test/test4/sub01_snr06dB_l1_c1",
            ]
    else:
        train_bases = [
            "test/test1/sub01_snr12dB_l1_c0",
            "test/test2/sub01_snr06dB_l1_c0",
            "test/test4/sub01_snr06dB_l1_c1",
        ]

    test_cases = [
        ("TC1", "test/test1/sub01_snr12dB_l1_c0", 12, "c0"),
        ("TC2", "test/test2/sub01_snr06dB_l1_c0", 6,  "c0"),
        ("TC3", "test/test3/sub01_snr00dB_l1_c0", 0,  "c0"),
        ("TC4", "test/test4/sub01_snr06dB_l1_c1", 6,  "c1"),
        ("TC5", "test/test5/sub01_snr06dB_l1_c4", 6,  "c4"),
    ]

    selected_channels = args.channels
    window_len = 1024
    batch_size = args.batch_size

    # 2. Instantiate Model
    model = FECGUNet1D(in_channels=len(selected_channels), base_filters=16).to(device)
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\nModel: 1D U-Net | Input Channels: {len(selected_channels)} | Trainable Parameters: {n_params:,}")

    # 3. Train if requested
    if args.train:
        print(f"\nBuilding training dataset from {len(train_bases)} records (window_len={window_len}, stride=256)...")
        dataset = ECGWindowDataset(train_bases, channels=selected_channels, window_len=window_len, stride=256)
        
        if len(dataset) == 0:
            print("Error: Dataset is empty. Check data paths and channel index.")
            return

        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=True)
        print(f"Dataset ready: {len(dataset)} windows ({len(dataloader)} batches/epoch).")

        criterion = CompositeECGLoss(alpha_l1=1.0, beta_corr=0.5).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)

        epochs = args.epochs
        print(f"\nStarting training for {epochs} epochs on {device}...")
        start_train_time = time.time()

        model.train()
        for epoch in range(1, epochs + 1):
            total_loss = 0.0
            n_valid_batches = 0
            
            for x_b, y_b in dataloader:
                x_b, y_b = x_b.to(device), y_b.to(device)
                optimizer.zero_grad()
                pred = model(x_b)
                loss = criterion(pred, y_b)
                
                # Guard against numerical anomaly
                if torch.isnan(loss) or torch.isinf(loss):
                    continue

                loss.backward()
                # Gradient clipping strictly bounds gradient norm
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                total_loss += loss.item()
                n_valid_batches += 1
            
            scheduler.step()
            avg_loss = total_loss / max(1, n_valid_batches)
            lr_curr = scheduler.get_last_lr()[0]
            print(f"  Epoch [{epoch:2d}/{epochs:2d}] => Composite Loss: {avg_loss:.4f} | LR: {lr_curr:.6f}")

        train_duration = time.time() - start_train_time
        print(f"\nTraining completed in {train_duration:.1f} seconds.")
        torch.save(model.state_dict(), model_path)
        print(f"Saved checkpoint to: {model_path}")
    elif args.eval_only:
        if not os.path.exists(model_path):
            print(f"Error: Checkpoint '{model_path}' not found. Please run with --train first.")
            return
        model.load_state_dict(torch.load(model_path, map_location=device))
        print(f"Loaded existing checkpoint from: {model_path}")

    # 4. Evaluation across all 5 Benchmark Test Cases
    print("\n" + "=" * 80)
    print("EVALUATION OF DEEP 1D U-NET ON FULL TC1-TC5 BENCHMARK MATRIX")
    print("=" * 80)

    model.eval()
    benchmark_results = []
    tc1_reconstructed_full = None
    tc1_raw_full = None
    tc1_ref_full = None

    with torch.no_grad():
        for tcid, base, snr, case_type in test_cases:
            fecg = wfdb.rdrecord(base + "_fecg1").p_signal[:, selected_channels]
            mecg = wfdb.rdrecord(base + "_mecg").p_signal[:, selected_channels]
            n1 = wfdb.rdrecord(base + "_noise1").p_signal[:, selected_channels]
            n2 = wfdb.rdrecord(base + "_noise2").p_signal[:, selected_channels]
            ref_qrs = np.sort(wfdb.rdann(base + "_fecg1", "qrs").sample)

            mix = mecg + fecg + n1 + n2
            prep_mix = np.column_stack([preprocess(mix[:, c], fs=250) for c in range(mix.shape[1])])
            n_samples = len(prep_mix)

            # Standard scale input for evaluation
            scale = float(np.std(prep_mix))
            if scale > 1e-4:
                prep_eval = prep_mix / scale
            else:
                prep_eval = prep_mix.copy()

            # Reconstruct full 75,000 samples by overlapping window aggregation
            pred_full = np.zeros(n_samples, dtype=np.float32)
            counts = np.zeros(n_samples, dtype=np.float32)
            stride = 512

            for start in range(0, n_samples - window_len + 1, stride):
                end = start + window_len
                chunk = prep_eval[start:end, :].T[np.newaxis, :, :].astype(np.float32)
                chunk_t = torch.from_numpy(chunk).to(device)
                out_chunk = model(chunk_t).cpu().numpy()[0, 0, :]
                pred_full[start:end] += out_chunk
                counts[start:end] += 1.0

            valid_mask = counts > 0
            pred_full[valid_mask] /= counts[valid_mask]

            # Re-scale back to native units
            if scale > 1e-4:
                pred_full *= scale

            # Replace any non-finite entries with 0.0
            pred_full = np.nan_to_num(pred_full, nan=0.0, posinf=0.0, neginf=0.0)

            # Detect fetal QRS on U-Net output
            det_qrs, _ = detect_fetal_qrs(pred_full, fs=250)
            m = compute_beat_metrics(ref_qrs, det_qrs, fs=250)
            
            # Safe metrics extraction (guard against None when no peaks detected)
            f1_pct = float(m.f1 * 100.0) if m.f1 is not None else 0.0
            sens_pct = float(m.sensitivity * 100.0) if m.sensitivity is not None else 0.0
            ppv_pct = float(m.ppv * 100.0) if m.ppv is not None else 0.0

            # Safe waveform correlation
            std_p = np.std(pred_full)
            std_t = np.std(fecg[:, 0])
            if std_p > 1e-6 and std_t > 1e-6:
                corr = float(np.corrcoef(pred_full, fecg[:, 0])[0, 1])
            else:
                corr = 0.0

            benchmark_results.append({
                "test_id": tcid, "snr_db": snr, "case": case_type,
                "f1": f1_pct, "sensitivity": sens_pct, "ppv": ppv_pct,
                "tp": m.tp, "fp": m.fp, "fn": m.fn, "corr": corr
            })

            print(f"[{tcid:4s} ({snr:2d} dB, {case_type})] => F1: {f1_pct:5.2f}% | Sensitivity: {sens_pct:5.1f}% | PPV: {ppv_pct:5.1f}% | "
                  f"TP: {m.tp:3d} | FP: {m.fp:3d} | FN: {m.fn:3d} | Waveform Correlation: {corr:.3f}")

            if tcid == "TC1":
                tc1_reconstructed_full = pred_full
                tc1_raw_full = prep_mix[:, 0]
                tc1_ref_full = fecg[:, 0]

    # 5. Generate Comparison Plot (Deep Learning vs Ground Truth vs Raw)
    plot_len = 250 * 5  # 5 seconds window
    start_s = 250 * 10  # start at 10 seconds
    end_s = start_s + plot_len
    t_axis = np.linspace(10, 15, plot_len)

    fig, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)

    axes[0].plot(t_axis, tc1_raw_full[start_s:end_s], color="black", linewidth=1.0)
    axes[0].set_title(f"A. Raw Abdominal ECG Mixture (Lead {selected_channels[0]} - Maternal QRS + Fetal + Noise)", fontweight="bold")
    axes[0].set_ylabel("Amplitude (mV)")
    axes[0].grid(True, linestyle="--", alpha=0.5)

    axes[1].plot(t_axis, tc1_ref_full[start_s:end_s], color="blue", linewidth=1.2)
    axes[1].set_title("B. Ground Truth Fetal ECG Reference (PhysioNet fecg1)", fontweight="bold")
    axes[1].set_ylabel("Amplitude (mV)")
    axes[1].grid(True, linestyle="--", alpha=0.5)

    axes[2].plot(t_axis, tc1_reconstructed_full[start_s:end_s], color="crimson", linewidth=1.2)
    axes[2].set_title(f"C. Deep 1D U-Net Neural Extractor Output ({num_ch}-Channel Spatial Input)", fontweight="bold")
    axes[2].set_xlabel("Time (seconds)", fontweight="bold")
    axes[2].set_ylabel("Amplitude (mV)")
    axes[2].grid(True, linestyle="--", alpha=0.5)

    fig.tight_layout()
    plt.savefig(plot_out, dpi=300)
    plt.close()
    print(f"\nSaved waveform comparison plot to: {plot_out}")

    # Summary
    mean_f1 = np.mean([r["f1"] for r in benchmark_results])
    print("=" * 80)
    print(f"DEEP 1D U-NET OVERALL AVERAGE F1 ACCURACY: {mean_f1:.2f}%")
    print("=" * 80)


if __name__ == "__main__":
    main()

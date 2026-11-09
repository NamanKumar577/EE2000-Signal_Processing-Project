"""
Deep 1D U-Net (results/benchmarks/models/fecg_unet_4ch_best.pt) on the same records
and scorer as v2 / v3 (beats scored from 20 s, +-50 ms, FHR = median-5 of detections).

NOT causal: zero-phase preprocessing + 1024-sample (4 s) windows averaged with
overlap. Its training records are not recorded; FECGSYNDB scores may include
records it was trained on (sub01 TC1/TC2/TC4 at least).

  python eval_unet.py syn [--full]   FECGSYNDB (every 7th record, or all 1,248)
  python eval_unet.py ad             ADFECGDB (5 real recordings, scalp-electrode reference)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import harness as H  # noqa: E402
from fecg.models.fecg_unet import FECGUNet1D  # noqa: E402
from src.preprocessing import preprocess  # noqa: E402
from src.qrs_detector import detect_fetal_qrs  # noqa: E402

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL = FECGUNet1D(in_channels=4, base_filters=16).to(DEV)
MODEL.load_state_dict(torch.load(ROOT / "results/benchmarks/models/fecg_unet_4ch_best.pt", map_location=DEV))
MODEL.eval()
WIN, STRIDE = 1024, 512


def fhr_median5(peaks, n):
    """Copy of fe3.fhr_median5 (fe3 needs numba, absent from the torch venv)."""
    fhr = np.zeros(n)
    buf = []
    for i in range(1, len(peaks)):
        rr = peaks[i] - peaks[i - 1]
        if 50 <= rr <= 300:
            buf = (buf + [rr])[-5:]
            fhr[peaks[i]:] = 60.0 * 250 / np.median(buf)
    return fhr


def unet_peaks(X):
    """X: (n, 4) device counts (3000 LSB/mV). Same normalisation and windowing as training eval."""
    mv = X / 3000.0
    prep = np.column_stack([preprocess(mv[:, c], fs=250) for c in range(4)])
    prep = prep / max(float(np.std(prep)), 1e-4)
    n = len(prep)
    out, cnt = np.zeros(n, np.float32), np.zeros(n, np.float32)
    starts = list(range(0, n - WIN + 1, STRIDE))
    if starts[-1] != n - WIN:
        starts.append(n - WIN)
    with torch.no_grad():
        batch = torch.from_numpy(np.stack([prep[s:s + WIN].T for s in starts]).astype(np.float32)).to(DEV)
        y = MODEL(batch).cpu().numpy()[:, 0]
    for s, w in zip(starts, y):
        out[s:s + WIN] += w
        cnt[s:s + WIN] += 1
    out = np.nan_to_num(out / np.maximum(cnt, 1))
    pk, _ = detect_fetal_qrs(out, fs=250)
    return np.asarray(pk, np.int64)


def scored(X, fq, extra):
    n = len(X)
    pk = unet_peaks(X)
    s = H.score(fq, pk, fhr_median5(pk, n), n, 5000)
    return {**extra, **{k: s[k] for k in ("f1", "se", "ppv", "fhr_mae", "tp", "fp", "fn")}}


def run_syn(full):
    recs = H.list_records() if full else H.list_records()[::7]
    rows = []
    for i, rec in enumerate(recs):
        d = H.load(rec)
        if d is not None:
            rows.append(scored(d["X"], d["fq"], {"rid": rec.rid, "sub": rec.sub, "cond": rec.cond}))
        if i % 50 == 0:
            print(f"{i}/{len(recs)}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "results_unet_syn.csv", index=False)
    b = pd.read_csv(HERE / "results_bitaccurate.csv").set_index("rid")
    print("U-Net :", df[["f1", "se", "ppv", "fhr_mae"]].mean().round(2).to_dict())
    print("  by cond:", df.groupby("cond").f1.mean().round(1).to_dict())
    print("  excl. sub01:", round(df[df["sub"] != "sub01"].f1.mean(), 2))
    print("v2 same records:", round(b.loc[df.rid, "f1"].mean(), 2), b.loc[df.rid].groupby("cond").f1.mean().round(1).to_dict())


def run_ad():
    import adfecgdb as A
    df = pd.DataFrame([scored(*A.load(r), {"record": r}) for r in A.RECORDS])
    df.to_csv(HERE / "results_unet_adfecgdb.csv", index=False)
    prev = pd.read_csv(HERE / "results_adfecgdb.csv").set_index("record")
    df = df.set_index("record").join(prev[["v2_f1", "hyb_f1"]])
    print(df[["f1", "se", "ppv", "fhr_mae", "v2_f1", "hyb_f1"]].round(1))
    print("mean:", df[["f1", "v2_f1", "hyb_f1"]].mean().round(1).to_dict())


if __name__ == "__main__":
    run_ad() if sys.argv[1] == "ad" else run_syn("--full" in sys.argv)

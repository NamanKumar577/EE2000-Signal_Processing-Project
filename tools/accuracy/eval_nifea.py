"""
Real clinical data (PhysioNet NIFEA): old frozen calibration vs v2 host
controller, both through the bit-accurate FPGA model.  NIFEA has no fetal
annotations -> surrogate metrics only (maternal coincidence via the independent
thoracic lead, physiological FHR fraction, RR variability).  First 10 minutes
of each of the 24 unique records (NR_13 == ARR_02, NR_14 == NR_07 dropped).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import wfdb
from scipy.signal import decimate, find_peaks, sosfilt, butter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import harness as H  # noqa: E402
from fecg.hardware.bit_accurate_reference import BitAccuratePipelineRunner, run_bit_accurate_pipeline_final  # noqa: E402
from fecg.host.adaptive_beamformer import plan_schedule  # noqa: E402

NIFEA = ROOT / "data" / "Non-Invasive_Fetal_ECG_Arrhythmia_Database" / "DESTINATION"
FS = 250
MAX_S = 600
SCORE0 = 5000
DUPES = {"NR_13", "NR_14"}


def load(rid):
    r = wfdb.rdrecord(str(NIFEA / rid))
    q = int(r.fs) // FS
    sig = r.p_signal[: int(MAX_S * r.fs)]
    sig = np.nan_to_num(sig)
    s250 = decimate(sig, q, ftype="iir", axis=0, zero_phase=False) if q > 1 else sig
    thor = s250[:, 0]
    X = s250[:, 1:5] * 3000.0          # same 3000 LSB/mV as FECGSYNDB
    return X, thor


def maternal_ref(thor):
    sos = butter(2, [8, 30], btype="band", fs=FS, output="sos")
    y = sosfilt(sos, thor)
    e = np.convolve(y * y, np.ones(30), mode="same")
    pk, _ = find_peaks(e, height=0.3 * np.percentile(e, 99.5), distance=75)
    return pk


def surrogate(peaks, fhr_x10, mpk, n):
    p = peaks[(peaks >= SCORE0) & (peaks < n)]
    if len(p) < 5:
        return {"beats_per_min": 0.0, "median_fhr": np.nan, "maternal_coinc_pct": np.nan,
                "fhr_110_160_pct": 0.0, "fhr_100_180_pct": 0.0, "rr_cv": np.nan}
    rr = np.diff(p)
    inst = 60.0 * FS / rr
    j = np.searchsorted(mpk, p)
    d = np.minimum(np.abs(p - mpk[np.clip(j - 1, 0, len(mpk) - 1)]), np.abs(p - mpk[np.clip(j, 0, len(mpk) - 1)]))
    rep = fhr_x10[SCORE0:n] / 10.0
    rep = rep[rep > 0]
    return {"beats_per_min": round(60.0 * len(p) / ((n - SCORE0) / FS), 1),
            "median_fhr": round(float(np.median(inst)), 1),
            "maternal_coinc_pct": round(100.0 * float(np.mean(d <= 13)), 1),
            "fhr_110_160_pct": round(100.0 * float(np.mean((rep >= 110) & (rep <= 160))), 1) if len(rep) else 0.0,
            "fhr_100_180_pct": round(100.0 * float(np.mean((rep >= 100) & (rep <= 180))), 1) if len(rep) else 0.0,
            "rr_cv": round(float(np.std(rr) / np.mean(rr)), 3)}


def one(rid):
    from fpga_implementation.uart_host.validate_real_datasets import HostSpatialCalibrator
    X, thor = load(rid)
    n = len(X)
    mpk = maternal_ref(thor)
    xq = np.clip(np.round(X), -32768, 32767).astype(np.int64)
    out = {"record": rid, "maternal_hr": round(60.0 * FS / float(np.median(np.diff(mpk))), 1)}
    # old: frozen autocorr calibrator on the first 10 s, weights from sample 0 (as previously reported)
    w, j, _, _ = HostSpatialCalibrator().calibrate(X[:2500], rule="autocorr")
    r_old = run_bit_accurate_pipeline_final(xq, w, latency=18)
    out.update({f"old_{k}": v for k, v in surrogate(np.asarray(r_old.peaks), r_old.fhr_hold, mpk, n).items()})
    # v2: causal host controller (0xC4 at 12 s, gated 0xC3), latency 13
    cmds = plan_schedule(X)
    r_new = BitAccuratePipelineRunner().process_block(xq, target_weights=[(c.t, c.w_q15, c.restart) for c in cmds])
    out.update({f"v2_{k}": v for k, v in surrogate(np.asarray(r_new.peaks), r_new.fhr_hold, mpk, n).items()})
    return out


if __name__ == "__main__":
    ids = sorted(p.stem for p in NIFEA.glob("*.hea") if p.stem not in DUPES)
    df = pd.DataFrame(H.run_parallel(one, ids, procs=12))
    df.to_csv(HERE / "results_nifea.csv", index=False)
    pd.set_option("display.width", 250)
    cols = ["record", "maternal_hr"] + [f"{a}_{k}" for k in ("median_fhr", "maternal_coinc_pct", "fhr_110_160_pct") for a in ("old", "v2")]
    print(df[cols].to_string(index=False))
    for a in ("old", "v2"):
        ok = (df[f"{a}_maternal_coinc_pct"] < 30) & (df[f"{a}_fhr_110_160_pct"] >= 70) & (df[f"{a}_median_fhr"].between(105, 180))
        print(a, "mean maternal coinc %.1f%%  mean in-range %.1f%%  plausible records %d/%d" % (
            df[f"{a}_maternal_coinc_pct"].mean(), df[f"{a}_fhr_110_160_pct"].mean(), ok.sum(), len(df)))

"""
Real clinical data WITH fetal annotations: PhysioNet/CinC Challenge 2013 set-a
(a01-a75, 60 s, 4 abdominal leads, 1 kHz, reference fetal QRS in .fqrs).

Protocol (same device timeline as FECGSYNDB):
  * 1 kHz -> 250 Hz with a causal anti-alias IIR (like an ADC front end), scaled
    to 3000 LSB/mV; annotations divided by 4.
  * old : frozen autocorr PCA calibration on the first 10 s applied from sample 0,
          latency 18 (the previously reported method)
    v2  : causal host controller (0xC4 at 12 s, gated 0xC3) + bit-exact model
  * beats scored from 20 s to the end (+-50 ms), FHR vs true FHR at every beat.
Records whose reference annotations are documented as unreliable in the
challenge literature are reported separately.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import wfdb
from scipy.signal import decimate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import harness as H  # noqa: E402
from fecg.hardware.bit_accurate_reference import BitAccuratePipelineRunner, run_bit_accurate_pipeline_final  # noqa: E402
from fecg.host.adaptive_beamformer import plan_schedule  # noqa: E402

BASE = ROOT / "data" / "noninvasive-fetal-ecg-the-physionet-computing-in-cardiology-challenge-2013-1.0.0" / "extracted"
UNRELIABLE = {"a33", "a38", "a47", "a52", "a54", "a71", "a74"}
SCORE0 = 5000


def rec_path(rid):
    for sub in ("set-a", "set-a-ext"):
        p = BASE / sub / rid
        if Path(str(p) + ".hea").exists():
            return p
    raise FileNotFoundError(rid)


def load(rid):
    p = rec_path(rid)
    r = wfdb.rdrecord(str(p))
    sig = np.nan_to_num(r.p_signal)            # microvolts
    q = int(r.fs) // 250
    s = decimate(sig, q, ftype="iir", axis=0, zero_phase=False)
    X = s * (3000.0 / 1000.0)                  # uV -> counts at 3000 LSB/mV
    fq = np.round(wfdb.rdann(str(p), "fqrs").sample / q).astype(np.int64)
    return X, fq


def one(rid):
    from fpga_implementation.uart_host.validate_real_datasets import HostSpatialCalibrator
    X, fq = load(rid)
    n = len(X)
    xq = np.clip(np.round(X), -32768, 32767).astype(np.int64)
    out = {"record": rid, "unreliable_ref": rid in UNRELIABLE,
           "clip_pct": round(100 * float(np.mean(np.abs(np.round(X)) > 32767)), 3)}
    w, j, _, _ = HostSpatialCalibrator().calibrate(X[:2500], rule="autocorr")
    r = run_bit_accurate_pipeline_final(xq, w, latency=18)
    s = H.score(fq, np.asarray(r.peaks), r.fhr_hold / 10.0, n, SCORE0)
    out.update({f"old_{k}": s[k] for k in ("tp", "fp", "fn", "f1", "se", "ppv", "fhr_mae")})
    cmds = plan_schedule(X)
    r = BitAccuratePipelineRunner().process_block(xq, target_weights=[(c.t, c.w_q15, c.restart) for c in cmds])
    s = H.score(fq, np.asarray(r.peaks), r.fhr_hold / 10.0, n, SCORE0)
    out.update({f"v2_{k}": s[k] for k in ("tp", "fp", "fn", "f1", "se", "ppv", "fhr_mae", "terr_mean")})
    out["v2_cmds"] = len(cmds)
    out["v2_sat"] = r.max_ranges["total_saturations"]
    return out


def summary(df, label):
    print(f"--- {label}: {len(df)} records")
    for a in ("old", "v2"):
        tp, fp, fn = df[f"{a}_tp"].sum(), df[f"{a}_fp"].sum(), df[f"{a}_fn"].sum()
        print(f"  {a:3s} mean F1 {df[f'{a}_f1'].mean():6.2f}  pooled F1 {200*tp/(2*tp+fp+fn):6.2f}  "
              f"Se {100*tp/(tp+fn):6.2f}  PPV {100*tp/(tp+fp):6.2f}  FHR MAE {df[f'{a}_fhr_mae'].mean():6.2f}  "
              f"median F1 {df[f'{a}_f1'].median():6.2f}  records>=95% {int((df[f'{a}_f1']>=95).sum())}")


if __name__ == "__main__":
    ids = [f"a{i:02d}" for i in range(1, 76)]
    df = pd.DataFrame(H.run_parallel(one, ids, procs=12))
    df.to_csv(HERE / "results_cinc2013.csv", index=False)
    pd.set_option("display.width", 220)
    print(df[["record", "unreliable_ref", "old_f1", "v2_f1", "v2_se", "v2_ppv", "v2_fhr_mae", "v2_terr_mean", "v2_cmds", "v2_sat"]]
          .round(1).to_string(index=False))
    summary(df, "all set-a (a01-a75)")
    summary(df[~df.unreliable_ref], "excluding 7 records with unreliable reference")

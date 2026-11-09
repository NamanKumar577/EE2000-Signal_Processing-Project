"""
Real data with an independent (scalp-electrode) fetal reference: PhysioNet ADFECGDB,
5 recordings x 5 min, 4 abdominal leads.  Same device timeline and scorer as
FECGSYNDB / CinC (0xC4 at 12 s, beats scored from 20 s, +-50 ms, FHR vs true FHR).

  v2     : host beamformer + bit-exact FPGA model (deployed design)
  hybrid : v3 prototype (fe3.system_hybrid)
  v4     : v3 + dynamic maternal-train selection + wider band (LP60, BP 15-40 Hz)
           + agreement-weighted candidate selection
  oracle : DIAGNOSTIC best single linear filter (uses labels) on raw / cancelled leads
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))
import harness as H  # noqa: E402
import fe3  # noqa: E402
import adfecgdb as A  # noqa: E402
import pipeline as P  # noqa: E402

SCORE0 = 5000
KEYS = ("tp", "fp", "fn", "f1", "se", "ppv", "fhr_mae")


def one(rid):
    from fecg.hardware.bit_accurate_reference import BitAccuratePipelineRunner
    from fecg.host.adaptive_beamformer import plan_schedule
    X, fq = A.load(rid)
    n = len(X)
    out = {"record": rid}
    xq = np.clip(np.round(X), -32768, 32767).astype(np.int64)
    cmds = plan_schedule(X)
    r = BitAccuratePipelineRunner().process_block(xq, target_weights=[(c.t, c.w_q15, c.restart) for c in cmds])
    s = H.score(fq, np.asarray(r.peaks), r.fhr_hold / 10.0, n, SCORE0)
    out.update({f"v2_{k}": s[k] for k in KEYS})
    (pk, fhr), _ = fe3.system_hybrid(X)
    s = H.score(fq, pk, fhr, n, SCORE0)
    out.update({f"hyb_{k}": s[k] for k in KEYS})
    P.set_band(P.V4_BAND)
    (pk, fhr), _ = fe3.system_hybrid(X, mat="dynamic", sel="both")
    s = H.score(fq, pk, fhr, n, SCORE0)
    out.update({f"v4_{k}": s[k] for k in KEYS})
    P.set_band(None)
    if "--oracle" in sys.argv:
        Xf = fe3.prefilter(X)
        w = fe3.oracle_filter(Xf, fq)
        out["orc_raw_f1"] = H.score(fq, *fe3.detect_on_lead(Xf @ w, 3127), n, SCORE0)["f1"]
        mpk, _ = fe3.maternal_peaks_robust(X)
        Z = fe3.cancel_maternal(Xf, mpk)
        w = fe3.oracle_filter(Z, fq)
        p, _ = fe3.track_beats(Z @ w, 3127, mpk=mpk)
        out["orc_canc_trk_f1"] = H.score(fq, p, fe3.fhr_median5(p, n), n, SCORE0)["f1"]
    return out


def summary(df, pre):
    tp, fp, fn = df[f"{pre}_tp"].sum(), df[f"{pre}_fp"].sum(), df[f"{pre}_fn"].sum()
    return (f"{pre:4s} mean F1 {df[f'{pre}_f1'].mean():6.2f}  pooled {200*tp/(2*tp+fp+fn):6.2f}  "
            f"Se {100*tp/(tp+fn):6.2f}  PPV {100*tp/(tp+fp):6.2f}  FHR MAE {df[f'{pre}_fhr_mae'].mean():6.2f}")


if __name__ == "__main__":
    df = pd.DataFrame(H.run_parallel(one, A.RECORDS, procs=5))
    df.to_csv(HERE / "results_adfecgdb.csv", index=False)
    pd.set_option("display.width", 220)
    print(df.round(1).to_string(index=False))
    for pre in ("v2", "hyb", "v4"):
        print(summary(df, pre))

"""Baseline: frozen bit-accurate model vs float mirror, old vs causal timeline."""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import harness as H  # noqa: E402
import pipeline as P  # noqa: E402

CAL_END = 512 + 1000  # calibrator uses samples [512, 1512)


def calib_frozen(Xprefix):
    from fpga_implementation.uart_host.validate_real_datasets import HostSpatialCalibrator
    w, j, conf, dbg = HostSpatialCalibrator().calibrate(Xprefix, rule="autocorr")
    return w, j


def run_float(X, w_q15, w_from, det_start, n):
    w = np.asarray(w_q15, float) / 32768.0
    W = np.zeros((n, X.shape[1]))
    W[:, 0] = 1.0                      # power-up unity bypass
    W[w_from:] = w
    proj = np.einsum("nc,nc->n", X, W)
    fe, bp = P.front_end(proj)
    e = P.mwi(bp * bp, 30)
    comp, raw, fhr = P.detect(np.abs(bp), e, det_start, 512, 50, 26, 18, 50, 300, 0, 1.66)
    return comp, fhr


def one(rec):
    d = H.load(rec)
    if d is None:
        return None
    X, fq, mq = d["X"], d["fq"], d["mq"]
    n = len(X)
    out = {"rid": rec.rid, "sub": rec.sub, "snr": rec.snr, "lay": rec.lay, "cond": rec.cond}
    w, j = calib_frozen(X[:2500])      # exactly what the old evaluation did (10 s buffer)
    out["pc"] = j
    # A: real bit-accurate model, old (non-causal) timeline, score from 512
    if BITACC:
        from fecg.hardware.bit_accurate_reference import run_bit_accurate_pipeline_final
        xq = np.clip(np.round(X), -32768, 32767).astype(np.int64)
        r = run_bit_accurate_pipeline_final(xq, w)
        fhr = r.fhr_hold / 10.0
        s = H.score(fq, np.asarray(r.peaks), fhr, n, 512, mq)
        out.update({f"A_{k}": v for k, v in s.items()})
    # B: float mirror, same old timeline
    comp, fhr = run_float(X, w, 0, 0, n)
    s = H.score(fq, comp, fhr, n, 512, mq)
    out.update({f"B_{k}": v for k, v in s.items()})
    # C: causal timeline. weights computed from samples seen so far, applied at CAL_END,
    #    detector warm-up NOT restarted (current RTL behaviour), score from CAL_END+512
    w2, _ = calib_frozen(X[:CAL_END])
    comp, fhr = run_float(X, w2, CAL_END, 0, n)
    s = H.score(fq, comp, fhr, n, CAL_END + 512, mq)
    out.update({f"C_{k}": v for k, v in s.items()})
    # D: causal timeline + detector warm-up restarted when the weights arrive
    comp, fhr = run_float(X, w2, CAL_END, CAL_END, n)
    s = H.score(fq, comp, fhr, n, CAL_END + 512, mq)
    out.update({f"D_{k}": v for k, v in s.items()})
    return out


BITACC = "--bitacc" in sys.argv

if __name__ == "__main__":
    recs = H.list_records()
    if "--quick" in sys.argv:
        recs = recs[::10]
    t0 = time.time()
    rows = [r for r in H.run_parallel(one, recs) if r is not None]
    df = pd.DataFrame(rows)
    tag = "bitacc" if BITACC else "float"
    df.to_csv(HERE / f"results_baseline_{tag}.csv", index=False)
    print(f"{len(df)} records, {time.time()-t0:.0f}s")
    cols = [c for c in df.columns if c.split("_", 1)[-1] in ("f1", "se", "ppv", "fhr_mae", "fhr_within5")]
    print(df[cols].mean().round(2).to_string())
    for v in ["B", "D"]:
        print(v, df.groupby("cond")[f"{v}_f1"].mean().round(2).to_dict())

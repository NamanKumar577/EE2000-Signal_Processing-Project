"""
Full-FECGSYNDB evaluation of the deployable system in FPGA-exact arithmetic:
  host  : src/fecg/host/adaptive_beamformer.py (streaming, causal, label-free)
  FPGA  : src/fecg/hardware/bit_accurate_reference.py (bit-exact golden model)
Timeline: power-up unity weights -> 0xC4 at 12 s -> 0xC3 updates every 2 s when
gated.  Beats scored from 20 s to the end of each 5-minute record.
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))
import harness as H  # noqa: E402
from fecg.host.adaptive_beamformer import plan_schedule  # noqa: E402
from fecg.hardware.bit_accurate_reference import BitAccuratePipelineRunner  # noqa: E402

SCORE0 = 5000


def one(rec):
    d = H.load(rec)
    if d is None:
        return None
    X, fq, mq = d["X"], d["fq"], d["mq"]
    n = len(X)
    cmds = plan_schedule(X)
    xq = np.clip(np.round(X), -32768, 32767).astype(np.int64)
    runner = BitAccuratePipelineRunner()
    res = runner.process_block(xq, target_weights=[(c.t, c.w_q15, c.restart) for c in cmds])
    s = H.score(fq, np.asarray(res.peaks), res.fhr_hold / 10.0, n, SCORE0, mq)
    out = {"rid": rec.rid, "sub": rec.sub, "snr": rec.snr, "lay": rec.lay, "cond": rec.cond,
           "n_cmds": len(cmds), "sat": res.max_ranges["total_saturations"],
           "ovf": res.max_ranges["total_state_overflows"]}
    out.update(s)
    return out


if __name__ == "__main__":
    recs = H.list_records()
    if "--quick" in sys.argv:
        recs = recs[::7]
    t0 = time.time()
    df = pd.DataFrame([r for r in H.run_parallel(one, recs) if r is not None])
    tag = "_quick" if "--quick" in sys.argv else ""
    df.to_csv(HERE / f"results_bitaccurate{tag}.csv", index=False)
    print(f"{len(df)} records, {time.time()-t0:.0f}s")
    print(df[["f1", "se", "ppv", "fhr_mae", "fhr_within5"]].mean().round(2).to_dict())
    tp, fp, fn = df.tp.sum(), df.fp.sum(), df.fn.sum()
    print("pooled Se %.2f PPV %.2f F1 %.2f" % (100 * tp / (tp + fn), 100 * tp / (tp + fp), 200 * tp / (2 * tp + fp + fn)))
    print(df.groupby("cond")[["f1", "fhr_mae"]].mean().round(2).T.to_string())
    print(df.groupby("snr")["f1"].mean().round(2).to_dict())
    print("records with saturation:", (df.sat > 0).sum(), " with overflow:", (df.ovf > 0).sum())

#!/usr/bin/env python3
"""
Physical evaluation of FECG v5 on the Spartan-7 board: the PC only streams the
recording (int16, 4 abdominal leads, 250 Hz) and logs what the board returns;
the whole algorithm runs on the FPGA (MicroBlaze + FPU, firmware fecg_v5.c).

For every record:
  * board beats/FHR are scored against the reference annotations (harness.score,
    same timeline as all other evaluations: scoring from 20 s, +-50 ms);
  * the same int16 stream is run through the PC build of the identical C source
    and the beat lists are compared (bit-exact check: t, fhr_x10, src).

Usage: python run_v5_board_eval.py --sets cdev,ad[,syn,ctest] [--port COM5] [--out DIR]
Outputs <out>/board_<sets>.csv (per record) and a summary print.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "accuracy"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness as H  # noqa: E402
import v5c  # noqa: E402
from devbench import _load, items  # noqa: E402
from v5_client import V5Board  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="cdev,ad")
    ap.add_argument("--port", default="COM5")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "report" / "night_20261109" / "board"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    board = V5Board(a.port)
    ident = board.ping()
    print("board:", ident, flush=True)
    rows = []
    its = items(a.sets.split(","))
    if a.limit:
        its = its[:a.limit]
    for item in its:
        d = _load(item)
        if d is None:
            continue
        X, fq = d
        n = len(X)
        rid = item[1] if isinstance(item[1], str) else item[1].rid
        xi = v5c.to_i16(X)
        t0 = time.perf_counter()
        board.reset()
        bb, cyc = board.run(xi)
        wall = time.perf_counter() - t0
        b_board = np.array([(t, int(round(f * 10)), s) for t, f, s, _ in bb], dtype=np.int64).reshape(-1, 3)
        b_pc = v5c.run_c(X)
        exact = (b_board.shape == b_pc.shape) and bool(np.all(b_board == b_pc))
        pk, fhr = v5c.beats_to_stream(b_board, n)
        r = H.score(fq, pk, fhr, n, 5000)
        row = {"set": item[0], "rid": rid, "f1": r["f1"], "se": r["se"], "ppv": r["ppv"],
               "fhr_mae": r["fhr_mae"], "n_beats": len(b_board), "bit_exact_vs_pc": exact,
               "n_pc": len(b_pc), "max_block_cycles": int(cyc.max()), "mean_cycles_per_sample": float(cyc.sum() / n),
               "stream_s": wall, "record_s": n / 250.0}
        rows.append(row)
        print(f"{item[0]:5s} {rid:24s} F1 {r['f1']:6.2f}  beats {len(b_board):4d}  exact {exact}  "
              f"cyc/sample {row['mean_cycles_per_sample']:8.0f}  {wall:5.1f}s for {n / 250:5.0f}s", flush=True)
    df = pd.DataFrame(rows)
    tag = a.sets.replace(",", "_")
    df.to_csv(out / f"board_{tag}.csv", index=False)
    summ = df.groupby("set").agg(f1=("f1", "mean"), se=("se", "mean"), ppv=("ppv", "mean"),
                                 fhr_mae=("fhr_mae", "mean"), records=("rid", "count"),
                                 bit_exact=("bit_exact_vs_pc", "mean"),
                                 cyc_per_sample=("mean_cycles_per_sample", "mean"),
                                 rt_factor=("record_s", "sum"))
    summ["rt_factor"] = summ["rt_factor"] / df.groupby("set")["stream_s"].sum()
    print(summ.round(3).to_string())
    (out / f"board_{tag}_summary.json").write_text(json.dumps({"board": ident, **{k: v for k, v in summ.round(4).to_dict("index").items()}}, indent=1))


if __name__ == "__main__":
    main()

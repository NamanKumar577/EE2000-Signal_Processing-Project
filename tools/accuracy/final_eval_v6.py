"""Evaluation of the v6 system model (bit-accurate RTL model + PC brain) on the same sets as
final_eval_pc.py.  Writes results_v6_<set>.csv.   python final_eval_v6.py synall cdev ad [ctest]"""
import sys
import pandas as pd
import harness as H
import v6c  # noqa: F401  (points v5c at the v6 model)
import v5c
from final_eval_pc import items

if __name__ == "__main__":
    for name in sys.argv[1:]:
        rows = [r for r in H.run_parallel(v5c.one, [(it, []) for it in items(name)], procs=14) if r]
        df = pd.DataFrame(rows)
        if name == "synall":
            df["cond"] = df.rid.str[-2:]
            df["snr"] = df.rid.str.extract(r"snr(\d+)dB")[0].astype(int)
        df.to_csv(f"results_v6_{name}.csv", index=False)
        print(name, len(df), df[["f1", "se", "ppv", "fhr_mae"]].mean().round(2).to_dict(), flush=True)
        if name == "synall":
            print(df.groupby("cond")[["f1", "fhr_mae"]].mean().round(2).to_string())

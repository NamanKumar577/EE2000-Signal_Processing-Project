"""Final PC evaluation of the frozen v5 C model (identical source to the FPGA firmware):
  full FECGSYNDB (all single-fetus records), CinC dev / held-out test, ADFECGDB.
Writes results_v5_final_<set>.csv."""
import sys
import pandas as pd
import harness as H
import fe3
import adfecgdb as A
import v5c


def items(name):
    if name == "synall":
        return [("syn", r) for r in H.list_records()]
    return {"cdev": [("cdev", r) for r in fe3.CINC_DEV], "ctest": [("ctest", r) for r in fe3.CINC_TEST],
            "ad": [("ad", r) for r in A.RECORDS]}[name]


if __name__ == "__main__":
    for name in sys.argv[1:]:
        rows = [r for r in H.run_parallel(v5c.one, [(it, []) for it in items(name)], procs=14) if r]
        df = pd.DataFrame(rows)
        if name == "synall":
            df["cond"] = df.rid.str[-2:]
            df["snr"] = df.rid.str.extract(r"snr(\d+)dB")[0].astype(int)
        df.to_csv(f"results_v5_final_{name}.csv", index=False)
        print(name, len(df), df[["f1", "se", "ppv", "fhr_mae"]].mean().round(2).to_dict(), flush=True)
        if name == "synall":
            print(df.groupby("cond")[["f1", "fhr_mae"]].mean().round(2).to_string())

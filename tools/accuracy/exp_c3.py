import sys, numpy as np, pandas as pd
import harness as H, exp_cinc as E, calib3 as C3
from fecg.host import adaptive_beamformer as AB
def one(rid):
    X,fq=E.load(rid); n=len(X)
    w,_=AB.calibrate(X[:3000]); w3,info=C3.calibrate3(X[:3000])
    f=lambda w: H.score(fq,*E.run_static(X,w,n),n,5000)["f1"]
    return dict(record=rid, unreliable=rid in E.UNRELIABLE, v2=f(w), v3=f(w3), oracle=f(E.oracle_w(X,fq+14,n)), rule=info["rule"])
if __name__=="__main__":
    df=pd.DataFrame(H.run_parallel(one,[f"a{i:02d}" for i in range(1,76)],procs=12))
    df.to_csv("results_c3_cinc.csv",index=False)
    print(df[["v2","v3","oracle"]].mean().round(2).to_dict(), "reliable", df[~df.unreliable][["v2","v3","oracle"]].mean().round(2).to_dict())
    print(df.rule.value_counts().to_dict(), " v3>=90:", (df.v3>=90).sum(), " oracle>=90:", (df.oracle>=90).sum())

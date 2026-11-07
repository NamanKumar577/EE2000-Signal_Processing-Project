"""Collect per-candidate features + F1 (for offline comparison of selection rules)."""
import sys, numpy as np, pandas as pd, harness as H, fe3
from eval_cinc2013 import load
def one(rid):
    X,fq=load(rid); n=len(X); Xf=fe3.prefilter(X); mpk,_=fe3.maternal_peaks_robust(X)
    Z=fe3.cancel_maternal(Xf,mpk,ncomp=3); rows=[]
    for k,w in enumerate(fe3.candidates_residual(Z,mpk,750,3750)):
        pk,fh=fe3.track_beats(fe3.project(Z,w,3750),3877,mpk=mpk)
        r=dict(record=rid,cand=k,f1=H.score(fq,pk,fh,n,5000)["f1"],q=fe3.tracker_quality(Z@w,mpk,1262,3750))
        r.update(fe3.candidate_features(Z@w,mpk,1262,3750)); rows.append(r)
    return rows
if __name__=="__main__":
    split="test" if "--test" in sys.argv else "dev"
    ids=fe3.CINC_TEST if split=="test" else fe3.CINC_DEV
    df=pd.DataFrame([r for rr in H.run_parallel(one,ids,procs=12) for r in rr]); df.to_csv(f"cands_{split}.csv",index=False); print(len(df))

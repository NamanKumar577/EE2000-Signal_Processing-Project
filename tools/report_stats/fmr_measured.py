#!/usr/bin/env python3
"""
Measured fetal/maternal amplitudes and FMR on the FECGSYNDB training subjects (sub01-sub07, snr12dB, l1, c0;
the separate fecg1 and mecg signals do not depend on the noise level). Reads data/FECGSD/DESTINATION.
Outputs tools/report_stats/out/fmr_measured.csv (per lead) and out/amplitude_measured.csv (summary).

  FMR per lead = RMS(fecg1) / RMS(mecg), mean over the 7 subjects   (Fig. fmr_topography, Sec. 1)
  peak-to-peak amplitude = median over beats of (max - min) in a +-50 ms window around each annotated R peak,
  per subject on its 32 abdominal leads, then mean over leads and subjects; reported for the maternal and the fetal signal.

    venv/Scripts/python.exe tools/report_stats/fmr_measured.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import wfdb

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/FECGSD/DESTINATION"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
W = 12  # +-50 ms at 250 Hz

fmr, amp_m, amp_f = [], [], []
for s in range(1, 8):
    r = str(BASE / f"sub{s:02d}/snr12dB/sub{s:02d}_snr12dB_l1_c0")
    f = wfdb.rdrecord(r + "_fecg1").p_signal
    m = wfdb.rdrecord(r + "_mecg").p_signal
    fmr.append(np.sqrt((f ** 2).mean(0)) / np.sqrt((m ** 2).mean(0)))
    for sig, ext, store in ((m, "_mecg", amp_m), (f, "_fecg1", amp_f)):
        pk = wfdb.rdann(r + ext, "qrs").sample
        pk = pk[(pk > W) & (pk < len(sig) - W)]
        seg = np.stack([sig[p - W:p + W + 1, :32] for p in pk])           # beats x window x leads
        store.append(np.median(seg.max(1) - seg.min(1), axis=0).mean())   # median over beats, mean over leads
F = np.array(fmr)
pd.DataFrame({"lead": np.arange(F.shape[1]), "fmr_mean": F.mean(0)}).to_csv(OUT / "fmr_measured.csv", index=False, float_format="%.4f")
m_pp, f_pp = np.mean(amp_m), np.mean(amp_f)
ab = F.mean(0)[:32]
summ = pd.DataFrame([dict(maternal_pp_mV=m_pp, fetal_pp_mV=f_pp, ratio=m_pp / f_pp, ratio_dB=20 * np.log10(m_pp / f_pp),
                          fmr_min=ab.min(), fmr_max=ab.max(), fmr_min_dB=20 * np.log10(ab.min()), fmr_max_dB=20 * np.log10(ab.max()),
                          top_lead=int(np.argmax(ab)), top_fmr=ab.max())])
summ.to_csv(OUT / "amplitude_measured.csv", index=False, float_format="%.4f")
print(summ.round(3).to_string(index=False))

"""Loader for PhysioNet ADFECGDB (5 real recordings, 4 abdominal leads, 1 kHz, 5 min).

Reference fetal R-peaks (.qrs) come from the direct scalp electrode, so they are an
independent ground truth.  Used only for scoring.
"""
from pathlib import Path

import numpy as np
import wfdb
from scipy.signal import decimate

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "data" / "ADFECGDB" / "abdominal-and-direct-fetal-ecg-database-1.0.0"
RECORDS = ["r01", "r04", "r07", "r08", "r10"]
FS = 250


def read_edf(path):
    """Minimal EDF/EDF+ reader -> (fs, dict name -> physical signal)."""
    raw = Path(path).read_bytes()
    hdr_bytes = int(raw[184:192])
    nrec = int(raw[236:244])
    dur = float(raw[244:252])
    ns = int(raw[252:256])
    o = 256

    def field(width):
        nonlocal o
        vals = [raw[o + i * width: o + (i + 1) * width].decode("latin-1").strip() for i in range(ns)]
        o += ns * width
        return vals

    labels = field(16); field(80); field(8)
    pmin = np.array(field(8), float); pmax = np.array(field(8), float)
    dmin = np.array(field(8), float); dmax = np.array(field(8), float)
    field(80)
    nsamp = np.array(field(8), int)
    data = np.frombuffer(raw[hdr_bytes:], dtype="<i2")
    rec_len = nsamp.sum()
    data = data[: nrec * rec_len].reshape(nrec, rec_len)
    out, start = {}, 0
    for i, lab in enumerate(labels):
        d = data[:, start:start + nsamp[i]].ravel().astype(float)
        start += nsamp[i]
        if lab.startswith("EDF Annotations"):
            continue
        g = (pmax[i] - pmin[i]) / (dmax[i] - dmin[i])
        out[lab] = (d - dmin[i]) * g + pmin[i]
    return nsamp[0] / dur, out


def load(rid):
    """-> X (n,4) at 250 Hz in device counts (3000 LSB/mV), fetal reference peaks at 250 Hz."""
    fs, sig = read_edf(DIR / f"{rid}.edf")
    A = np.stack([sig[f"Abdomen_{k}"] for k in range(1, 5)], axis=1) / 1000.0   # uV -> mV
    q = int(round(fs)) // FS
    X = decimate(A, q, ftype="iir", axis=0, zero_phase=False) * 3000.0       # causal anti-alias
    fq = wfdb.rdann(str(DIR / f"{rid}.edf"), "qrs").sample
    # decimate's causal IIR (order-8 Chebyshev) adds ~4 output-sample... measured below; keep raw /q
    return X, np.round(fq / q).astype(int)

#!/usr/bin/env python3
"""
fpga_implementation/simulation/verify_detector_restart.py
Bit-exact xsim verification of the restartable adaptive_detector.

  1. A FECGSYNDB record is run through the bit-accurate model with the host
     schedule from src/fecg/host/adaptive_beamformer.py (0xC4 at 12 s, gated
     0xC3 updates) -> MWI stream, |bp16| stream, restart sample indices.
  2. Integer reference of the detector candidates (m, energy); cross-checked
     against the bit-accurate model's localised/fused raw peaks.
  3. tb_detector_golden.v is simulated with Vivado xsim on the same MWI stream
     and restart pulses; every candidate must match exactly.
Usage: python verify_detector_restart.py [record_id ...]
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "accuracy"))
from fecg.hardware.bit_accurate_reference import (  # noqa: E402
    BitAccuratePipelineRunner, DET_RESTART_DELAY, RR_MAX, RR_MIN)
from fecg.host.adaptive_beamformer import plan_schedule  # noqa: E402
import harness as H  # noqa: E402

VIVADO = Path(r"C:\AMDDesignTools\2025.2\Vivado\bin")
RTL = ROOT / "fpga_implementation" / "rtl"
TB = ROOT / "fpga_implementation" / "testbenches" / "unit"
WORK = ROOT / "fpga_implementation" / "simulation" / "vivado_sim_out" / "detector_golden"


def ref_candidates(xint, restarts, warmup=512, refr=50, delay=DET_RESTART_DELAY):
    cands = []
    peak = noise = wmax = wsum = 0
    wcnt, wdone, enabled, last, cd = 0, -1, False, -10 ** 9, 0
    for t in range(len(xint)):
        if t in restarts:
            cd = delay
        if cd > 0:
            cd -= 1
            if cd == 0:
                wcnt, wmax, wsum, enabled = 0, 0, 0, False
        mw = int(xint[t])
        if wcnt < warmup:
            wmax = max(wmax, mw)
            wsum += mw
            wcnt += 1
            if wcnt == warmup:
                peak, noise, wdone = wmax, wsum >> 9, t
                enabled = peak > noise
            continue
        if enabled and t >= 2:
            m, v, vp = t - 1, int(xint[t - 1]), int(xint[t - 2])
            if vp < v and v >= mw and m >= wdone:
                thr = (peak >> 2) + noise - (noise >> 2)
                if v > thr:
                    if m - last >= refr:
                        cands.append((m, v))
                        last = m
                        peak += (v - peak) >> 3
                else:
                    noise += (v - noise) >> 3
    return cands


def localise_and_fuse(cands, absbp, loc=26):
    raw = []
    for m, _ in cands:
        t = m + 1
        lo = max(0, t - (loc - 1))
        best = lo
        for i in range(lo + 1, t + 1):
            if absbp[i] > absbp[best]:
                best = i
        if raw and best - raw[-1] < RR_MIN:
            if absbp[best] > absbp[raw[-1]]:
                raw[-1] = best
        else:
            raw.append(best)
    return raw


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit(f"FAILED: {cmd}")
    return r.stdout


def verify(rid: str) -> bool:
    rec = [r for r in H.list_records() if r.rid == rid][0]
    d = H.load(rec)
    X = d["X"]
    cmds = plan_schedule(X)
    xq = np.clip(np.round(X), -32768, 32767).astype(np.int64)
    res = BitAccuratePipelineRunner().process_block(
        xq, target_weights=[(c.t, c.w_q15, c.restart) for c in cmds])
    restarts = {c.t for c in cmds if c.restart}
    cands = ref_candidates(res.x_int, restarts)
    raw = localise_and_fuse(cands, np.abs(res.det_bp))
    model_raw = list(map(int, res.raw_peaks))
    if raw != model_raw:
        print(f"[{rid}] reference/model mismatch ({len(raw)} vs {len(model_raw)})")
        return False

    WORK.mkdir(parents=True, exist_ok=True)
    with open(WORK / "detector_stim.hex", "w") as f:
        for t, v in enumerate(res.x_int):
            f.write(f"{1 if t in restarts else 0:01x}{int(v):09x}\n")
    files = " ".join(str(p) for p in [RTL / "adaptive_detector.v", TB / "tb_detector_golden.v"])
    run(f'"{VIVADO / "xvlog.bat"}" {files}', WORK)
    run(f'"{VIVADO / "xelab.bat"}" tb_detector_golden -s det_golden -debug off', WORK)
    out = run(f'"{VIVADO / "xsim.bat"}" det_golden -R', WORK)
    done = [ln for ln in out.splitlines() if "TB_DONE" in ln]
    rtl = [tuple(map(int, ln.split())) for ln in open(WORK / "detector_cand_rtl.txt") if ln.strip()]
    ok = rtl == [(int(m), int(v)) for m, v in cands]
    first_diff = next((i for i, (a, b) in enumerate(zip(rtl, cands)) if a != tuple(b)), None)
    print(f"[{rid}] samples={len(res.x_int)} restarts={sorted(restarts)} cmds={len(cmds)} "
          f"candidates ref={len(cands)} rtl={len(rtl)} -> {'PASS (bit-exact)' if ok else 'FAIL'}"
          + ("" if ok else f" first diff idx {first_diff}") + f" | {done[0] if done else ''}")
    return ok


if __name__ == "__main__":
    ids = sys.argv[1:] or ["sub01_snr06dB_l1_c0", "sub05_snr03dB_l3_c3"]
    results = [verify(r) for r in ids]
    sys.exit(0 if all(results) else 1)

#!/usr/bin/env python3
"""
Physical evaluation of FECG v6 (hand-written RTL on the Spartan-7 + PC brain).

The PC streams the recording (int16, 4 leads, 250 Hz) in 64-sample SAMPLES frames and
waits for DONE after each.  Every frame the FPGA sends is piped into the PC brain
(fpga_implementation/v6/model/v6_brain.exe); the brain's answers (PCA projections,
maternal train, template basis, calibration, selection) go back to the FPGA.
All sample-rate processing - filters, maternal detection and cancellation, 16
projections, trackers, features, output beats and FHR - happens in the RTL.

Per record:
  * board beats/FHR scored against the annotations (harness.score, from 20 s, +-50 ms);
  * the complete uplink byte stream of the board is compared with the bit-accurate C
    system model (fpga_implementation/v6/model/v6_sim.exe) -> "bit_exact".

Usage: python run_v6_board_eval.py --sets cdev,ad[,syn,ctest] [--port COM5] [--limit N] [--out DIR]
       V6_VARIANT=v61 python run_v6_board_eval.py ...   (v6.1: board programmed with v6/program_v61.tcl)
       V6_VARIANT=v7  python run_v6_board_eval.py ...   (v7-DL: board programmed with v6/program_v7.tcl;
                                                         the recording is still streamed in 64-sample chunks,
                                                         FLUSH at the end, final beats = OUT7 frames)
"""
import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import serial

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "accuracy"))
import harness as H  # noqa: E402
import v5c  # noqa: E402
from devbench import _load, items  # noqa: E402

MODEL = ROOT / "fpga_implementation" / "v6" / "model"
VARIANT = os.environ.get("V6_VARIANT", "v6")          # "v61": v6.1 brain + model (board must run build/v61/v61.bit)
V7 = VARIANT == "v7"                                  # "v7": v7-DL look-ahead on the board (build/v7/v7.bit)
CHUNK = 64


def frame(cmd, payload=b""):
    n = len(payload)
    x = cmd ^ (n & 255) ^ (n >> 8)
    for b in payload:
        x ^= b
    return bytes([0xA5, 0x5A, cmd, n & 255, n >> 8]) + payload + bytes([x])


def read_frame(read):
    """read(n) -> bytes; returns (cmd, payload, raw) of the next valid frame."""
    while True:
        b = read(1)
        if b != b"\xA5":
            continue
        if read(1) != b"\x5A":
            continue
        h = read(3)
        cmd, n = h[0], h[1] | (h[2] << 8)
        p = read(n)
        x = read(1)[0]
        c = h[0] ^ h[1] ^ h[2]
        for v in p:
            c ^= v
        if c != x:
            raise IOError(f"checksum error in frame {cmd:02X}")
        return cmd, p, b"\xA5\x5A" + h + p + bytes([x])


class V6System:
    def __init__(self, port, baud=921600):
        self.ser = serial.Serial(port, baud, timeout=0.2)
        self.lock = threading.Lock()
        self.brain = subprocess.Popen([str(MODEL / f"{VARIANT}_brain.exe")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        self.n_rsp = 0
        threading.Thread(target=self._brain_to_fpga, daemon=True).start()

    def _brain_read(self, n):
        out = b""
        while len(out) < n:
            d = self.brain.stdout.read(n - len(out))
            if not d:
                raise EOFError("brain exited")
            out += d
        return out

    def _brain_to_fpga(self):
        try:
            while True:
                _, _, raw = read_frame(self._brain_read)
                with self.lock:
                    self.ser.write(raw)
                self.n_rsp += 1
        except EOFError:
            pass

    def _ser_read(self, n):
        out = b""
        t0 = time.time()
        while len(out) < n:
            d = self.ser.read(n - len(out))
            if d:
                out += d
                t0 = time.time()
            elif time.time() - t0 > 20:
                raise TimeoutError("FPGA silent for 20 s")
        return out

    def _frames_until(self, stop, up, outs):
        """read board frames until cmd `stop`: OUT (0x8B) / OUT7 (0x8D) beats are collected, the rest goes to the brain"""
        while True:
            cmd, p, raw = read_frame(self._ser_read)
            up += raw
            if cmd == stop:
                return
            if cmd in outs:
                outs[cmd].append((int.from_bytes(p[0:4], "little"), p[4] | (p[5] << 8), p[6]))
            elif cmd != 0x8E:
                self.brain.stdin.write(raw)

    def run(self, xi):
        """xi: (n, 4) int16.  Returns (final beats [t, fhr_x10, src], causal OUT beats, uplink bytes).
        v7: after the last chunk the PC sends FLUSH and reads the remaining OUT7 frames up to END7;
        the final beats are the OUT7 beats (the causal v6.1 OUT beats are returned as well)."""
        with self.lock:
            self.ser.write(frame(0x01))
        time.sleep(0.05)
        self.ser.reset_input_buffer()
        self.brain.stdin.write(frame(0x01))
        up = bytearray()
        outs = {0x8B: [], 0x8D: []}
        for c0 in range(0, len(xi), CHUNK):
            blk = np.ascontiguousarray(xi[c0:c0 + CHUNK]).astype("<i2").tobytes()
            with self.lock:
                self.ser.write(frame(0x02, blk))
            self._frames_until(0x8C, up, outs)
        if V7:
            with self.lock:
                self.ser.write(frame(0x03))
            self._frames_until(0x8E, up, outs)
        arr = {c: np.array(v, dtype=np.int64).reshape(-1, 3) for c, v in outs.items()}
        return arr[0x8D] if V7 else arr[0x8B], arr[0x8B], bytes(up)


def model_stream(xi):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "x.i16")
        open(f, "wb").write(np.ascontiguousarray(xi).astype("<i2").tobytes())
        env = dict(os.environ, V6_DUMP=os.path.join(d, "g"))
        out = subprocess.run([str(MODEL / f"{VARIANT}_sim.exe"), f], capture_output=True, text=True, env=env, check=True).stdout
        hexs = open(os.path.join(d, "g_up.hex")).read().split()
    b = np.array([list(map(int, l.split())) for l in out.splitlines() if l.strip()], dtype=np.int64).reshape(-1, 3)
    return b, bytes(int(h, 16) for h in hexs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="cdev,ad")
    ap.add_argument("--port", default="COM5")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "report" / "rtl_pc_split" / "board"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sysm = V6System(a.port)
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
        bb, bc, up = sysm.run(xi)
        wall = time.perf_counter() - t0
        bm, upm = model_stream(xi)
        exact = up == upm
        pk, fhr = v5c.beats_to_stream(bb, n)
        r = H.score(fq, pk, fhr, n, 5000)
        row = {"set": item[0], "rid": rid, "f1": r["f1"], "se": r["se"], "ppv": r["ppv"], "fhr_mae": r["fhr_mae"],
               "n_beats": len(bb), "bit_exact": exact, "uplink_bytes": len(up),
               "uplink_md5": hashlib.md5(up).hexdigest(), "stream_s": wall, "record_s": n / 250.0}
        if V7:                                        # the causal v6.1 output of the same run, for comparison
            pkc, fhrc = v5c.beats_to_stream(bc, n)
            rc = H.score(fq, pkc, fhrc, n, 5000)
            row.update({"f1_causal": rc["f1"], "fhr_mae_causal": rc["fhr_mae"]})
        rows.append(row)
        print(f"{item[0]:5s} {rid:24s} F1 {r['f1']:6.2f}  beats {len(bb):4d}  uplink {len(up):8d} B  bit-exact {exact}  "
              f"{wall:5.1f}s for {n / 250:5.0f}s", flush=True)
    df = pd.DataFrame(rows)
    tag = a.sets.replace(",", "_")
    df.to_csv(out / f"board_{tag}.csv", index=False)
    agg = dict(f1=("f1", "mean"), se=("se", "mean"), ppv=("ppv", "mean"), fhr_mae=("fhr_mae", "mean"),
               records=("rid", "count"), bit_exact=("bit_exact", "mean"), record_s=("record_s", "sum"),
               stream_s=("stream_s", "sum"))
    if V7:
        agg.update(f1_causal=("f1_causal", "mean"), fhr_mae_causal=("fhr_mae_causal", "mean"))
    summ = df.groupby("set").agg(**agg)
    summ["rt_factor"] = summ["record_s"] / summ["stream_s"]
    print(summ.round(3).to_string())


if __name__ == "__main__":
    main()

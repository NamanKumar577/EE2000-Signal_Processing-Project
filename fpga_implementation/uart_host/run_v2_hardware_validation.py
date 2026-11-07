#!/usr/bin/env python3
"""
fpga_implementation/uart_host/run_v2_hardware_validation.py
Physical Spartan-7 validation of the v2 system (adaptive host beamformer +
0xC4 detector restart + latency 13).

For each record:
  * samples streamed to the board at 250 Hz over COM5;
  * the streaming host controller (src/fecg/host/adaptive_beamformer.py) decides
    weight packets causally; each is written before the sample it applies to;
  * the bit-accurate model mirrors the board with continuous state (the board
    must be freshly programmed / reset before the run);
  * compared: clean FECG stream (0x5A) sample-by-sample, beat telemetry (0xAA)
    timestamps and FHR, and beat accuracy of the BOARD output vs annotations.
Usage: python run_v2_hardware_validation.py [--port COM5] [--seconds 60] rid ...
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import serial

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "accuracy"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fecg_uart_client import (  # noqa: E402
    UARTStreamFramer, encode_calibration_packet, encode_sample_packet)
from fecg.hardware.bit_accurate_reference import BitAccuratePipelineRunner  # noqa: E402
from fecg.host.adaptive_beamformer import AdaptiveBeamformerHost  # noqa: E402
import harness as H  # noqa: E402

OUT = ROOT / "validation" / "v2_hardware_20261107"


def stream_record(ser, rec, n_samples, runner, t_base, log):
    d = H.load(rec)
    X = d["X"][:n_samples]
    fq = d["fq"]
    xq = np.clip(np.round(X), -32768, 32767).astype(np.int64)
    host = AdaptiveBeamformerHost()
    framer = UARTStreamFramer()
    rx_fecg, rx_beats = [], []
    cmds = []
    pending = []                     # commands decided after sample t-1 -> sent before sample t
    t0 = time.perf_counter()
    nxt = t0
    for t in range(n_samples):
        for c in pending:
            ser.write(encode_calibration_packet(c.w_q15, restart_detector=c.restart))
            cmds.append((t, c.w_q15, c.restart))
        pending = []
        ser.write(encode_sample_packet(t & 0xFF, *(int(v) for v in xq[t])))
        # host sees sample t, may decide a command that applies from sample t+1
        new = host.push(X[t:t + 1])
        pending = new
        if ser.in_waiting:
            for typ, obj, _ in framer.feed(ser.read(ser.in_waiting)):
                if typ == "FECG_STREAM":
                    rx_fecg.append(obj.sample_s24)
                elif typ == "TELEMETRY":
                    rx_beats.append((obj.timestamp, int(round(obj.fhr_bpm * 10)), obj.flag))
        nxt += 0.004
        dl = nxt - time.perf_counter()
        if dl > 0:
            time.sleep(dl)
    end = time.perf_counter() + 1.5
    while time.perf_counter() < end:
        if ser.in_waiting:
            for typ, obj, _ in framer.feed(ser.read(ser.in_waiting)):
                if typ == "FECG_STREAM":
                    rx_fecg.append(obj.sample_s24)
                elif typ == "TELEMETRY":
                    rx_beats.append((obj.timestamp, int(round(obj.fhr_bpm * 10)), obj.flag))
        else:
            time.sleep(0.01)
    elapsed = time.perf_counter() - t0

    # Python mirror (continuous state, identical command timing)
    res = runner.process_block(xq, target_weights=cmds)
    py_fecg = np.asarray(res.fecg)
    py_peaks_global = np.asarray(res.telemetry_peaks) + t_base   # what the board transmits
    fpga_fecg = np.asarray(rx_fecg, dtype=np.int64)
    m = min(len(fpga_fecg), len(py_fecg))
    err = np.abs(fpga_fecg[:m] - py_fecg[:m])
    fpga_ts = np.array([b[0] for b in rx_beats], dtype=np.int64)
    beats_match = (len(fpga_ts) == len(py_peaks_global) and np.array_equal(fpga_ts, py_peaks_global))
    # FHR telemetry vs model FHR stream shortly after each beat
    fhr_ok = 0
    for ts, fx, _ in rx_beats:
        lo = int(ts - t_base)
        win = res.fhr_hold[max(0, lo):min(len(res.fhr_hold), lo + 80)]
        fhr_ok += int(fx in set(map(int, win)))
    # accuracy of the BOARD's beats against the annotations (score from 20 s)
    board_peaks = fpga_ts - t_base
    fhr_board = np.zeros(n_samples)
    for ts, fx, _ in rx_beats:
        k = int(ts - t_base)
        if 0 <= k < n_samples:
            fhr_board[k:] = fx / 10.0
    sc = H.score(fq[fq < n_samples], board_peaks, fhr_board, n_samples, 5000)
    out = {
        "record": rec.rid, "samples": n_samples, "elapsed_s": round(elapsed, 1),
        "fecg_rx": int(len(fpga_fecg)), "fecg_missing": int(n_samples - len(fpga_fecg)),
        "crc_errors": int(framer.total_crc_errors),
        "fecg_max_err_lsb": int(err.max()) if m else -1,
        "fecg_exact_pct": round(100.0 * float(np.mean(err == 0)), 3) if m else 0.0,
        "beats_board": int(len(fpga_ts)), "beats_model": int(len(py_peaks_global)),
        "beat_timestamps_identical": bool(beats_match),
        "fhr_telemetry_match": f"{fhr_ok}/{len(rx_beats)}",
        "weight_packets": len(cmds), "c4_packets": sum(1 for c in cmds if c[2]),
        "board_F1": round(sc["f1"], 2), "board_Se": round(sc["se"], 2), "board_PPV": round(sc["ppv"], 2),
        "board_FHR_MAE": round(sc["fhr_mae"], 2),
    }
    log(json.dumps(out))
    return out, fpga_fecg, py_fecg, rx_beats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM5")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("records", nargs="*")
    a = ap.parse_args()
    ids = a.records or ["sub01_snr06dB_l1_c0", "sub04_snr00dB_l2_c1", "sub07_snr09dB_l3_c2",
                        "sub10_snr12dB_l1_c2", "sub08_snr03dB_l5_c0"]
    recs = {r.rid: r for r in H.list_records()}
    OUT.mkdir(parents=True, exist_ok=True)
    logf = open(OUT / "hardware_run.log", "a", encoding="utf-8")

    def log(msg):
        print(msg)
        logf.write(msg + "\n")
        logf.flush()

    log(f"=== v2 hardware validation {time.strftime('%Y-%m-%d %H:%M:%S')} port={a.port} ===")
    from fecg.host.adaptive_beamformer import calibrate
    calibrate(np.random.default_rng(0).standard_normal((3000, 4)))   # JIT warm-up before streaming
    ser = serial.Serial(a.port, a.baud, timeout=0.05, write_timeout=2.0)
    ser.reset_input_buffer()
    runner = BitAccuratePipelineRunner()   # board must be freshly programmed
    t_base = 0
    rows = []
    for spec in ids:
        rid, _, secs = spec.partition(":")
        n = min(int((float(secs) if secs else a.seconds) * 250), 75000)
        row, f_fpga, f_py, beats = stream_record(ser, recs[rid], n, runner, t_base, log)
        np.savez_compressed(OUT / f"{rid}_board_vs_model.npz", fpga_fecg=f_fpga, model_fecg=f_py,
                            beats=np.array(beats, dtype=np.int64))
        rows.append(row)
        t_base += n
    ser.close()
    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "v2_hardware_results.csv", index=False)
    log(df.to_string())


if __name__ == "__main__":
    main()

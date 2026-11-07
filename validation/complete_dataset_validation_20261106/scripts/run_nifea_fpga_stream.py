#!/usr/bin/env python3
"""
scratch/run_nifea_fpga_stream.py
──────────────────────────────────────────────────────────────────────────────
Physical Hardware Validation of Clinical NIFEA Biopotentials on Spartan-7 FPGA
- Interface: Physical FTDI USB-UART on COM5 (115200 baud, 8-N-1)
- Bitstream: fecg_multichannel_top.bit on AMD XC7S50-1CSGA324C
- Streams representative continuous clinical segments (2,500 samples / 10s each)
  from both Normal and Arrhythmia cohorts (NR_01, NR_02, ARR_02, ARR_06, ARR_10).
- Compares physical FPGA output waveforms against continuous BitAccuratePipelineRunner.
- Tracks packet integrity, CRC-8 errors, framing errors, missing packets, sample intervals.
- HARDWARE ONLY: Zero software fallback.
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import time
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import wfdb
from scipy.signal import decimate
import serial

PROJECT_ROOT = Path(r"D:\signal_project")
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fpga_implementation.uart_host.validate_real_datasets import HostSpatialCalibrator
from fpga_implementation.uart_host.fecg_uart_client import (
    UARTStreamFramer, encode_sample_packet, encode_calibration_packet
)
from fecg.hardware.bit_accurate_reference import BitAccuratePipelineRunner

NIFEA_DIR = PROJECT_ROOT / "data" / "Non-Invasive_Fetal_ECG_Arrhythmia_Database" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "complete_dataset_validation_20261106"
LOGS_DIR = OUT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
HW_WAVEFORMS_DIR = OUT_DIR / "waveforms" / "fpga_hardware"
HW_WAVEFORMS_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / "NIFEA_FPGA_PHYSICAL_RESULTS.csv"
EXEC_LOG = LOGS_DIR / "nifea_fpga_physical_stream.log"

TEST_RECORDS = ["NR_01", "NR_02", "ARR_02", "ARR_06", "ARR_10"]
TARGET_FS = 250
ADC_SCALE_LSB_PER_MV = 3000.0
SAMPLES_PER_CASE = 2500  # 10.0 seconds continuous stream per record

def run_nifea_hardware_stream(port="COM5", baud=115200):
    log_f = open(EXEC_LOG, "w", encoding="utf-8")
    
    def log(msg):
        print(msg)
        log_f.write(msg + "\n")
        log_f.flush()

    log("=" * 80)
    log("NIFEA PHYSICAL SPARTAN-7 FPGA HARDWARE VALIDATION (COM5)")
    log(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Port: {port} @ {baud} baud (8-N-1)")
    log(f"Records to stream: {TEST_RECORDS}")
    log(f"Samples per record: {SAMPLES_PER_CASE} ({SAMPLES_PER_CASE/TARGET_FS:.1f} s continuous)")
    log("=" * 80)

    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=0.1, write_timeout=1.0)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        log(f"[OK] Successfully opened {port}.")
    except Exception as e:
        log(f"[FATAL] Cannot open {port}: {e}")
        log_f.close()
        sys.exit(1)

    pipeline_runner = BitAccuratePipelineRunner()
    all_results = []
    
    for case_idx, rec_id in enumerate(TEST_RECORDS, 1):
        log(f"\n--- Case {case_idx}/{len(TEST_RECORDS)}: {rec_id} ---")
        
        # Load and decimate
        r = wfdb.rdrecord(str(NIFEA_DIR / rec_id))
        orig_fs = int(r.fs)
        q = orig_fs // TARGET_FS
        sig_250 = decimate(r.p_signal, q, ftype="iir", axis=0, zero_phase=False)
        
        # 4 abdominal leads scaled to LSB
        x4_mv = sig_250[:SAMPLES_PER_CASE, 1:5]
        x_q12 = np.clip(np.round(x4_mv * ADC_SCALE_LSB_PER_MV), -32768, 32767).astype(np.int64)
        
        # Calibrate
        calibrator = HostSpatialCalibrator()
        w_q15, pc_idx, conf, debug = calibrator.calibrate(x_q12, rule="autocorr")
        weights_list = [int(w) for w in w_q15]
        log(f"  Calibrated PC{pc_idx}, Weights: {weights_list}, Conf: {conf:.3f}")
        
        # Step A: Python Continuous Bit-Accurate Execution
        py_res = pipeline_runner.process_block(x_q12, new_weights=weights_list)
        py_fecg = py_res.fecg
        
        # Step B: Physical FPGA Hardware Streaming
        cal_pkt = encode_calibration_packet(weights_list)
        ser.write(cal_pkt)
        time.sleep(0.015)
        
        framer = UARTStreamFramer()
        rx_fecg_samples: List[int] = []
        rx_fecg_seqs: List[int] = []
        rx_fecg_timestamps: List[float] = []
        rx_telemetry_events: List[Any] = []
        
        missing_packet_count = 0
        seq_gap_count = 0
        last_seq = None
        
        log(f"  Streaming {SAMPLES_PER_CASE} samples to Spartan-7 on {port} at 250 Hz (4.0 ms interval)...")
        t_stream_start = time.perf_counter()
        next_sample_tx = t_stream_start
        
        for t in range(SAMPLES_PER_CASE):
            pkt = encode_sample_packet(
                t & 0xFF,
                int(x_q12[t, 0]), int(x_q12[t, 1]),
                int(x_q12[t, 2]), int(x_q12[t, 3])
            )
            ser.write(pkt)
            
            # Non-blocking receive drain
            in_w = ser.in_waiting
            if in_w > 0:
                raw_bytes = ser.read(in_w)
                for ptype, pobj, _ in framer.feed(raw_bytes):
                    rx_time = time.perf_counter()
                    if ptype == "FECG_STREAM":
                        rx_fecg_samples.append(pobj.sample_s24)
                        rx_fecg_seqs.append(pobj.seq)
                        rx_fecg_timestamps.append(rx_time)
                        if last_seq is not None:
                            expected_seq = (last_seq + 1) & 0xFF
                            if pobj.seq != expected_seq:
                                seq_gap_count += 1
                        last_seq = pobj.seq
                    elif ptype == "TELEMETRY":
                        rx_telemetry_events.append((rx_time, pobj))

            # Maintain strict 250 Hz pacing (4.000 ms)
            next_sample_tx += 0.0040
            delay = next_sample_tx - time.perf_counter()
            if delay > 0:
                time.sleep(delay)

        # Drain residual pipeline output (up to 1.5s timeout)
        drain_deadline = time.perf_counter() + 1.5
        while time.perf_counter() < drain_deadline and len(rx_fecg_samples) < SAMPLES_PER_CASE:
            in_w = ser.in_waiting
            if in_w > 0:
                raw_bytes = ser.read(in_w)
                for ptype, pobj, _ in framer.feed(raw_bytes):
                    rx_time = time.perf_counter()
                    if ptype == "FECG_STREAM":
                        rx_fecg_samples.append(pobj.sample_s24)
                        rx_fecg_seqs.append(pobj.seq)
                        rx_fecg_timestamps.append(rx_time)
                        if last_seq is not None:
                            expected_seq = (last_seq + 1) & 0xFF
                            if pobj.seq != expected_seq:
                                seq_gap_count += 1
                        last_seq = pobj.seq
                    elif ptype == "TELEMETRY":
                        rx_telemetry_events.append((rx_time, pobj))
            else:
                time.sleep(0.005)

        t_elapsed = time.perf_counter() - t_stream_start
        fpga_fecg = np.array(rx_fecg_samples, dtype=np.int64)
        n_rx = len(fpga_fecg)
        missing_pkts = max(0, SAMPLES_PER_CASE - n_rx)
        crc_err = framer.total_crc_errors
        frame_err = framer.total_bytes_dropped
        
        # Step D: Waveform Comparison (FPGA Captured vs Continuous Python Reference)
        n_cmp = min(n_rx, len(py_fecg))
        if n_cmp > 0:
            diff_arr = np.abs(fpga_fecg[:n_cmp] - py_fecg[:n_cmp])
            max_err_lsb = int(np.max(diff_arr))
            mae_lsb = float(np.mean(diff_arr))
            exact_match_count = int(np.sum(diff_arr == 0))
            exact_match_pct = float(100.0 * exact_match_count / n_cmp)
        else:
            max_err_lsb = -1
            mae_lsb = -1.0
            exact_match_pct = 0.0

        # Step E: Arrival Timing
        if len(rx_fecg_timestamps) > 1:
            arrival_intervals_ms = np.diff(rx_fecg_timestamps) * 1000.0
            mean_int = float(np.mean(arrival_intervals_ms))
            med_int = float(np.median(arrival_intervals_ms))
        else:
            mean_int = med_int = 0.0
            
        log(f"  Execution time: {t_elapsed:.2f} s ({SAMPLES_PER_CASE/t_elapsed:.1f} samples/s)")
        log(f"  Samples sent: {SAMPLES_PER_CASE}, Packets RX: {n_rx}, Missing: {missing_pkts}, CRC err: {crc_err}")
        log(f"  Waveform parity: Max Error = {max_err_lsb} LSB, MAE = {mae_lsb:.4f} LSB, Exact Match = {exact_match_pct:.2f}%")
        log(f"  Timing intervals: Mean = {mean_int:.3f} ms, Median = {med_int:.4f} ms")
        
        # Save captured waveforms
        df_hw = pd.DataFrame({
            "sample_index": np.arange(n_cmp),
            "time_s": np.arange(n_cmp) / TARGET_FS,
            "py_reference_s24": py_fecg[:n_cmp],
            "fpga_captured_s24": fpga_fecg[:n_cmp],
            "error_lsb": diff_arr[:n_cmp]
        })
        hw_csv_path = HW_WAVEFORMS_DIR / f"{rec_id}_fpga_hardware_waveforms.csv"
        df_hw.to_csv(hw_csv_path, index=False)
        
        all_results.append({
            "case_index": case_idx,
            "record_id": rec_id,
            "samples_sent": SAMPLES_PER_CASE,
            "fecg_packets_rx": n_rx,
            "telemetry_packets_rx": len(rx_telemetry_events),
            "missing_packets": missing_pkts,
            "crc_errors": crc_err,
            "framing_errors": frame_err,
            "max_abs_error_lsb": max_err_lsb,
            "mean_abs_error_lsb": round(mae_lsb, 4),
            "exact_match_pct": round(exact_match_pct, 2),
            "mean_interval_ms": round(mean_int, 3),
            "median_interval_ms": round(med_int, 4)
        })

    ser.close()
    
    df_res = pd.DataFrame(all_results)
    df_res.to_csv(OUT_CSV, index=False)
    log(f"\nSaved hardware summary to: {OUT_CSV}")
    log_f.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=str, default="COM5")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    run_nifea_hardware_stream(port=args.port, baud=args.baud)

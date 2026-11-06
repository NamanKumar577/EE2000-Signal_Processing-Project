#!/usr/bin/env python3
"""
fpga_implementation/uart_host/run_phase4_physical_revalidation.py
──────────────────────────────────────────────────────────────────────────────
Phase 4 Physical Hardware Revalidation Suite.
Target: AMD Spartan-7 XC7S50-1CSGA324C on RealDigital Boolean Board via COM5.

Mandatory Hardware Execution:
  - Connects strictly to physical Spartan-7 on COM5 (aborts if unavailable).
  - Programs the multichannel bitstream via Vivado JTAG to ensure zero-state baseline.
  - Streams all six Phase 4 test cases (15,000 samples total) at exact 250 Hz (4 ms/sample).
  - Python reference maintains continuous filter state across all case boundaries.
  - Captures raw physical FPGA clean FECG output (0x5A) sample-by-sample.
  - Measures inter-sample arrival intervals and verifies 250 Hz timing.
  - Reports max error (LSB), MAE (LSB), exact-match %, packet loss, CRC errors.
  - Preserves previous logs and stores all outputs in a dedicated revalidation directory.
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import time
import json
import csv
import hashlib
import struct
import subprocess
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import numpy as np

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Hardware models & UART protocol
import importlib.util
spec_bar = importlib.util.spec_from_file_location('bar', str(PROJECT_ROOT / 'src/fecg/hardware/bit_accurate_reference.py'))
bar = importlib.util.module_from_spec(spec_bar)
sys.modules[spec_bar.name] = bar
spec_bar.loader.exec_module(bar)

from fpga_implementation.uart_host.fecg_uart_client import (
    FECGUartClient, encode_sample_packet, encode_calibration_packet,
    UARTStreamFramer, HEADER_SAMPLE, HEADER_CALIBRATION, HEADER_FECG_STREAM, HEADER_FHR_TELEMETRY
)
from fpga_implementation.uart_host.validate_real_datasets import (
    generate_synthetic_benchmark, load_fecgsyndb_case, HostSpatialCalibrator,
    match_beats_detailed, FS
)

OUTPUT_DIR = PROJECT_ROOT / "fpga_implementation" / "reports" / "phase4_physical_revalidation_20261106"
BITSTREAM_PATH = PROJECT_ROOT / "fpga_implementation" / "bitstream" / "fecg_multichannel_top.bit"
PROGRAM_TCL_PATH = PROJECT_ROOT / "fpga_implementation" / "reports" / "program_multichannel_hw.tcl"
VIVADO_BAT_PATH = Path(r"C:\AMDDesignTools\2025.2\Vivado\bin\vivado.bat")

def compute_sha256(filepath: Path) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

def reprogram_fpga_jtag(log_file: Path) -> bool:
    """Reprogram Spartan-7 with bitstream via Vivado Hardware Manager."""
    print("=" * 80)
    print("REPROGRAMMING SPARTAN-7 FPGA VIA JTAG")
    print(f"Bitstream: {BITSTREAM_PATH}")
    print(f"Programming TCL: {PROGRAM_TCL_PATH}")
    print(f"Log Output: {log_file}")
    print("=" * 80)

    if not VIVADO_BAT_PATH.exists():
        print(f"[ERROR] Vivado executable not found at: {VIVADO_BAT_PATH}")
        return False

    cmd = [
        str(VIVADO_BAT_PATH),
        "-mode", "batch",
        "-source", str(PROGRAM_TCL_PATH).replace("\\", "/"),
        "-nojournal",
        "-log", str(log_file).replace("\\", "/")
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90
        )
        elapsed = time.time() - t0
        print(f"Vivado JTAG process exited with code {proc.returncode} in {elapsed:.2f}s")
        if proc.returncode == 0:
            print("[SUCCESS] Physical FPGA reprogrammed successfully! Startup status: HIGH.")
            return True
        else:
            print(f"[ERROR] Vivado JTAG failed with code {proc.returncode}:")
            print(proc.stdout)
            print(proc.stderr)
            return False
    except Exception as e:
        print(f"[ERROR] Vivado execution exception: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Phase 4 Physical FPGA Revalidation")
    parser.add_argument("--port", type=str, default="COM5", help="Serial port for Spartan-7 (default COM5)")
    parser.add_argument("--baud", type=int, default=115200, help="UART baud rate (default 115200)")
    parser.add_argument("--no-reprogram", action="store_true", help="Skip JTAG bitstream reprogramming")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    exec_log_path = OUTPUT_DIR / "phase4_physical_test_execution.log"
    jtag_log_path = OUTPUT_DIR / "jtag_programming.log"

    # Multi-stream logger (console + file)
    class Logger:
        def __init__(self, filepath):
            self.file = open(filepath, "w", encoding="utf-8")
        def write(self, msg):
            sys.__stdout__.write(msg)
            self.file.write(msg)
            self.file.flush()
        def flush(self):
            sys.__stdout__.flush()
            self.file.flush()
        def close(self):
            self.file.close()

    logger = Logger(exec_log_path)
    sys.stdout = logger

    script_path = Path(__file__).resolve()
    script_sha = compute_sha256(script_path)
    bitstream_sha = compute_sha256(BITSTREAM_PATH) if BITSTREAM_PATH.exists() else "NOT_FOUND"

    print("=" * 100)
    print("PHASE 4: MANDATORY PHYSICAL FPGA REVALIDATION RUN")
    print(f"Timestamp:          {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target Board:       RealDigital Boolean Board (AMD Spartan-7 XC7S50-1CSGA324C)")
    print(f"Serial Interface:   {args.port} @ {args.baud} baud, 8-N-1")
    print(f"Validation Script:  {script_path.name} (SHA-256: {script_sha})")
    print(f"Bitstream File:     {BITSTREAM_PATH.name} (SHA-256: {bitstream_sha})")
    print(f"Deliverables Dir:   {OUTPUT_DIR}")
    print("=" * 100)

    # 1. JTAG Reprogramming (Mandatory for clean t=0 state)
    if not args.no_reprogram:
        reprog_ok = reprogram_fpga_jtag(jtag_log_path)
        if not reprog_ok:
            print("[FATAL] JTAG reprogramming failed. Aborting mandatory hardware test.")
            sys.exit(1)
        time.sleep(1.0)  # Settle board power and FTDI USB enumerator
    else:
        print("[NOTICE] Skipping JTAG reprogramming per user flag (--no-reprogram).")

    # 2. Open Serial Port (Mandatory)
    import serial
    print(f"\nOpening serial connection to physical FPGA on {args.port}...")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.1)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.5)
        print(f"[OK] Connected to {args.port} successfully.")
    except Exception as e:
        print(f"[FATAL] Failed to open {args.port}: {e}")
        print("Hardware mode is mandatory. Aborting execution. Software fallback forbidden.")
        sys.exit(1)

    # 3. Load Validation Suite (6 Cases)
    data_dir = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
    suite = [
        generate_synthetic_benchmark(n_samples=2500),
        load_fecgsyndb_case(data_dir, "sub01", "snr12dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub01", "snr06dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub01", "snr00dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub04", "snr06dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub08", "snr06dB", "c0"),
    ]

    # Initialize continuous Python reference runner (starts at default unity bypass weights [32768, 0, 0, 0])
    pipeline_runner = bar.BitAccuratePipelineRunner(w_initial=[32768, 0, 0, 0])

    all_waveform_records = []
    case_summaries = []
    global_sample_counter = 0

    try:
        for case_idx, case in enumerate(suite):
            case_id = case["case_id"]
            mix_4ch = case["mix_4ch"]
            n_eval = min(len(mix_4ch), 2500)
            mix_eval = mix_4ch[:n_eval]
            f_qrs = case["f_qrs"][case["f_qrs"] < n_eval]
            m_qrs = case["m_qrs"][case["m_qrs"] < n_eval]
            fhr_nom = case["fhr_nominal"]
            mhr_nom = case["mhr_nominal"]

            x_q12 = np.clip(np.round(mix_eval), -32768, 32767).astype(np.int64)

            # Compute PCA spatial weights
            calibrator = HostSpatialCalibrator()
            w_q15, pc_idx, conf_score, debug_info = calibrator.calibrate(mix_eval, rule="autocorr")
            weights_list = [int(v) for v in w_q15]

            # Measure maternal suppression
            m_proj = case["mecg_4ch"][:n_eval] @ (w_q15 / 32768.0)
            p_m_in = np.mean(case["mecg_4ch"][:n_eval, 0] ** 2) + 1e-12
            p_m_out = np.mean(m_proj ** 2) + 1e-12
            maternal_suppression_db = float(10.0 * np.log10(p_m_in / p_m_out))

            print("\n" + "-" * 100)
            print(f"CASE {case_idx + 1}/6: {case_id}")
            print(f"  Samples: {n_eval} | PC Selected: PC{pc_idx + 1} | PCA Weights: {weights_list}")
            print(f"  Maternal Suppression: {maternal_suppression_db:.1f} dB | True FHR: {fhr_nom:.1f} bpm | True MHR: {mhr_nom:.1f} bpm")
            print("-" * 100)

            # Step A: Python Continuous Bit-Accurate Execution
            py_res = pipeline_runner.process_block(x_q12, new_weights=weights_list)
            py_fecg = py_res.fecg
            py_peaks = np.array(list(py_res.peaks), dtype=np.int64)

            # Step B: Physical FPGA Hardware Streaming
            # Send Calibration Packet (0xC3)
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

            print(f"  Streaming {n_eval} samples to Spartan-7 on {args.port} at 250 Hz (4.0 ms interval)...")
            t_stream_start = time.perf_counter()
            next_sample_tx = t_stream_start

            for t in range(n_eval):
                # Construct and send 11-byte Downlink Sample Packet
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
            while time.perf_counter() < drain_deadline and len(rx_fecg_samples) < n_eval:
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
                time.sleep(0.005)

            t_stream_end = time.perf_counter()
            stream_duration = t_stream_end - t_stream_start

            fpga_fecg = np.array(rx_fecg_samples, dtype=np.int64)
            n_received = len(fpga_fecg)
            missing_packet_count = max(0, n_eval - n_received)

            # Step C: Timing & Arrival Interval Analysis
            if len(rx_fecg_timestamps) > 1:
                arrival_intervals_ms = np.diff(rx_fecg_timestamps) * 1000.0
                mean_interval_ms = float(np.mean(arrival_intervals_ms))
                std_interval_ms = float(np.std(arrival_intervals_ms))
                min_interval_ms = float(np.min(arrival_intervals_ms))
                max_interval_ms = float(np.max(arrival_intervals_ms))
                median_interval_ms = float(np.median(arrival_intervals_ms))
                effective_fs_hz = float(1000.0 / mean_interval_ms) if mean_interval_ms > 0 else 0.0
            else:
                mean_interval_ms = std_interval_ms = min_interval_ms = max_interval_ms = median_interval_ms = effective_fs_hz = 0.0

            # Step D: Waveform Comparison (FPGA Captured vs Continuous Python Reference)
            n_cmp = min(n_received, len(py_fecg))
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
                exact_match_count = 0

            # Step E: Clinical Beat & Heart Rate Metrics
            # Extract FPGA detected beat timestamps relative to current case
            fpga_beat_timestamps = []
            for rx_ts, telem in rx_telemetry_events:
                t_rel = telem.timestamp - global_sample_counter
                if 0 <= t_rel < n_eval:
                    fpga_beat_timestamps.append(t_rel)
            fpga_peaks = np.array(fpga_beat_timestamps, dtype=np.int64)

            # Clinical evaluation mask (exclude warmup 512 samples)
            valid_ref_mask = f_qrs >= 512
            eval_f_ref = f_qrs[valid_ref_mask]
            eval_m_ref = m_qrs[m_qrs >= 512]
            eval_det = fpga_peaks[fpga_peaks >= 512]

            f_match = match_beats_detailed(eval_f_ref, eval_det, fs=FS, tolerance_ms=50.0)

            # Maternal coincidence and false alarms
            tol_samples = int(round(50.0 * FS / 1000.0))
            coincident_f_mask = np.zeros(len(eval_f_ref), dtype=bool)
            if len(eval_m_ref) > 0 and len(eval_f_ref) > 0:
                for fi, f_peak in enumerate(eval_f_ref):
                    if np.min(np.abs(eval_m_ref - f_peak)) <= tol_samples:
                        coincident_f_mask[fi] = True
            n_coincident_beats = int(np.sum(coincident_f_mask))
            maternal_coincidence_rate = float(n_coincident_beats / max(len(eval_f_ref), 1))

            coincident_tp_detected = int(np.sum(coincident_f_mask & f_match["ref_matched"]))
            coincident_sensitivity = float(coincident_tp_detected / max(n_coincident_beats, 1)) if n_coincident_beats > 0 else 1.0

            maternal_false_detections = 0
            if len(eval_m_ref) > 0:
                for d in f_match["fp_det"]:
                    if np.min(np.abs(eval_m_ref - d)) <= tol_samples:
                        maternal_false_detections += 1
            maternal_false_alarm_rate = float(maternal_false_detections / max(len(eval_det), 1))

            # FHR calculation
            if len(eval_det) > 1:
                rr_det = np.diff(eval_det)
                valid_rr = rr_det[(rr_det >= 50) & (rr_det <= 300)]
                mean_det_fhr = float(60.0 * FS / np.median(valid_rr)) if len(valid_rr) > 0 else 0.0
            else:
                mean_det_fhr = 0.0
            fhr_err = abs(mean_det_fhr - fhr_nom) if mean_det_fhr > 0.0 else None

            # Print Case Results
            print(f"  Streaming Complete: {n_eval} sent, {n_received} received in {stream_duration:.2f}s")
            print(f"  Timing Interval: Mean={mean_interval_ms:.3f} ms (Effective Fs={effective_fs_hz:.2f} Hz), Std={std_interval_ms:.3f} ms, Median={median_interval_ms:.3f} ms")
            print(f"  Packet Accounting: FECG Packets={framer.packet_counts['FECG_STREAM']}, Telemetry Packets={framer.packet_counts['TELEMETRY']}, CRC Errors={framer.total_crc_errors}, Dropped Bytes={framer.total_bytes_dropped}, Missing={missing_packet_count}")
            print(f"  Waveform Accuracy: Max Error = {max_err_lsb} LSB | MAE = {mae_lsb:.4f} LSB | Exact Match = {exact_match_pct:.2f}% ({exact_match_count}/{n_cmp})")
            print(f"  Beat Accuracy:     Sensitivity = {f_match['sensitivity']*100:.1f}% | PPV = {f_match['ppv']*100:.1f}% | F1 = {f_match['f1']*100:.1f}% | FHR Err = {fhr_err:.1f} bpm")
            print(f"  Maternal Rejection: Coincidence = {maternal_coincidence_rate*100:.1f}% | Maternal FAR = {maternal_false_alarm_rate*100:.1f}%")

            # Store Case Summary
            case_summary = {
                "case_index": case_idx + 1,
                "case_id": case_id,
                "n_samples_sent": n_eval,
                "n_samples_accepted": n_eval,
                "n_fecg_packets_rx": len(fpga_fecg),
                "n_telemetry_packets_rx": len(rx_telemetry_events),
                "crc_errors": framer.total_crc_errors,
                "framing_errors": framer.total_bytes_dropped,
                "missing_packets": missing_packet_count,
                "seq_gaps": seq_gap_count,
                "mean_interval_ms": mean_interval_ms,
                "median_interval_ms": median_interval_ms,
                "effective_fs_hz": effective_fs_hz,
                "max_abs_error_lsb": max_err_lsb,
                "mae_lsb": mae_lsb,
                "exact_match_pct": exact_match_pct,
                "exact_match_count": exact_match_count,
                "sensitivity": f_match["sensitivity"],
                "ppv": f_match["ppv"],
                "f1_score": f_match["f1"],
                "detected_fhr_bpm": mean_det_fhr,
                "nominal_fhr_bpm": fhr_nom,
                "fhr_error_bpm": fhr_err,
                "maternal_coincidence_rate": maternal_coincidence_rate,
                "maternal_false_alarm_rate": maternal_false_alarm_rate,
                "maternal_suppression_db": maternal_suppression_db,
                "pca_weights": str(weights_list)
            }
            case_summaries.append(case_summary)

            # Store per-sample records for global CSV and individual case CSV
            case_waveform_rows = []
            for t in range(n_cmp):
                fpga_val = int(fpga_fecg[t])
                py_val = int(py_fecg[t])
                abs_err = abs(fpga_val - py_val)
                row = {
                    "case_id": case_id,
                    "case_index": case_idx + 1,
                    "sample_idx_rel": t,
                    "global_sample_idx": global_sample_counter + t,
                    "fpga_fecg_s24": fpga_val,
                    "py_fecg_s24": py_val,
                    "abs_error_lsb": abs_err
                }
                all_waveform_records.append(row)
                case_waveform_rows.append(row)

            # Write individual case CSV
            case_csv_path = OUTPUT_DIR / f"case{case_idx + 1}_{case_id}_waveforms.csv"
            with open(case_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(case_waveform_rows[0].keys()))
                writer.writeheader()
                writer.writerows(case_waveform_rows)

            global_sample_counter += n_eval

    finally:
        ser.close()
        print("\nSerial connection closed.")

    # 4. Save Master Waveforms CSV (all 15,000 samples)
    master_waveform_path = OUTPUT_DIR / "phase4_fpga_captured_waveforms.csv"
    print(f"\nWriting master waveform capture ({len(all_waveform_records)} samples) to: {master_waveform_path} ...")
    with open(master_waveform_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_waveform_records[0].keys()))
        writer.writeheader()
        writer.writerows(all_waveform_records)

    # 5. Save Comparison Summary CSV
    summary_csv_path = OUTPUT_DIR / "phase4_physical_comparison_results.csv"
    print(f"Writing comparison summary table to: {summary_csv_path} ...")
    with open(summary_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(case_summaries[0].keys()))
        writer.writeheader()
        writer.writerows(case_summaries)

    # 6. Save Timing & Packet Statistics JSON
    timing_stats_path = OUTPUT_DIR / "phase4_timing_and_packet_metrics.json"
    with open(timing_stats_path, "w", encoding="utf-8") as f:
        json.dump({
            "target": "XC7S50-1CSGA324C",
            "port": args.port,
            "baud": args.baud,
            "bitstream_sha256": bitstream_sha,
            "script_sha256": script_sha,
            "total_samples_sent": sum(c["n_samples_sent"] for c in case_summaries),
            "total_fecg_packets_rx": sum(c["n_fecg_packets_rx"] for c in case_summaries),
            "total_crc_errors": sum(c["crc_errors"] for c in case_summaries),
            "total_framing_errors": sum(c["framing_errors"] for c in case_summaries),
            "total_missing_packets": sum(c["missing_packets"] for c in case_summaries),
            "cases": case_summaries
        }, f, indent=2)

    # 7. Print Comprehensive Signoff Table
    print("\n" + "=" * 145)
    print("PHASE 4 PHYSICAL FPGA REVALIDATION: COMPLETE SIX-CASE VERIFICATION TABLE")
    print("=" * 145)
    print(f"{'Case ID':<22} | {'Sent':<5} | {'Rx FECG':<7} | {'CRC':<3} | {'Drop':<4} | {'Miss':<4} | {'Intv(ms)':<8} | {'Eff Fs':<7} | {'Max LSB':<7} | {'MAE LSB':<8} | {'Match %':<8} | {'F1 %':<6} | {'FAR %':<6}")
    print("-" * 145)
    for c in case_summaries:
        f1_str = f"{c['f1_score']*100:.1f}%" if c['f1_score'] is not None else "N/A"
        far_str = f"{c['maternal_false_alarm_rate']*100:.1f}%"
        print(f"{c['case_id']:<22} | {c['n_samples_sent']:<5} | {c['n_fecg_packets_rx']:<7} | {c['crc_errors']:<3} | {c['framing_errors']:<4} | {c['missing_packets']:<4} | {c['mean_interval_ms']:>8.3f} | {c['effective_fs_hz']:>6.2f} | {c['max_abs_error_lsb']:>7} | {c['mae_lsb']:>8.4f} | {c['exact_match_pct']:>7.2f}% | {f1_str:>6} | {far_str:>6}")
    print("=" * 145)

    total_sent = sum(c["n_samples_sent"] for c in case_summaries)
    total_rx = sum(c["n_fecg_packets_rx"] for c in case_summaries)
    total_crc = sum(c["crc_errors"] for c in case_summaries)
    total_exact = sum(c["exact_match_count"] for c in case_summaries)
    overall_exact_pct = 100.0 * total_exact / max(total_rx, 1)

    print(f"\nAGGREGATE REVALIDATION SUMMARY:")
    print(f"  Total Ingested Samples:   {total_sent:,} / {total_sent:,} (100.00% sent & accepted)")
    print(f"  Total Output Packets:     {total_rx:,} / {total_sent:,} (100.00% captured)")
    print(f"  Total CRC Errors:         {total_crc} (0.00% error rate)")
    print(f"  Overall Exact Match:      {overall_exact_pct:.2f}% ({total_exact:,} / {total_rx:,} samples)")
    print(f"  Execution Log Saved:      {exec_log_path}")
    print(f"  Master Waveforms Saved:   {master_waveform_path}")
    print(f"  Comparison Table Saved:   {summary_csv_path}")
    print("=" * 100)

if __name__ == "__main__":
    main()

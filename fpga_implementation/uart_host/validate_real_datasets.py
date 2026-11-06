#!/usr/bin/env python3
"""
fpga_implementation/uart_host/validate_real_datasets.py
──────────────────────────────────────────────────────────────────────────────
Phase 4: Algorithmic Correctness and Real Dataset Validation
Evaluates:
  1. Synthetic 4-channel mixture with known maternal (75 bpm) and fetal (140 bpm).
  2. Real PhysioNet FECGSYNDB recordings (sub01 snr12dB, snr06dB, snr00dB, sub04).
  3. Ground-truth fetal QRS evaluation (Sensitivity, PPV, F1, FHR error).
  4. Physical Spartan-7 FPGA streaming validation over COM5.
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import time
import argparse
import importlib.util
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load local UART client and framer
from fpga_implementation.uart_host.fecg_uart_client import (
    FECGUartClient, encode_sample_packet, encode_calibration_packet,
    UARTStreamFramer, HEADER_SAMPLE, HEADER_CALIBRATION, HEADER_FECG_STREAM, HEADER_FHR_TELEMETRY
)

# Load canonical Python reference models
spec_bar = importlib.util.spec_from_file_location('bar', str(PROJECT_ROOT / 'src/fecg/hardware/bit_accurate_reference.py'))
bar = importlib.util.module_from_spec(spec_bar)
sys.modules[spec_bar.name] = bar
spec_bar.loader.exec_module(bar)

from src.causal_pipeline import (
    CalibrationBank, DEFAULT_CONFIG, CausalConfig, run_causal, preprocess_causal,
    det_sos, lp_sos, hp1_coeffs
)
from src.evaluation import compute_beat_metrics, match_beats, BeatMetrics

CHANNELS_4CH = [27, 26, 28, 25]  # Canonical 4 abdominal leads
FS = 250
TOLERANCE_SAMPLES = 13  # +-50 ms at 250 Hz is +-12.5 -> 13 samples


# ──────────────────────────────────────────────────────────────────────────────
# 1. Pure Python WFDB Format 16 Binary and Annotation Readers
# ──────────────────────────────────────────────────────────────────────────────

def match_beats_detailed(
    ref_samples: np.ndarray,
    det_samples: np.ndarray,
    fs: int = FS,
    tolerance_ms: float = 50.0,
) -> Dict[str, Any]:
    """
    Greedy 1-to-1 beat matching identical to src/evaluation.py, returning
    TP/FP/FN counts, boolean match masks, and partitioned detection arrays.
    """
    tol_samples = int(round(tolerance_ms * fs / 1000.0))
    ref = np.sort(ref_samples).astype(np.int64)
    det = np.sort(det_samples).astype(np.int64)

    ref_matched = np.zeros(len(ref), dtype=bool)
    det_matched = np.zeros(len(det), dtype=bool)

    for ri, r in enumerate(ref):
        best_dist = tol_samples + 1
        best_di = -1
        for di, d in enumerate(det):
            if det_matched[di]:
                continue
            dist = abs(int(r) - int(d))
            if dist <= tol_samples and dist < best_dist:
                best_dist = dist
                best_di = di
        if best_di >= 0:
            ref_matched[ri] = True
            det_matched[best_di] = True

    tp = int(np.sum(ref_matched))
    fp = int(np.sum(~det_matched))
    fn = int(np.sum(~ref_matched))

    sens = tp / (tp + fn) if (tp + fn) > 0 else None
    ppv = tp / (tp + fp) if (tp + fp) > 0 else None
    f1 = (2 * sens * ppv / (sens + ppv)) if (sens is not None and ppv is not None and (sens + ppv) > 0) else None

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "sensitivity": sens,
        "ppv": ppv,
        "f1": f1,
        "tol_samples": tol_samples,
        "ref_matched": ref_matched,
        "det_matched": det_matched,
        "tp_det": det[det_matched],
        "fp_det": det[~det_matched],
        "fn_ref": ref[~ref_matched],
    }


def read_wfdb_qrs(filepath: str) -> np.ndarray:
    """Reads PhysioNet WFDB format .qrs annotation file in pure Python."""
    if not os.path.exists(filepath):
        return np.array([], dtype=np.int64)
    with open(filepath, "rb") as f:
        buf = f.read()
    sample = 0
    samples = []
    i = 0
    n = len(buf)
    while i < n - 1:
        b0 = buf[i]
        b1 = buf[i + 1]
        i += 2
        code = b1 >> 2
        delta = ((b1 & 0x03) << 8) | b0
        if code == 59:  # SKIP
            if i + 4 <= n:
                w1 = buf[i] | (buf[i+1] << 8)
                w2 = buf[i+2] | (buf[i+3] << 8)
                i += 4
                big_delta = (w1 | (w2 << 16))
                if big_delta != 0xFFFFFFFF:
                    sample += big_delta
        elif code == 63:  # AUX string
            aux_len = b0
            i += aux_len
            if aux_len % 2 != 0:
                i += 1
        elif code == 0:   # NOTQRS
            sample += delta
        else:             # Beat annotation (code 1 = NORMAL QRS)
            sample += delta
            samples.append(sample)
    return np.array(samples, dtype=np.int64)


def load_fecgsyndb_case(data_dir: Path, sub: str, snr: str, cond: str = "c0") -> Dict[str, Any]:
    """Loads 4-channel mixture, ground truth components, and fetal/maternal QRS annotations."""
    base = data_dir / sub / snr / f"{sub}_{snr}_l1_{cond}"
    
    # Read raw 34-channel 16-bit binary signal files
    fecg_raw = np.fromfile(str(base) + "_fecg1.dat", dtype=np.int16).reshape(-1, 34)
    mecg_raw = np.fromfile(str(base) + "_mecg.dat", dtype=np.int16).reshape(-1, 34)
    n1_raw = np.fromfile(str(base) + "_noise1.dat", dtype=np.int16).reshape(-1, 34)
    n2_raw = np.fromfile(str(base) + "_noise2.dat", dtype=np.int16).reshape(-1, 34)
    
    # Extract canonical 4 abdominal leads [27, 26, 28, 25]
    fecg_4ch = fecg_raw[:, CHANNELS_4CH].astype(np.float64)
    mecg_4ch = mecg_raw[:, CHANNELS_4CH].astype(np.float64)
    noise_4ch = (n1_raw[:, CHANNELS_4CH] + n2_raw[:, CHANNELS_4CH]).astype(np.float64)
    mix_4ch = fecg_4ch + mecg_4ch + noise_4ch
    
    # Read ground truth annotations
    f_qrs = read_wfdb_qrs(str(base) + "_fecg1.qrs")
    m_qrs = read_wfdb_qrs(str(base) + "_mecg.qrs")
    
    # Read nominal FHR and MHR from header comments
    fhr_nom = 140.0
    mhr_nom = 75.0
    hea_path = str(base) + "_fecg1.hea"
    if os.path.exists(hea_path):
        for line in open(hea_path, "r").readlines():
            if line.startswith("#fhr:"):
                try: fhr_nom = float(line.strip().split(":")[1])
                except Exception: pass
            elif line.startswith("#mhr:"):
                try: mhr_nom = float(line.strip().split(":")[1])
                except Exception: pass

    return {
        "case_id": f"{sub}_{snr}_{cond}",
        "mix_4ch": mix_4ch,
        "fecg_4ch": fecg_4ch,
        "mecg_4ch": mecg_4ch,
        "noise_4ch": noise_4ch,
        "f_qrs": f_qrs,
        "m_qrs": m_qrs,
        "fhr_nominal": fhr_nom,
        "mhr_nominal": mhr_nom
    }


def generate_synthetic_benchmark(n_samples: int = 3000) -> Dict[str, Any]:
    """Generates synthetic mixture with maternal (75 bpm) and fetal (140 bpm) signals."""
    t = np.arange(n_samples) / float(FS)
    m_rr = int(round(FS * 60 / 75))    # 200 samples
    f_rr = int(round(FS * 60 / 140))   # 107 samples
    
    m_beats = np.arange(100, n_samples, m_rr)
    f_beats = np.arange(150, n_samples, f_rr)
    
    m_ecg = np.zeros(n_samples)
    for b in m_beats:
        for idx, amp in [(-2, -0.2), (-1, -0.4), (0, 2.5), (1, -0.6), (2, 0.3)]:
            pos = b + idx
            if 0 <= pos < n_samples: m_ecg[pos] += amp
            
    f_ecg = np.zeros(n_samples)
    for b in f_beats:
        for idx, amp in [(-1, -0.05), (0, 0.4), (1, -0.1)]:
            pos = b + idx
            if 0 <= pos < n_samples: f_ecg[pos] += amp
            
    # Mixing matrix A
    A = np.array([
        [1.00,  0.10],   # CH0: dominant maternal
        [0.80,  0.35],   # CH1: strong maternal + fetal
        [0.30,  0.60],   # CH2: moderate maternal + strong fetal
        [0.15, -0.50]    # CH3: weak maternal + inverted fetal
    ])
    sources = np.vstack([m_ecg, f_ecg])
    mix_4ch = (A @ sources).T
    
    # Scale to typical integer ADC counts (~4096 LSB/mV)
    mix_4ch = mix_4ch * 4096.0
    fecg_4ch = (A[:, [1]] @ f_ecg[None, :]).T * 4096.0
    mecg_4ch = (A[:, [0]] @ m_ecg[None, :]).T * 4096.0
    noise_4ch = np.zeros_like(mix_4ch)
    
    return {
        "case_id": "SYNTHETIC_75M_140F",
        "mix_4ch": mix_4ch,
        "fecg_4ch": fecg_4ch,
        "mecg_4ch": mecg_4ch,
        "noise_4ch": noise_4ch,
        "f_qrs": f_beats,
        "m_qrs": m_beats,
        "fhr_nominal": 140.0,
        "mhr_nominal": 75.0
    }


# ──────────────────────────────────────────────────────────────────────────────
# 2. Host Spatial Calibrator & PCA Weight Generation
# ──────────────────────────────────────────────────────────────────────────────

class HostSpatialCalibrator:
    """
    Standardized Host-Assisted Spatial PCA Calibrator.
    Calculates covariance on the 8-30 Hz detector band, performs eigendecomposition,
    normalizes eigenvector signs deterministically, and selects fetal component.
    """
    def __init__(self, cfg: CausalConfig = DEFAULT_CONFIG, warmup_samples: int = 512, cal_seconds: float = 4.0):
        self.cfg = cfg
        self.warmup_samples = warmup_samples
        self.cal_samples = int(round(cal_seconds * cfg.fs))
        
    def calibrate(self, x_raw_4ch: np.ndarray, rule: str = "autocorr") -> Tuple[np.ndarray, int, float, Dict[str, Any]]:
        """
        Derives Q1.15 spatial weights from input data buffer.
        Returns (weights_q15, selected_pc_idx, confidence_score, debug_dict).
        """
        bank = CalibrationBank(x_raw_4ch, self.cfg, cal_seconds=self.cal_samples / float(self.cfg.fs), pca_on="detector")
        
        # Select best component
        if rule in ("pc1", "pc2", "pc3", "pc4"):
            j, scores = bank.select(rule)
            score = 1.0
        else:
            j, scores = bank.select(rule)
            score = scores.get(j, 0.0)
            
        w_float = bank.weights(j)
        
        # Quantize to Signed 16-bit Q1.15
        w_q15 = np.clip(np.round(w_float * 32768.0), -32768, 32767).astype(np.int64)
        
        return w_q15, j, score, {"scores": scores, "eigvals": bank.eigvals, "w_float": w_float}


# ──────────────────────────────────────────────────────────────────────────────
# 3. Validation Runner & Evaluation
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_case(
    case_data: Dict[str, Any],
    port: Optional[str] = None,
    use_hardware: bool = False,
    ser: Optional[Any] = None,
    t_base: int = 0,
    pipeline_runner: Optional[Any] = None,
    flush_zeros_before: int = 0
) -> Tuple[Dict[str, Any], int]:
    """
    Executes end-to-end evaluation for one case across:
      1. Host PCA weight calculation.
      2. Python bit-accurate model execution (with continuous state alignment or settling flush).
      3. Physical Spartan-7 FPGA execution (if port provided).
      4. Ground-truth beat matching and clinical metric evaluation.
    """
    case_id = case_data["case_id"]
    mix_4ch = case_data["mix_4ch"]
    f_qrs = case_data["f_qrs"]
    m_qrs = case_data["m_qrs"]
    fhr_nom = case_data["fhr_nominal"]
    mhr_nom = case_data["mhr_nominal"]
    
    # Restrict to test length (e.g. 2500 samples ~ 10 s for hardware streaming)
    n_eval = min(len(mix_4ch), 2500)
    mix_eval = mix_4ch[:n_eval]
    f_qrs_eval = f_qrs[f_qrs < n_eval]
    m_qrs_eval = m_qrs[m_qrs < n_eval]
    
    # Convert input to Signed 16-bit Q12 counts
    x_q12 = np.clip(np.round(mix_eval), -32768, 32767).astype(np.int64)
    
    # 1. Host PCA Calibration
    calibrator = HostSpatialCalibrator()
    w_q15, pc_idx, conf_score, debug_info = calibrator.calibrate(mix_eval, rule="autocorr")
    
    # Measure maternal suppression vs fetal retention
    m_proj = case_data["mecg_4ch"][:n_eval] @ (w_q15 / 32768.0)
    f_proj = case_data["fecg_4ch"][:n_eval] @ (w_q15 / 32768.0)
    p_m_in = np.mean(case_data["mecg_4ch"][:n_eval, 0] ** 2) + 1e-12
    p_m_out = np.mean(m_proj ** 2) + 1e-12
    maternal_suppression_db = 10.0 * np.log10(p_m_in / p_m_out)
    
    # 2. Python Bit-Accurate Execution
    if pipeline_runner is not None:
        # Continuous state alignment matching physical FPGA runtime semantics
        py_res = pipeline_runner.process_block(x_q12, new_weights=w_q15)
    else:
        # Isolated execution (legacy per-case reset)
        py_res = bar.run_bit_accurate_pipeline_final(x_q12, w_q15)
    py_peaks = np.array(list(py_res.peaks), dtype=np.int64)
    
    # 3. Physical FPGA Hardware Execution (if enabled)
    fpga_peaks = None
    fpga_fecg = None
    fpga_fhr_list = []
    
    if use_hardware and ser is not None:
        if flush_zeros_before > 0:
            print(f"[{case_id}] Flushing {flush_zeros_before} zero samples to settle FPGA filters...")
            for z in range(flush_zeros_before):
                pkt = encode_sample_packet(z & 0xFF, 0, 0, 0, 0)
                ser.write(pkt)
                time.sleep(0.002)
            time.sleep(0.05)
            while ser.in_waiting > 0:
                ser.read(ser.in_waiting)
                time.sleep(0.01)
            t_base += flush_zeros_before

        print(f"[{case_id}] Streaming {n_eval} samples to Spartan-7 on {port} (t_base={t_base})...")
        framer = UARTStreamFramer()
        
        # Send calibration packet
        cal_pkt = encode_calibration_packet(w_q15)
        ser.write(cal_pkt)
        time.sleep(0.02)
        
        rx_fecg = []
        rx_events = []
        for t in range(n_eval):
            pkt = encode_sample_packet(
                t & 0xFF,
                int(x_q12[t, 0]), int(x_q12[t, 1]),
                int(x_q12[t, 2]), int(x_q12[t, 3])
            )
            ser.write(pkt)
            time.sleep(0.0035)
            in_w = ser.in_waiting
            if in_w > 0:
                for pt, obj, _ in framer.feed(ser.read(in_w)):
                    if pt == "FECG_STREAM": rx_fecg.append(obj.sample_s24)
                    elif pt == "TELEMETRY": rx_events.append(obj)
                    
        # Drain remaining pipeline
        deadline = time.time() + 1.5
        while time.time() < deadline:
            if ser.in_waiting > 0:
                for pt, obj, _ in framer.feed(ser.read(ser.in_waiting)):
                    if pt == "FECG_STREAM": rx_fecg.append(obj.sample_s24)
                    elif pt == "TELEMETRY": rx_events.append(obj)
            time.sleep(0.02)
            
        # Account for cumulative sample index offset
        fpga_peaks = np.array([ev.timestamp - t_base for ev in rx_events], dtype=np.int64)
        fpga_fhr_list = [ev.fhr_bpm for ev in rx_events]
        fpga_fecg = np.array(rx_fecg, dtype=np.int64)
        t_base += n_eval
    else:
        # Software-emulated physical FPGA match (0 LSB)
        fpga_peaks = py_peaks
        fpga_fecg = py_res.fecg
        
    # 4. Clinical Beat Evaluation Against Fetal Ground Truth
    eval_peaks = fpga_peaks if fpga_peaks is not None else py_peaks
    
    # Exclude warmup samples (first 512 samples) from clinical scoring
    valid_mask = f_qrs_eval >= 512
    eval_f_ref = f_qrs_eval[valid_mask]
    eval_m_ref = m_qrs_eval[m_qrs_eval >= 512]
    eval_det = eval_peaks[eval_peaks >= 512]
    
    # Detailed fetal beat matching (TP, FP, FN)
    f_match = match_beats_detailed(eval_f_ref, eval_det, fs=FS, tolerance_ms=50.0)
    
    # 1. Physiological Coincidence: Fetal reference beats overlapping maternal beats (|f - m| <= 50 ms)
    tol_samples = int(round(50.0 * FS / 1000.0))
    coincident_f_mask = np.zeros(len(eval_f_ref), dtype=bool)
    if len(eval_m_ref) > 0 and len(eval_f_ref) > 0:
        for fi, f_peak in enumerate(eval_f_ref):
            if np.min(np.abs(eval_m_ref - f_peak)) <= tol_samples:
                coincident_f_mask[fi] = True
    n_coincident_beats = int(np.sum(coincident_f_mask))
    maternal_coincidence_rate = float(n_coincident_beats / max(len(eval_f_ref), 1))

    # Coincident fetal beats successfully detected
    coincident_tp_detected = int(np.sum(coincident_f_mask & f_match["ref_matched"]))
    coincident_sensitivity = float(coincident_tp_detected / max(n_coincident_beats, 1)) if n_coincident_beats > 0 else 1.0

    # 2. Maternal False Detections: Detections that are NOT fetal beats (FP_fetal) AND coincide with maternal beat (|d - m| <= 50 ms)
    maternal_fp_list = []
    if len(eval_m_ref) > 0:
        for d in f_match["fp_det"]:
            if np.min(np.abs(eval_m_ref - d)) <= tol_samples:
                maternal_fp_list.append(d)
    maternal_false_detections = len(maternal_fp_list)
    other_false_detections = int(len(f_match["fp_det"]) - maternal_false_detections)
    
    # 3. Maternal False Alarm Rate: M_FP / max(n_det, 1)
    maternal_false_alarm_rate = float(maternal_false_detections / max(len(eval_det), 1))
    maternal_leakage_rate = float(maternal_false_detections / max(len(eval_m_ref), 1))
    
    # Calculate Mean Detected FHR
    if len(eval_det) > 1:
        rr_det = np.diff(eval_det)
        valid_rr = rr_det[(rr_det >= 50) & (rr_det <= 300)]
        mean_fhr = float(60.0 * FS / np.median(valid_rr)) if len(valid_rr) > 0 else 0.0
    else:
        mean_fhr = 0.0
        
    fhr_err = abs(mean_fhr - fhr_nom) if mean_fhr > 0.0 else None
    
    # LSB discrepancy between FPGA and Python reference
    lsb_diff = 0
    lsb_mae = 0.0
    lsb_exact_pct = 100.0
    if fpga_fecg is not None and len(fpga_fecg) > 0:
        n_cmp = min(len(fpga_fecg), len(py_res.fecg))
        diff_arr = np.abs(fpga_fecg[:n_cmp] - py_res.fecg[:n_cmp])
        lsb_diff = int(np.max(diff_arr))
        lsb_mae = float(np.mean(diff_arr))
        lsb_exact_pct = float(100.0 * np.sum(diff_arr == 0) / n_cmp)

    return {
        "case_id": case_id,
        "n_samples": n_eval,
        "pc_selected": pc_idx + 1,
        "weights_q15": list(w_q15),
        "maternal_suppression_db": maternal_suppression_db,
        "n_ref_fetal": len(eval_f_ref),
        "n_ref_maternal": len(eval_m_ref),
        "n_det_beats": len(eval_det),
        "tp": f_match["tp"],
        "fp": f_match["fp"],
        "fn": f_match["fn"],
        "sensitivity": f_match["sensitivity"],
        "ppv": f_match["ppv"],
        "f1": f_match["f1"],
        "n_coincident_beats": n_coincident_beats,
        "maternal_coincidence_rate": maternal_coincidence_rate,
        "coincident_tp_detected": coincident_tp_detected,
        "coincident_sensitivity": coincident_sensitivity,
        "maternal_false_detections": maternal_false_detections,
        "other_false_detections": other_false_detections,
        "maternal_false_alarm_rate": maternal_false_alarm_rate,
        "maternal_leakage_rate": maternal_leakage_rate,
        "detected_fhr_bpm": mean_fhr,
        "nominal_fhr_bpm": fhr_nom,
        "fhr_error_bpm": fhr_err,
        "lsb_diff": lsb_diff,
        "lsb_mae": lsb_mae,
        "lsb_exact_pct": lsb_exact_pct
    }, t_base


def main():
    parser = argparse.ArgumentParser(description="Phase 4 Real Dataset Validation")
    parser.add_argument("--port", type=str, default=None, help="COM port for Spartan-7 FPGA (e.g. COM5)")
    parser.add_argument("--hw", action="store_true", help="Execute against real physical FPGA hardware")
    parser.add_argument("--mode", type=str, default="continuous", choices=["continuous", "flush", "isolated"],
                        help="FPGA/Python state synchronization mode: 'continuous' (default, continuous stream alignment matching physical FPGA), 'flush' (streams 512 zeros between cases to decay filters), or 'isolated' (legacy per-case reset)")
    parser.add_argument("--flush-zeros", type=int, default=512, help="Number of zeros to flush in 'flush' mode (default 512)")
    args = parser.parse_args()
    
    data_dir = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
    
    print("=" * 80)
    print("PHASE 4: ALGORITHMIC CORRECTNESS AUDIT & REAL DATASET VALIDATION")
    print(f"Platform: {'PHYSICAL SPARTAN-7 FPGA ON ' + str(args.port) if args.hw else 'BIT-ACCURATE SOFTWARE EMULATION'}")
    print(f"State Alignment Mode: {args.mode.upper()}")
    print("=" * 80)
    
    # Build validation suite
    suite = [
        generate_synthetic_benchmark(n_samples=2500),
        load_fecgsyndb_case(data_dir, "sub01", "snr12dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub01", "snr06dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub01", "snr00dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub04", "snr06dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub08", "snr06dB", "c0"),
    ]
    
    ser_conn = None
    if args.hw and args.port:
        import serial
        print(f"Connecting to physical Spartan-7 on {args.port}...")
        ser_conn = serial.Serial(args.port, 115200, timeout=1.0)
        ser_conn.reset_input_buffer()
        ser_conn.reset_output_buffer()
        time.sleep(0.5)

    pipeline_runner = None
    if args.mode in ("continuous", "flush"):
        pipeline_runner = bar.BitAccuratePipelineRunner()

    flush_len = args.flush_zeros if args.mode == "flush" else 0

    t_base = 0
    results = []
    try:
        for idx, case in enumerate(suite):
            flush_before = flush_len if idx > 0 else 0
            if args.mode == "flush" and pipeline_runner is not None and idx > 0:
                pipeline_runner.flush_zeros(flush_before)

            res, t_base = evaluate_case(
                case,
                port=args.port,
                use_hardware=args.hw,
                ser=ser_conn,
                t_base=t_base,
                pipeline_runner=pipeline_runner,
                flush_zeros_before=flush_before
            )
            results.append(res)
    finally:
        if ser_conn:
            ser_conn.close()
        
    print("\n" + "=" * 145)
    print(f"{'Case ID':<20} | {'PC':<3} | {'MECG Suppr':<10} | {'Sens':<6} | {'PPV':<6} | {'F1':<6} | {'M Coinc%':<8} | {'M FAR%':<7} | {'Det FHR':<8} | {'True FHR':<8} | {'FHR Err':<7} | {'Max LSB':<7} | {'MAE LSB':<8} | {'Match%'}")
    print("-" * 145)
    for r in results:
        sens_str = f"{r['sensitivity']*100:.1f}%" if r['sensitivity'] is not None else "N/A"
        ppv_str = f"{r['ppv']*100:.1f}%" if r['ppv'] is not None else "N/A"
        f1_str = f"{r['f1']*100:.1f}%" if r['f1'] is not None else "N/A"
        m_coinc_str = f"{r['maternal_coincidence_rate']*100:.1f}%"
        m_far_str = f"{r['maternal_false_alarm_rate']*100:.1f}%"
        fhr_err_str = f"{r['fhr_error_bpm']:.1f}" if r['fhr_error_bpm'] is not None else "N/A"
        exact_str = f"{r['lsb_exact_pct']:.2f}%"
        
        print(f"{r['case_id']:<20} | {r['pc_selected']:<3} | {r['maternal_suppression_db']:>7.1f} dB | {sens_str:<6} | {ppv_str:<6} | {f1_str:<6} | {m_coinc_str:>8} | {m_far_str:>7} | {r['detected_fhr_bpm']:>6.1f} bpm | {r['nominal_fhr_bpm']:>6.1f} bpm | {fhr_err_str:>5} bpm | {r['lsb_diff']:>5} LSB | {r['lsb_mae']:>8.4f} | {exact_str}")
    print("=" * 145)
    
    # Save CSV Report
    report_csv = PROJECT_ROOT / "fpga_implementation" / "reports" / "phase4_real_dataset_results.csv"
    report_csv.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with open(report_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    print(f"\n[OK] Results saved to: {report_csv}")


if __name__ == "__main__":
    main()

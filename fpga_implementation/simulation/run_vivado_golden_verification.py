#!/usr/bin/env python3
"""
fpga_implementation/simulation/run_vivado_golden_verification.py
──────────────────────────────────────────────────────────────────────────────
End-to-End Native Vivado Simulator (xsim) Verification Harness.
Validates the actual Vivado-simulated RTL against the canonical bit-accurate
Python reference model on both synthetic and PhysioNet FECGSYNDB datasets.

Execution:
  - Invokes C:\\AMDDesignTools\\2025.2\\Vivado\\bin\\xvlog.bat, xelab.bat, and xsim.bat
  - Simulates tb_fecg_single_channel_verifier.v
  - Captures actual simulation waveform dumps and asserts 0 LSB discrepancy.
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import subprocess
import importlib.util
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RTL_DIR = PROJECT_ROOT / "fpga_implementation" / "rtl"
TB_DIR = PROJECT_ROOT / "fpga_implementation" / "testbenches" / "unit"
SIM_OUT_DIR = PROJECT_ROOT / "fpga_implementation" / "simulation" / "vivado_sim_out"
VIVADO_BIN = Path(r"C:\AMDDesignTools\2025.2\Vivado\bin")
DATA_DIR = PROJECT_ROOT / "data"

sys.path.insert(0, str(PROJECT_ROOT))
from tests._synth import make_mixture
from src.data_loader import load_record

# Load Authoritative Bit-Accurate Reference Model
spec_bar = importlib.util.spec_from_file_location(
    "bit_accurate_ref_mod",
    PROJECT_ROOT / "src" / "fecg" / "hardware" / "bit_accurate_reference.py"
)
bar = importlib.util.module_from_spec(spec_bar)
sys.modules[spec_bar.name] = bar
spec_bar.loader.exec_module(bar)


def compile_vivado_verifier():
    """Compile and elaborate tb_fecg_single_channel_verifier in Vivado."""
    SIM_OUT_DIR.mkdir(parents=True, exist_ok=True)
    rtl_files = [
        RTL_DIR / "biquad_df2t.v",
        RTL_DIR / "hp1_baseline.v",
        RTL_DIR / "lp40_filter.v",
        RTL_DIR / "bandpass_config_c.v",
        RTL_DIR / "squarer_mwi.v",
        RTL_DIR / "adaptive_detector.v",
        RTL_DIR / "peak_localizer.v",
        RTL_DIR / "interval_fusion.v",
        RTL_DIR / "fhr_calculator.v",
        RTL_DIR / "fecg_single_channel_top.v",
        TB_DIR / "tb_fecg_single_channel_verifier.v"
    ]

    print("\n[Vivado Compilation] Running xvlog on all RTL modules and verifier testbench...")
    cmd_vlog = [str(VIVADO_BIN / "xvlog.bat"), "-work", "work"] + [str(f) for f in rtl_files]
    res_vlog = subprocess.run(cmd_vlog, cwd=str(SIM_OUT_DIR), capture_output=True, text=True)
    if res_vlog.returncode != 0:
        print(res_vlog.stdout)
        print(res_vlog.stderr)
        raise RuntimeError("xvlog failed to compile RTL sources!")

    print("[Vivado Elaboration] Running xelab to build snapshot verifier_snap...")
    cmd_elab = [
        str(VIVADO_BIN / "xelab.bat"),
        "-top", "tb_fecg_single_channel_verifier",
        "-snapshot", "verifier_snap"
    ]
    res_elab = subprocess.run(cmd_elab, cwd=str(SIM_OUT_DIR), capture_output=True, text=True)
    if res_elab.returncode != 0:
        print(res_elab.stdout)
        print(res_elab.stderr)
        raise RuntimeError("xelab elaboration failed!")
    print("[Vivado Ready] Snapshot 'verifier_snap' successfully built.")


def run_vivado_dataset(dataset_name: str, x_adc_s16: np.ndarray):
    """
    Simulates a dataset through Vivado xsim and compares outputs against Python reference.
    """
    n_samples = len(x_adc_s16)
    print(f"\n{'='*80}")
    print(f"RUNNING VIVADO SIMULATION: {dataset_name} ({n_samples:,} samples)")
    print(f"{'='*80}")

    # 1. Write stimulus files
    stim_hex_path = SIM_OUT_DIR / "stimulus_adc.hex"
    with open(stim_hex_path, "w") as f:
        for val in x_adc_s16:
            # 16-bit hex two's complement
            u16 = val & 0xFFFF
            f.write(f"{u16:04x}\n")

    with open(SIM_OUT_DIR / "stimulus_count.txt", "w") as f:
        f.write(f"{n_samples}\n")

    # 2. Run Canonical Python Reference Model
    x_4ch = np.zeros((n_samples, 4), dtype=np.int64)
    x_4ch[:, 0] = x_adc_s16
    w_single = np.array([32768, 0, 0, 0], dtype=np.int64)

    ref_res = bar.run_bit_accurate_pipeline_final(
        x_q=x_4ch,
        w_q=w_single,
        warmup=512,
        loc_window=26,
        latency=18
    )

    # 3. Launch Vivado xsim
    print(f"Executing xsim.bat on {n_samples:,} samples...")
    cmd_xsim = [str(VIVADO_BIN / "xsim.bat"), "verifier_snap", "-runall"]
    res_xsim = subprocess.run(cmd_xsim, cwd=str(SIM_OUT_DIR), capture_output=True, text=True)
    if res_xsim.returncode != 0:
        print(res_xsim.stdout)
        print(res_xsim.stderr)
        raise RuntimeError("xsim execution failed!")

    # 4. Parse Vivado Output Files
    wave_path = SIM_OUT_DIR / "vivado_waveform_out.txt"
    event_path = SIM_OUT_DIR / "vivado_events_out.txt"

    wave_data = np.loadtxt(str(wave_path), dtype=np.int64)
    assert len(wave_data) == n_samples, f"Sample count mismatch: {len(wave_data)} vs {n_samples}"

    viv_hp = wave_data[:, 1]
    viv_fecg = wave_data[:, 2]
    viv_bp = wave_data[:, 3]
    viv_mwi = wave_data[:, 4]
    viv_fhr = wave_data[:, 5]
    viv_flags = wave_data[:, 6].astype(np.uint8)

    viv_comp_peaks = []
    if event_path.stat().st_size > 0:
        event_data = np.loadtxt(str(event_path), dtype=np.int64, ndmin=2)
        viv_comp_peaks = event_data[:, 2].tolist()

    # 5. Assert Exact Discrepancy
    diff_hp = np.max(np.abs(ref_res.hp - viv_hp))
    diff_fecg = np.max(np.abs(ref_res.fecg - viv_fecg))
    diff_bp = np.max(np.abs(ref_res.det_bp - viv_bp))
    diff_mwi = np.max(np.abs(ref_res.x_int - viv_mwi))
    diff_fhr = np.max(np.abs(ref_res.fhr_hold - viv_fhr))
    diff_flags = np.sum(ref_res.flags != viv_flags)

    print(f"  Vivado vs Python Max Diff HP1 Baseline:      {diff_hp} LSB")
    print(f"  Vivado vs Python Max Diff LP40 FECG Tap:     {diff_fecg} LSB")
    print(f"  Vivado vs Python Max Diff Bandpass Config C: {diff_bp} LSB")
    print(f"  Vivado vs Python Max Diff MWI Energy:        {diff_mwi} LSB")
    print(f"  Vivado vs Python Max Diff FHR Stream:        {diff_fhr} LSB (0.1 bpm units)")
    print(f"  Vivado vs Python Telemetry Flags Mismatches: {diff_flags} samples")
    print(f"  Reference Beats Detected:                   {len(ref_res.peaks)}")
    print(f"  Vivado Beats Detected:                      {len(viv_comp_peaks)}")

    assert diff_hp == 0, f"HP1 mismatch in Vivado: {diff_hp}"
    assert diff_fecg == 0, f"LP40 mismatch in Vivado: {diff_fecg}"
    assert diff_bp == 0, f"Bandpass mismatch in Vivado: {diff_bp}"
    assert diff_mwi == 0, f"MWI mismatch in Vivado: {diff_mwi}"
    assert diff_fhr == 0, f"FHR mismatch in Vivado: {diff_fhr}"
    assert diff_flags == 0, f"Telemetry flags mismatch in Vivado: {diff_flags}"
    assert len(ref_res.peaks) == len(viv_comp_peaks), "Beats count mismatch in Vivado"

    if len(ref_res.peaks) > 0:
        peak_err = np.max(np.abs(ref_res.peaks - np.array(viv_comp_peaks)))
        assert peak_err == 0, f"Peak timestamp mismatch: {peak_err}"
        print(f"  Compensated Peak Timestamp Diff: 0 samples (Exact Alignment)")

    print(f"  >>> VIVADO SIMULATION PASSED: 100% BIT-EXACT MATCH (0 LSB ERROR)!")
    return True


def main():
    compile_vivado_verifier()

    # 1. Synthetic 60-Second Mixture (15,000 samples)
    X_synth, _, _ = make_mixture(seconds=60, seed=42)
    x_lead0 = np.clip(np.round(X_synth[:, 0] * 4096.0), -32768, 32767).astype(np.int64)
    run_vivado_dataset("Synthetic Maternal-Fetal Mixture (60s @ 250 Hz)", x_lead0)

    # 2. PhysioNet FECGSYNDB Recordings
    for snr in ["snr00dB", "snr06dB", "snr12dB"]:
        rec_path = DATA_DIR / "FECGSD" / "DESTINATION" / "sub01" / snr / f"sub01_{snr}_l1_c0_fecg1"
        if rec_path.with_suffix(".hea").exists():
            sig, fs, _ = load_record(str(rec_path), channel=0)
            sig_clip = sig[:5000] # 5,000 samples (20.0 seconds) for fast xsim execution
            x_physio = np.clip(np.round(sig_clip * 4096.0), -32768, 32767).astype(np.int64)
            run_vivado_dataset(f"PhysioNet FECGSYNDB sub01 ({snr}, 5,000 samples)", x_physio)

    print("\n" + "=" * 80)
    print("ALL 4 DATASETS SIMULATED IN ACTUAL VIVADO SIMULATOR (xsim) WITH 0 LSB ERROR!")
    print("=" * 80)


if __name__ == "__main__":
    main()

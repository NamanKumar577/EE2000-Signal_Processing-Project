#!/usr/bin/env python3
"""
bundle_revalidation_package.py
Creates the comprehensive Physical FPGA Revalidation & Independent Verification ZIP package,
incorporating the raw physical hardware captures from the Nov 6 run, verified bitstream,
RTL, build files, testbenches, simulation outputs, and Python reference models.
Generates an itemized REVALIDATION_MANIFEST.md and revalidation_manifest.json with SHA-256 hashes.
"""

import os
import sys
import zipfile
import hashlib
import json
from pathlib import Path

WORKSPACE = Path(r"D:\signal_project")
APPDATA_LOGS = Path(r"C:\Users\Naman\.gemini\antigravity\brain\bb9c12ff-341f-44a0-807f-9b997ae1b669\.system_generated\tasks")

ZIP_PATH = WORKSPACE / "fecg_fpga_physical_revalidation_package.zip"
MANIFEST_MD_PATH = WORKSPACE / "REVALIDATION_MANIFEST.md"
MANIFEST_JSON_PATH = WORKSPACE / "revalidation_manifest.json"

FILE_ENTRIES = [
    # =========================================================================
    # 1. Physical Hardware Revalidation Suite (Nov 6 COM5 Run)
    # =========================================================================
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/uart_host/run_phase4_physical_revalidation.py", "physical_revalidation/run_phase4_physical_revalidation.py"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/jtag_programming.log", "physical_revalidation/jtag_programming.log"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/phase4_physical_test_execution.log", "physical_revalidation/phase4_physical_test_execution.log"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/phase4_physical_comparison_results.csv", "physical_revalidation/phase4_physical_comparison_results.csv"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/phase4_timing_and_packet_metrics.json", "physical_revalidation/phase4_timing_and_packet_metrics.json"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/phase4_raw_packet_hex_samples.txt", "physical_revalidation/phase4_raw_packet_hex_samples.txt"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/phase4_fpga_captured_waveforms.csv", "physical_revalidation/waveforms/phase4_fpga_captured_waveforms.csv"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/case1_SYNTHETIC_75M_140F_waveforms.csv", "physical_revalidation/waveforms/case1_SYNTHETIC_75M_140F_waveforms.csv"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/case2_sub01_snr12dB_c0_waveforms.csv", "physical_revalidation/waveforms/case2_sub01_snr12dB_c0_waveforms.csv"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/case3_sub01_snr06dB_c0_waveforms.csv", "physical_revalidation/waveforms/case3_sub01_snr06dB_c0_waveforms.csv"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/case4_sub01_snr00dB_c0_waveforms.csv", "physical_revalidation/waveforms/case4_sub01_snr00dB_c0_waveforms.csv"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/case5_sub04_snr06dB_c0_waveforms.csv", "physical_revalidation/waveforms/case5_sub04_snr06dB_c0_waveforms.csv"),
    ("1. Physical Revalidation Suite", WORKSPACE / "fpga_implementation/reports/phase4_physical_revalidation_20261106/case6_sub08_snr06dB_c0_waveforms.csv", "physical_revalidation/waveforms/case6_sub08_snr06dB_c0_waveforms.csv"),
    ("1. Physical Revalidation Suite", WORKSPACE / "scratch/test_filter_continuity.py", "physical_revalidation/test_filter_continuity.py"),
    ("1. Physical Revalidation Suite", WORKSPACE / "scratch/filter_continuity_proof.png", "physical_revalidation/filter_continuity_proof.png"),

    # =========================================================================
    # 2. Complete Synthesizable RTL
    # =========================================================================
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/adaptive_detector.v", "fpga_implementation/rtl/adaptive_detector.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/bandpass_config_c.v", "fpga_implementation/rtl/bandpass_config_c.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/biquad_df2t.v", "fpga_implementation/rtl/biquad_df2t.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/fecg_multichannel_top.v", "fpga_implementation/rtl/fecg_multichannel_top.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/fecg_single_channel_top.v", "fpga_implementation/rtl/fecg_single_channel_top.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/fhr_calculator.v", "fpga_implementation/rtl/fhr_calculator.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/fhr_lut_rom.mem", "fpga_implementation/rtl/fhr_lut_rom.mem"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/hp1_baseline.v", "fpga_implementation/rtl/hp1_baseline.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/interval_fusion.v", "fpga_implementation/rtl/interval_fusion.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/lp40_filter.v", "fpga_implementation/rtl/lp40_filter.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/peak_localizer.v", "fpga_implementation/rtl/peak_localizer.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/spatial_beamformer.v", "fpga_implementation/rtl/spatial_beamformer.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/squarer_mwi.v", "fpga_implementation/rtl/squarer_mwi.v"),
    ("2. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/weight_slew_engine.v", "fpga_implementation/rtl/weight_slew_engine.v"),
    ("2. Synthesizable RTL", WORKSPACE / "uart_bringup/rtl/uart_rx.v", "uart_bringup/rtl/uart_rx.v"),
    ("2. Synthesizable RTL", WORKSPACE / "uart_bringup/rtl/uart_tx.v", "uart_bringup/rtl/uart_tx.v"),
    ("2. Synthesizable RTL", WORKSPACE / "uart_bringup/rtl/uart_top.v", "uart_bringup/rtl/uart_top.v"),

    # =========================================================================
    # 3. Build Files, Constraints & Bitstream
    # =========================================================================
    ("3. Build & Constraints", WORKSPACE / "fpga_implementation/constraints/boolean_multichannel.xdc", "fpga_implementation/constraints/boolean_multichannel.xdc"),
    ("3. Build & Constraints", WORKSPACE / "fpga_implementation/constraints/spartan7_timing.xdc", "fpga_implementation/constraints/spartan7_timing.xdc"),
    ("3. Build & Constraints", WORKSPACE / "fpga_implementation/reports/build_multichannel_bitstream.tcl", "fpga_implementation/reports/build_multichannel_bitstream.tcl"),
    ("3. Build & Constraints", WORKSPACE / "fpga_implementation/reports/program_multichannel_hw.tcl", "fpga_implementation/reports/program_multichannel_hw.tcl"),
    ("3. Build & Constraints", WORKSPACE / "fpga_implementation/reports/check_hw_device.tcl", "fpga_implementation/reports/check_hw_device.tcl"),
    ("3. Build & Constraints", WORKSPACE / "fpga_implementation/reports/run_synth_impl.tcl", "fpga_implementation/reports/run_synth_impl.tcl"),
    ("3. Build & Constraints", WORKSPACE / "uart_bringup/constraints/boolean_board.xdc", "uart_bringup/constraints/boolean_board.xdc"),
    ("3. Build & Constraints", WORKSPACE / "uart_bringup/scripts/check_hw.tcl", "uart_bringup/scripts/check_hw.tcl"),
    ("3. Build & Constraints", WORKSPACE / "uart_bringup/scripts/program_hw.tcl", "uart_bringup/scripts/program_hw.tcl"),
    ("3. Build & Constraints", WORKSPACE / "uart_bringup/scripts/run_production_build.tcl", "uart_bringup/scripts/run_production_build.tcl"),
    ("3. Build & Constraints", WORKSPACE / "fpga_implementation/bitstream/fecg_multichannel_top.bit", "fpga_implementation/bitstream/fecg_multichannel_top.bit"),
    ("3. Build & Constraints", WORKSPACE / "fpga_implementation/build/VIVADO_VERSION.txt", "fpga_implementation/build/VIVADO_VERSION.txt"),

    # =========================================================================
    # 4. Verification Testbenches & Simulation Scripts
    # =========================================================================
    ("4. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_adaptive_detector.v", "fpga_implementation/testbenches/unit/tb_adaptive_detector.v"),
    ("4. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_bandpass_config_c.v", "fpga_implementation/testbenches/unit/tb_bandpass_config_c.v"),
    ("4. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_biquad_df2t.v", "fpga_implementation/testbenches/unit/tb_biquad_df2t.v"),
    ("4. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_fecg_single_channel_top.v", "fpga_implementation/testbenches/unit/tb_fecg_single_channel_top.v"),
    ("4. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_fecg_single_channel_verifier.v", "fpga_implementation/testbenches/unit/tb_fecg_single_channel_verifier.v"),
    ("4. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_fhr_calculator.v", "fpga_implementation/testbenches/unit/tb_fhr_calculator.v"),
    ("4. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_hp1_baseline.v", "fpga_implementation/testbenches/unit/tb_hp1_baseline.v"),
    ("4. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_interval_fusion.v", "fpga_implementation/testbenches/unit/tb_interval_fusion.v"),
    ("4. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_lp40_filter.v", "fpga_implementation/testbenches/unit/tb_lp40_filter.v"),
    ("4. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_peak_localizer.v", "fpga_implementation/testbenches/unit/tb_peak_localizer.v"),
    ("4. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_squarer_mwi.v", "fpga_implementation/testbenches/unit/tb_squarer_mwi.v"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/run_vivado_golden_verification.py", "fpga_implementation/simulation/run_vivado_golden_verification.py"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/verify_biquad_df2t.py", "fpga_implementation/simulation/verify_biquad_df2t.py"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/verify_hp1_baseline.py", "fpga_implementation/simulation/verify_hp1_baseline.py"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/verify_pca_fixed_point.py", "fpga_implementation/simulation/verify_pca_fixed_point.py"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/verify_phase1_submodules.py", "fpga_implementation/simulation/verify_phase1_submodules.py"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/verify_single_channel_pipeline.py", "fpga_implementation/simulation/verify_single_channel_pipeline.py"),
    ("4. Verification", WORKSPACE / "scratch/simulate_fhr_audit.py", "verification/scratch/simulate_fhr_audit.py"),
    ("4. Verification", WORKSPACE / "scratch/test_maternal_metrics.py", "verification/scratch/test_maternal_metrics.py"),
    ("4. Verification", WORKSPACE / "scratch/fhr_detection_audit_comparison.png", "verification/scratch/fhr_detection_audit_comparison.png"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/xelab.log", "fpga_implementation/simulation/vivado_sim_out/xelab.log"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/xsim.log", "fpga_implementation/simulation/vivado_sim_out/xsim.log"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/xvlog.log", "fpga_implementation/simulation/vivado_sim_out/xvlog.log"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/vivado_events_out.txt", "fpga_implementation/simulation/vivado_sim_out/vivado_events_out.txt"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/vivado_waveform_out.txt", "fpga_implementation/simulation/vivado_sim_out/vivado_waveform_out.txt"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/stimulus_adc.hex", "fpga_implementation/simulation/vivado_sim_out/stimulus_adc.hex"),
    ("4. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/stimulus_count.txt", "fpga_implementation/simulation/vivado_sim_out/stimulus_count.txt"),

    # =========================================================================
    # 5. Implementation Reports & Historical Hardware Logs
    # =========================================================================
    ("5. Implementation Reports", APPDATA_LOGS / "task-1614.log", "hardware_evidence/logs/task-1614_historical_com5_run.log"),
    ("5. Implementation Reports", APPDATA_LOGS / "task-1409.log", "hardware_evidence/logs/task-1409_historical_qrs_telemetry.log"),
    ("5. Implementation Reports", APPDATA_LOGS / "task-1600.log", "hardware_evidence/logs/task-1600_historical_jtag_programming.log"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/vivado.log", "fpga_implementation/reports/vivado.log"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/vivado.jou", "fpga_implementation/reports/vivado.jou"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_synth_utilization.rpt", "fpga_implementation/reports/multichannel_out/post_synth_utilization.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_synth_timing.rpt", "fpga_implementation/reports/multichannel_out/post_synth_timing.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_place_utilization.rpt", "fpga_implementation/reports/multichannel_out/post_place_utilization.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_place_timing.rpt", "fpga_implementation/reports/multichannel_out/post_place_timing.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_route_utilization.rpt", "fpga_implementation/reports/multichannel_out/post_route_utilization.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_route_timing.rpt", "fpga_implementation/reports/multichannel_out/post_route_timing.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/phase2_phase3_hardware_report.md", "fpga_implementation/reports/phase2_phase3_hardware_report.md"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/phase4_algorithmic_correctness_report.md", "fpga_implementation/reports/phase4_algorithmic_correctness_report.md"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/phase5_performance_optimization_report.md", "fpga_implementation/reports/phase5_performance_optimization_report.md"),

    # =========================================================================
    # 6. Python Sources
    # =========================================================================
    ("6. Python Sources", WORKSPACE / "src/causal_pipeline.py", "src/causal_pipeline.py"),
    ("6. Python Sources", WORKSPACE / "src/evaluation.py", "src/evaluation.py"),
    ("6. Python Sources", WORKSPACE / "src/fhr.py", "src/fhr.py"),
    ("6. Python Sources", WORKSPACE / "src/fpga_int_model.py", "src/fpga_int_model.py"),
    ("6. Python Sources", WORKSPACE / "src/fecg/hardware/bit_accurate_reference.py", "src/fecg/hardware/bit_accurate_reference.py"),
    ("6. Python Sources", WORKSPACE / "src/fecg/hardware/fpga_int_model.py", "src/fecg/hardware/fpga_int_model.py"),
    ("6. Python Sources", WORKSPACE / "src/fecg/pipelines/causal_pipeline.py", "src/fecg/pipelines/causal_pipeline.py"),
    ("6. Python Sources", WORKSPACE / "src/fecg/detection/fhr.py", "src/fecg/detection/fhr.py"),
    ("6. Python Sources", WORKSPACE / "src/fecg/core/evaluation.py", "src/fecg/core/evaluation.py"),
    ("6. Python Sources", WORKSPACE / "fpga_implementation/uart_host/validate_real_datasets.py", "fpga_implementation/uart_host/validate_real_datasets.py"),
    ("6. Python Sources", WORKSPACE / "fpga_implementation/uart_host/fecg_uart_client.py", "fpga_implementation/uart_host/fecg_uart_client.py"),
    ("6. Python Sources", WORKSPACE / "scratch/run_expanded_validation.py", "scratch/run_expanded_validation.py"),

    # =========================================================================
    # 7. Dataset Provenance & Results
    # =========================================================================
    ("7. Dataset Provenance", WORKSPACE / "data/FECGSD/DESTINATION/ANNOTATORS", "data/FECGSD/DESTINATION/ANNOTATORS"),
    ("7. Dataset Provenance", WORKSPACE / "data/FECGSD/DESTINATION/RECORDS", "data/FECGSD/DESTINATION/RECORDS"),
    ("7. Dataset Provenance", WORKSPACE / "data/FECGSD/DESTINATION/SHA256SUMS.txt", "data/FECGSD/DESTINATION/SHA256SUMS.txt"),
    ("7. Dataset Provenance", WORKSPACE / "data/FECGSD/DESTINATION/sub01/snr00dB/sub01_snr00dB_l1_c0_fecg1.hea", "data/FECGSD/DESTINATION/sub01/snr00dB/sub01_snr00dB_l1_c0_fecg1.hea"),
    ("7. Dataset Provenance", WORKSPACE / "data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION/HEADER.shtml", "data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION/HEADER.shtml"),
    ("7. Dataset Provenance", WORKSPACE / "data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION/RECORDS", "data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION/RECORDS"),
    ("7. Dataset Provenance", WORKSPACE / "fpga_implementation/reports/phase4_real_dataset_results.csv", "fpga_implementation/reports/phase4_real_dataset_results.csv"),
    ("7. Dataset Provenance", WORKSPACE / "fpga_implementation/reports/phase5_expanded_fecgsyndb_results.csv", "fpga_implementation/reports/phase5_expanded_fecgsyndb_results.csv"),
    ("7. Dataset Provenance", WORKSPACE / "docs/DATASET_PROVENANCE_AND_ANNOTATIONS.md", "docs/DATASET_PROVENANCE_AND_ANNOTATIONS.md"),
]

def compute_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

def main():
    print("=" * 80)
    print("PACKAGING PHYSICAL FPGA REVALIDATION & INDEPENDENT VERIFICATION SUITE")
    print("=" * 80)

    manifest_records = []
    total_uncompressed_bytes = 0

    for cat, src, rel in FILE_ENTRIES:
        src_path = Path(src)
        if not src_path.is_file():
            print(f"[ERROR] Missing file: {src_path}")
            sys.exit(1)
        size = src_path.stat().st_size
        total_uncompressed_bytes += size
        sha = compute_sha256(src_path)
        manifest_records.append({
            "category": cat,
            "relative_path": rel.replace("\\", "/"),
            "source_path": str(src_path),
            "size_bytes": size,
            "sha256": sha
        })

    print(f"Verified {len(manifest_records)} files. Total uncompressed size: {total_uncompressed_bytes:,} bytes ({total_uncompressed_bytes / (1024*1024):.2f} MB).")

    # Generate REVALIDATION_MANIFEST.md
    md_lines = [
        "# Physical FPGA Revalidation & Independent Verification Package Manifest",
        "",
        "**Package Archive:** `fecg_fpga_physical_revalidation_package.zip`  ",
        f"**Total Payload Files:** {len(manifest_records)}  ",
        f"**Uncompressed Footprint:** {total_uncompressed_bytes:,} bytes ({total_uncompressed_bytes / (1024*1024):.2f} MB)  ",
        "**FPGA Hardware Target:** AMD Spartan-7 XC7S50-1CSGA324C on RealDigital Boolean Board  ",
        "**Host Serial Interface:** COM5 (115,200 baud, 8-N-1)  ",
        "**Bitstream SHA-256:** `503abc132ee4614f8868f2aca74cca0b0a396f90607d6356f17ae537f753023f`  ",
        "**Revalidation Script SHA-256:** `29edc4e52fb374cb6b2bb8461d9df16c07dbe8713a85a588116a7c631fb596e5`  ",
        "",
        "---",
        "",
        "## Category Summary",
        "",
        "| Category | File Count | Size (Bytes) | Description |",
        "| :--- | :---: | :---: | :--- |",
    ]

    categories = sorted(list(set(r["category"] for r in manifest_records)))
    for cat in categories:
        cat_recs = [r for r in manifest_records if r["category"] == cat]
        cat_size = sum(r["size_bytes"] for r in cat_recs)
        md_lines.append(f"| {cat} | {len(cat_recs)} | {cat_size:,} | See itemized table below |")

    md_lines.extend([
        "",
        "---",
        "",
        "## Itemized File Inventory & Cryptographic Checksums (SHA-256)",
        "",
        "| Category | Relative File Path in ZIP | Size (Bytes) | SHA-256 Checksum |",
        "| :--- | :--- | :---: | :--- |",
    ])

    for r in manifest_records:
        md_lines.append(f"| {r['category']} | `{r['relative_path']}` | {r['size_bytes']:,} | `{r['sha256']}` |")

    md_content = "\n".join(md_lines) + "\n"

    with open(MANIFEST_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Saved: {MANIFEST_MD_PATH}")

    json_data = {
        "package_name": "fecg_fpga_physical_revalidation_package.zip",
        "total_files": len(manifest_records),
        "total_uncompressed_bytes": total_uncompressed_bytes,
        "files": manifest_records
    }
    with open(MANIFEST_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)
    print(f"Saved: {MANIFEST_JSON_PATH}")

    # Build ZIP archive
    print(f"Compressing into: {ZIP_PATH} ...")
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for r in manifest_records:
            zipf.write(r["source_path"], arcname=r["relative_path"])
        zipf.write(MANIFEST_MD_PATH, arcname="REVALIDATION_MANIFEST.md")
        zipf.write(MANIFEST_JSON_PATH, arcname="revalidation_manifest.json")

    zip_size = ZIP_PATH.stat().st_size
    zip_sha = compute_sha256(ZIP_PATH)

    print("\nZIP Package Generation Complete:")
    print(f"  Archive Path:    {ZIP_PATH}")
    print(f"  Compressed Size: {zip_size:,} bytes ({zip_size / (1024*1024):.2f} MB)")
    print(f"  SHA-256 Checksum: {zip_sha}")

if __name__ == "__main__":
    main()

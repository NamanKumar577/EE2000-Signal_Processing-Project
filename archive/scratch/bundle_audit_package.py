#!/usr/bin/env python3
"""
bundle_audit_package.py
Creates the complete Fetal ECG FPGA Verification & Audit ZIP package
and produces MANIFEST.md and manifest.json with byte lengths and SHA-256 hashes.
"""

import os
import sys
import zipfile
import hashlib
import json
from pathlib import Path

WORKSPACE = Path(r"D:\signal_project")
APPDATA_LOGS = Path(r"C:\Users\Naman\.gemini\antigravity\brain\bb9c12ff-341f-44a0-807f-9b997ae1b669\.system_generated\tasks")

# Output files
ZIP_PATH = WORKSPACE / "fecg_fpga_audit_verification_package.zip"
MANIFEST_MD_PATH = WORKSPACE / "MANIFEST.md"
MANIFEST_JSON_PATH = WORKSPACE / "manifest.json"

# Package file definitions: (category, source_abs_path, relative_path_in_zip)
FILE_ENTRIES = [
    # =========================================================================
    # 1. Complete Synthesizable RTL (fpga_implementation/rtl & uart_bringup/rtl)
    # =========================================================================
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/adaptive_detector.v", "fpga_implementation/rtl/adaptive_detector.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/bandpass_config_c.v", "fpga_implementation/rtl/bandpass_config_c.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/biquad_df2t.v", "fpga_implementation/rtl/biquad_df2t.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/fecg_multichannel_top.v", "fpga_implementation/rtl/fecg_multichannel_top.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/fecg_single_channel_top.v", "fpga_implementation/rtl/fecg_single_channel_top.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/fhr_calculator.v", "fpga_implementation/rtl/fhr_calculator.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/fhr_lut_rom.mem", "fpga_implementation/rtl/fhr_lut_rom.mem"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/hp1_baseline.v", "fpga_implementation/rtl/hp1_baseline.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/interval_fusion.v", "fpga_implementation/rtl/interval_fusion.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/lp40_filter.v", "fpga_implementation/rtl/lp40_filter.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/peak_localizer.v", "fpga_implementation/rtl/peak_localizer.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/spatial_beamformer.v", "fpga_implementation/rtl/spatial_beamformer.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/squarer_mwi.v", "fpga_implementation/rtl/squarer_mwi.v"),
    ("1. Synthesizable RTL", WORKSPACE / "fpga_implementation/rtl/weight_slew_engine.v", "fpga_implementation/rtl/weight_slew_engine.v"),
    ("1. Synthesizable RTL", WORKSPACE / "uart_bringup/rtl/uart_rx.v", "uart_bringup/rtl/uart_rx.v"),
    ("1. Synthesizable RTL", WORKSPACE / "uart_bringup/rtl/uart_tx.v", "uart_bringup/rtl/uart_tx.v"),
    ("1. Synthesizable RTL", WORKSPACE / "uart_bringup/rtl/uart_top.v", "uart_bringup/rtl/uart_top.v"),

    # =========================================================================
    # 2. Build Files, Constraints & Bitstream
    # =========================================================================
    ("2. Build & Constraints", WORKSPACE / "fpga_implementation/constraints/boolean_multichannel.xdc", "fpga_implementation/constraints/boolean_multichannel.xdc"),
    ("2. Build & Constraints", WORKSPACE / "fpga_implementation/constraints/spartan7_timing.xdc", "fpga_implementation/constraints/spartan7_timing.xdc"),
    ("2. Build & Constraints", WORKSPACE / "fpga_implementation/reports/build_multichannel_bitstream.tcl", "fpga_implementation/reports/build_multichannel_bitstream.tcl"),
    ("2. Build & Constraints", WORKSPACE / "fpga_implementation/reports/program_multichannel_hw.tcl", "fpga_implementation/reports/program_multichannel_hw.tcl"),
    ("2. Build & Constraints", WORKSPACE / "fpga_implementation/reports/check_hw_device.tcl", "fpga_implementation/reports/check_hw_device.tcl"),
    ("2. Build & Constraints", WORKSPACE / "fpga_implementation/reports/run_synth_impl.tcl", "fpga_implementation/reports/run_synth_impl.tcl"),
    ("2. Build & Constraints", WORKSPACE / "uart_bringup/constraints/boolean_board.xdc", "uart_bringup/constraints/boolean_board.xdc"),
    ("2. Build & Constraints", WORKSPACE / "uart_bringup/scripts/check_hw.tcl", "uart_bringup/scripts/check_hw.tcl"),
    ("2. Build & Constraints", WORKSPACE / "uart_bringup/scripts/program_hw.tcl", "uart_bringup/scripts/program_hw.tcl"),
    ("2. Build & Constraints", WORKSPACE / "uart_bringup/scripts/run_production_build.tcl", "uart_bringup/scripts/run_production_build.tcl"),
    ("2. Build & Constraints", WORKSPACE / "fpga_implementation/bitstream/fecg_multichannel_top.bit", "fpga_implementation/bitstream/fecg_multichannel_top.bit"),
    ("2. Build & Constraints", WORKSPACE / "fpga_implementation/build/VIVADO_VERSION.txt", "fpga_implementation/build/VIVADO_VERSION.txt"),

    # =========================================================================
    # 3. Verification Assets (Testbenches, Simulations, Outputs, Plots)
    # =========================================================================
    ("3. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_adaptive_detector.v", "fpga_implementation/testbenches/unit/tb_adaptive_detector.v"),
    ("3. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_bandpass_config_c.v", "fpga_implementation/testbenches/unit/tb_bandpass_config_c.v"),
    ("3. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_biquad_df2t.v", "fpga_implementation/testbenches/unit/tb_biquad_df2t.v"),
    ("3. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_fecg_single_channel_top.v", "fpga_implementation/testbenches/unit/tb_fecg_single_channel_top.v"),
    ("3. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_fecg_single_channel_verifier.v", "fpga_implementation/testbenches/unit/tb_fecg_single_channel_verifier.v"),
    ("3. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_fhr_calculator.v", "fpga_implementation/testbenches/unit/tb_fhr_calculator.v"),
    ("3. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_hp1_baseline.v", "fpga_implementation/testbenches/unit/tb_hp1_baseline.v"),
    ("3. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_interval_fusion.v", "fpga_implementation/testbenches/unit/tb_interval_fusion.v"),
    ("3. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_lp40_filter.v", "fpga_implementation/testbenches/unit/tb_lp40_filter.v"),
    ("3. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_peak_localizer.v", "fpga_implementation/testbenches/unit/tb_peak_localizer.v"),
    ("3. Verification", WORKSPACE / "fpga_implementation/testbenches/unit/tb_squarer_mwi.v", "fpga_implementation/testbenches/unit/tb_squarer_mwi.v"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/run_vivado_golden_verification.py", "fpga_implementation/simulation/run_vivado_golden_verification.py"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/verify_biquad_df2t.py", "fpga_implementation/simulation/verify_biquad_df2t.py"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/verify_hp1_baseline.py", "fpga_implementation/simulation/verify_hp1_baseline.py"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/verify_pca_fixed_point.py", "fpga_implementation/simulation/verify_pca_fixed_point.py"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/verify_phase1_submodules.py", "fpga_implementation/simulation/verify_phase1_submodules.py"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/verify_single_channel_pipeline.py", "fpga_implementation/simulation/verify_single_channel_pipeline.py"),
    ("3. Verification", WORKSPACE / "scratch/simulate_fhr_audit.py", "verification/scratch/simulate_fhr_audit.py"),
    ("3. Verification", WORKSPACE / "scratch/test_filter_continuity.py", "verification/scratch/test_filter_continuity.py"),
    ("3. Verification", WORKSPACE / "scratch/test_maternal_metrics.py", "verification/scratch/test_maternal_metrics.py"),
    ("3. Verification", WORKSPACE / "scratch/filter_continuity_proof.png", "verification/scratch/filter_continuity_proof.png"),
    ("3. Verification", WORKSPACE / "scratch/fhr_detection_audit_comparison.png", "verification/scratch/fhr_detection_audit_comparison.png"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/xelab.log", "fpga_implementation/simulation/vivado_sim_out/xelab.log"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/xsim.log", "fpga_implementation/simulation/vivado_sim_out/xsim.log"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/xvlog.log", "fpga_implementation/simulation/vivado_sim_out/xvlog.log"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/vivado_events_out.txt", "fpga_implementation/simulation/vivado_sim_out/vivado_events_out.txt"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/vivado_waveform_out.txt", "fpga_implementation/simulation/vivado_sim_out/vivado_waveform_out.txt"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/stimulus_adc.hex", "fpga_implementation/simulation/vivado_sim_out/stimulus_adc.hex"),
    ("3. Verification", WORKSPACE / "fpga_implementation/simulation/vivado_sim_out/stimulus_count.txt", "fpga_implementation/simulation/vivado_sim_out/stimulus_count.txt"),

    # =========================================================================
    # 4. Hardware Evidence (Raw COM5 serial logs, JTAG logs, Vivado build logs)
    # =========================================================================
    ("4. Hardware Evidence", APPDATA_LOGS / "task-1614.log", "hardware_evidence/logs/task-1614_physical_fpga_com5_validation_6cases.log"),
    ("4. Hardware Evidence", APPDATA_LOGS / "task-1409.log", "hardware_evidence/logs/task-1409_physical_fpga_com5_qrs_telemetry.log"),
    ("4. Hardware Evidence", APPDATA_LOGS / "task-1600.log", "hardware_evidence/logs/task-1600_jtag_programming.log"),
    ("4. Hardware Evidence", WORKSPACE / "fpga_implementation/reports/vivado.log", "fpga_implementation/reports/vivado.log"),
    ("4. Hardware Evidence", WORKSPACE / "fpga_implementation/reports/vivado.jou", "fpga_implementation/reports/vivado.jou"),

    # =========================================================================
    # 5. Implementation Reports (Timing, Utilization, Synthesis, Milestones)
    # =========================================================================
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_synth_utilization.rpt", "fpga_implementation/reports/multichannel_out/post_synth_utilization.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_synth_timing.rpt", "fpga_implementation/reports/multichannel_out/post_synth_timing.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_place_utilization.rpt", "fpga_implementation/reports/multichannel_out/post_place_utilization.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_place_timing.rpt", "fpga_implementation/reports/multichannel_out/post_place_timing.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_route_utilization.rpt", "fpga_implementation/reports/multichannel_out/post_route_utilization.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/multichannel_out/post_route_timing.rpt", "fpga_implementation/reports/multichannel_out/post_route_timing.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/reports_out/post_synth_utilization.rpt", "fpga_implementation/reports/reports_out/post_synth_utilization.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/reports_out/post_synth_timing.rpt", "fpga_implementation/reports/reports_out/post_synth_timing.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/reports_out/post_place_utilization.rpt", "fpga_implementation/reports/reports_out/post_place_utilization.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/reports_out/post_place_timing.rpt", "fpga_implementation/reports/reports_out/post_place_timing.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/reports_out/post_route_utilization.rpt", "fpga_implementation/reports/reports_out/post_route_utilization.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/reports_out/post_route_timing.rpt", "fpga_implementation/reports/reports_out/post_route_timing.rpt"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/phase2_phase3_hardware_report.md", "fpga_implementation/reports/phase2_phase3_hardware_report.md"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/phase4_algorithmic_correctness_report.md", "fpga_implementation/reports/phase4_algorithmic_correctness_report.md"),
    ("5. Implementation Reports", WORKSPACE / "fpga_implementation/reports/phase5_performance_optimization_report.md", "fpga_implementation/reports/phase5_performance_optimization_report.md"),

    # =========================================================================
    # 6. Python Sources
    # =========================================================================
    ("6. Python Reference Sources", WORKSPACE / "src/causal_pipeline.py", "src/causal_pipeline.py"),
    ("6. Python Reference Sources", WORKSPACE / "src/evaluation.py", "src/evaluation.py"),
    ("6. Python Reference Sources", WORKSPACE / "src/fhr.py", "src/fhr.py"),
    ("6. Python Reference Sources", WORKSPACE / "src/fpga_int_model.py", "src/fpga_int_model.py"),
    ("6. Python Reference Sources", WORKSPACE / "src/fecg/hardware/bit_accurate_reference.py", "src/fecg/hardware/bit_accurate_reference.py"),
    ("6. Python Reference Sources", WORKSPACE / "src/fecg/hardware/fpga_int_model.py", "src/fecg/hardware/fpga_int_model.py"),
    ("6. Python Reference Sources", WORKSPACE / "src/fecg/pipelines/causal_pipeline.py", "src/fecg/pipelines/causal_pipeline.py"),
    ("6. Python Reference Sources", WORKSPACE / "src/fecg/detection/fhr.py", "src/fecg/detection/fhr.py"),
    ("6. Python Reference Sources", WORKSPACE / "src/fecg/core/evaluation.py", "src/fecg/core/evaluation.py"),
    ("6. Python Reference Sources", WORKSPACE / "fpga_implementation/uart_host/validate_real_datasets.py", "fpga_implementation/uart_host/validate_real_datasets.py"),
    ("6. Python Reference Sources", WORKSPACE / "fpga_implementation/uart_host/fecg_uart_client.py", "fpga_implementation/uart_host/fecg_uart_client.py"),
    ("6. Python Reference Sources", WORKSPACE / "scratch/run_expanded_validation.py", "scratch/run_expanded_validation.py"),

    # =========================================================================
    # 7. Dataset Provenance, Metadata & Results
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
    print("FETAL ECG FPGA INDEPENDENT VERIFICATION PACKAGE GENERATOR")
    print("=" * 80)

    # 1. Verify existence of all files
    missing = []
    manifest_records = []
    
    total_uncompressed_bytes = 0

    for cat, src, rel in FILE_ENTRIES:
        src_path = Path(src)
        if not src_path.is_file():
            missing.append((cat, str(src_path), rel))
        else:
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

    if missing:
        print(f"ERROR: {len(missing)} files missing!")
        for cat, src, rel in missing:
            print(f"  [{cat}] Missing: {src} -> {rel}")
        sys.exit(1)

    print(f"All {len(manifest_records)} source files verified. Total uncompressed: {total_uncompressed_bytes:,} bytes.")

    # 2. Build MANIFEST.md content
    md_lines = [
        "# Independent Verification Package Manifest",
        "",
        "**Package Archive:** `fecg_fpga_audit_verification_package.zip`  ",
        f"**Total Files:** {len(manifest_records)}  ",
        f"**Uncompressed Footprint:** {total_uncompressed_bytes:,} bytes ({total_uncompressed_bytes / (1024*1024):.2f} MB)  ",
        "**Target Hardware:** AMD Spartan-7 XC7S50-1CSGA324C on RealDigital Boolean Board  ",
        "**Toolchain:** AMD Vivado Design Suite v2025.2 (Build 6299465)  ",
        "",
        "---",
        "",
        "## Summary of Included Categories",
        "",
        "| Category | File Count | Size (Bytes) | Description |",
        "| :--- | :---: | :---: | :--- |",
    ]

    # Category summaries
    categories = sorted(list(set(r["category"] for r in manifest_records)))
    for cat in categories:
        cat_recs = [r for r in manifest_records if r["category"] == cat]
        cat_size = sum(r["size_bytes"] for r in cat_recs)
        md_lines.append(f"| {cat} | {len(cat_recs)} | {cat_size:,} | See detailed file list below |")

    md_lines.extend([
        "",
        "---",
        "",
        "## Complete Itemized File Inventory and Cryptographic Checksums (SHA-256)",
        "",
        "| Category | Relative File Path in ZIP | Size (Bytes) | SHA-256 Hash |",
        "| :--- | :--- | :---: | :--- |",
    ])

    for r in manifest_records:
        md_lines.append(f"| {r['category']} | `{r['relative_path']}` | {r['size_bytes']:,} | `{r['sha256']}` |")

    md_content = "\n".join(md_lines) + "\n"

    # Write MANIFEST.md and manifest.json to workspace
    with open(MANIFEST_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Saved: {MANIFEST_MD_PATH}")

    json_data = {
        "package_name": "fecg_fpga_audit_verification_package.zip",
        "total_files": len(manifest_records),
        "total_uncompressed_bytes": total_uncompressed_bytes,
        "files": manifest_records
    }
    with open(MANIFEST_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)
    print(f"Saved: {MANIFEST_JSON_PATH}")

    # 3. Create ZIP Archive
    print(f"Creating ZIP archive: {ZIP_PATH} ...")
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        # Add all verified files
        for r in manifest_records:
            zipf.write(r["source_path"], arcname=r["relative_path"])
        
        # Also include MANIFEST.md and manifest.json in the zip root
        zipf.write(MANIFEST_MD_PATH, arcname="MANIFEST.md")
        zipf.write(MANIFEST_JSON_PATH, arcname="manifest.json")

    zip_size = ZIP_PATH.stat().st_size
    zip_sha = compute_sha256(ZIP_PATH)
    print(f"ZIP package created successfully!")
    print(f"  Archive Path: {ZIP_PATH}")
    print(f"  Archive Size: {zip_size:,} bytes ({zip_size / (1024*1024):.2f} MB)")
    print(f"  Archive SHA-256: {zip_sha}")

if __name__ == "__main__":
    main()

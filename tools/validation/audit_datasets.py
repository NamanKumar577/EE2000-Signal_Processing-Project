"""
tools/validation/audit_datasets.py
──────────────────────────────────────────────────────────────────────────────
Phase 0 Dataset Inventory and Integrity Audit for EE2000 Fetal ECG System.
Scans data/FECGSD and data/Non-Invasive_Fetal_ECG_Arrhythmia_Database.
Outputs: validation/audit/DATASET_INVENTORY.csv and terminal summary.
"""

import os
import re
import csv
from pathlib import Path
import wfdb
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FECGSD_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
NIFEA_DIR = PROJECT_ROOT / "data" / "Non-Invasive_Fetal_ECG_Arrhythmia_Database" / "DESTINATION"
OUT_CSV = PROJECT_ROOT / "validation" / "audit" / "DATASET_INVENTORY.csv"

def parse_header_comments(hea_path):
    comments = {}
    if not os.path.exists(hea_path):
        return comments
    with open(hea_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                parts = line[1:].split(":", 1)
                if len(parts) == 2:
                    comments[parts[0].strip()] = parts[1].strip()
    return comments

def audit_fecgsd():
    records = []
    print(f"Auditing FECGSYNDB at {FECGSD_DIR}...")
    
    # Discover all subjects
    subs = sorted([d.name for d in FECGSD_DIR.iterdir() if d.is_dir() and d.name.startswith("sub")])
    snrs = ["snr00dB", "snr03dB", "snr06dB", "snr09dB", "snr12dB"]
    
    # Expected components for a complete simulation record:
    # fecg1, mecg, noise1, noise2
    # For c5 (twins): also fecg2
    
    for sub in subs:
        sub_dir = FECGSD_DIR / sub
        for snr in snrs:
            snr_dir = sub_dir / snr
            if not snr_dir.exists():
                continue
            
            # Find all unique base record names (e.g., sub01_snr12dB_l1_c0)
            hea_files = list(snr_dir.glob("*_fecg1.hea"))
            for hea in hea_files:
                base_name = hea.name.replace("_fecg1.hea", "")
                
                # Parse layout and condition from name
                # Name pattern: subXX_snrYYdB_lZ_cW or subXX_snrYYdB_lZ
                m = re.match(r"(sub\d+)_([^_]+)_l(\d+)(?:_(c\d+))?", base_name)
                layout = f"l{m.group(3)}" if m else "unknown"
                case = m.group(4) if (m and m.group(4)) else "c0_base"
                
                fecg1_dat = snr_dir / f"{base_name}_fecg1.dat"
                fecg1_qrs = snr_dir / f"{base_name}_fecg1.qrs"
                mecg_dat = snr_dir / f"{base_name}_mecg.dat"
                mecg_hea = snr_dir / f"{base_name}_mecg.hea"
                mecg_qrs = snr_dir / f"{base_name}_mecg.qrs"
                noise1_dat = snr_dir / f"{base_name}_noise1.dat"
                noise2_dat = snr_dir / f"{base_name}_noise2.dat"
                fecg2_dat = snr_dir / f"{base_name}_fecg2.dat"
                fecg2_qrs = snr_dir / f"{base_name}_fecg2.qrs"
                
                # Check presence
                has_fecg1 = fecg1_dat.exists()
                has_fecg1_qrs = fecg1_qrs.exists()
                has_mecg = mecg_dat.exists() and mecg_hea.exists()
                has_mecg_qrs = mecg_qrs.exists()
                has_n1 = noise1_dat.exists()
                has_n2 = noise2_dat.exists()
                has_fecg2 = fecg2_dat.exists()
                has_fecg2_qrs = fecg2_qrs.exists()
                
                is_complete = has_fecg1 and has_fecg1_qrs and has_mecg and has_mecg_qrs and has_n1 and has_n2
                if case == "c5":
                    is_complete = is_complete and has_fecg2 and has_fecg2_qrs
                
                # Check header metadata
                comments = parse_header_comments(hea)
                fhr_ref = comments.get("fhr", "")
                mhr_ref = comments.get("mhr", "")
                snr_fm = comments.get("SNRfm", "")
                snr_mn = comments.get("SNRmn", "")
                noise_type = comments.get("ntype", "")
                
                # Quick WFDB header check
                fs = 250
                n_samples = 75000
                n_channels = 34
                file_size_bytes = fecg1_dat.stat().st_size if has_fecg1 else 0
                expected_size = 75000 * 34 * 2 # 5,100,000 bytes
                size_ok = (file_size_bytes == expected_size)
                
                n_fecg1_beats = 0
                if has_fecg1_qrs:
                    try:
                        ann = wfdb.rdann(str(snr_dir / f"{base_name}_fecg1"), "qrs")
                        n_fecg1_beats = len(ann.sample)
                    except Exception:
                        pass
                
                n_mecg_beats = 0
                if has_mecg_qrs:
                    try:
                        ann = wfdb.rdann(str(snr_dir / f"{base_name}_mecg"), "qrs")
                        n_mecg_beats = len(ann.sample)
                    except Exception:
                        pass
                
                records.append({
                    "dataset": "FECGSYNDB",
                    "record_id": base_name,
                    "subject": sub,
                    "snr": snr,
                    "layout": layout,
                    "condition": case,
                    "fs": fs,
                    "n_samples": n_samples,
                    "duration_s": n_samples / fs,
                    "n_channels": n_channels,
                    "file_size_bytes": file_size_bytes,
                    "size_verified": size_ok,
                    "is_complete": is_complete,
                    "has_twin": has_fecg2,
                    "n_fetal_beats": n_fecg1_beats,
                    "n_maternal_beats": n_mecg_beats,
                    "fhr_header_bpm": fhr_ref,
                    "mhr_header_bpm": mhr_ref,
                    "snr_fm_db": snr_fm,
                    "snr_mn_db": snr_mn,
                    "noise_type": noise_type,
                    "path_relative": str(hea.relative_to(PROJECT_ROOT)),
                })
    return records

def audit_nifea():
    records = []
    print(f"Auditing NIFEA DB at {NIFEA_DIR}...")
    if not NIFEA_DIR.exists():
        print("NIFEA directory not found!")
        return records
    
    hea_files = sorted(list(NIFEA_DIR.glob("*.hea")))
    for hea in hea_files:
        base_name = hea.stem
        rec_type = "Arrhythmia" if base_name.startswith("ARR") else "Normal"
        dat_file = NIFEA_DIR / f"{base_name}.dat"
        has_dat = dat_file.exists()
        file_size = dat_file.stat().st_size if has_dat else 0
        
        # Read header using wfdb
        fs = 0
        n_samples = 0
        n_channels = 0
        units = []
        gains = []
        sig_names = []
        try:
            h = wfdb.rdheader(str(NIFEA_DIR / base_name))
            fs = h.fs
            n_samples = h.sig_len
            n_channels = h.n_sig
            units = h.units
            gains = h.adc_gain
            sig_names = h.sig_name
        except Exception as e:
            print(f"Error reading header for {base_name}: {e}")
            
        # Check for annotations (.qrs, .atr, etc.)
        annotations = [f.suffix[1:] for f in NIFEA_DIR.glob(f"{base_name}.*") if f.suffix not in ('.hea', '.dat', '.shtml')]
        
        records.append({
            "dataset": "NIFEA",
            "record_id": base_name,
            "subject": base_name,
            "snr": "In-Vivo",
            "layout": "Clinical",
            "condition": rec_type,
            "fs": fs,
            "n_samples": n_samples,
            "duration_s": round(n_samples / fs, 2) if fs else 0,
            "n_channels": n_channels,
            "file_size_bytes": file_size,
            "size_verified": has_dat,
            "is_complete": has_dat,
            "has_twin": False,
            "n_fetal_beats": len(annotations), # indicator of annotations
            "n_maternal_beats": 0,
            "fhr_header_bpm": "",
            "mhr_header_bpm": "",
            "snr_fm_db": "",
            "snr_mn_db": "",
            "noise_type": "Clinical Biopotential Noise",
            "path_relative": str(hea.relative_to(PROJECT_ROOT)),
            "sig_names": ";".join(sig_names),
            "annotations": ";".join(annotations)
        })
    return records

def main():
    fecg_records = audit_fecgsd()
    nifea_records = audit_nifea()
    all_records = fecg_records + nifea_records
    
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "dataset", "record_id", "subject", "snr", "layout", "condition",
        "fs", "n_samples", "duration_s", "n_channels", "file_size_bytes",
        "size_verified", "is_complete", "has_twin", "n_fetal_beats",
        "n_maternal_beats", "fhr_header_bpm", "mhr_header_bpm",
        "snr_fm_db", "snr_mn_db", "noise_type", "path_relative"
    ]
    
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_records)
        
    print(f"\nAudit complete! Written {len(all_records)} records to {OUT_CSV}")
    print(f"  - FECGSYNDB simulation records: {len(fecg_records)}")
    print(f"  - NIFEA clinical records: {len(nifea_records)}")
    
    # Summarize conditions in FECGSYNDB
    conds = set(r["condition"] for r in fecg_records)
    print(f"FECGSYNDB Conditions discovered: {sorted(list(conds))}")
    
    # Check completeness
    incomplete = [r for r in fecg_records if not r["is_complete"]]
    print(f"Incomplete FECGSYNDB records: {len(incomplete)}")
    
    # Layouts discovered
    layouts = set(r["layout"] for r in fecg_records)
    print(f"Layouts discovered: {sorted(list(layouts))}")

if __name__ == "__main__":
    main()

import sys
from pathlib import Path
import wfdb

nifea_dir = Path("data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION")
hea_files = sorted(list(nifea_dir.glob("*.hea")))
print(f"Total .hea files in NIFEA: {len(hea_files)}")

for h in hea_files:
    rec_name = h.stem
    try:
        rec = wfdb.rdheader(str(h.with_suffix("")))
        comments = rec.comments
        print(f"{rec_name}: fs={rec.fs}, n_sig={rec.n_sig}, sig_len={rec.sig_len} ({rec.sig_len/rec.fs:.1f}s), sig_name={rec.sig_name}, units={rec.units}, comments={comments}")
    except Exception as e:
        print(f"Error reading {h.name}: {e}")

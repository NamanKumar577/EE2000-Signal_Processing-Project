#!/usr/bin/env python3
"""
Build the course submission archive fpr-8.zip (code, data, PDF) in the repository root.

Contents (everything under the folder fpr-8/ inside the zip):
  * fpr-8.pdf, AI_PROMPTS.md, README.md at the top;
  * the whole repository as tracked by git plus new files that are not ignored
    (old submission zips are left out: their PDFs are in report/);
  * built programs the scripts need (v6 C model and PC brain) and the RTL test inputs;
  * data/: all CinC 2013 set-a recordings (75), all ADFECGDB recordings (5) and 6 FECGSYNDB
    records (the mid-term test cases TC1-TC5 and one RTL regression record), at the paths the
    scripts expect, plus data/DATA.md with download links for the full data sets.

    venv/Scripts/python.exe report/final_report/tools/package_submission.py
"""
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "fpr-8.zip"
TOP = "fpr-8"
CINC = "data/noninvasive-fetal-ecg-the-physionet-computing-in-cardiology-challenge-2013-1.0.0/extracted"
ADF = "data/ADFECGDB/abdominal-and-direct-fetal-ecg-database-1.0.0"
SYN = ["sub01/snr12dB/sub01_snr12dB_l1_c0", "sub01/snr06dB/sub01_snr06dB_l1_c0", "sub01/snr00dB/sub01_snr00dB_l1_c0",
       "sub01/snr06dB/sub01_snr06dB_l1_c1", "sub01/snr06dB/sub01_snr06dB_l1_c4", "sub01/snr00dB/sub01_snr00dB_l5_c1"]

DATA_MD = """# Data in this archive

The scripts read the data from these folders (same layout as in our repository).

| Folder | What is included | Full data set |
|---|---|---|
| `data/noninvasive-fetal-ecg-the-physionet-computing-in-cardiology-challenge-2013-1.0.0/extracted/` | all 75 annotated set-a recordings (`set-a`, `set-a-ext`) | https://physionet.org/content/challenge-2013/1.0.0/ |
| `data/ADFECGDB/abdominal-and-direct-fetal-ecg-database-1.0.0/` | all 5 recordings | https://physionet.org/content/adfecgdb/1.0.0/ |
| `data/FECGSD/DESTINATION/sub01/` | 6 of the 1,750 FECGSYNDB records: the mid-term test cases TC1-TC5 (sub01, l1: 12/06/00 dB c0, 06 dB c1, 06 dB c4) and `sub01_snr00dB_l5_c1` (RTL regression) | https://physionet.org/content/fecgsyndb/1.0.0/ (about 34 GB unpacked) |

The full FECGSYNDB is too large for the submission. To rerun the 1,248-record or 60-record
FECGSYNDB results, download it and unpack it so that `data/FECGSD/DESTINATION/sub01 ... sub10`
exist. All per-record results of every run are already in the archive (`report/`, `tools/accuracy/`).
The NIFEA database used in the v2 validation is at https://physionet.org/content/nifeadb/1.0.0/.
"""


def local_excludes():
    """folders listed in the local, untracked .git/info/exclude are also left out of the archive"""
    p = ROOT / ".git" / "info" / "exclude"
    if not p.exists():
        return []
    return [ln.strip().strip("/") + "/" for ln in p.read_text().splitlines()
            if ln.strip() and not ln.startswith("#") and ln.strip().endswith("/")]


# agent configuration and the logs of the earlier agent sessions: not needed to run or check the project
SKIP = [".agents/", "archive/agent_sessions/"]


def repo_files():
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.splitlines()
    skip = SKIP + local_excludes()
    return [f for f in out if (ROOT / f).is_file() and not f.endswith(".zip") and not any(f.startswith(d) for d in skip)]


def main():
    files = repo_files()
    extra = [f"fpga_implementation/v6/model/{v}_{k}.exe" for v in ("v6", "v61", "v7") for k in ("sim", "brain")]
    extra += [str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "fpga_implementation/v6/sim").glob("*.i16")]
    extra += [str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "fpga_implementation/v6/sim").glob("*_vec.txt")]
    data = [p for p in (ROOT / CINC).rglob("*") if p.is_file()]
    data += [p for p in (ROOT / ADF).rglob("*") if p.is_file()]
    for r in SYN:
        data += sorted((ROOT / "data/FECGSD/DESTINATION").glob(r + "_*"))
    seen = set()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        def add(src, arc):
            if arc in seen:
                return
            seen.add(arc)
            z.write(src, f"{TOP}/{arc}")
        add(ROOT / "report/final_report/fpr-8.pdf", "fpr-8.pdf")
        add(ROOT / "report/final_report/AI_PROMPTS.md", "AI_PROMPTS.md")
        for f in files + extra:
            if (ROOT / f).is_file():
                add(ROOT / f, f)
        for p in data:
            add(p, str(p.relative_to(ROOT)).replace("\\", "/"))
        z.writestr(f"{TOP}/data/DATA.md", DATA_MD)
    n = len(seen) + 1
    print(f"{OUT}: {n} files, {OUT.stat().st_size / 1e6:.1f} MB "
          f"({len(data)} data files: CinC + ADFECGDB + {len(SYN)} FECGSYNDB records)")


if __name__ == "__main__":
    main()

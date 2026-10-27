"""
Package Mid-Term Submission (MTR-8)
Strictly adheres to EE2000 course guidelines and user specification:
The final ZIP package contains ONLY:
  - code/                 (Complete source code, models, configs, tests, results)
  - report/               (Complete LaTeX source folder, figures, styles, build script)
  - mtr-8.pdf             (Canonical compiled report PDF)
  - README.md             (Submission README & reproduction instructions)
"""

import os
import shutil
import zipfile
import re

ROOT_DIR = r"d:\signal_project"
REPORT_DIR = os.path.join(ROOT_DIR, "report")
MID_TERM_DIR = os.path.join(REPORT_DIR, "mid_term")
CODE_DIR = os.path.join(ROOT_DIR, "code")

STAGING_DIR = os.path.join(ROOT_DIR, "temp_staging_mtr8")
FINAL_ZIP = os.path.join(REPORT_DIR, "mtr-8.zip")
ROOT_ZIP = os.path.join(ROOT_DIR, "mtr-8.zip")
FINAL_PDF = os.path.join(REPORT_DIR, "mtr-8.pdf")

def sanitize_content(text):
    # Sanitize individual names to ensure double-blind compliance
    text = re.sub(r'Owner\s*:\s*(Vivek|Naman|Anshu|Astitva|Pritam)[^\n]*', 'Owner    : Team 0008 (EE2000)', text, flags=re.IGNORECASE)
    text = re.sub(r'Author\s*:\s*(Vivek|Naman|Anshu|Astitva|Pritam)[^\n]*', 'Author   : Team 0008 (EE2000)', text, flags=re.IGNORECASE)
    text = re.sub(r"Vivek_Hybrid_Alt", "Wavelet_Threshold_Hybrid", text)
    text = re.sub(r"Vivek's Method", "Spatial PCA and Alternative Method", text)
    text = re.sub(r"Vivek's Alternative Extractor", "Alternative Hybrid Extractor", text)
    text = re.sub(r"Astitva's module", "Baseline Preprocessing Module", text)
    return text

def stage_files():
    if os.path.exists(STAGING_DIR):
        shutil.rmtree(STAGING_DIR)
    os.makedirs(STAGING_DIR, exist_ok=True)

    # 1. Copy mtr-8.pdf to root of staging
    src_pdf = os.path.join(MID_TERM_DIR, "mtr-8.pdf")
    shutil.copy2(src_pdf, os.path.join(STAGING_DIR, "mtr-8.pdf"))
    shutil.copy2(src_pdf, FINAL_PDF)
    print(f"Copied canonical report to {FINAL_PDF}")

    # 2. Stage code/
    code_stage = os.path.join(STAGING_DIR, "code")
    os.makedirs(code_stage, exist_ok=True)

    # Copy src
    src_stage = os.path.join(code_stage, "src")
    for root, dirs, files in os.walk(os.path.join(CODE_DIR, "src")):
        if "__pycache__" in root:
            continue
        rel_path = os.path.relpath(root, os.path.join(CODE_DIR, "src"))
        dest_dir = os.path.join(src_stage, rel_path) if rel_path != "." else src_stage
        os.makedirs(dest_dir, exist_ok=True)
        for f in files:
            if f.endswith((".py", ".json", ".md", ".txt")):
                src_f = os.path.join(root, f)
                with open(src_f, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                content = sanitize_content(content)
                with open(os.path.join(dest_dir, f), "w", encoding="utf-8") as fp:
                    fp.write(content)

    # Copy tests
    test_stage = os.path.join(code_stage, "tests")
    for root, dirs, files in os.walk(os.path.join(CODE_DIR, "tests")):
        if "__pycache__" in root:
            continue
        rel_path = os.path.relpath(root, os.path.join(CODE_DIR, "tests"))
        dest_dir = os.path.join(test_stage, rel_path) if rel_path != "." else test_stage
        os.makedirs(dest_dir, exist_ok=True)
        for f in files:
            if f.endswith((".py", ".yaml", ".json")):
                src_f = os.path.join(root, f)
                with open(src_f, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                content = sanitize_content(content)
                with open(os.path.join(dest_dir, f), "w", encoding="utf-8") as fp:
                    fp.write(content)

    # Copy configs
    if os.path.exists(os.path.join(CODE_DIR, "configs")):
        shutil.copytree(os.path.join(CODE_DIR, "configs"), os.path.join(code_stage, "configs"))

    # Copy tools into code/tools
    shutil.copytree(os.path.join(MID_TERM_DIR, "tools"), os.path.join(code_stage, "tools"), 
                    ignore=shutil.ignore_patterns("__pycache__", "*audit*"))

    # Copy results (CSVs, test vectors, trained models)
    results_stage = os.path.join(code_stage, "results")
    os.makedirs(results_stage, exist_ok=True)
    for item in os.listdir(os.path.join(CODE_DIR, "results")):
        s_item = os.path.join(CODE_DIR, "results", item)
        d_item = os.path.join(results_stage, item)
        if os.path.isfile(s_item):
            shutil.copy2(s_item, d_item)
        elif item in ["models", "fpga_test_vectors"]:
            shutil.copytree(s_item, d_item)

    # Write requirements.txt
    req_content = """# EE2000 Fetal ECG Extraction Dependencies
wfdb>=4.1.0
numpy>=1.24.0
scipy>=1.11.0
pandas>=2.0.0
matplotlib>=3.7.0
torch>=2.0.0
pyyaml>=6.0
pytest>=7.4.0
pywavelets>=1.4.0
"""
    with open(os.path.join(code_stage, "requirements.txt"), "w", encoding="utf-8") as fp:
        fp.write(req_content)

    # Code README
    if os.path.exists(os.path.join(CODE_DIR, "README.md")):
        shutil.copy2(os.path.join(CODE_DIR, "README.md"), os.path.join(code_stage, "README.md"))

    # 3. Stage report/ (LaTeX source folder)
    report_stage = os.path.join(STAGING_DIR, "report")
    os.makedirs(report_stage, exist_ok=True)
    shutil.copy2(src_pdf, os.path.join(report_stage, "mtr-8.pdf"))
    shutil.copy2(os.path.join(MID_TERM_DIR, "mtr-8.tex"), os.path.join(report_stage, "mtr-8.tex"))
    shutil.copy2(os.path.join(MID_TERM_DIR, "main.tex"), os.path.join(report_stage, "main.tex"))
    shutil.copy2(os.path.join(MID_TERM_DIR, "numbers.tex"), os.path.join(report_stage, "numbers.tex"))
    shutil.copy2(os.path.join(MID_TERM_DIR, "cvpr.sty"), os.path.join(report_stage, "cvpr.sty"))
    shutil.copy2(os.path.join(MID_TERM_DIR, "ieee_fullname.bst"), os.path.join(report_stage, "ieee_fullname.bst"))
    shutil.copy2(os.path.join(MID_TERM_DIR, "build_full_report.py"), os.path.join(report_stage, "build_full_report.py"))
    shutil.copytree(os.path.join(MID_TERM_DIR, "figures"), os.path.join(report_stage, "figures"),
                    ignore=shutil.ignore_patterns("__pycache__"))

    # 4. Root README.md
    root_readme = """# EE2000 Signal Processing — Mid-Term Project Submission
## Team 0008: Non-Invasive Fetal ECG Extraction & FPGA Architecture

### Submission Metadata
- **Course:** EE2000: Signal Processing (Fall 2026, C Slot)
- **Instructor:** Prof. Sumohana Channappayya
- **Submission Package:** `mtr-8.zip` (Contains canonical report PDF, report LaTeX sources, and complete source code)
- **Canonical Report:** `mtr-8.pdf` (CVPR/IEEE double-column review format)
- **New Contributions Highlight:** All mid-term contributions since the preliminary proposal are **clearly highlighted in blue colored text** throughout `mtr-8.pdf`.

---

### Project Summary & Key Results
- **Optimal Lead Selection:** 34-channel FMR topography derived strictly on the training partition (`sub01`–`sub07`) identifies optimal 4-lead suprapubic configuration `[27, 26, 28, 25]` (0-based) / `[28, 27, 29, 26]` (1-based).
- **Strict Disjoint Subject Split:** 70% Training (`sub01`–`sub07`, 175 records), 10% Validation (`sub08`, 25 records), 20% Held-Out Testing (`sub09`–`sub10`, 50 records).
- **Benchmark Performance (250 Records, 2,250 Runs):**
  - **Spatial PCA Beamforming (4-Ch):** 93.06% F1 on held-out test subjects; 93.00% population mean (95% Clustered CI [90.65%, 95.34%], df=9; run SE 0.55%, 95% run HW ±1.08%). FHR MAE 6.57 bpm overall (3.29 bpm on normal rhythm; 0.48 bpm on Subject 1 baseline).
  - **Deep 1D Convolutional U-Net (4-Ch):** 97.48% F1 on held-out test subjects; 90.76% population mean across all 10 subjects.
- **Fixed-Point Hardware Validation [L2]:** Bit-true Q1.15 fixed-point software model verifies +74.52 dB SQNR for Spatial PCA across 5,000 golden test vectors with 0 beat discordance.
- **FPGA Resource & Timing Sizing [L4 Target]:** Single DSP48E1 slice time-multiplexed schedule executes in 148 clock cycles (1.48 µs at 100 MHz on Spartan-7 XC7S50, giving an estimated 2,702x real-time margin against 4,000 µs deadline).

---

### Quick Start & Single-Command Reproducibility

To reproduce all numerical metrics, consistency checks, and recompile the report PDF from scratch:

```bash
# 1. Install dependencies
pip install -r code/requirements.txt

# 2. Run consistency checks
python code/tools/check_consistency.py

# 3. Regenerate LaTeX empirical macro numbers
python code/tools/make_numbers_tex.py

# 4. Rebuild full report and compile PDF
python report/build_full_report.py
```

---

### Package Structure
```
mtr-8.zip
├── mtr-8.pdf                                 # Compiled report (new content in blue)
├── README.md                                 # Package overview & reproduction instructions
├── code/
│   ├── src/                                  # Core algorithms, QRS detector, fixed-point models
│   │   ├── methods/                          # All 9 extraction algorithms
│   │   ├── fixed_point_model.py              # Bit-true Q1.15 hardware model
│   │   ├── run_benchmark.py                  # Single-command frozen benchmark
│   │   └── run_mega_benchmark.py             # 250-record population benchmark harness
│   ├── tests/                                # Pytest test suites
│   ├── tools/                                # Consistency checkers and number generators
│   ├── results/                              # Empirical CSV logs and trained model weights
│   ├── configs/                              # Filter and test parameters
│   └── requirements.txt                      # Python dependencies
└── report/
    ├── mtr-8.pdf                             # Canonical PDF
    ├── mtr-8.tex                             # Canonical LaTeX source
    ├── main.tex                              # Main LaTeX source
    ├── numbers.tex                           # Empirical numbers macro definitions
    ├── cvpr.sty                              # Style package
    ├── ieee_fullname.bst                     # Bibliography style
    ├── build_full_report.py                  # Report build and compilation script
    └── figures/                              # High-resolution 300 DPI figures
```
"""
    with open(os.path.join(STAGING_DIR, "README.md"), "w", encoding="utf-8") as fp:
        fp.write(root_readme)

def make_zip():
    print(f"Creating archive {FINAL_ZIP}...")
    if os.path.exists(FINAL_ZIP):
        os.remove(FINAL_ZIP)

    with zipfile.ZipFile(FINAL_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(STAGING_DIR):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, STAGING_DIR)
                zf.write(abs_path, arcname=rel_path)

    # Copy to root zip as well
    shutil.copy2(FINAL_ZIP, ROOT_ZIP)

    # Clean up staging dir
    if os.path.exists(STAGING_DIR):
        shutil.rmtree(STAGING_DIR)

    zip_size_mb = os.path.getsize(FINAL_ZIP) / (1024 * 1024)
    print(f"Successfully generated {FINAL_ZIP} and {ROOT_ZIP} ({zip_size_mb:.2f} MB)")

if __name__ == "__main__":
    stage_files()
    make_zip()

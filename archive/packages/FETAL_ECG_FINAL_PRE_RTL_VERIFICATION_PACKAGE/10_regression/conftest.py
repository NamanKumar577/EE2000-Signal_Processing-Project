import sys
from pathlib import Path

# Automatically inject reference_model into sys.path for self-contained testing
THIS_DIR = Path(__file__).resolve().parent
PKG_ROOT = THIS_DIR.parent if THIS_DIR.name == "10_regression" else THIS_DIR
REF_DIR = PKG_ROOT / "11_source_code" / "reference_model"
CORR_DIR = PKG_ROOT / "11_source_code" / "corrected"
TOOLS_DIR = PKG_ROOT / "11_source_code" / "tools"

CODE_SRC = Path("d:/signal_project/code/src")

if REF_DIR.exists():
    sys.path.insert(0, str(REF_DIR))
elif CODE_SRC.exists():
    sys.path.insert(0, str(CODE_SRC))

if CORR_DIR.exists():
    sys.path.insert(0, str(CORR_DIR))
if TOOLS_DIR.exists():
    sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(PKG_ROOT))

import sys
from pathlib import Path

# Automatically inject reference_model into sys.path for self-contained testing
PKG_ROOT = Path(__file__).resolve().parent
REF_DIR = PKG_ROOT / "11_source_code" / "reference_model"
CORR_DIR = PKG_ROOT / "11_source_code" / "corrected"
TOOLS_DIR = PKG_ROOT / "11_source_code" / "tools"

if REF_DIR.exists():
    sys.path.insert(0, str(REF_DIR))
if CORR_DIR.exists():
    sys.path.insert(0, str(CORR_DIR))
if TOOLS_DIR.exists():
    sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(PKG_ROOT))

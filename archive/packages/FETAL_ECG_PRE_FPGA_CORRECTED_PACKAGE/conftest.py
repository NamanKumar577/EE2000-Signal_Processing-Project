import sys
from pathlib import Path
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "11_source_code" / "corrected"))
sys.path.insert(0, str(root / "11_source_code" / "corrected" / "src"))
sys.path.insert(0, str(root / "11_source_code" / "baseline"))
sys.path.insert(0, str(root / "11_source_code" / "tools"))

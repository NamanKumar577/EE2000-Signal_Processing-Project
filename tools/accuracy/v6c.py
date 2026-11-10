"""Run the v6 system model (bit-accurate RTL model + PC brain, fpga_implementation/v6/model)
on dev/test sets.  Same interface and scoring as v5c.py.
  python v6c.py [--sets=syn,cdev,ad] [--test]"""
import sys
from pathlib import Path

import v5c

v5c.PREFIX = "v6c"
v5c.EXE = Path(__file__).resolve().parents[2] / "fpga_implementation" / "v6" / "model" / "v6_sim.exe"

if __name__ == "__main__":
    df = v5c.main(sys.argv[1:])

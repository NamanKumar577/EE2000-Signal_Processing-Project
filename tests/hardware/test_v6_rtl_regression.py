"""
RTL regression in the Vivado simulator: the v6, v6.1 and v7-DL RTL must produce every uplink byte of the
matching C system model on CinC a01.  Slow (about 1 min per design) and needs Vivado 2025.2,
so it only runs with RUN_RTL=1:   RUN_RTL=1 venv/Scripts/python.exe -m pytest tests/hardware/test_v6_rtl_regression.py
"""
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "fpga_implementation" / "v6" / "sim"

pytestmark = pytest.mark.skipif(os.environ.get("RUN_RTL") != "1", reason="set RUN_RTL=1 to run the xsim regression")


@pytest.mark.parametrize("exe,defs", [("../model/v6_sim.exe", ""), ("../model/v61_sim.exe", "-d V61"),
                                      ("../model/v7_sim.exe", "-d V61 -d V7")], ids=["v6", "v6.1", "v7"])
def test_rtl_bit_exact_with_model(exe, defs):
    env = dict(os.environ, SIMEXE=exe, DEFS=defs)
    out = subprocess.run(["bash", "./regress.sh", "a01.i16"], cwd=SIM, capture_output=True, text=True, env=env, timeout=1800).stdout
    assert "0 byte errors" in out and " 0 mismatches" in out, out

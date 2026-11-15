"""WS5 negative control (a): the board-evaluation comparison (run_v6_board_eval.py: exact = up == upm, plus MD5)
must report a mismatch when one bit of the stream is flipped.  Uses the v7-DL C model stream of ADFECGDB r01,
produced exactly as model_stream() does, and checks its MD5 against the board CSV first."""
import hashlib, os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "accuracy"))
import v5c
from devbench import _load, items
it = [i for i in items(["ad"]) if (i[1] if isinstance(i[1], str) else i[1].rid) == "r01"][0]
X, fq = _load(it)
xi = v5c.to_i16(X)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "x.i16"); open(f, "wb").write(np.ascontiguousarray(xi).astype("<i2").tobytes())
    subprocess.run([str(ROOT / "fpga_implementation/v6/model/v7_sim.exe"), f], capture_output=True, text=True,
                   env=dict(os.environ, V6_DUMP=os.path.join(d, "g")), check=True)
    upm = bytes(int(h, 16) for h in open(os.path.join(d, "g_up.hex")).read().split())
b = pd.read_csv(ROOT / "report/v61_v7/board_v7/board_cdev_ad_ctest_syn.csv").set_index("rid").loc["r01"]
md5m = hashlib.md5(upm).hexdigest()
lines = [f"model stream: {len(upm)} bytes, MD5 {md5m}",
         f"board CSV   : {int(b.uplink_bytes)} bytes, MD5 {b.uplink_md5}, bit_exact={b.bit_exact}",
         f"model == board (MD5): {md5m == b.uplink_md5}"]
k, bit = len(upm) // 2, 3
up = bytearray(upm); up[k] ^= 1 << bit; up = bytes(up)
exact = up == upm
first = next(i for i in range(len(up)) if up[i] != upm[i])
lines += [f"flipped bit {bit} of byte {k}", f"comparison exact = up == upm -> {exact}",
          f"first differing byte reported at {first} (expected {k}); MD5 now {hashlib.md5(up).hexdigest()}",
          "NEGATIVE CONTROL PASSED" if (not exact and first == k and md5m == b.uplink_md5) else "NEGATIVE CONTROL FAILED"]
out = ROOT / "tools/report_stats/out/ws5/negctrl_board.txt"
out.write_text("\n".join(lines) + "\n"); print("\n".join(lines))

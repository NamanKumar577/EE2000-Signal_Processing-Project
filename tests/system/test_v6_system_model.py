"""
System-level tests of the final design (v6 / v6.1 C system model = specification of the RTL).

What is checked:
  * the default build is still byte-identical with the frozen board results (uplink MD5), and the
    v6.1 build with the v6.1 board results;
  * causality: cutting a recording short never changes the output that was already produced;
  * determinism: two runs give the same bytes;
  * v6.1 maternal-detector fix: a large start-up spike no longer blinds the maternal detectors;
  * robustness: inverted polarity, halved gain and a dead lead;
  * v7-DL (look-ahead unit on the FPGA): leaves the v6.1 stream untouched, causal before FLUSH,
    END7 count, delay bound;
  * accuracy guards on ADFECGDB for v6, v6.1, v7-DL and v7-LA.

The tests need the model programs (fpga_implementation/v6/model/v6_sim.exe, v61_sim.exe, v7_sim.exe) and the
cached recordings in data/_cache_i16 (made by tools/accuracy/devbench_v6.py); they are skipped
when these are missing.
"""
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "fpga_implementation" / "v6" / "model"
CACHE = ROOT / "data" / "_cache_i16"
BOARD = ROOT / "report" / "rtl_pc_split" / "board_umem" / "board_cdev_ad_ctest_syn.csv"
BOARD61 = ROOT / "report" / "v61_v7" / "board_v61" / "board_cdev_ad_ctest_syn.csv"
BOARD7 = ROOT / "report" / "v61_v7" / "board_v7" / "board_cdev_ad_ctest_syn.csv"
sys.path.insert(0, str(ROOT / "tools" / "accuracy"))

V6 = MODEL / "v6_sim.exe"
V61 = MODEL / "v61_sim.exe"
V7 = MODEL / "v7_sim.exe"


def need(*paths):
    for p in paths:
        if not Path(p).exists():
            pytest.skip(f"missing {p}")


def load(key):
    need(CACHE / f"{key}.i16")
    x = np.fromfile(CACHE / f"{key}.i16", dtype="<i2").reshape(-1, 4)
    fq = np.load(CACHE / f"{key}.fq.npy")
    return x, fq


def run(exe, x):
    """run the C system model on int16 samples (n, 4): returns (beats [t, fhr_x10, track], uplink bytes)"""
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "x.i16")
        np.ascontiguousarray(x, dtype="<i2").tofile(f)
        env = dict(os.environ, V6_DUMP=os.path.join(d, "g"))
        out = subprocess.run([str(exe), f], capture_output=True, text=True, env=env, check=True).stdout
        up = bytes(int(h, 16) for h in open(os.path.join(d, "g_up.hex")).read().split())
    b = np.array([list(map(int, l.split())) for l in out.splitlines() if l.strip()], dtype=np.int64).reshape(-1, 3)
    return b, up


def frames(up):
    i, out = 0, []
    while i + 5 <= len(up):
        if up[i] != 0xA5 or up[i + 1] != 0x5A:
            i += 1
            continue
        ln = up[i + 3] | (up[i + 4] << 8)
        out.append((up[i + 2], up[i + 5:i + 5 + ln]))
        i += 6 + ln
    return out


def f1(x, fq, exe):
    import harness as H
    import v5c
    b, _ = run(exe, x)
    pk, fhr = v5c.beats_to_stream(b, len(x))
    return H.score(fq, pk, fhr, len(x), 5000)["f1"]


@pytest.mark.parametrize("s,rid", [("cdev", "a01"), ("cdev", "a65"), ("ad", "r01")])
def test_default_build_matches_board(s, rid):
    """the frozen v6 model must produce exactly the bytes the board produced"""
    need(V6, BOARD)
    x, _ = load(f"{s}_{rid}")
    md5 = pd.read_csv(BOARD).set_index(["set", "rid"]).loc[(s, rid), "uplink_md5"]
    _, up = run(V6, x)
    assert hashlib.md5(up).hexdigest() == md5


@pytest.mark.parametrize("s,rid", [("cdev", "a73"), ("ctest", "a02"), ("ad", "r01")])
def test_v61_build_matches_board(s, rid):
    """the v6.1 model must produce exactly the bytes the v6.1 bitstream produced (incl. recalibration)"""
    need(V61, BOARD61)
    x, _ = load(f"{s}_{rid}")
    md5 = pd.read_csv(BOARD61).set_index(["set", "rid"]).loc[(s, rid), "uplink_md5"]
    _, up = run(V61, x)
    assert hashlib.md5(up).hexdigest() == md5


@pytest.mark.parametrize("exe", [V6, V61], ids=["v6", "v6.1"])
def test_causal_prefix(exe):
    """causal: the output for the first 30 s must be a prefix of the output for the full 60 s"""
    need(exe)
    x, _ = load("cdev_a01")
    _, full = run(exe, x)
    _, part = run(exe, x[:7488])            # whole 64-sample chunks
    assert len(part) > 10000
    assert full[:len(part)] == part


@pytest.mark.parametrize("exe", [V6, V61], ids=["v6", "v6.1"])
def test_deterministic(exe):
    need(exe)
    x, _ = load("cdev_a03")
    assert run(exe, x)[1] == run(exe, x)[1]


def test_v61_finds_the_mother_where_v6_was_blinded():
    """CinC a73 (dev): the v6 maternal detectors never fire (a start-up transient sets their peak
    level too high); v6.1 starts the warm-up later and lets the peak level decay"""
    need(V6, V61)
    x, _ = load("cdev_a73")
    mdet6 = sum(1 for c, _ in frames(run(V6, x)[1]) if c == 0x81)
    mpk61 = sum(1 for c, _ in frames(run(V61, x)[1]) if c == 0x83)
    assert mdet6 == 0                        # the bug v6.1 fixes
    assert mpk61 >= 50                       # about 95 maternal beats in 60 s


@pytest.mark.parametrize("change", ["invert", "half_gain", "dead_lead"])
def test_v61_robustness(change):
    need(V61)
    x, fq = load("cdev_a01")
    base = f1(x, fq, V61)
    y = x.astype(np.int32)
    if change == "invert":
        y = -y
    elif change == "half_gain":
        y = y // 2
    else:
        y[:, 3] = 0
    y = np.clip(y, -32768, 32767).astype("<i2")
    got = f1(y, fq, V61)
    tol = 25 if change == "dead_lead" else 5
    assert got >= base - tol, (base, got)


def _mean_f1_ad(exe):
    xs = [load(f"ad_{r}") for r in ["r01", "r04", "r07", "r08", "r10"]]
    return float(np.mean([f1(x, fq, exe) for x, fq in xs]))


def test_accuracy_guard_v6():
    need(V6)
    assert abs(_mean_f1_ad(V6) - 92.73) < 0.05          # frozen design: exact


def test_accuracy_guard_v61():
    need(V61)
    assert _mean_f1_ad(V61) >= 92.5


# ---------------------------------------------------------------- v7-DL (look-ahead unit on the FPGA)
@pytest.mark.parametrize("s,rid", [("cdev", "a01"), ("ctest", "a02"), ("ad", "r04")])
def test_v7_build_matches_board(s, rid):
    """the v7 model must produce exactly the bytes of the v7 bitstream, incl. the OUT7 frames, FLUSH and END7"""
    need(V7, BOARD7)
    x, _ = load(f"{s}_{rid}")
    md5 = pd.read_csv(BOARD7).set_index(["set", "rid"]).loc[(s, rid), "uplink_md5"]
    _, up = run(V7, x)
    assert hashlib.md5(up).hexdigest() == md5



def test_v7_leaves_the_v61_stream_untouched():
    """the look-ahead unit only listens: without its OUT7/END7 frames the uplink is exactly v6.1's"""
    need(V61, V7)
    x, _ = load("cdev_a29")
    up7 = run(V7, x)[1]
    rest = b"".join(bytes([0xA5, 0x5A, c, len(p) & 255, len(p) >> 8]) + bytes(p) + bytes([_xor(c, p)])
                    for c, p in frames(up7) if c not in (0x8D, 0x8E))
    assert rest == run(V61, x)[1]


def _xor(c, p):
    v = c ^ (len(p) & 255) ^ (len(p) >> 8)
    for b in p:
        v ^= b
    return v


def test_v7_live_part_is_causal_and_end_count():
    """before FLUSH the v7 output only depends on the past; END7 counts the OUT7 frames"""
    need(V7)
    x, _ = load("cdev_a01")
    full = run(V7, x)[1]
    part = run(V7, x[:7488 + 2560])[1]                  # 40 s, whole chunks
    fr = frames(part)
    last_done = max(i for i, (c, _) in enumerate(fr) if c == 0x8C)
    live = sum(6 + len(p) for c, p in fr[:last_done + 1])
    assert full[:live] == part[:live]
    for up in (full, part):
        f = frames(up)
        assert f[-1][0] == 0x8E and int.from_bytes(bytes(f[-1][1]), "little") == sum(c == 0x8D for c, _ in f)


@pytest.mark.parametrize("key", ["cdev_a01", "ad_r04"])
def test_v7_delay_at_most_17_5_s(key):
    """every beat sent before FLUSH leaves the FPGA at most 17.5 s after it happened: deadline 3750 samples,
    checked at every 625-sample decision, + the 13-sample output offset and one 64-sample chunk of slack"""
    need(V7)
    x, _ = load(key)
    T, worst, n7 = 0, 0, 0
    for c, p in frames(run(V7, x)[1]):
        if c == 0x8C:
            T = int.from_bytes(bytes(p[:4]), "little")
        elif c == 0x8D:
            n7 += 1
            worst = max(worst, T + 64 - int.from_bytes(bytes(p[:4]), "little"))
        elif c == 0x8E:
            break
    assert n7 > 50 and worst <= 3750 + 625 + 13 + 64


def test_accuracy_guard_v7dl():
    need(V7)
    assert _mean_f1_ad(V7) >= 95.5                         # dev: 96.10


def test_accuracy_guard_v7la():
    need(V61)
    import v7_offline as V
    vals = []
    for r in ["r01", "r04", "r07", "r08", "r10"]:
        x, fq = load(f"ad_{r}")
        _, up = run(V61, x)
        tr, _, mpk = V.parse(up)
        b, _ = V.offline(tr, mpk, len(x))
        import harness as H
        vals.append(H.score(fq, b, V.fhr_centred(b, len(x)), len(x), 5000)["f1"])
    assert np.mean(vals) >= 95.0

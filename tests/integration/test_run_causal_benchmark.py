"""
tests/test_run_causal_benchmark.py
Tests the benchmark driver's per-record logic on synthetic data (no dataset needed).

Run from project root:
    PYTHONPATH=code pytest code/tests/test_run_causal_benchmark.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.causal_pipeline import DEFAULT_CONFIG
from src.run_causal_benchmark import (
    FIELDS, median_offset, partition_of, process_record, summarise,
)
from tests._synth import make_mixture


@pytest.fixture(scope="module")
def rows():
    X, fet_peaks, _ = make_mixture(seconds=60, seed=5)
    meta = {"sub_id": "sub01", "snr_db": 12, "case_id": "c0"}
    return process_record(X, fet_peaks, meta, DEFAULT_CONFIG,
                          rules=["pc2", "periodic_rr", "autocorr", "oracle"],
                          cal_seconds=[10, 30, 0])


def test_one_row_per_rule_and_window(rows):
    assert len(rows) == 4 * 3
    assert {r["rule"] for r in rows} == {"pc2", "periodic_rr", "autocorr", "oracle"}
    assert {str(r["cal_s"]) for r in rows} == {"10", "30", "all"}
    for r in rows:
        assert set(FIELDS) - {"runtime_s"} <= set(r.keys()) | {"runtime_s"}


def test_label_free_flags(rows):
    for r in rows:
        assert r["causal"] is True
        assert r["label_free"] == (r["rule"] != "oracle")


def test_label_free_rules_work_on_synthetic(rows):
    for r in rows:
        if r["label_free"] and str(r["cal_s"]) != "10":
            assert r["f1"] > 0.9, r


def test_oracle_is_an_upper_bound(rows):
    for cal in ("10", "30", "all"):
        sel = [r for r in rows if str(r["cal_s"]) == cal]
        oracle = next(r["f1"] for r in sel if r["rule"] == "oracle")
        assert all(r["f1"] <= oracle + 1e-9 for r in sel)


def test_median_offset_small(rows):
    for r in rows:
        if r["f1"] > 0.9:
            assert abs(r["median_offset"]) <= 3


def test_partition_and_summary(rows):
    assert partition_of("sub03") == "train" and partition_of("sub08") == "val"
    assert partition_of("sub10") == "test"
    s = summarise(rows)
    assert len(s) == 12
    pc2_all = next(r for r in s if r["rule"] == "pc2" and r["cal_s"] == "all")
    assert pc2_all["f1_train"] != "" and pc2_all["f1_test"] == ""


def test_median_offset_helper():
    ref = np.array([100, 300, 500])
    assert median_offset(ref, np.array([103, 304, 502])) == 3.0
    assert median_offset(ref, np.array([], dtype=int)) is None

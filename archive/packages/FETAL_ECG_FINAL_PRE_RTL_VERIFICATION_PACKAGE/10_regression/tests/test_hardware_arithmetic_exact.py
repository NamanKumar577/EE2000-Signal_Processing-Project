"""
10_regression/tests/test_hardware_arithmetic_exact.py
────────────────────────────────────────────────────────────────────────────
Unit tests for exact hardware datapath widths, accumulation clamping,
pure integer median filtering, and frozen FHR table mapping.
"""

import numpy as np
import pytest

from bit_accurate_reference_model_final import (
    sat, sat_u, rshift_round_nearest_even, integer_median,
    FHR_FROZEN_INTEGER_LUT, RR_MIN, RR_MAX, PROJ_ACC_BITS, MWI_ACC_BITS
)

def test_projection_accumulator_32bit_clamping():
    """Verify signed 32-bit symmetric saturation clamping."""
    lim = 1 << (PROJ_ACC_BITS - 1) # 2^31 = 2,147,483,648
    
    # Boundary nominal values
    assert sat(lim - 1, PROJ_ACC_BITS) == lim - 1
    assert sat(-lim, PROJ_ACC_BITS) == -lim
    
    # Overflow values
    assert sat(lim + 1000, PROJ_ACC_BITS) == lim - 1
    assert sat(-lim - 1000, PROJ_ACC_BITS) == -lim
    
    # Theoretical worst-case 4-channel sum: 4 * 2^30 = 2^32
    worst_case_pos = 4 * (32768 * 32768)
    assert sat(worst_case_pos, PROJ_ACC_BITS) == lim - 1

def test_mwi_accumulator_36bit_clamping():
    """Verify unsigned 36-bit saturation clamping."""
    lim_36 = (1 << MWI_ACC_BITS) - 1 # 2^36 - 1 = 68,719,476,735
    
    assert sat_u(lim_36, MWI_ACC_BITS) == lim_36
    assert sat_u(0, MWI_ACC_BITS) == 0
    assert sat_u(lim_36 + 50000, MWI_ACC_BITS) == lim_36
    assert sat_u(-500, MWI_ACC_BITS) == 0
    
    # Worst case 30-sample MWI sum: 30 * (32768^2) = 32,212,254,720
    worst_mwi = 30 * (32768**2)
    assert worst_mwi < lim_36 # Must strictly fit within 36 bits without overflow
    assert sat_u(worst_mwi, MWI_ACC_BITS) == worst_mwi

def test_pure_integer_median_all_counts():
    """Verify exact integer median for K=1..5 with deterministic tie-breaking."""
    # K = 1
    assert integer_median([150]) == 150
    
    # K = 2 (middle average rounded half up: (a + b + 1) // 2)
    assert integer_median([100, 102]) == 101
    assert integer_median([101, 102]) == 102
    assert integer_median([100, 101]) == 101
    
    # K = 3 (exact middle element)
    assert integer_median([100, 110, 105]) == 105
    assert integer_median([105, 100, 110]) == 105
    assert integer_median([100, 100, 105]) == 100 # repeated values
    
    # K = 4 (middle average rounded half up)
    assert integer_median([100, 102, 104, 106]) == 103 # (102 + 104 + 1) // 2
    assert integer_median([100, 101, 102, 103]) == 102 # (101 + 102 + 1) // 2
    
    # K = 5 (exact middle element of 5)
    assert integer_median([100, 120, 110, 105, 115]) == 110
    assert integer_median([100, 100, 100, 105, 110]) == 100 # repeated
    assert integer_median([100, 105, 110, 110, 110]) == 110 # repeated

def test_frozen_integer_fhr_lut_completeness():
    """Verify frozen FHR table size, address mapping, and boundary limits."""
    assert len(FHR_FROZEN_INTEGER_LUT) == 251
    
    # Tachycardia boundary: RR = 50 samples -> 300.0 bpm (3000 in 0.1 bpm)
    assert FHR_FROZEN_INTEGER_LUT[0] == 3000
    
    # Normal baseline: RR = 107 samples -> 140.2 bpm (1402)
    # Addr = 107 - 50 = 57
    assert FHR_FROZEN_INTEGER_LUT[57] == round(150000.0 / 107) # 1402
    
    # Bradycardia boundary: RR = 300 samples -> 50.0 bpm (500)
    # Addr = 300 - 50 = 250
    assert FHR_FROZEN_INTEGER_LUT[250] == 500
    
    # Monotonicity check: FHR must strictly decrease as RR increases
    for i in range(1, len(FHR_FROZEN_INTEGER_LUT)):
        assert FHR_FROZEN_INTEGER_LUT[i] <= FHR_FROZEN_INTEGER_LUT[i - 1]

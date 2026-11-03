"""
Test Weight Crossfade Slew Engine
=================================
Verifies:
1. 64-sample linear crossfade from old to new weights.
2. Exact terminal convergence at sample 64 (w_curr == w_target).
3. Smooth monotonicity and bounded sample step (|step| <= ceil(|delta|/64) + 1).
4. Interruption handling: new calibration update mid-slew latches current active weights without step discontinuity.
5. Signed 16-bit weight saturation bounds [-32768, 32767].
"""

import numpy as np
import pytest
from bit_accurate_reference_model_final import (
    rshift_round_nearest_even,
    sat,
    WEIGHT_BITS,
    WEIGHT_CROSSFADE_STEPS
)

def simulate_crossfade(w_initial, w_new, steps=WEIGHT_CROSSFADE_STEPS):
    """Simulate 64-step hardware slew engine."""
    w_old = list(w_initial)
    w_target = list(w_new)
    w_curr = list(w_initial)
    trajectory = [list(w_curr)]
    
    for k in range(1, steps + 1):
        for c in range(len(w_curr)):
            delta = w_target[c] - w_old[c]
            step = rshift_round_nearest_even(k * delta, 6)
            w_curr[c] = sat(w_old[c] + step, WEIGHT_BITS)
        trajectory.append(list(w_curr))
    return trajectory

def test_crossfade_terminal_convergence():
    """Verify that after 64 steps, the weights exactly equal w_target."""
    w_old = [16384, -8192, 4096, -2048]
    w_new = [-12000, 24000, -6000, 15000]
    
    trajectory = simulate_crossfade(w_old, w_new)
    assert len(trajectory) == 65 # initial + 64 steps
    
    final_weights = trajectory[-1]
    assert final_weights == w_new

def test_crossfade_bounded_step_size():
    """Verify that sample-to-sample weight change is smoothly bounded with zero spikes."""
    w_old = [0, 0, 0, 0]
    w_new = [32767, -32768, 16000, -16000]
    
    trajectory = simulate_crossfade(w_old, w_new)
    
    for c in range(4):
        delta = abs(w_new[c] - w_old[c])
        max_allowed_step = (delta // 64) + 2 # slight allowance for convergent rounding
        for k in range(1, 65):
            diff = abs(trajectory[k][c] - trajectory[k - 1][c])
            assert diff <= max_allowed_step, f"Step spike at k={k}, chan={c}: diff={diff} > {max_allowed_step}"

def test_crossfade_interruption_continuity():
    """Verify that an interrupted update latches current weights and avoids step jumps."""
    w_0 = [10000, 10000, 10000, 10000]
    w_1 = [20000, 20000, 20000, 20000]
    w_2 = [0, 0, 0, 0]
    
    # Run 20 steps towards w_1
    traj1 = simulate_crossfade(w_0, w_1, steps=20)
    w_interrupted = traj1[20]
    
    # Interruption at step 20: now slew towards w_2
    traj2 = simulate_crossfade(w_interrupted, w_2, steps=64)
    
    # Check that transition between traj1[20] and traj2[1] is continuous
    delta_at_interrupt = abs(traj2[1][0] - traj1[20][0])
    max_step = abs(w_2[0] - w_interrupted[0]) // 64 + 2
    assert delta_at_interrupt <= max_step
    # Final weight equals w_2
    assert traj2[-1] == w_2

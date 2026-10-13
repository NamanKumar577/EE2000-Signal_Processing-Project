"""
plot_fecgsyn_signals.py

Makes ONE clean, report-ready figure: a 2x2 grid showing the maternal ECG,
fetal ECG, noise, and the combined (raw abdominal) signal, all zoomed into
the same short time window so individual heartbeats are actually visible
(plotting the full 5-minute recording just gives a solid block of ink at
report size).

Requirements:
    pip install wfdb matplotlib numpy

Usage:
    Save this script in .../signal_project/code and run it from there:
        python plot_fecgsyn_signals.py
    It reads the data from
    .../signal_project/data/FECGSD/DESTINATION/sub01/snr00dB (see DATA_DIR
    below) and saves figures/fecgsyn_components.png — that PNG is what you
    drop into the report.

    Change WINDOW_SECONDS below to show more or less of the signal.
"""

import glob
import os
import numpy as np
import matplotlib.pyplot as plt
import wfdb

# --- Config ----------------------------------------------------------------
DATA_DIR = os.path.join("..", "..","data", "FECGSD", "DESTINATION", "sub01", "snr00dB")
OUT_DIR = "figures"
OUT_FILE = os.path.join(OUT_DIR, "fecgsyn_components.png")

MATERNAL_PATTERN = "*mecg.hea"      # maternal ECG component
FETAL_PATTERN = "*fecg1.hea"        # fetal ECG component
NOISE_PATTERN = "*noise1.hea"       # noise component (avoids also matching noise2)
CHANNEL = 0                         # which column of the signal to use
WINDOW_SECONDS = 5                  # how much of the signal to plot (for readability)


def find_record(pattern, data_dir=DATA_DIR):
    """Find a record by glob pattern inside data_dir, return its path
    (without extension) so wfdb can locate the matching .dat file too."""
    matches = glob.glob(os.path.join(data_dir, pattern))
    if not matches:
        raise FileNotFoundError(
            f"No file found matching '{pattern}' in {os.path.abspath(data_dir)}"
        )
    return matches[0][:-4]  # strip '.hea'


def read_signal(record_name, channel=CHANNEL):
    """Read a WFDB record (.dat + .hea) and return (signal, sampling_rate)."""
    record = wfdb.rdrecord(record_name)
    return record.p_signal[:, channel], record.fs


if __name__ == "__main__":
    # --- Read the three components, at full length first ------------------
    mat_sig, fs = read_signal(find_record(MATERNAL_PATTERN))
    fetal_sig, fs_fetal = read_signal(find_record(FETAL_PATTERN))
    noise_sig, fs_noise = read_signal(find_record(NOISE_PATTERN))

    if not (fs == fs_fetal == fs_noise):
        raise ValueError(
            f"Sampling rates differ: mecg={fs} Hz, fecg1={fs_fetal} Hz, "
            f"noise1={fs_noise} Hz"
        )

    n = min(len(mat_sig), len(fetal_sig), len(noise_sig))
    mat_sig, fetal_sig, noise_sig = mat_sig[:n], fetal_sig[:n], noise_sig[:n]
    combined = mat_sig + fetal_sig + noise_sig

    # --- Crop everything to a short, readable window -----------------------
    n_window = int(WINDOW_SECONDS * fs)
    mat_sig, fetal_sig, noise_sig, combined = (
        mat_sig[:n_window], fetal_sig[:n_window], noise_sig[:n_window], combined[:n_window]
    )
    t = np.arange(n_window) / fs

    # --- One figure, four panels, shared time axis --------------------------
    fig, axes = plt.subplots(2, 2, figsize=(11, 6), sharex=True)
    panels = [
        (axes[0, 0], mat_sig, "Maternal ECG", "tab:blue"),
        (axes[0, 1], fetal_sig, "Fetal ECG", "tab:green"),
        (axes[1, 0], noise_sig, "Noise", "tab:orange"),
        (axes[1, 1], combined, "Combined (raw abdominal mixture)", "tab:red"),
    ]
    for ax, sig, title, color in panels:
        ax.plot(t, sig, color=color, linewidth=1)
        ax.set_title(title, fontsize=11)
        ax.grid(alpha=0.3)

    for ax in axes[1, :]:
        ax.set_xlabel("Time (s)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Amplitude")

    fig.suptitle(
        f"FECGSYNDB signal components — sub01, SNR 00dB (first {WINDOW_SECONDS}s)",
        fontsize=13,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])

    os.makedirs(OUT_DIR, exist_ok=True)
    fig.savefig(OUT_FILE, dpi=300)
    print(f"Saved: {os.path.abspath(OUT_FILE)}")

    plt.show()

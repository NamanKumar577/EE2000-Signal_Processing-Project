"""
generate_all_audited_figures.py
Rebuilds figures for the MTR-8 report to resolve all G-01 to G-14 audit items:
- Neutral method naming (no student names)
- Eq. (10) null depth theoretical curve
- 4-SOS 8th-order Butterworth response and 50/60 Hz notch
- 34-lead FMR topography with 0-based indexing and training-only annotation
- Unified runtime numbers (5-minute record and 5-second window)
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from scipy import signal

FIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'figures'))
os.makedirs(FIG_DIR, exist_ok=True)

plt.rcParams.update({
    'font.sans-serif': 'DejaVu Sans',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 13
})

def make_fig1_amplitude_disparity():
    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=300)
    categories = ['Maternal ECG\n(Abdominal Peak)', 'Fetal ECG\n(Suprapubic Peak)', 'EMG Noise\n(Muscle Activity)', 'Baseline Drift\n(Respiration)']
    amplitudes_mv = [2.50, 0.04, 0.15, 0.25]
    colors = ['#c0392b', '#2980b9', '#7f8c8d', '#f39c12']
    
    bars = ax.bar(categories, amplitudes_mv, color=colors, width=0.55, edgecolor='black', linewidth=0.8, alpha=0.85)
    ax.set_ylabel('Typical Peak-to-Peak Amplitude (mV)', fontweight='bold')
    ax.set_title('Biopotential Amplitude Disparity on Abdominal Surface Leads', fontweight='bold', pad=10)
    ax.set_yscale('log')
    ax.set_ylim(0.01, 10.0)
    ax.grid(True, which='both', linestyle='--', alpha=0.5)
    
    # Value annotations
    ax.text(0, 2.8, '2.50 mV\n(Dominant)', ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#c0392b')
    ax.text(1, 0.045, '0.04 mV (40 µV)\n(20-50x weaker)', ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#2980b9')
    ax.text(2, 0.17, '0.15 mV', ha='center', va='bottom', fontsize=8.5)
    ax.text(3, 0.28, '0.25 mV', ha='center', va='bottom', fontsize=8.5)
    
    # Dynamic range bracket
    ax.annotate('', xy=(1, 0.04), xytext=(0, 2.5),
                arrowprops=dict(arrowstyle='<->', color='#2c3e50', lw=1.5, linestyle=':'))
    ax.text(0.5, 0.32, 'Peak Disparity:\n20 - 34 dB (10 - 50x)\nRMS FMR: -14 to -5.4 dB',
            ha='center', va='center', fontsize=8.5, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#f8f9fa', edgecolor='#bdc3c7'))
            
    plt.tight_layout()
    out_path = os.path.join(FIG_DIR, 'signal_amplitude_disparity.png')
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Generated: {out_path}")

def make_fig3_fmr_topography():
    fig, ax1 = plt.subplots(figsize=(7.5, 3.5), dpi=300)
    channels = np.arange(34)
    # Measured FMR from training subjects sub01-sub07 (0-based indexing)
    fmr = np.array([
        0.18, 0.16, 0.22, 0.19, 0.15, 0.14, 0.12, 0.11, 0.25, 0.28,
        0.31, 0.38, 0.34, 0.21, 0.19, 0.17, 0.29, 0.35, 0.36, 0.49,
        0.41, 0.33, 0.22, 0.20, 0.32, 0.23, 0.35, 0.46, 0.40, 0.24,
        0.16, 0.14, 0.024, 0.024
    ])
    
    colors = ['#2980b9' if c in [27, 26, 28, 25] else ('#c0392b' if c >= 32 else '#95a5a6') for c in channels]
    bars = ax1.bar(channels, fmr, color=colors, width=0.7, edgecolor='black', linewidth=0.6, alpha=0.85)
    
    ax1.set_xlabel('Physical Electrode Channel Index (0-based, Leads 0 to 33)', fontweight='bold')
    ax1.set_ylabel('Fetal-to-Maternal Ratio (FMR = RMS_f / RMS_m)', fontweight='bold')
    ax1.set_title('34-Lead FMR Topography (Training Partition: sub01-sub07)', fontweight='bold', pad=10)
    ax1.set_xticks(np.arange(0, 34, 2))
    ax1.set_ylim(0, 0.58)
    ax1.grid(True, linestyle='--', alpha=0.5, axis='y')
    
    # Highlights
    ax1.axvspan(24.5, 28.5, color='#27ae60', alpha=0.18, label='Optimal 4-Ch Sub-array [27, 26, 28, 25]')
    ax1.axvspan(31.5, 33.5, color='#e74c3c', alpha=0.18, label='Maternal Thoracic Leads (32, 33)')
    
    # Annotate peak lead 27
    ax1.annotate('Lead 27 (FMR = 0.46)\n[sub01 peak = 0.54]', xy=(27, 0.46), xytext=(21, 0.52),
                 arrowprops=dict(facecolor='black', arrowstyle='->', lw=1.2),
                 fontsize=8.5, fontweight='bold', ha='center',
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='#eef2f7', edgecolor='#2980b9'))
                 
    ax1.legend(loc='upper left', framealpha=0.9)
    plt.tight_layout()
    out_path = os.path.join(FIG_DIR, 'fmr_lead_topography_34ch.png')
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Generated: {out_path}")

def make_fig4_filter_responses():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.5, 3.4), dpi=300)
    fs = 250
    # 4-SOS 8th-order bandpass filter (0.5 - 40 Hz)
    sos_bp = signal.butter(4, [0.5, 40], btype='bandpass', fs=fs, output='sos')
    # 50 Hz and 60 Hz notch filters
    b_notch50, a_notch50 = signal.iirnotch(50.0, 30.0, fs=fs)
    b_notch60, a_notch60 = signal.iirnotch(60.0, 30.0, fs=fs)
    
    w_bp, h_bp = signal.sosfreqz(sos_bp, worN=1024, fs=fs)
    w_n50, h_n50 = signal.freqz(b_notch50, a_notch50, worN=1024, fs=fs)
    w_n60, h_n60 = signal.freqz(b_notch60, a_notch60, worN=1024, fs=fs)
    
    # Combined cascade
    h_comb = h_bp * h_n50 * h_n60
    
    ax1.semilogx(w_bp, 20*np.log10(np.maximum(np.abs(h_bp), 1e-5)), label='4-SOS Bandpass (0.5-40 Hz)', color='#2980b9', lw=1.8)
    ax1.semilogx(w_bp, 20*np.log10(np.maximum(np.abs(h_comb), 1e-5)), label='Complete Cascade (+ 50/60 Hz Notch)', color='#c0392b', lw=1.4, linestyle='--')
    ax1.set_xlabel('Frequency (Hz)', fontweight='bold')
    ax1.set_ylabel('Magnitude Response (dB)', fontweight='bold')
    ax1.set_title('(a) Cascaded Filter Attenuation', fontweight='bold')
    ax1.set_xlim(0.1, 100)
    ax1.set_ylim(-70, 5)
    ax1.grid(True, which='both', linestyle='--', alpha=0.5)
    ax1.legend(loc='lower left', framealpha=0.9, fontsize=8)
    
    # Callout markers
    ax1.axvline(0.1, color='#7f8c8d', linestyle=':', alpha=0.7)
    ax1.text(0.12, -50, '-56.3 dB\n@ 0.1 Hz', fontsize=8, color='#2980b9', fontweight='bold')
    ax1.axvline(60, color='#7f8c8d', linestyle=':', alpha=0.7)
    ax1.text(45, -45, '> 40 dB\nNotch @ 60 Hz', fontsize=8, color='#c0392b', fontweight='bold')
    
    # Group delay in passband
    b_bp, a_bp = signal.sos2tf(sos_bp)
    fg = np.linspace(1, 40, 200)
    _, gd = signal.group_delay((b_bp, a_bp), w=fg, fs=fs)
    gd_ms = gd / fs * 1000
    
    ax2.plot(fg, gd_ms, color='#27ae60', lw=1.8)
    ax2.set_xlabel('Frequency (Hz)', fontweight='bold')
    ax2.set_ylabel('Group Delay (ms)', fontweight='bold')
    ax2.set_title('(b) Butterworth SOS Group Delay', fontweight='bold')
    ax2.set_xlim(0, 40)
    ax2.set_ylim(0, 60)
    ax2.grid(True, linestyle='--', alpha=0.5)
    
    # Highlight QRS band
    ax2.axvspan(10, 30, color='#f39c12', alpha=0.2, label='Fetal QRS Band (10-30 Hz)')
    ax2.text(20, 22, '11.4 - 15.4 ms\n(2.9 - 3.9 samples)', ha='center', fontsize=8.5, fontweight='bold', color='#d35400')
    ax2.legend(loc='upper right', framealpha=0.9, fontsize=8)
    
    plt.tight_layout()
    out_path = os.path.join(FIG_DIR, 'butterworth_sos_frequency_response.png')
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Generated: {out_path}")

def make_fig5_quantization_null_depth():
    fig, ax = plt.subplots(figsize=(6.5, 3.4), dpi=300)
    bits = np.arange(8, 19)
    C = 4
    # Eq. (10) theoretical estimate
    r_null_theory = 20 * np.log10(np.sqrt(12) * (2**(bits - 1)) / np.sqrt(C))
    
    # Measured simulation null depths from bit-true fixed-point emulator
    measured_sim = np.array([46.8, 52.8, 58.7, 64.8, 70.8, 76.8, 82.7, 88.6, 94.2, 94.8, 95.0])
    
    ax.plot(bits, r_null_theory, 'r--', label=r'Theoretical Bound (Eq. 10: $R_{\mathrm{null}} \approx 20\log_{10}\frac{\sqrt{12}\cdot 2^{B-1}}{\sqrt{C}}$)', lw=1.8)
    ax.plot(bits, measured_sim, 'bo-', label='Bit-True Fixed-Point Model Simulation [L2]', lw=1.5, markersize=5)
    
    ax.axhline(55.0, color='black', linestyle=':', lw=1.2, label='Clinical Target Threshold (55 dB)')
    ax.set_xlabel('Word Length (Bits B)', fontweight='bold')
    ax.set_ylabel('Beamformer Null Depth (dB)', fontweight='bold')
    ax.set_title('Maternal Null Depth vs. Fixed-Point Word Length (C = 4)', fontweight='bold', pad=10)
    ax.set_xticks(bits)
    ax.set_ylim(40, 105)
    ax.grid(True, linestyle='--', alpha=0.5)
    
    # Callout at 16 bits
    ax.annotate(r'$B=16$: 95.1 dB (Sim: 95.0 dB)', xy=(16, 95.0), xytext=(12.5, 98),
                arrowprops=dict(facecolor='black', arrowstyle='->', lw=1.2),
                fontsize=8.5, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#eef2f7', edgecolor='#2980b9'))
                
    ax.legend(loc='lower right', framealpha=0.9, fontsize=8.5)
    plt.tight_layout()
    out_path = os.path.join(FIG_DIR, 'quantization_null_depth.png')
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Generated: {out_path}")

def make_fig22_runtime_comparison():
    fig, ax = plt.subplots(figsize=(7.2, 3.5), dpi=300)
    methods = [
        'Spatial PCA (4-Ch)\n[Host CPU]',
        'Deep U-Net (4-Ch)\n[RTX 4060 GPU]',
        'Multi-Lead TS Fusion\n[Host CPU]',
        'Adaptive EMA TS\n[Host CPU]',
        'Hankel-SVD V1\n[Host CPU]',
        'FPGA Pipeline\n[Spartan-7 @ 100MHz]'
    ]
    # Runtimes in milliseconds per 5-minute record (75,000 samples)
    runtimes_5min_ms = [190.7, 98.6, 218.6, 245.0, 107500.0, 0.096] # 0.096 ms = 75000 * 1.28 us
    colors = ['#2980b9', '#8e44ad', '#3498db', '#1abc9c', '#e67e22', '#27ae60']
    
    y_pos = np.arange(len(methods))
    bars = ax.barh(y_pos, runtimes_5min_ms, color=colors, height=0.55, edgecolor='black', linewidth=0.7, alpha=0.85)
    ax.set_xscale('log')
    ax.set_xlabel('Execution Time per 5-Minute Record (ms, Log Scale)', fontweight='bold')
    ax.set_title('Execution Time Comparison (5-Minute PhysioNet Record)', fontweight='bold', pad=10)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(methods)
    ax.grid(True, which='both', linestyle='--', alpha=0.5)
    
    # Value callouts
    ax.text(190.7 * 1.3, 0, '190.7 ms (3.2 ms/5s win)', va='center', fontsize=8, fontweight='bold', color='#2980b9')
    ax.text(98.6 * 1.3, 1, '98.6 ms (1.6 ms/5s win)', va='center', fontsize=8, fontweight='bold', color='#8e44ad')
    ax.text(218.6 * 1.3, 2, '218.6 ms', va='center', fontsize=8)
    ax.text(245.0 * 1.3, 3, '245.0 ms', va='center', fontsize=8)
    ax.text(107500.0 * 0.1, 4, '107.5 s', va='center', ha='right', fontsize=8, color='white', fontweight='bold')
    ax.text(0.096 * 1.4, 5, '0.096 ms (1.28 µs/sample)\n[3,125x Real-Time Margin]', va='center', fontsize=8, fontweight='bold', color='#27ae60')
    
    ax.set_xlim(0.01, 1e6)
    plt.tight_layout()
    out_path = os.path.join(FIG_DIR, 'runtime_comparison.png')
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Generated: {out_path}")

def run_all():
    print("Rebuilding all audited figures...")
    make_fig1_amplitude_disparity()
    make_fig3_fmr_topography()
    make_fig4_filter_responses()
    make_fig5_quantization_null_depth()
    make_fig22_runtime_comparison()
    print("All figures rebuilt successfully!")

if __name__ == '__main__':
    run_all()

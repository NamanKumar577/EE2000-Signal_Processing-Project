# Executive Summary: Pre-FPGA Technical Readiness

1. Full-Layout Benchmark: Layout-invariance confirmed across l1-l5 (Mean F1 = 78.59%, range 77.78% to 79.47%).
2. Spatial Calibration: Autocorrelation selector achieves 77.94% F1 and 82.10% on sub08 with 1.0% maternal lock.
3. Detector Parameters: Config C (12-35 Hz, MWI 30, Ref 200ms) eliminates 11,533 false alarms and achieves 12.55 bpm MAE.
4. FHR Post-Processing: Un-gated midpoint split rejected due to 73.5% false insertions (99.4% in c2). M4-Modified achieves 4.69 bpm MAE.
5. Bit-Accurate Verification: 98.39% exact 0-sample match, 99.12% within 2 samples, -0.16% F1 delta. HP1 accumulator sized to 32 bits.
6. RTL Readiness: All 14 modules specified with pin interfaces and timing budgets. Zero RTL currently exists in repo.

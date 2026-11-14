# v6 simulation waveforms

`tb_wave.v` wraps the normal system testbench (`../tb_core.v`, which streams a recording like the board host and checks every output byte against the C model) and brings readable internal signals to the top: raw leads, front-end output, canceller writes, maternal peaks, selected track, FHR, unit hand-shakes and the PC link.

## 1. Batch run (makes `wave.vcd`, about 30 s)

```
bash fpga_implementation/v6/sim/wave/run_wave.sh            # CinC a01, first 30 s
venv/Scripts/python.exe report/final_report/tools/plot_waves.py   # figures/wave_*.png for the report
```

The run must end with `RESULT: 164447 uplink bytes, 2721 frames, 0 byte errors`.

## 2. Vivado waveform window (for screenshots)

Run step 1 once first (it compiles the snapshot). Then double-click `open_wave_gui.bat`, or from a Windows terminal:

```
cd fpga_implementation\v6\sim\wave
open_wave_gui.bat
```

The Vivado simulator opens, adds the signals in groups and runs the whole 30-s recording (about a minute). Then:

1. Click **Zoom Fit** to see the whole run (like `wave_overview.png`).
2. For analogue traces, select `raw_lead1`, `xf_lead1`, `fhr_x10`, right-click, **Waveform Style > Analog**, and set the radix to **Signed Decimal**.
3. Good places to zoom (use the time box or the markers):
   - about 15 ms: the PCA request (`msg_cmd = 80`, then `pca_answer`);
   - about 44 ms: the GEVD request and `calibrated` going high;
   - after 112 ms: OUT frames, `sel_track`, `fhr_x10`;
   - any single sample after 120 ms: `fe_go` ... `tk_done` hand-shakes, about 1,500 to 2,500 clock cycles.
4. Take screenshots (Windows: `Win + Shift + S`) and save them as
   `report/final_report/figures/vivado_wave_1.png`, `vivado_wave_2.png`, ...

| File | Purpose |
|---|---|
| `tb_wave.v` | wrapper testbench with the named signals |
| `run_wave.sh` | golden streams from the C model, compile, batch simulation, `wave.vcd` |
| `wave_vcd.tcl` | which signals go into the VCD |
| `wave_gui.tcl`, `open_wave_gui.bat` | Vivado GUI with the signals added |

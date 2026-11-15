# Non-Invasive Fetal ECG Extraction and Fetal Heart Rate on a Spartan-7 FPGA

EE2000 Signal Processing course project, Team 8 (paper ID 0008).

We extract the fetal heartbeat from four electrodes on the mother's abdomen, where the fetal ECG is 10 to 250 times weaker than the mother's, and report the fetal heart rate (FHR) in real time. The final design (**v7-DL**) runs as **hand-written Verilog on a Spartan-7 XC7S50 FPGA** (RealDigital Boolean Board). The recording is streamed to the board in 0.256-s frames; the FPGA gives a live estimate at once and the final beats, chosen by an on-chip look-ahead unit, about 13.5 s later (at most 17.5 s). It also shows the final heart rate on the board's displays. A PC answers only five low-rate requests and never sees the recording. All on-board methods are **causal** (v7-DL with a fixed output delay) and **label-free** (annotations are used only for scoring); v7-LA is an offline reference that sees the whole recording.

- Final report: [`report/final_report/fpr-8.pdf`](report/final_report/fpr-8.pdf) (new text in blue; mid-term text in black)
- AI prompts (course requirement): [`report/final_report/AI_PROMPTS.pdf`](report/final_report/AI_PROMPTS.pdf)
- Earlier reports: [`report/mtr-8.pdf`](report/mtr-8.pdf) (mid-term), [`report/preliminary/PPR-8.pdf`](report/preliminary/PPR-8.pdf) (proposal)

---

## Final results (v7-DL, measured on the board)

| Data set | Records | Beat F1 (%) [95% CI] | FHR error (bpm) | Board = C model | v6 F1 | v6.1 F1 |
|---|---|---|---|---|---|---|
| FECGSYNDB, synthetic (60-record subset) | 60 | 93.4 [89.3, 96.7] | 4.2 | 60/60 | 91.8 | 91.6 |
| ADFECGDB, real, scalp-electrode reference | 5 | 96.1 [92.8, 98.9] | 2.1 | 5/5 | 92.7 | 92.9 |
| PhysioNet/CinC 2013, real, development half | 38 | 84.7 [78.6, 89.8] | 6.5 | 38/38 | 76.0 | 80.4 |
| **PhysioNet/CinC 2013, real, held-out half** | **37** | **76.9 [68.3, 84.7]** | **11.5** | **37/37** | **65.5** | **71.9** |
| FECGSYNDB, all records (C model) | 1,248 | 93.7 | 4.0 | - | 91.4 | 91.9 |

- **Bit-exact:** for v6, v6.1 and v7-DL the board's complete output byte stream equals our C model on all 140 records tested on hardware.
- **FPGA (v7-DL):** XC7S50 at 50 MHz, 26,701 LUTs (82%), 15,970 flip-flops, 71/75 block RAM, 43 DSP, timing met (+0.05 ns), 0.45 W on-chip power (Vivado estimate). v6: 18,127 LUTs, 60 BRAM, 33 DSP.
- **Speed and delay:** the FPGA logic alone needs a median of 1,485 clock cycles per sample (about 140× faster than real time, v6 in simulation). The whole board system, including the UART link and the PC, runs 4–4.5× faster than real time. Live beats come 1.5–2 s after they occur; the final v7-DL beats about 13.5 s (median), at most 17.5 s.
- **Held-out data:** the CinC test half was scored once per frozen design (v5, v6, v6.1, v7-LA, v7-DL) and never used for a design decision.

---

## What we did

| Phase | When | What we did | Outcome |
|---|---|---|---|
| Proposal | Sep 2026 | Literature survey; chose PhysioNet FECGSYNDB; work plan | `report/preliminary/PPR-8.pdf` |
| Mid-term | Oct 2026 | Compared 9 methods on FECGSYNDB: SVD (3 variants), template subtraction, wavelet/LMS hybrids, 4-lead spatial PCA, 1D U-Net; fixed-point model; FPGA sizing | Spatial PCA best (batch evaluation); `report/mtr-8.pdf` |
| Causal re-evaluation | 31 Oct – 6 Nov | Strictly causal pipeline and integer golden model; UART bring-up on the board; full-dataset audit | Mid-term design: 93.0% → 82.2% F1 when run causally |
| v2 | 7 Nov | PC computes beamformer weights by self-referencing GEVD; RTL fixes (latency, detector restart, peak localiser) | FECGSYNDB 95.6%; board bit-exact; but only 41% on real CinC data |
| Real data, v3, v4 | 7–9 Nov | Added CinC 2013 (dev/test split) and ADFECGDB; Python prototypes with maternal cancellation, beat trackers, candidate selection | Real-data F1 rose step by step |
| v5 | 9–10 Nov | Whole algorithm in C on a MicroBlaze soft processor inside the FPGA | CinC test 65.8%, ADFECGDB 93.4%, bit-exact |
| v6 | 10–14 Nov | Bit-accurate integer C model, then hand-written Verilog for all sample-rate work and a PC "brain" for 5 decisions; block-RAM sharing (99% → 80%); live web demo | CinC test 65.5%, board bit-exact |
| v6.1 | 14 Nov | Robust maternal detector, recalibration every 30 s (C model, RTL, board); smarter causal selection tried and rejected | CinC test 71.9% |
| v7-LA | 14 Nov | Offline look-ahead on the PC over the whole recording (Viterbi over track qualities, beat clean-up, centred FHR) | CinC test 75.6%, FECGSYNDB 94.3% |
| **v7-DL (final)** | 14 Nov | RTL look-ahead unit on the FPGA: final beats with a fixed ~13.5 s delay while the recording is streamed; FHR on the board displays; web page shows final and live FHR; final report | Results above |

**The final algorithm** (per 250 Hz sample, 4 leads): filters → maternal R-peak detection (PCA of the first 10 s) → per-lead maternal ECG cancellation (template from the last 20 beats) → 16 candidate fetal tracks from self-calibrated GEVD spatial filters → RR-predictive beat trackers → label-free selection every 2.5 s → live beats and FHR. From v6.1 the spatial filters are recalibrated every 30 s. In v7-DL a look-ahead unit on the FPGA then scores all 16 tracks over 15 s before to 7.5 s after each 2.5-s segment, runs one Viterbi step, cleans up the beats and outputs the final beats and FHR.

**Team (work division over the whole project):**

| Member | Part |
|---|---|
| Naman | Data, test set-up and integration: SVD methods (mid-term), data set preparation, test cases and test suite (incl. v6.1/v7 tests), web demo and its v7 view, report assembly |
| Vivek | Fixed-point design and first full FPGA version: wavelet-threshold and SVD-template methods (mid-term), fixed-point model, UART and protocol, v5 on MicroBlaze, board evaluation script and the v6.1/v7 board runs |
| Anshu | Real-time algorithm and accuracy: template subtraction and multichannel study (mid-term), U-Net baseline, causal algorithm v2–v5, CinC protocol and scoring, v6.1 ideas, look-ahead algorithms v7-LA and v7-DL |
| Astitva | Final hardware design: SWT-LMS-SSNF method (mid-term), hardware/PC split, bit-accurate C model, Verilog RTL, testbenches, board verification, BRAM optimisation, v6.1 RTL, look-ahead unit v7_la and display unit |

---

## Repository layout

```text
fpga_implementation/
  v6/                   FINAL DESIGNS: v6, v6.1 (define V61), v7-DL (defines V61 + V7)
    rtl/                  Verilog (v6_top, v6_core, v6_link, v6_uart, v6_fe, v6_mat, v6_canc, v6_trk, v6_sos, v6_mwi, v6_det,
                          v7_la = look-ahead unit, v7_disp = 7-segment displays)
    model/                bit-accurate C model (fpga_model.c, v7_post.c), PC brain (brain.c), protocol (proto.h)
    sim/                  system testbench (tb_core.v), regression (regress.sh); sim/wave/ = waveform run + Vivado GUI
    build/                bitstreams v6.bit, v61/v61.bit, v7/v7.bit with utilisation / timing / power reports
    build_v6.tcl, build_v61.tcl, build_v7.tcl, program_v6/v61/v7.tcl, report_power_v6.tcl, v6.xdc, v7.xdc
  uart_host/            PC side: run_v6_board_eval.py (board), run_v6_model_eval.py (no board), older v2/v5 clients
  webdemo/              local web page: upload a recording, live FHR from the board
  v5/                   MicroBlaze version (C algorithm in algo/)
  rtl/, bitstream/ ...  v2 RTL
tools/accuracy/         data loaders, causal scoring harness, Python prototypes v2-v4, v6.1/v7 studies (devbench_v6.py,
                        v7_offline.py, v7_live.py, v7_delay_sweep.py; exp_taps.py with its model copy in _taps/),
                        per-record result CSVs
src/fecg/               mid-term Python package (methods, preprocessing, detection, fixed-point models)
tests/                  pytest suite (unit, integration, hardware, regression)
scripts/                mid-term benchmark and training scripts
report/                 PPR-8, MTR-8, final_report/ (FPR-8), work logs: v61_v7/ (v6.1, v7), rtl_pc_split/ (v6), night_20261109/ (v5)
validation/, results/   mid-term and v2 validation results
docs/                   literature, hardware specifications, audits
archive/, code/         superseded code, packages and the legacy source tree (kept for reference)
data/                   data sets (not in git, see below)
```

---

## Setup

1. **Python 3.10+** (we used 3.13 on Windows):
   ```bash
   python -m venv venv
   venv/Scripts/pip install -r requirements.txt        # Linux/macOS: venv/bin/pip
   ```
2. **Data.** Put the PhysioNet data sets under `data/` at these paths (the submission zip already contains them, except most of FECGSYNDB; see `data/DATA.md` there):
   - `data/noninvasive-fetal-ecg-the-physionet-computing-in-cardiology-challenge-2013-1.0.0/extracted/set-a/` and `set-a-ext/` ([CinC 2013](https://physionet.org/content/challenge-2013/1.0.0/))
   - `data/ADFECGDB/abdominal-and-direct-fetal-ecg-database-1.0.0/` ([ADFECGDB](https://physionet.org/content/adfecgdb/1.0.0/))
   - `data/FECGSD/DESTINATION/sub01 ... sub10/` ([FECGSYNDB](https://physionet.org/content/fecgsyndb/1.0.0/))
3. **For the hardware parts:** AMD Vivado 2025.2 (scripts assume `C:/AMDDesignTools/2025.2/Vivado/bin`), the Boolean Board on a USB serial port (default `COM5`), and gcc (MinGW) if you want to rebuild the C model. The report needs TeX Live (`pdflatex`).

All commands below are run from the repository root.

---

## How to use

### 1. Evaluate the final design without the board
The C system model produces the same output bytes as the board. `V6_VARIANT` selects the version (`v6` default, `v61`, `v7`).
```bash
cd fpga_implementation/uart_host
V6_VARIANT=v7 ../../venv/Scripts/python.exe run_v6_model_eval.py --sets ad,cdev,ctest      # add syn if FECGSYNDB is present
```

### 2. Run on the FPGA board
```bash
C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat -mode batch -nojournal -nolog -source fpga_implementation/v6/program_v7.tcl
V6_VARIANT=v7 venv/Scripts/python.exe fpga_implementation/uart_host/run_v6_board_eval.py --sets cdev,ad,ctest --port COM5 --out report/my_board_run
```
For each record this streams the recording to the board in 64-sample frames, runs the PC brain, sends FLUSH at the end (v7), scores the final beats and checks that the board's output is bit-exact with the C model. `V6_VARIANT` must match the bitstream on the board (`program_v6.tcl` ↔ `v6`, `program_v61.tcl` ↔ `v61`, `program_v7.tcl` ↔ `v7`). Program the board again after every power cycle.

### 3. Live web demo
```bash
V6_VARIANT=v7 venv/Scripts/python.exe fpga_implementation/webdemo/server.py --port COM5      # then open http://localhost:8050
```
With v7 the page shows the final FHR from the FPGA look-ahead (about 15 s behind), the live estimate next to it and the current delay; the board's displays show the final FHR and the number of final beats. Upload a WFDB recording (`.hea` + `.dat`, optional `.fqrs`/`.qrs` annotations, or a `.zip`) or a 4-column CSV. The page shows board status, processing stage, the four leads with beat marks, live FHR and maternal rate, and accuracy when annotations exist. Results are saved in `fpga_implementation/webdemo/runs/`. The page only runs when the board answers; it never falls back to software.

### 4. RTL simulation (Vivado simulator)
```bash
cd fpga_implementation/v6/sim
V6_DUMP=G ../model/v6_sim.exe r_cdev_a07.i16 > /dev/null && ./run_tb.sh       # one record: RTL vs C model, byte by byte
./regress.sh a01.i16 r_*.i16                                               # all 8 regression records (v6)
SIMEXE=../model/v7_sim.exe DEFS="-d V61 -d V7" ./regress.sh a01_30s.i16 a01.i16 r_*.i16      # v7-DL
bash wave/run_wave.sh                                                      # waveform run (wave/wave.vcd), CinC a01, 30 s
```
To view the waveforms in the Vivado GUI, run `wave/open_wave_gui.bat` after `run_wave.sh` (see `fpga_implementation/v6/sim/wave/README.md`).

### 5. Build the bitstream and reports
```bash
C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat -mode batch -nojournal -nolog -source fpga_implementation/v6/build_v7.tcl          # build/v7/v7.bit + reports (about 30 min)
C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat -mode batch -nojournal -nolog -source fpga_implementation/v6/build_v6.tcl          # build/v6.bit + reports
C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat -mode batch -nojournal -nolog -source fpga_implementation/v6/report_power_v6.tcl    # power + per-module utilisation
```

### 6. Rebuild the C model and PC brain
```bash
cd fpga_implementation/v6/model
gcc -O2 -std=c99 -msse2 -mfpmath=sse -ffp-contract=off -o v6_sim.exe sim_main.c fpga_model.c brain.c -lm
gcc -O2 -std=gnu99 -msse2 -mfpmath=sse -ffp-contract=off -o v6_brain.exe brain_main.c brain.c -lm
gcc -O2 -std=gnu99 -msse2 -mfpmath=sse -ffp-contract=off -DV7 -o v7_sim.exe sim_main.c fpga_model.c brain.c v7_post.c -lm
gcc -O2 -std=gnu99 -msse2 -mfpmath=sse -ffp-contract=off -DV7 -o v7_brain.exe brain_main.c brain.c -lm
```
(`-DV61` with `v61_sim.exe` / `v61_brain.exe` for v6.1.)
Rule we followed for every change: C model first, then RTL, then `sim/regress.sh`, then build, then the board check.

### 7. Regenerate the final report
```bash
venv/Scripts/python.exe report/final_report/tools/make_final_figures.py      # result figures (fin_*.png)
venv/Scripts/python.exe report/final_report/tools/plot_waves.py              # simulation figures (wave_*.png), needs step 4's wave.vcd
venv/Scripts/python.exe report/final_report/tools/fix_midterm_figures.py     # corrected mid-term figures used in the final report
venv/Scripts/python.exe report/final_report/tools/pc_link_traffic.py         # PC <-> FPGA link traffic per PC decision
venv/Scripts/python.exe report/final_report/tools/final_analysis.py          # confidence intervals, failure analysis, timeline
venv/Scripts/python.exe report/final_report/tools/make_v7_figures.py         # v6.1 / v7 figures and confidence intervals
venv/Scripts/python.exe report/final_report/tools/make_delay_figure.py       # v7-DL F1 against output delay (input: tools/accuracy/v7_delay_sweep.py)
venv/Scripts/python.exe report/final_report/tools/check_final_numbers.py     # checks the numbers in the text against the result files
cd report/final_report && pdflatex fpr-8.tex && pdflatex fpr-8.tex && pdflatex fpr-8.tex
```
`tools/package_submission.py` builds the submission archive `fpr-8.zip` (code, data, PDF) in the repository root. The AI prompts are built from `AI_PROMPTS.tex`: `cd report/final_report && pdflatex AI_PROMPTS.tex && pdflatex AI_PROMPTS.tex`.

### 8. Tests
```bash
venv/Scripts/python.exe -m pytest tests -q        # 270 passed, 3 skipped (RUN_RTL=1 runs the slow RTL simulations)
```

### 9. Earlier versions
- v5 (MicroBlaze): `fpga_implementation/v5/program_v5.tcl` loads `build/download.bit` (the frozen v5 bitstream is `build/download_v5_final.bit`); then run `fpga_implementation/uart_host/run_v5_board_eval.py`.
- Mid-term benchmarks: `scripts/benchmarks/run_benchmark.py`, `run_mega_benchmark.py`, `run_causal_benchmark.py` (each has `--help`).

---

## Work logs and results

| Where | What |
|---|---|
| `report/v61_v7/LOG.md` | v6.1, v7-LA and v7-DL: experiments, RTL, board results, F1 against delay, delay-tap filter study |
| `report/v61_v7/board_v61/`, `board_v7/` | per-record board results of v6.1 and v7-DL |
| `report/rtl_pc_split/LOG.md` | v6 design, verification, board results, BRAM change |
| `report/night_20261109/LOG.md`, `RESULTS.md` | v5 experiments, every accepted and rejected idea with numbers |
| `report/rtl_pc_split/board_umem/` | per-record board results of the v6 bitstream |
| `tools/accuracy/results_*.csv` | per-record results of every earlier version |
| `fpga_implementation/v6/PLANNED_CHANGES.md` | changes done and ideas still open |

---

## Use of AI

We used AI tools as programming aids; the AI disclosure sections of the reports describe this, and the prompts are in [`report/final_report/AI_PROMPTS.pdf`](report/final_report/AI_PROMPTS.pdf) as the course requires.

# Demo day command sheet (team only)

Private notes for the 4 of us. Files in this folder:

| File | What |
|---|---|
| `README.md` | this command sheet |
| `01_EXPLANATION.md` | longer explanation of the project |
| `02_PRESENTATION_QA.md` | likely questions with short answers |
| `03_KEY_NUMBERS.md` | one-page cheat sheet of numbers |


> **This folder is for the team only.** It is committed to our private GitHub repository, but it is also listed in `.git\info\exclude` (a local file), and `package_submission.py` leaves every folder listed there out of `fpr-8.zip`. On a fresh clone, add the line `team/` to `.git\info\exclude` before packaging. Do not mention this folder in the report or the repository READMEs.

All commands are **PowerShell** (Windows 11), started from the repository root unless a step says otherwise:

```powershell
Set-Location D:\signal_project
```

Tools on this laptop:

| Tool | Path | Note |
|---|---|---|
| Python venv | `D:\signal_project\venv\Scripts\python.exe` | call it directly, no need to "activate" |
| Vivado 2025.2 | `C:\AMDDesignTools\2025.2\Vivado\bin\vivado.bat` | **not on the PowerShell PATH**, always use the full path |
| Git Bash | `C:\Program Files\Git\bin\bash.exe` | needed for the `.sh` scripts; not on the PowerShell PATH |
| gcc (MinGW) | `C:\MinGW\bin\gcc.exe` | on PATH |
| pdflatex | `C:\texlive\2026\bin\windows\pdflatex.exe` | on PATH |
| Board serial port | usually `COM5` ("USB Serial Port (COM5)") | COM3/COM4 are Bluetooth, ignore them |

---

## 0. The one rule: bitstream and `V6_VARIANT` must match

The board runs one of three designs. The PC programs (PC brain and C model) must be the same design. You choose the PC side with the environment variable `V6_VARIANT`.

| Design | Bitstream | Program script (in `fpga_implementation\v6\`) | `V6_VARIANT` | PC programs used |
|---|---|---|---|---|
| **v7-DL (final)** | `build\v7\v7.bit` | `program_v7.tcl` | `v7` | `model\v7_brain.exe`, `model\v7_sim.exe` |
| v6.1 | `build\v61\v61.bit` | `program_v61.tcl` | `v61` | `v61_brain.exe`, `v61_sim.exe` |
| v6 | `build\v6.bit` | `program_v6.tcl` | `v6` **or not set** | `v6_brain.exe`, `v6_sim.exe` |

- If `V6_VARIANT` is not set, the scripts use **v6**. With the v7 board this gives wrong results, so always set it.
- `$env:V6_VARIANT = 'v7'` stays set only in that PowerShell window. Check it with `$env:V6_VARIANT`; clear it with `Remove-Item Env:V6_VARIANT`.
- The web server reads `V6_VARIANT` once at start. After you change the bitstream, restart the server.

---

## 1. Before the demo (checklist)

Do this 15 minutes before, in this order.

1. **Board powered and connected.** Power switch on, the USB cable in the board's USB port. Check that Windows sees the serial port:
   ```powershell
   Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -like '*(COM*' } | Select-Object Status, FriendlyName
   ```
   Look for `OK  USB Serial Port (COM5)`. If the number is not 5, use `--port COMx` everywhere below.
2. **Stop every old web server and batch script.** They keep COM5 open (section 3).
3. **Program the board with v7** (section 2). You must do this after **every** power-off: the FPGA forgets its bitstream.
4. **Check the board displays.** Right after programming, v7 shows `----` on display 0 and `0000` on display 1. The v6 and v6.1 bitstreams do not use the displays at all.
5. **Optional, 15 s: prove the board is v7.** Run the batch check with one record (section 6, `--limit 1`). `bit-exact True` means the board matches the v7 model.
6. **Start the web demo in v7 mode** (section 4) and open http://localhost:8050 with **Ctrl+F5**.
7. **Header check on the page:**
   - pill `Design: v7-DL · look-ahead on the FPGA`;
   - green dot `FPGA connected` (yellow = not answering, red = not connected, pulsing green = processing);
   - under it, `v7-DL RTL answering on COM5 · probe round trip … ms`.
8. **Do one full dry run with a01** before the audience arrives (about 65 s).

### How to know which design is really on the board

- The page pill and `/api/status` → `"variant"` show the `V6_VARIANT` **the server was started with**. They do **not** read the FPGA. The board probe (a reset plus one empty frame) is answered by all three bitstreams in the same way.
- Real checks:
  - the last line Vivado printed when you programmed (`PROGRAMMED …/build/v7/v7.bit`);
  - the displays (`----` / `0000` after programming, or the last FHR and beat count): only v7 drives them;
  - a batch run with `--limit 1` gives `bit-exact True` only when `V6_VARIANT` matches the bitstream.

Ask the running server what it was started with (second PowerShell window; when no run is going, this also probes the board):

```powershell
(Invoke-RestMethod http://localhost:8050/api/status).board | Format-List state, detail, variant, variant_name, port
```

Expected: `state : connected`, `variant : v7`, `variant_name : v7-DL`, `port : COM5`.

---

## 2. Programming the board

Programming uses the JTAG part of the USB link, not COM5, so the web server can stay open. A run in progress breaks, though, and you must restart the server if you change the design.

```powershell
Set-Location D:\signal_project\fpga_implementation\v6
& C:\AMDDesignTools\2025.2\Vivado\bin\vivado.bat -mode batch -nojournal -nolog -source program_v7.tcl     # final design
& C:\AMDDesignTools\2025.2\Vivado\bin\vivado.bat -mode batch -nojournal -nolog -source program_v61.tcl    # v6.1
& C:\AMDDesignTools\2025.2\Vivado\bin\vivado.bat -mode batch -nojournal -nolog -source program_v6.tcl     # v6
Set-Location D:\signal_project
```

Run only the line you need. Success looks like this (near the end):

```
INFO: [Labtools 27-3164] End of startup status: HIGH
PROGRAMMED D:/signal_project/fpga_implementation/v6/build/v7/v7.bit
```

On the board after v7 programming: display 0 `----`, display 1 `0000`.

### On-board displays (v7 bitstream only)

| Display | Shows | Notes |
|---|---|---|
| 0 | final fetal heart rate in bpm (rounded) from the latest final beat | `----` until the first final beat of a run |
| 1 | number of final beats sent in this run (4 digits, e.g. `0102`) | |

- Both displays are cleared when a new recording starts. Strictly, this happens when the board sends its maternal-PCA request, at 10 s into the recording.
- Pressing BTN0 resets the board and the displays.
- After a full a01 run, display 1 shows `0102`.

LEDs (all three designs):
- LED7: link error;
- LED6: samples waiting;
- LED5: calibrated (lights at about 15 s);
- LED2–0: the unit that is working.

---

## 3. Stop all running web-demo servers / see who holds COM5

Only one program can open COM5. A web server keeps COM5 open the whole time it runs, even when idle.

**List** what is running (safe, changes nothing):

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*webdemo*server.py*' -or $_.CommandLine -like '*run_v6_board_eval*' } | Select-Object ProcessId, ParentProcessId, CommandLine | Format-Table -AutoSize -Wrap
```

You normally see 2 lines per server: the venv launcher and its child Python. Both are `python.exe`.

**Stop ALL web-demo servers:**

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*webdemo*server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

**Stop a batch board evaluation** that is still running:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*run_v6_board_eval*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

Run the list command again afterwards: it should print nothing.

A server started in your own window can also be stopped with **Ctrl+C** in that window.

**Who holds the web port 8050.** More than one line means more than one server is listening. Windows allows this, and the browser may then reach the old one.

```powershell
Get-NetTCPConnection -LocalPort 8050 -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, OwningProcess
Get-Process -Id <OwningProcess>
```

**COM5 "Access is denied"** means another program has the port open. The server prints:
```
Board: COM5: could not open port 'COM5': PermissionError(13, 'Access is denied.', None, 5)
```
The page shows `FPGA not connected` with the same text.

Windows has no built-in command that names the owner of a COM port. In practice it is one of these:
- a second web server;
- a batch `run_v6_board_eval.py`;
- a serial terminal (PuTTY, Tera Term, Arduino IDE, VS Code serial monitor).

Stop them with the commands above, then click **Reconnect** on the page.

---

## 4. Start the web demo (v7 mode)

```powershell
Set-Location D:\signal_project
$env:V6_VARIANT = 'v7'
venv\Scripts\python.exe fpga_implementation\webdemo\server.py
```

Options:
- `--port COM6` for another serial port;
- `--http 8051` for another web port.

Start-up takes about 8 s. The window then prints:

```
Board: v7-DL RTL answering on COM5
Open http://localhost:8050
```

Keep this window open; closing it stops the server.

Open **http://localhost:8050** in the browser and press **Ctrl+F5** to make sure the newest page is loaded.

If the board line says something else:

| Printed | Meaning |
|---|---|
| `Board: COM5 open but the FPGA does not answer (bitstream loaded?)` | not programmed, e.g. after power-off: program it (section 2), then click Reconnect |
| `Board: COM5 not found (USB cable / driver?)` | cable or power |
| `Board: COM5: could not open port … Access is denied` | port busy (section 3) |

The server also accepts the board's other designs: `$env:V6_VARIANT = 'v61'` with the v6.1 bitstream, or `'v6'` with v6.

### Which files to load

Folder (CinC 2013, real 60-s recordings, 4 abdominal leads, 1 kHz):

```
D:\signal_project\data\noninvasive-fetal-ecg-the-physionet-computing-in-cardiology-challenge-2013-1.0.0\extracted\set-a\       (a01 – a25)
D:\signal_project\data\noninvasive-fetal-ecg-the-physionet-computing-in-cardiology-challenge-2013-1.0.0\extracted\set-a-ext\   (a26 – a75)
```

On the page:
1. In **1 · Recording**, click the file button and Ctrl+click **`aXX.hea`, `aXX.dat`, `aXX.fqrs`**. The `.fqrs` file holds the reference beats; without it no accuracy is shown.
2. Click **Load**. The page shows: `a01 · 60.0 s · 1000 Hz in → 250 Hz · leads AECG1, AECG2, AECG3, AECG4`, then `Fetal annotations: yes`.
3. Click **Start (real time)**.

Suggested records. Numbers are the board F1 (%) of the v7 run in `report\v61_v7\board_v7\`; "live" is the v6.1 output of the same run.

| Record | Folder | Live v6.1 F1 | Final v7 F1 | Final beats | Use it for |
|---|---|---|---|---|---|
| **a01** | `set-a` | 95.0 | **98.0** | 102 | main demo, clean record |
| a03 | `set-a` | 88.6 | 96.5 | 85 | the look-ahead fixes the live mistakes |
| a07 | `set-a` | 58.8 | 71.3 | 86 | harder record, still clearly better |
| a73 | **`set-a-ext`** | 22.4 | 43.5 | 77 | honest hard case: still fails even with look-ahead (the reference is reliable) |

- The page shows only the **final** F1. The live v6.1 F1 comes from the batch run (column `f1_causal`).
- **Cannot be loaded by the page:**
  - ADFECGDB (`.edf` files);
  - FECGSYNDB (stored as separate fetal, maternal and noise files; the mixture is built by our scripts).

  Use CinC records. A CSV with 4 lead columns also works; enter its sample rate.

### What the page shows during a 60-s record (v7)

| Time in the recording | What you see |
|---|---|
| 0 – 10 s | Stage "Learning the maternal signal (collecting 10 s for PCA)"; the 4 leads scroll. |
| about 10 s | Log: "FPGA asked the PC brain: maternal PCA". Stage "Maternal detection + cancellation …". The maternal heart rate appears. The board displays clear. |
| about 15 s | Log: "GEVD calibration". Stage "PC brain: GEVD calibration of 16 candidate fetal tracks", then "Fetal trackers warming up". LED5 lights. |
| about 20 s | Stage "Monitoring: live beats (causal v6.1 output)". Under the big number: "live estimate: NNN bpm". The dashed live curve starts. "track selection" requests every 2.5 s. |
| about 34 s | First **final** beats (about 14–15 s after the beat itself). Stage "Final beats from the FPGA look-ahead unit (about 15 s behind the stream)". Big FHR number = final value. **Look-ahead delay** card about 13–15 s. Board displays start counting. |
| 34 – 60 s | Final beats follow about 13.5 s behind. The signal window shows the 10 s "where the final beats are"; the grey area on the trend is "not final yet". A second "GEVD calibration" request may appear in the log: that is the 30-s recalibration of v6.1 (at most one in a 60-s record). |
| 60 s | Log: "60.0 s · end of the recording: FLUSH sent, the FPGA finishes the last … s with the data it has". Delay card "0 (done)". Then "Saved: …\webdemo\runs\a01_<date>_<time>" and "Finished: 102 final fetal beats reported". |
| end | Accuracy card (final beats): **a01 F1 ≈ 98.0 %**. Display 1 = `0102`. Buttons "Download beats.csv / summary.json". |

- **The running F1 during a v7 run is too low; this is expected.** Beats from the last ~15 s are not final yet, so they count as missed. Quote only the number after FLUSH.
- Other cards:
  - "Selected track (of 16)": the track of the newest final beat ("filled" = a missed beat filled in by the clean-up);
  - "FPGA time per 0.256 s chunk";
  - "PC brain replies".
- Each run is saved in `fpga_implementation\webdemo\runs\<record>_<date>_<time>\` (`beats.csv`, `summary.json`).

---

## 5. What to point at on the board during a web run (v7)

| When | What happens on the board |
|---|---|
| ~10 s | displays clear (`----` / `0000`) |
| ~15 s | LED5 (calibrated) lights |
| ~34 s | display 1 starts counting final beats; display 0 shows the final FHR, the same as the big number on the page |
| end | after FLUSH: a01 shows `0102` on display 1 |

---

## 6. Batch board evaluation (no web page)

**Stop the web server first** (section 3): both need COM5.

```powershell
Set-Location D:\signal_project
$env:V6_VARIANT = 'v7'
venv\Scripts\python.exe fpga_implementation\uart_host\run_v6_board_eval.py --sets cdev --limit 3 --out "$env:TEMP\v7_eval"
```

- Options: `--sets` (comma list of `cdev`, `ctest`, `ad`, `syn`), `--limit N` (first N records), `--port COM5` (default), `--out DIR`.
- **Always give `--out`.** The default folder is `report\rtl_pc_split\board\`, and a run there can overwrite saved v6 results.

Expected output for v7, about 13 s per record (from `report\v61_v7\board_v7.log`):

```
cdev  a01                      F1  98.02  beats  102  uplink   444487 B  bit-exact True   12.6s for    60s
cdev  a03                      F1  96.47  beats   85  uplink   472019 B  bit-exact True   14.5s for    60s
cdev  a05                      F1  98.82  beats   89  uplink   420085 B  bit-exact True   12.7s for    60s
```

Then a summary table per set with these columns:
- `f1`, `se`, `ppv`, `fhr_mae`;
- `records`;
- `bit_exact`: share of records that were bit-exact, so 1.0 = all;
- `rt_factor`: times faster than real time, about 4.5;
- `f1_causal`, `fhr_mae_causal`: the live v6.1 output of the same run.

The per-record CSV is `$env:TEMP\v7_eval\board_cdev.csv`.

**What `bit-exact True` means:** the whole byte stream the board sent for that record is identical, byte for byte, to what the C model (`v7_sim.exe`) produces for the same input. This covers:
- all requests to the PC;
- live beats;
- OUT7 final beats;
- END7.

So the hardware computes exactly what the model computes.
- `False` almost always means a wrong `V6_VARIANT`, a board that was not reprogrammed, or a rebuilt `.exe`.
- With `V6_VARIANT=v7` on a non-v7 board, the run hangs after the first record and stops with `FPGA silent for 20 s`.

| Set | Records | Board time (v7 run) |
|---|---|---|
| `cdev` CinC dev (odd records) | 38 | about 13 s per 60-s record (11–16 s), 8.4 min total |
| `ctest` CinC test (even records) | 37 | about 13 s per record, 8.2 min total |
| `ad` ADFECGDB | 5 | about 69 s per 5-min record, 5.7 min total |
| `syn` FECGSYNDB subset | 60 | 60–90 s per 5-min record (mean 74 s), 74 min total |
| all four (140 records) | 140 | **about 1.6 h** (5,789 s): never run this in the demo |

Same scoring **without the board**, using the C model only (no COM port needed). It gives the same F1 as the board lines above:

```powershell
$env:V6_VARIANT = 'v7'
venv\Scripts\python.exe fpga_implementation\uart_host\run_v6_model_eval.py --sets cdev --limit 3
```

---

## 7. Test suite

Safe to run while the board is busy: no test opens a serial port.

```powershell
Set-Location D:\signal_project
venv\Scripts\python.exe -m pytest -q tests
```

Expected last line: **`270 passed, 3 skipped`** (273 tests are collected). The 3 skipped tests are the slow RTL simulations, which run only with `RUN_RTL=1`. Each runs xsim on CinC a01 for v6, v6.1 and v7 and needs Git Bash on the PATH:

```powershell
$env:PATH = 'C:\Program Files\Git\bin;' + $env:PATH
$env:RUN_RTL = '1'
venv\Scripts\python.exe -m pytest -q tests\hardware\test_v6_rtl_regression.py      # expect: 3 passed (several minutes per design)
Remove-Item Env:RUN_RTL
```

Git Bash form: `RUN_RTL=1 venv/Scripts/python.exe -m pytest -q tests/hardware/test_v6_rtl_regression.py`

---

## 8. RTL simulation regression (Vivado xsim, no board)

`regress.sh` is a bash script.

- It writes the golden streams with the C model.
- It compiles the RTL and runs the system testbench, which checks every output byte against the model.
- It overwrites the scratch files in `sim\` (`G_up.hex`, `G_script.txt`, logs). These are git-ignored.

**Git Bash:**

```bash
cd /d/signal_project/fpga_implementation/v6/sim
SIMEXE=../model/v7_sim.exe DEFS="-d V61 -d V7" ./regress.sh a01_30s.i16
```

**Same thing from PowerShell** (note the doubled single quotes):

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -lc 'cd /d/signal_project/fpga_implementation/v6/sim && SIMEXE=../model/v7_sim.exe DEFS=''-d V61 -d V7'' ./regress.sh a01_30s.i16'
```

Expected (one line per record, takes a few minutes):

```
a01_30s: RESULT: 162133 uplink bytes, 2730 frames, 0 byte errors, expected next byte xx (x = end) 0 mismatches
```

What to look for: **`0 byte errors`** and **`0 mismatches`**.

- Full v7 regression (9 records, slow, up to ~7 min per 2-min record): `./regress.sh a01_30s.i16 a01.i16 r_*.i16`. The last results are in `report\v61_v7\xsim_v7.log`.
- v6.1: `SIMEXE=../model/v61_sim.exe DEFS="-d V61" ./regress.sh a01.i16`.
- v6: `./regress.sh a01.i16` (no variables).

### Waveforms (Vivado GUI)

The waveform set-up in `fpga_implementation\v6\sim\wave\` is for the **v6** RTL on CinC a01, first 30 s. v6.1 and v7 are built on top of this datapath. There is no v7-specific waveform script.

1. Batch run, makes `wave.vcd` and compiles the snapshot (about 30 s). It must print `RESULT: 164447 uplink bytes, 2721 frames, 0 byte errors …`:
   ```powershell
   & 'C:\Program Files\Git\bin\bash.exe' -lc 'bash /d/signal_project/fpga_implementation/v6/sim/wave/run_wave.sh'
   ```
   Git Bash: `bash fpga_implementation/v6/sim/wave/run_wave.sh`
2. Open the Vivado simulator GUI with the signals already grouped. It simulates the whole 30 s first, which takes 1 to a few minutes:
   ```powershell
   Set-Location D:\signal_project\fpga_implementation\v6\sim\wave
   .\open_wave_gui.bat
   Set-Location D:\signal_project
   ```
3. In the GUI:
   1. **Zoom Fit** to see the whole run.
   2. Make the traces analogue: select `raw_lead1`, `xf_lead1`, `fhr_x10`, right-click → Waveform Style → Analog, radix Signed Decimal.
   3. Good places to zoom:
      - ~15 ms: PCA request (`msg_cmd = 80`);
      - ~44 ms: GEVD request, `calibrated` goes high;
      - after 112 ms: OUT frames, `sel_track`, `fhr_x10`;
      - any sample after 120 ms: hand-shakes `fe_go` … `tk_done`, about 1,500–2,500 cycles.

   Details: `fpga_implementation\v6\sim\wave\README.md`.

---

## 9. Building a bitstream (do NOT do this right before the demo)

It overwrites the bitstream that was checked on the board.

```powershell
Set-Location D:\signal_project\fpga_implementation\v6
& C:\AMDDesignTools\2025.2\Vivado\bin\vivado.bat -mode batch -nojournal -nolog -source build_v7.tcl
Set-Location D:\signal_project
```

- About **30 min** (the last v7 build ran from 18:12 to 18:42). It ends with `BUILD_DONE`.
- `build_v61.tcl` → `build\v61\`; `build_v6.tcl` → `build\v6.bit` plus reports in `build\`.

Reports for v7 in `fpga_implementation\v6\build\v7\`:

| File | Content |
|---|---|
| `util.rpt` | utilisation (LUTs, flip-flops, BRAM, DSP) |
| `util_hier.rpt` | utilisation per module (e.g. `v7_la` 7,297 LUTs in the routed design) |
| `timing.rpt` | timing; look for "All user specified timing constraints are met." and WNS |
| `power.rpt` | Vivado power estimate |
| `drc.rpt`, `util_synth.rpt` | design rule check, post-synthesis utilisation |
| `v7.bit` | the bitstream |

Quick look:

```powershell
Set-Location D:\signal_project\fpga_implementation\v6
Select-String -Path build\v7\util.rpt -Pattern '^\| (Slice LUTs|Block RAM Tile|DSPs) ' | ForEach-Object { $_.Line }
Select-String -Path build\v7\timing.rpt -Pattern 'timing constraints are met' | ForEach-Object { $_.Line }
Select-String -Path build\v7\power.rpt -Pattern 'Total On-Chip Power' | ForEach-Object { $_.Line }
Set-Location D:\signal_project
```

Expected:
- `26701 … 81.90` LUTs;
- `71 … 94.67` BRAM tiles;
- `43` DSPs;
- `All user specified timing constraints are met.`;
- `0.445` W.

The v6 power and per-module report reruns the v6 implementation and writes `build\power.rpt` and `build\util_hier.rpt`:

```powershell
Set-Location D:\signal_project\fpga_implementation\v6
& C:\AMDDesignTools\2025.2\Vivado\bin\vivado.bat -mode batch -nojournal -nolog -source report_power_v6.tcl
Set-Location D:\signal_project
```

---

## 10. Building the C models and PC brain

Only needed if you change the C code. The `.exe` files are already there. Keep exactly these flags: other flags can change the floating-point results of the brain and break bit-exactness.

```powershell
Set-Location D:\signal_project\fpga_implementation\v6\model
# v6
gcc -O2 -std=c99   -msse2 -mfpmath=sse -ffp-contract=off -o v6_sim.exe sim_main.c fpga_model.c brain.c -lm
gcc -O2 -std=gnu99 -msse2 -mfpmath=sse -ffp-contract=off -o v6_brain.exe brain_main.c brain.c -lm
# v6.1
gcc -O2 -std=c99   -msse2 -mfpmath=sse -ffp-contract=off -DV61 -o v61_sim.exe sim_main.c fpga_model.c brain.c -lm
gcc -O2 -std=gnu99 -msse2 -mfpmath=sse -ffp-contract=off -DV61 -o v61_brain.exe brain_main.c brain.c -lm
# v7-DL (final; -DV7 switches on V61 as well)
gcc -O2 -std=c99   -msse2 -mfpmath=sse -ffp-contract=off -DV7 -o v7_sim.exe sim_main.c fpga_model.c brain.c v7_post.c -lm
gcc -O2 -std=gnu99 -msse2 -mfpmath=sse -ffp-contract=off -DV7 -o v7_brain.exe brain_main.c brain.c -lm
Set-Location D:\signal_project
```

- The brain must use `-std=gnu99`, because it needs `_fileno` for binary stdin.
- Order of work we always followed: C model → RTL → `regress.sh` → build → board check.

---

## 11. Accuracy scripts (C model only, no board)

**Dev bench.** It compiles model variants with `-D` switches and scores them on the dev sets, 12 processes in parallel.

```powershell
Set-Location D:\signal_project
venv\Scripts\python.exe tools\accuracy\devbench_v6.py 'v6' 'v61=-DV61' 'v7=-DV7' '--sets=cdev'
```

- Write `--sets=cdev` **with `=`**. With a space, `--sets` would be read as a variant name.
- Sets:
  - `syn` (60-record subset);
  - `cdev`;
  - `ad`;
  - default `syn,cdev,ad`;
  - `--sets=synall` (all 1,248, long);
  - `--test` (CinC test only; we scored it once per frozen design, never use it to choose anything).
- Expected mean F1:

  | Variant | cdev | ad | syn |
  |---|---|---|---|
  | `v6` | 76.04 | 92.73 | 91.83 |
  | `v61` | 80.41 | 92.87 | 91.64 |
  | `v7` | 84.68 | 96.10 | 93.39 |

- Side effects: builds into `tools\accuracy\_v6build\` and overwrites `tools\accuracy\results_devbench_v6.csv`. Both are git-ignored.

**v7-LA**, the offline look-ahead on the PC (float, sees the whole recording; not on the board):

```powershell
venv\Scripts\python.exe tools\accuracy\v7_offline.py --sets cdev,ad
```

- Prints the mean per set of `f1_causal` (= v6.1) and `f1` (= v7-LA).
- Expected:
  - cdev 80.41 → 84.55;
  - ad 92.87 → 95.80.
- Options: `--test` (CinC test: 75.64), `--out file.csv`, `--switch`, `--half`, `--noclean`.

`tools\accuracy\v7_live.py` is the float design study we used to choose the v7-DL delay. It is not needed for the demo.

---

## 12. Rebuilding the report PDF and the submission zip

Only the PDF (from `report\final_report`):

```powershell
Set-Location D:\signal_project\report\final_report
pdflatex fpr-8.tex
pdflatex fpr-8.tex
Set-Location D:\signal_project
```

- Run it twice so the references are right. No BibTeX is needed, because the bibliography is inside the `.tex` file.
- If pdflatex stops at a `?` prompt, type `x` and Enter, or use `pdflatex -interaction=nonstopmode fpr-8.tex`.

Everything (figures, checks, PDF, zip), from the repository root:

```powershell
Set-Location D:\signal_project
venv\Scripts\python.exe report\final_report\tools\make_final_figures.py      # fin_*.png
venv\Scripts\python.exe report\final_report\tools\make_v7_figures.py         # fin_v7_*.png (v6.1 / v7 figures)
venv\Scripts\python.exe report\final_report\tools\plot_waves.py              # wave_*.png, needs wave.vcd from section 8
venv\Scripts\python.exe report\final_report\tools\final_analysis.py          # CIs, CinC failure table, timeline (runs the C model)
venv\Scripts\python.exe report\final_report\tools\check_final_numbers.py     # last line should be: ALL CHECKS PASSED
Set-Location report\final_report; pdflatex fpr-8.tex; pdflatex fpr-8.tex; pdflatex fpr-8.tex; Set-Location D:\signal_project
venv\Scripts\python.exe report\final_report\tools\package_submission.py      # writes D:\signal_project\fpr-8.zip (~255 MB)
```

- The figure scripts overwrite the PNGs in `report\final_report\figures\`.
- **Do not regenerate `AI_PROMPTS.md`.** It is the final, hand-edited version. `extract_ai_prompts.py` would overwrite it, so never run it again, and do not add new prompts to the file.
- The zip leaves out `.agents\` and `archive\agent_sessions\` (agent configuration and old agent session logs), as well as this folder.
- This folder is committed to git, but it is also listed in `.git\info\exclude` (a local file, not part of the repository), and `package_submission.py` leaves the folders listed there out of the zip. On a fresh clone, add the line `team/` to `.git\info\exclude` again before packaging, or the folder goes into `fpr-8.zip`.
- The zip script adds the v6, v6.1 and v7 model programs (`v6_sim.exe`, `v61_sim.exe`, `v7_sim.exe` and the matching `*_brain.exe`) from the model folder.

---

## 13. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Server prints / page shows `COM5: could not open port 'COM5': PermissionError(13, 'Access is denied.' …)` | another program has COM5: second server, batch eval, serial terminal | Section 3: stop them, then **Reconnect** on the page |
| Page: `FPGA not answering` (yellow), detail `COM5 open but the FPGA does not answer (bitstream loaded?)` | board was powered off or reset, so no bitstream | Program again (section 2), click **Reconnect** |
| Page: `FPGA not connected`, detail `COM5 not found (USB cable / driver?)` | cable out, board off, or a different COM number | Check power and cable; run `Get-PnpDevice` (section 1); use the port list on the page or `--port COMx` |
| Batch eval stops with `TimeoutError: FPGA silent for 20 s` | not programmed, power cycled, wrong `V6_VARIANT` (v7 waits for END7 that a v6/v6.1 board never sends), BTN0 pressed | Reprogram; check `$env:V6_VARIANT` matches the bitstream; run again |
| Page error `FPGA stopped answering for 5 s (cable unplugged or board reset?)` | same as above, during a web run | same fix; then Reconnect and Start again |
| `bit-exact False` in the batch eval | `V6_VARIANT` does not match the bitstream, or `.exe` files rebuilt with other flags | Set the right variant (section 0); rebuild with the exact flags (section 10) |
| No final beats on the page, "Final fetal beats 0", error at the end | server in v7 mode but board has v6/v6.1 | Program v7 or restart the server with the matching `V6_VARIANT` |
| Page looks old or the pill shows the wrong design | browser cache, or an old server still answers on 8050 | Stop **all** servers (section 3), start one, then **Ctrl+F5** |
| Page: `Server not reachable` | server window closed or crashed | Start it again (section 4) |
| Start button greyed out | hover: `FPGA not connected` or `Load a recording first` | Fix the board / click Load |
| Upload error `No .hea header found …` | only `.dat` selected | Select `.hea` **and** `.dat` (and `.fqrs`) together |
| Upload error `Need 4 abdominal leads, header has N …` | not a 4-lead recording | Use CinC `aXX` files; ADFECGDB `.edf` and FECGSYNDB cannot be loaded |
| No accuracy card | `.fqrs` not selected | Load again with the `.fqrs` file |
| Running F1 low during a v7 run | the last ~15 s have no final beats yet | Normal; read the F1 after FLUSH |
| `A run is already in progress.` / `Stop the current run before uploading.` | a run is going | Click **Stop**, wait for "Stopped by user" |
| Vivado: cannot connect to `localhost:3121` / no hw_target / no `xc7s50_0` device | hw_server not running, cable not seen, or another Vivado holds the cable | Close other Vivado Hardware Manager windows; replug USB; start `& C:\AMDDesignTools\2025.2\Vivado\bin\hw_server.bat` in a separate window and run the program script again. Cable drivers: `C:\AMDDesignTools\2025.2\Vivado\data\xicom\cable_drivers\nt64\` (admin) |
| `vivado` / `vivado.bat` "not recognized" | Vivado is not on PATH | Use the full path `& C:\AMDDesignTools\2025.2\Vivado\bin\vivado.bat …` |
| Two servers on port 8050 at the same time (the second one starts without error) | Windows lets a second Python server bind the same port, so the browser may talk to the old one. The new one usually also prints "Access is denied" for COM5 | Stop **all** servers (section 3), start exactly one, Ctrl+F5 |
| RTL pytest: `FileNotFoundError` for `bash` | Git Bash not on PATH in PowerShell | `$env:PATH = 'C:\Program Files\Git\bin;' + $env:PATH` |
| `devbench_v6.py` builds a variant called `--sets` | used `--sets cdev` with a space | Write `--sets=cdev` |
| `gcc` not found | MinGW not on PATH | Use `C:\MinGW\bin\gcc.exe` |
| Board results look like v6 although the board is v7 | `V6_VARIANT` not set in this window (defaults to v6) | `$env:V6_VARIANT = 'v7'`, restart the server / script |

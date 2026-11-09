# FECG v5 platform: MicroBlaze soft-core on the Boolean board

The whole FECG algorithm runs on the FPGA in v5. The PC only streams the raw 4-lead recording and logs the beats the board sends back.

The hardware is a MicroBlaze CPU with a hardware single-precision FPU, running C firmware out of on-chip BRAM.

## Hardware (`build_v5.tcl`, part xc7s50csga324-1)
| Item | Value |
|---|---|
| System clock | 73.728 MHz from an MMCM (100 MHz in on F14), period 13.563 ns. All logic is on this clock. |
| CPU | MicroBlaze v11.0, 5-stage pipeline, no caches |
| CPU options | Extended FPU (`C_USE_FPU=2`: fadd/fmul/fdiv/fcmp, plus flt/fint/fsqrt), barrel shifter, 32-bit HW multiplier, HW divider, pattern compare. MDM (JTAG debug) is included. |
| Code and data RAM | LMB BRAM, **256 KB** at `0x00000000–0x0003FFFF`. Holds code, data, bss and the 16 KB stack. |
| Extra data RAM | AXI BRAM, **32 KB** at `0xC0000000–0xC0007FFF`. Linker section `.bigdata`. |
| UART | AXI UART16550 at `0x44A00000` (registers at +0x1000), **921600 baud** 8N1 (divisor 5, exact). RX V12, TX U11. |
| Timer | AXI Timer at `0x41C00000`. Free-running up-counter, 1 tick = 1 CPU cycle. |
| LEDs | AXI GPIO at `0x40000000`, LED[7:0]. LED0 = alive; LED[7:1] = block counter. |
| Reset | BTN0 (J2), active-high, through `proc_sys_reset` |

**RAM ceiling.** The xc7s50 has 75 BRAM36 tiles of 4 KB each, about 300 KB in total:
- the LMB uses 64 tiles;
- the 32 KB AXI BRAM uses 8 tiles;
- 3 tiles are left.

That makes **288 KB the practical maximum**, because each controller must be a power of two. There is no external RAM on the board.

Utilization, timing: see `reports/utilization.rpt` and `reports/timing.rpt` (numbers in the final section).

## Firmware (`fw/`)
| File | Purpose |
|---|---|
| `main.c` | Lock-step framed UART protocol, benchmark, memory test |
| `fecg_algo.h` | Algorithm API: `fecg_reset()`, `fecg_push(x[4], out, max_out)` |
| `fecg_algo_stub.c` | Stub that emits a fake beat every 100 samples. Replace it with the real algorithm. |
| `platform.h` | Register map and clock / baud constants |
| `sys_stubs.c` | `inbyte` / `outbyte` for newlib. No Xilinx BSP is used: the toolchain specs link `-lxil`, so `build_fw.sh` creates an empty `libxil.a`. |
| `lscript.ld` | Toolchain default `xilinx.ld` plus the `.bigdata` region. Asserts both RAM limits at link time. |

**Placing big arrays in the AXI BRAM:**
```c
static float ring[4096] __attribute__((section(".bigdata")));
```
- `.bigdata` is `NOLOAD`: it is **not zeroed at boot**, so clear it in `fecg_reset()`.
- AXI access is slower than LMB (several cycles per word). Keep hot loops on LMB data.

**Compiler flags** (`build_fw.sh`):
```
-O2 -ffp-contract=off -fno-math-errno -mcpu=v11.0 -mlittle-endian -mxl-barrel-shift
-mno-xl-soft-mul -mno-xl-soft-div -mhard-float -mxl-float-convert -mxl-float-sqrt -mxl-pattern-compare
```
There is no fast-math and no FMA contraction.

**Bit-exactness against a PC build of the same C:**
- **`float` only.** `double` is software-emulated on MicroBlaze: slow, but still IEEE.
- **x86-64 SSE math only.** Do not use x87 (32-bit MinGW) on the PC side.
- **Correctly rounded operations:** `+ - * /` and `sqrtf` are IEEE correctly rounded on both sides.
- **libm transcendentals** (`expf`, `logf`, `powf` and others) come from different libraries on the two sides: newlib here, MSVCRT/glibc on the PC. They are **not** guaranteed bit-identical. Use your own implementation compiled on both sides if exactness matters.
- **Denormals:** the MicroBlaze FPU flushes them to zero, while x86 SSE keeps them by default. To match, set FTZ/DAZ in the PC build (`_mm_setcsr(_mm_getcsr() | 0x8040)`), or keep values away from about 1e-38.

## Protocol (both directions)
Every frame has this layout:
`A5 5A cmd len_lo len_hi payload[len] xor8(cmd, len_lo, len_hi, payload)`

| Command | Reply |
|---|---|
| `0x01` RESET | `0x81`: calls `fecg_reset()`; the sample index restarts at 0 |
| `0x02` SAMPLES, N×4 int16 LE, N ≤ 256 | `0x82`: u32 cycles spent in `fecg_push` for the block, u16 nbeats, then nbeats × (u32 t, u16 fhr_x10, u8 src, u8 flags) |
| `0x03` PING | `0x83`: `"FECG-v5 73728000 921600"` |
| `0x04` BENCH | `0x84`: 5 × u32 cycle counts (see below) |
| `0x05` MEMTEST | `0x85`: u32 words, u32 errors, u32 cycles (pattern test of the AXI BRAM) |
| bad checksum or unknown command | `0xEE` followed by the command byte |

The firmware does no computation while receiving. So lock-step blocks of 250 samples never overflow the 16-byte UART FIFO, however long `fecg_push` takes.

## Build / program / run
**Hardware** (only after changing the block design; about 7 min):
```
cd D:/signal_project/fpga_implementation/v5
C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat -mode batch -nojournal -log build/vivado.log -source build_v5.tcl
```
This produces `build/sys_hw.bit`, `build/sys.mmi`, `build/sys.xsa` and `reports/`.

**Firmware** (seconds, no resynthesis; the ELF is merged into the bitstream with updatemem):
```
bash build_fw.sh                         # stub algorithm
bash build_fw.sh fw/fecg_algo.c [more.c] # real algorithm sources
```
This produces `build/fw.elf` and `build/download.bit`.

**Program:**
```
C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat -mode batch -nojournal -nolog -source program_v5.tcl
```

**Self-test** (ping, benchmark, memory test, 60 s stream):
```
D:/signal_project/venv/Scripts/python.exe ../uart_host/v5_client.py --port COM5 --baud 921600 --seconds 60
```

**Python use:**
```python
from v5_client import V5Board
b = V5Board("COM5")
b.reset()
beats, cyc = b.run(X_int16)   # X: (n, 4); beats: [(t, fhr_bpm, src, flags)]
```

## Measured on the board (2026-11-09, COM5, stub firmware)
**Implementation:**
- Timing is met: WNS +1.91 ns at 13.563 ns (73.73 MHz), hold +0.022 ns.
- Utilization: 3,340 LUTs (10.3%), 2,883 FFs (4.4%), **72 of 75 BRAM36 tiles (96%)**, 5 of 120 DSPs.

**Self-test (`v5_client.py`):**
- PING returns `FECG-v5 73728000 921600`.
- 921600 baud is stable: 15,000 samples streamed in 250-sample blocks in 1.92 s, which is **7,800 samples/s (31× real time)**.
- All 150 stub beats came back with correct timestamps and payload.
- MEMTEST: 32 KB AXI BRAM, 0 errors. That is about 17 cycles per AXI word access, against 1–2 for LMB.
- The stub algorithm costs about 136 cycles per sample (sample unpack plus call).

**Compute budget per sample:**
- 294,912 cycles at real time (250 Hz).
- About 9,400 cycles of algorithm time per sample before throughput drops below the UART-limited ~7,800 samples/s.
- The board is lock-step, so heavier algorithms simply run slower than 31×, never wrong.

| BENCH (`0x04`) | Cycles | Per operation |
|---|---|---|
| 99,840 float MAC (`acc += a[i]*b[i]`, LMB) | 1,799,085 | **~18 cycles/MAC** (loop-carried FPU latency) |
| 10,000 float div + add | 420,012 | ~42 |
| 10,000 `sqrtf` + int→float + add | 500,012 | ~50 (hardware `fsqrt`) |
| 99,840 int16 MAC | 1,499,173 | ~15 |
| 100,000 empty volatile loop | 1,200,014 | 12 (loop overhead) |

A dependent float MAC is limited by fadd latency. Several independent accumulators (unroll 4) should get close to the ~4-cycle issue rate.

## Gotchas
- **UART Lite tops out at 230400 baud** in Vivado 2025.2, so the design uses UART16550 with the system clock chosen to give an exact divisor (73.728 MHz = 16 × 5 × 921600).
- **BD automation for `axi_bram_ctrl` fails in batch mode** (`get_rule_options`), so the controller is wired by hand in `build_v5.tcl`.
- MicroBlaze automation `debug_module` takes `{Debug Only}`, with a space.
- **Build with `vivado.bat` via `cmd //c`** from Git Bash.
- The FTDI port must not be held open by another program (for example the v2 scripts) while `v5_client.py` runs.
- **The v2 bitstream is not overwritten.** To go back to v2, program `fpga_implementation/bitstream/fecg_multichannel_top.bit` (also backed up in `report/night_20261109/`).

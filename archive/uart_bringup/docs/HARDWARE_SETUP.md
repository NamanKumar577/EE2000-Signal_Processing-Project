# Hardware Setup & Pin Mapping Guide for Spartan-7 XC7S50 UART Bringup

**Target Silicon:** AMD/Xilinx Spartan-7 `XC7S50-1CSGA324C`  
**Communication Standard:** Asynchronous Serial (UART), 8 Data Bits, No Parity, 1 Stop Bit (8-N-1)  
**I/O Logic Level:** 3.3 V LVCMOS (`LVCMOS33`)  

---

## 1. Physical Hardware Overview

The repository codebase targets the **RealDigital Boolean Board** (Spartan-7 XC7S50), while also being compatible with the **Digilent Arty S7-50** development board.

```
       LAPTOP (USB Port)
              │
              │  Standard USB-A to Micro-B Cable
              ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ ONBOARD USB-TO-UART BRIDGE (FTDI FT2232H / CP2102N)          │
   │  - Enumerates on Laptop as a Virtual COM Port               │
   │  - Translates USB packets to 3.3V UART signals              │
   └───────────────┬─────────────────────────────▲───────────────┘
          TX Data  │                             │  RX Data
          (3.3V)   │                             │  (3.3V)
                   ▼                             │
   ┌─────────────────────────────────────────────┴───────────────┐
   │ AMD / XILINX SPARTAN-7 XC7S50 FPGA                           │
   │                                                             │
   │  - Master Clock: 100.000 MHz Crystal Oscillator             │
   │  - UART RX Pin: Receives serial stream into uart_rx.v       │
   │  - UART TX Pin: Transmits serial stream from uart_tx.v      │
   │  - Reset Pin  : Pushbutton BTN0 (Debounced/Synchronized)    │
   │  - Status LEDs: Visual proof of RX, TX, Error flags         │
   └─────────────────────────────────────────────────────────────┘
```

---

## 2. Board Pin Comparison & Constraints

### 2.1 Primary Target: RealDigital Boolean Board (`XC7S50-1CSGA324C`)
*Constraints File:* `uart_bringup/constraints/boolean_board.xdc`

| Signal Name | FPGA Pin | I/O Standard | Direction | Description & Peripheral |
|---|:---:|:---:|:---:|---|
| `clk` | **`E3`** | `LVCMOS33` | Input | 100.0 MHz master crystal oscillator ($T = 10.0\,\text{ns}$) |
| `rst_pin` | **`J2`** | `LVCMOS33` | Input | Pushbutton `BTN[0]` (Active-High when pressed) |
| `uart_rxd` | **`V12`** | `LVCMOS33` | Input | FPGA UART RX (connected to FTDI Bridge TXD) |
| `uart_txd` | **`U11`** | `LVCMOS33` | Output | FPGA UART TX (connected to FTDI Bridge RXD) |
| `led[0]` | **`G1`** | `LVCMOS33` | Output | RX Activity indicator (toggles on each received byte) |
| `led[1]` | **`G2`** | `LVCMOS33` | Output | TX Activity indicator (toggles on each transmitted byte) |
| `led[2]` | **`F1`** | `LVCMOS33` | Output | Framing Error sticky flag (illuminates if stop bit corrupted) |
| `led[3]` | **`F2`** | `LVCMOS33` | Output | FIFO Overflow sticky flag (illuminates if buffer overruns) |
| `led[7:4]` | **`D2, D1, E2, E1`** | `LVCMOS33` | Output | Upper nibble of most recently received byte |

### 2.2 Secondary Target: Digilent Arty S7-50 (`XC7S50-CSGA324`)
*Constraints File:* `uart_bringup/constraints/arty_s7_50.xdc`

| Signal Name | FPGA Pin | I/O Standard | Direction | Description & Peripheral |
|---|:---:|:---:|:---:|---|
| `clk` | **`R2`** | `LVCMOS33` | Input | 100.0 MHz master crystal oscillator |
| `rst_pin` | **`G15`** | `LVCMOS33` | Input | Pushbutton `BTN0` (Active-High when pressed) |
| `uart_rxd` | **`V12`** | `LVCMOS33` | Input | FPGA UART RX (connected to FTDI Bridge TXD) |
| `uart_txd` | **`R12`** | `LVCMOS33` | Output | FPGA UART TX (connected to FTDI Bridge RXD) |
| `led[0]` | **`E18`** | `LVCMOS33` | Output | LD0 green LED (RX Activity toggle) |
| `led[1]` | **`F13`** | `LVCMOS33` | Output | LD1 green LED (TX Activity toggle) |
| `led[2]` | **`E13`** | `LVCMOS33` | Output | LD2 green LED (Framing Error flag) |
| `led[3]` | **`H14`** | `LVCMOS33` | Output | LD3 green LED (Overflow flag) |

---

## 3. Voltage Level & Electrical Compatibility

- **FPGA Bank Voltage ($V_{\text{CCO}}$):** User I/O banks connected to the USB-UART bridge operate at **3.3 V**.
- **Standard:** `LVCMOS33` ($V_{IL} \le 0.8\,\text{V}$, $V_{IH} \ge 2.0\,\text{V}$, $V_{OL} \le 0.4\,\text{V}$, $V_{OH} \ge 2.4\,\text{V}$).
- **Safety:** The onboard FTDI FT2232H / CP2102N bridge is powered by the board's 3.3V regulator and is directly compatible with the Spartan-7 I/O pins. **No level shifters are required** when using the onboard USB port.
- **Warning on External Adapters:** If connecting an external USB-to-UART adapter (e.g. FTDI breakout, CH340, CP2102) to standard PMOD headers, ensure the adapter's jumper is set to **3.3 V** (NEVER connect 5.0 V logic directly to Spartan-7 I/O pins, as 7-series FPGAs are NOT 5V tolerant).

---

## 4. Laptop Host Device Discovery

When the FPGA board is connected to the laptop via USB:
1. Windows will recognize the onboard USB-to-UART controller.
2. Open Windows **Device Manager** -> expand **Ports (COM & LPT)**.
3. Look for:
   - `USB Serial Port (COMx)` (FTDI FT2232H / CP2102N)
   - Or run our discovery tool:
     ```powershell
     python uart_bringup/python/uart_test.py --list
     ```

*Current Host Machine Scan Result:*
- At present, no USB-to-UART hardware bridge is plugged in (only Bluetooth COM3/COM4 links detected).
- As soon as the FPGA board is plugged in, run `--list` to discover the assigned COM port.

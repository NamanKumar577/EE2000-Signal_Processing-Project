# Host PC UART Communication Suite (`fpga_implementation/uart_host/`)

This directory provides host-side Python utilities, streaming drivers, calibration engines, and real-time telemetry processing for interfacing with the AMD/Xilinx Spartan-7 FPGA accelerator over the FTDI FT2232H USB-UART bridge at 921,600 baud (bringup fallback: 115,200 baud).

## Core Driver & Streaming Engine

### `fecg_uart_client.py`
The production host-side communication client and streaming engine:
- **Port:** Connects to `COM5` (or specified serial port) at 115,200 baud or 921,600 baud (8-N-1).
- **Packets Encoded:**
  - **Downlink Sample Packet (`0xA5`, 11 Bytes):** Encodes 4-channel signed 16-bit Q12 samples at 250 Hz with 8-bit rolling sequence counter and CRC8-CCITT.
  - **Downlink Calibration Packet (`0xC3`, 10 Bytes):** Encodes 4 signed 16-bit Q1.15 spatial weights with CRC8-CCITT.
- **Packets Decoded:**
  - **Uplink Clean FECG Stream (`0x5A`, 6 Bytes):** Decodes signed 24-bit Q20 maternal-subtracted filtered FECG stream at 250 Hz ($2^{20}\text{ LSB/mV}$).
  - **Uplink QRS Event & FHR Telemetry (`0xAA`, 8 Bytes):** Decodes latency-compensated 24-bit sample timestamp, 16-bit FHR in $0.1\text{ bpm}$, and authoritative beat classification flags (`REAL`, `FUSED`, `HELD`, `WARMUP`, calibration confidence, saturation flag).
  - **Uplink Hardware Diagnostics (`0xEE`, 8 Bytes):** Decodes hardware anomaly alerts (CRC errors, sequence gaps, filter saturation, FIFO overflow).
- **Robust Framing Engine (`UARTStreamFramer`):**
  - Resynchronizes immediately after corrupted bytes or line noise without desynchronizing subsequent frames.
  - Zero false lock or frame starvation.
- **Multithreading & Streaming:**
  - Non-blocking background listener thread with thread-safe telemetry queues.
  - Rate-pacing generator streaming at exactly $f_s = 250\text{ Hz}$ ($4.0\text{ ms}$ interval).
  - In-memory `MockSerialPort` for full-duplex offline unit/integration testing without hardware.

### Usage:
```bash
# Run bit-accurate offline protocol self-test:
python fpga_implementation/uart_host/fecg_uart_client.py --self-test

# Connect to FPGA on COM5 at 115,200 baud:
python fpga_implementation/uart_host/fecg_uart_client.py --port COM5 --baud 115200

# Connect to FPGA on COM5 at 921,600 baud:
python fpga_implementation/uart_host/fecg_uart_client.py --port COM5 --baud 921600

# Scan available serial ports:
python fpga_implementation/uart_host/fecg_uart_client.py --list-ports
```

# ==============================================================================
# Constraints File: boolean_board.xdc
# Target Board: RealDigital Boolean Board (Spartan-7 XC7S50-1CSGA324C, xc7s50csga324-1)
# Project: Standalone UART Echo Verification (Laptop <-> FPGA)
# Top Module: uart_top (uart_top.v)
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. System Clock (100.0 MHz Master Oscillator)
#    - Pin F14: IO_L13P_T2_MRCC_15 in Bank 15 (3.3V)
#    - Period: 10.000 ns, 50% duty cycle (0.0 ns rise, 5.0 ns fall)
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN F14 IOSTANDARD LVCMOS33 } [get_ports { clk }]
create_clock -period 10.000 -name sys_clk_pin -waveform {0.000 5.000} -add [get_ports { clk }]

# ------------------------------------------------------------------------------
# 2. Reset Pushbutton (BTN[0] on Boolean Board - Active-High)
#    - Pin H4: IO_L22N_T3_35 in Bank 35 (3.3V)
#    - BTN0 circuit: External 10k pull-down to GND; pressed state = 3.3V (HIGH)
#    - RTL uart_top.v RESET_POLARITY_LOW = 0 -> sys_rst = rst_pin (Active-High)
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN J2  IOSTANDARD LVCMOS33 } [get_ports { rst_pin }]

# ------------------------------------------------------------------------------
# 3. USB-to-UART Bridge Interface (FTDI FT2232H / Micro-B Connector)
#    - uart_rxd (FPGA Input from FTDI TXD pin 38 / BDBUS0): Pin U11 (IO_L24P_T3_D17_14 in Bank 14)
#    - uart_txd (FPGA Output to FTDI RXD pin 39 / BDBUS1): Pin V12 (IO_L24N_T3_D16_14 in Bank 14)
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN V12 IOSTANDARD LVCMOS33 } [get_ports { uart_rxd }]
set_property -dict { PACKAGE_PIN U11 IOSTANDARD LVCMOS33 } [get_ports { uart_txd }]

# ------------------------------------------------------------------------------
# 4. Diagnostic & Status LEDs (Green Discrete LEDs LD0 - LD7, Bank 35)
#    - led[0] (G2): RX Activity Toggle (flips state on each byte received)
#    - led[1] (H2): TX Activity Toggle (flips state on each byte transmitted)
#    - led[2] (F2): Framing Error Sticky Flag (illuminates on stop-bit error)
#    - led[3] (F5): FIFO Overflow Sticky Flag (illuminates if host overruns FIFO)
#    - led[4] (E4): Upper nibble bit 4 of most recently received byte (rx_data[4])
#    - led[5] (E3): Upper nibble bit 5 of most recently received byte (rx_data[5])
#    - led[6] (F3): Upper nibble bit 6 of most recently received byte (rx_data[6])
#    - led[7] (D6): Upper nibble bit 7 of most recently received byte (rx_data[7])
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN G1  IOSTANDARD LVCMOS33 } [get_ports { led[0] }]
set_property -dict { PACKAGE_PIN G2  IOSTANDARD LVCMOS33 } [get_ports { led[1] }]
set_property -dict { PACKAGE_PIN F1  IOSTANDARD LVCMOS33 } [get_ports { led[2] }]
set_property -dict { PACKAGE_PIN F2  IOSTANDARD LVCMOS33 } [get_ports { led[3] }]
set_property -dict { PACKAGE_PIN E1  IOSTANDARD LVCMOS33 } [get_ports { led[4] }]
set_property -dict { PACKAGE_PIN E2  IOSTANDARD LVCMOS33 } [get_ports { led[5] }]
set_property -dict { PACKAGE_PIN E3  IOSTANDARD LVCMOS33 } [get_ports { led[6] }]
set_property -dict { PACKAGE_PIN E5  IOSTANDARD LVCMOS33 } [get_ports { led[7] }]

# ------------------------------------------------------------------------------
# 5. FPGA Configuration & Bitstream Settings (Bank 0 / QSPI S25FL128S Flash)
# ------------------------------------------------------------------------------
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]

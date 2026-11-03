# ==============================================================================
# Constraints File: boolean_board.xdc
# Target Board: RealDigital Boolean Board (Spartan-7 XC7S50-1CSGA324C)
# Project: Standalone UART Echo Verification (Laptop <-> FPGA)
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. System Clock (100.0 MHz Master Oscillator)
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN E3  IOSTANDARD LVCMOS33 } [get_ports { clk }]
create_clock -period 10.000 -name sys_clk_pin -waveform {0.000 5.000} -add [get_ports { clk }]

# ------------------------------------------------------------------------------
# 2. Reset Pushbutton (BTN[0] on Boolean Board - Active-High)
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN J2  IOSTANDARD LVCMOS33 } [get_ports { rst_pin }]

# ------------------------------------------------------------------------------
# 3. USB-to-UART Bridge Interface (FTDI FT2232H / Micro-B Connector)
#    - uart_rxd: FPGA Input from Host (connected to FTDI TXD)
#    - uart_txd: FPGA Output to Host (connected to FTDI RXD)
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN V12 IOSTANDARD LVCMOS33 } [get_ports { uart_rxd }]
set_property -dict { PACKAGE_PIN U11 IOSTANDARD LVCMOS33 } [get_ports { uart_txd }]

# ------------------------------------------------------------------------------
# 4. Diagnostic & Status LEDs
#    - led[0] (G1): RX Activity Toggle (flips state on each byte received)
#    - led[1] (G2): TX Activity Toggle (flips state on each byte transmitted)
#    - led[2] (F1): Framing Error Sticky Flag (illuminates on stop-bit error)
#    - led[3] (F2): FIFO Overflow Sticky Flag (illuminates if host overruns FIFO)
#    - led[7:4]   : Upper nibble of most recent byte (E1, E2, D1, D2)
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN G1  IOSTANDARD LVCMOS33 } [get_ports { led[0] }]
set_property -dict { PACKAGE_PIN G2  IOSTANDARD LVCMOS33 } [get_ports { led[1] }]
set_property -dict { PACKAGE_PIN F1  IOSTANDARD LVCMOS33 } [get_ports { led[2] }]
set_property -dict { PACKAGE_PIN F2  IOSTANDARD LVCMOS33 } [get_ports { led[3] }]
set_property -dict { PACKAGE_PIN E1  IOSTANDARD LVCMOS33 } [get_ports { led[4] }]
set_property -dict { PACKAGE_PIN E2  IOSTANDARD LVCMOS33 } [get_ports { led[5] }]
set_property -dict { PACKAGE_PIN D1  IOSTANDARD LVCMOS33 } [get_ports { led[6] }]
set_property -dict { PACKAGE_PIN D2  IOSTANDARD LVCMOS33 } [get_ports { led[7] }]

# ------------------------------------------------------------------------------
# 5. FPGA Configuration & Bitstream Settings
# ------------------------------------------------------------------------------
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]

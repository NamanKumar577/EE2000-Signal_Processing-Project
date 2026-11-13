# ==============================================================================
# Constraints File: arty_s7_50.xdc
# Target Board: Digilent Arty S7-50 (Spartan-7 XC7S50-CSGA324)
# Project: Standalone UART Echo Verification (Laptop <-> FPGA)
#
# Note: Use this constraint file if targeting the Digilent Arty S7-50 board.
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. System Clock (100.0 MHz Master Crystal Oscillator)
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN R2  IOSTANDARD LVCMOS33 } [get_ports { clk }]
create_clock -period 10.000 -name sys_clk_pin -waveform {0.000 5.000} -add [get_ports { clk }]

# ------------------------------------------------------------------------------
# 2. Reset Pushbutton (BTN0 - Active-High)
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN G15 IOSTANDARD LVCMOS33 } [get_ports { rst_pin }]

# ------------------------------------------------------------------------------
# 3. USB-to-UART Bridge Interface (FTDI on Arty S7)
#    - uart_rxd: FPGA Input from Host (Arty pin V12)
#    - uart_txd: FPGA Output to Host (Arty pin R12)
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN V12 IOSTANDARD LVCMOS33 } [get_ports { uart_rxd }]
set_property -dict { PACKAGE_PIN R12 IOSTANDARD LVCMOS33 } [get_ports { uart_txd }]

# ------------------------------------------------------------------------------
# 4. Diagnostic & Status LEDs (Arty 4 Discrete Green LEDs + RGB LEDs)
# ------------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN E18 IOSTANDARD LVCMOS33 } [get_ports { led[0] }]
set_property -dict { PACKAGE_PIN F13 IOSTANDARD LVCMOS33 } [get_ports { led[1] }]
set_property -dict { PACKAGE_PIN E13 IOSTANDARD LVCMOS33 } [get_ports { led[2] }]
set_property -dict { PACKAGE_PIN H14 IOSTANDARD LVCMOS33 } [get_ports { led[3] }]
set_property -dict { PACKAGE_PIN J15 IOSTANDARD LVCMOS33 } [get_ports { led[4] }]
set_property -dict { PACKAGE_PIN G17 IOSTANDARD LVCMOS33 } [get_ports { led[5] }]
set_property -dict { PACKAGE_PIN F15 IOSTANDARD LVCMOS33 } [get_ports { led[6] }]
set_property -dict { PACKAGE_PIN C15 IOSTANDARD LVCMOS33 } [get_ports { led[7] }]

# ------------------------------------------------------------------------------
# 5. FPGA Configuration & Bitstream Settings
# ------------------------------------------------------------------------------
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]

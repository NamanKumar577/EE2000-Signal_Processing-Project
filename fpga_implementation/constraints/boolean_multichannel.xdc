# =============================================================================
# Constraints File: boolean_multichannel.xdc
# Target: RealDigital Boolean Board (AMD Spartan-7 XC7S50-1CSGA324C)
# Design: Multichannel PCA Fetal ECG Processor with UART Telemetry
# =============================================================================

# -----------------------------------------------------------------------------
# 1. Master System Clock (100.0 MHz Oscillator)
# -----------------------------------------------------------------------------
set_property PACKAGE_PIN F14 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]
create_clock -period 10.000 -name sys_clk_pin -waveform {0.000 5.000} [get_ports clk]

# -----------------------------------------------------------------------------
# 2. Reset Pushbutton (BTN0, active-high)
# -----------------------------------------------------------------------------
set_property PACKAGE_PIN J2 [get_ports rst_pin]
set_property IOSTANDARD LVCMOS33 [get_ports rst_pin]
set_false_path -from [get_ports rst_pin]

# -----------------------------------------------------------------------------
# 3. FTDI USB-UART Serial Interface (FT2232H Channel B)
# -----------------------------------------------------------------------------
# FPGA RX pin (receives from PC TX)
set_property PACKAGE_PIN V12 [get_ports uart_rxd]
set_property IOSTANDARD LVCMOS33 [get_ports uart_rxd]
set_false_path -from [get_ports uart_rxd]

# FPGA TX pin (transmits to PC RX)
set_property PACKAGE_PIN U11 [get_ports uart_txd]
set_property IOSTANDARD LVCMOS33 [get_ports uart_txd]
set_false_path -to [get_ports uart_txd]

# -----------------------------------------------------------------------------
# 4. Diagnostic LEDs (LED0 .. LED7)
# -----------------------------------------------------------------------------
set_property PACKAGE_PIN G1 [get_ports {led[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[0]}]

set_property PACKAGE_PIN G2 [get_ports {led[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[1]}]

set_property PACKAGE_PIN F1 [get_ports {led[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[2]}]

set_property PACKAGE_PIN F2 [get_ports {led[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[3]}]

set_property PACKAGE_PIN E1 [get_ports {led[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[4]}]

set_property PACKAGE_PIN E2 [get_ports {led[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[5]}]

set_property PACKAGE_PIN E3 [get_ports {led[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[6]}]

set_property PACKAGE_PIN E5 [get_ports {led[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[7]}]

set_false_path -to [get_ports {led[*]}]

# -----------------------------------------------------------------------------
# 5. Configuration & Bitstream Settings
# -----------------------------------------------------------------------------
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]

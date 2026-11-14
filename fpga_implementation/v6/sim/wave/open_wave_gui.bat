@echo off
rem Opens the v6 system simulation in the Vivado simulator GUI with the waveform signals added.
rem Run "bash run_wave.sh" once before this (it compiles the snapshot and makes the input files).
rem The whole 30-s recording is simulated (a few minutes); then zoom in and take screenshots.
cd /d %~dp0
call C:\AMDDesignTools\2025.2\Vivado\bin\xsim.bat tb_wave -gui -tclbatch wave_gui.tcl

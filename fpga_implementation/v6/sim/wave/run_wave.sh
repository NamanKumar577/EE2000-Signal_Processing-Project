#!/bin/bash
# Run the v6 system test on a recording with the Vivado simulator and dump waveforms (wave.vcd).
#   bash run_wave.sh [recording.i16]      (default: ../a01_30s.i16, CinC a01, first 30 s)
# Steps: C model makes the golden streams -> xvlog/xelab -> xsim batch with wave_vcd.tcl.
set -e
cd "$(dirname "$0")"
REC=${1:-../a01_30s.i16}
V=/c/AMDDesignTools/2025.2/Vivado/bin
V6_DUMP=G ../../model/v6_sim.exe "$REC" > beats_model.txt
R=../../rtl
cmd //c "$V\xvlog.bat $R/v6_uart.v $R/v6_link.v $R/v6_sos.v $R/v6_mwi.v $R/v6_det.v $R/v6_fe.v $R/v6_mat.v $R/v6_canc.v $R/v6_trk.v $R/v6_core.v ../tb_core.v tb_wave.v" > xv.log 2>&1
cmd //c "$V\xelab.bat -debug typical tb_wave -s tb_wave" > xe.log 2>&1
grep -E "ERROR" xv.log xe.log | head -20 || true
cmd //c "$V\xsim.bat tb_wave -tclbatch wave_vcd.tcl" > xs.log 2>&1
grep -E "RESULT|MISMATCH|TIMEOUT|ERROR" xs.log | head -10
ls -la wave.vcd

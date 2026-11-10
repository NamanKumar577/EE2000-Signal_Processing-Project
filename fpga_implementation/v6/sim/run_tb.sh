#!/bin/bash
# compile + run the v6 system testbench (uses G_up.hex / G_script.txt in this directory)
V=/c/AMDDesignTools/2025.2/Vivado/bin
cmd //c "$V\xvlog.bat ..\rtl\v6_uart.v ..\rtl\v6_link.v ..\rtl\v6_sos.v ..\rtl\v6_mwi.v ..\rtl\v6_det.v ..\rtl\v6_fe.v ..\rtl\v6_mat.v ..\rtl\v6_canc.v ..\rtl\v6_trk.v ..\rtl\v6_core.v tb_core.v" > xv.log 2>&1
grep -E "ERROR|WARNING" xv.log | head -30
cmd //c "$V\xelab.bat -debug off tb_core -s tb_core" > xe.log 2>&1
grep -E "ERROR|WARNING: \[VRFC" xe.log | head -30
cmd //c "$V\xsim.bat tb_core -R" > xs.log 2>&1
grep -E "MISMATCH|RESULT|TIMEOUT|ERROR|frames|too many|Fatal" xs.log | head -40

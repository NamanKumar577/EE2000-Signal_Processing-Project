#!/bin/bash
# RTL regression: for each <name>.i16 given, make golden streams with the C system model and
# run the RTL testbench; prints one result line per record.
for f in "$@"; do
  b=$(basename $f .i16)
  V6_DUMP=G ../model/v6_sim.exe $f > /dev/null 2>&1
  ./run_tb.sh > /dev/null 2>&1
  echo "$b: $(grep -E 'RESULT|TIMEOUT|too many' xs.log | head -1) $(grep -c MISMATCH xs.log) mismatches"
done

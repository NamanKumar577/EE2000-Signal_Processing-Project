#!/usr/bin/env bash
# Rebuild the v5 firmware and merge it into a download bitstream (no resynthesis).
#   ./build_fw.sh [algo.c ...]      default algorithm: fw/fecg_algo_stub.c
# Output: build/fw.elf, build/download.bit  (program with: vivado -mode batch -source program_v5.tcl)
set -euo pipefail
cd "$(dirname "$0")"
TOOLS=/c/AMDDesignTools/2025.2
export PATH=$TOOLS/gnu/microblaze/nt/bin:$PATH
ALGO=("$@")
[ ${#ALGO[@]} -eq 0 ] && ALGO=(fw/fecg_algo_stub.c)
LMB_BYTES=$((256 * 1024))

mkdir -p build/lib
if [ ! -f build/lib/libxil.a ]; then          # specs link -lxil; we use no BSP
  echo "" > build/empty.c
  mb-gcc -c -mlittle-endian -o build/empty.o build/empty.c
  mb-ar rcs build/lib/libxil.a build/empty.o
fi

# -ffp-contract=off and no fast-math: float results match an x86-64 SSE build of the same C
CFLAGS="-O2 -ffp-contract=off -fno-math-errno -mcpu=v11.0 -mlittle-endian -mxl-barrel-shift -mno-xl-soft-mul -mno-xl-soft-div \
 -mhard-float -mxl-float-convert -mxl-float-sqrt -mxl-pattern-compare -Wall -Ifw"
# fw/lscript.ld asserts the LMB (256 KB) and .bigdata (32 KB AXI BRAM) limits at link time
mb-gcc $CFLAGS -Lbuild/lib -T fw/lscript.ld -Wl,--defsym=_STACK_SIZE=0x4000 -Wl,--defsym=_HEAP_SIZE=0x0 \
  -o build/fw.elf fw/main.c fw/sys_stubs.c "${ALGO[@]}" -lm
mb-size -A build/fw.elf | grep -E "text|data|bss|stack|bigdata|Total"
END=$(mb-nm build/fw.elf | awk '$3=="_stack"{print strtonum("0x"$1)}')
BIG=$(mb-nm build/fw.elf | awk '$3=="_bigdata_end"{print strtonum("0x"$1) - 0xC0000000}')
echo "LMB used (incl. 16 KB stack) = $END of $LMB_BYTES bytes; .bigdata used = $BIG of 32768 bytes"

cmd //c "$(cygpath -w $TOOLS/Vivado/bin/updatemem.bat) -force -meminfo build\\sys.mmi -data build\\fw.elf \
 -proc sys_i/microblaze_0 -bit build\\sys_hw.bit -out build\\download.bit" > build/updatemem.log 2>&1 \
  || { tail -20 build/updatemem.log; exit 1; }
echo "OK: build/download.bit"

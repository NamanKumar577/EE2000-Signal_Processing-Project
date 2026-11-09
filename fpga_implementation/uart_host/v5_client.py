#!/usr/bin/env python3
"""
Host client for the FECG v5 MicroBlaze firmware (fpga_implementation/v5/fw/main.c).

Lock-step framed protocol, both directions:
    A5 5A cmd len_lo len_hi payload[len] xor8(cmd, len_lo, len_hi, payload)
  0x01 RESET            -> 0x81
  0x02 SAMPLES N*4 i16  -> 0x82 u32 cycles, u16 nbeats, nbeats*(u32 t, u16 fhr_x10, u8 src, u8 flags)
  0x03 PING             -> 0x83 ASCII "FECG-v5 <clockHz> <baud>"
  0x04 BENCH            -> 0x84 5*u32 cycles
  0x05 MEMTEST          -> 0x85 u32 words, u32 errors, u32 cycles (32 KB AXI BRAM)
  error                 -> 0xEE <cmd>

Self-test:  python v5_client.py [--port COM5] [--baud 921600] [--seconds 60]
"""
import argparse
import struct
import time

import numpy as np
import serial

MAX_N = 256


class V5Error(RuntimeError):
    pass


class V5Board:
    def __init__(self, port="COM5", baud=921600, timeout=5.0):
        self.ser = serial.Serial(port, baud, timeout=timeout)
        self.timeout = timeout
        time.sleep(0.05)
        self.ser.reset_input_buffer()

    def close(self):
        self.ser.close()

    # ── framing
    @staticmethod
    def _frame(cmd, payload=b""):
        n = len(payload)
        x = cmd ^ (n & 0xFF) ^ (n >> 8)
        for b in payload:
            x ^= b
        return bytes([0xA5, 0x5A, cmd, n & 0xFF, n >> 8]) + payload + bytes([x])

    def _read_exact(self, n):
        buf = self.ser.read(n)
        if len(buf) != n:
            raise V5Error(f"timeout: wanted {n} bytes, got {len(buf)}")
        return buf

    def _recv(self):
        deadline = time.perf_counter() + self.timeout
        prev = None
        while True:                       # sync on A5 5A
            if time.perf_counter() > deadline:
                raise V5Error("timeout waiting for frame sync")
            b = self._read_exact(1)[0]
            if prev == 0xA5 and b == 0x5A:
                break
            prev = b
        cmd, l0, l1 = self._read_exact(3)
        n = l0 | (l1 << 8)
        payload = self._read_exact(n)
        chk = self._read_exact(1)[0]
        x = cmd ^ l0 ^ l1
        for b in payload:
            x ^= b
        if x != chk:
            raise V5Error(f"bad checksum on reply 0x{cmd:02X}")
        if cmd == 0xEE:
            raise V5Error(f"board rejected command 0x{payload[0]:02X}")
        return cmd, payload

    def _xfer(self, cmd, payload=b""):
        self.ser.write(self._frame(cmd, payload))
        rc, pl = self._recv()
        if rc != (cmd | 0x80):
            raise V5Error(f"unexpected reply 0x{rc:02X} to 0x{cmd:02X}")
        return pl

    # ── commands
    def ping(self):
        return self._xfer(0x03).decode("ascii")

    def reset(self):
        self._xfer(0x01)

    def bench(self):
        return struct.unpack("<5I", self._xfer(0x04))

    def memtest(self):
        """Pattern test of the 32 KB AXI BRAM -> (words, errors, cycles)."""
        return struct.unpack("<3I", self._xfer(0x05))

    def push_block(self, X):
        """X: (N, 4) int16-range array, N <= 256. Returns (beats, cycles), beats = list of
        (t, fhr_bpm, src, flags)."""
        X = np.asarray(X)
        if X.ndim != 2 or X.shape[1] != 4 or len(X) > MAX_N:
            raise ValueError("X must be (N<=256, 4)")
        pl = self._xfer(0x02, np.clip(X, -32768, 32767).astype("<i2").tobytes())
        cycles, nb = struct.unpack_from("<IH", pl, 0)
        beats = []
        for i in range(nb):
            t, fhr, src, fl = struct.unpack_from("<IHBB", pl, 6 + 8 * i)
            beats.append((t, fhr / 10.0, src, fl))
        return beats, cycles

    def run(self, X, block=250):
        """Stream a whole (n, 4) record; returns (beats, per-block cycles)."""
        beats, cyc = [], []
        for i in range(0, len(X), block):
            b, c = self.push_block(X[i:i + block])
            beats += b
            cyc.append(c)
        return beats, np.array(cyc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM5")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--seconds", type=float, default=60)
    a = ap.parse_args()
    b = V5Board(a.port, a.baud)
    print("PING :", b.ping())
    clk = int(b.ping().split()[1])
    names = ["99,840 float MAC", "10,000 float div+add", "10,000 sqrtf+add", "99,840 int16 MAC",
             "100,000 empty volatile loop"]
    for nm, c in zip(names, b.bench()):
        print(f"BENCH: {nm:28s} {c:9d} cycles")
    w, e, c = b.memtest()
    print(f"MEMTEST: AXI BRAM {w * 4} bytes, {e} errors, {c} cycles")
    b.reset()
    n = int(a.seconds * 250)
    rng = np.random.default_rng(0)
    X = np.zeros((n, 4), np.int16)
    X[n // 2:] = rng.integers(-3000, 3000, (n - n // 2, 4))
    t0 = time.perf_counter()
    beats, cyc = b.run(X)
    dt = time.perf_counter() - t0
    exp = [t for t in range(n) if t % 100 == 99]
    ok = [t for t, *_ in beats] == exp
    flags_ok = all(fl == (int(X[t, 0]) & 0xFF) for t, _, _, fl in beats)
    print(f"STREAM: {n} samples in {dt:.2f} s = {n / dt:.0f} samples/s ({n / dt / 250:.1f}x real time)")
    print(f"STREAM: beats {len(beats)} (expected {len(exp)}), timestamps {'OK' if ok else 'MISMATCH'}, "
          f"payload echo {'OK' if flags_ok else 'MISMATCH'}")
    print(f"STREAM: algo cycles/block mean {cyc.mean():.0f}, max {cyc.max()} "
          f"(real-time budget: {clk} per 250-sample block = 1 s)")
    b.close()


if __name__ == "__main__":
    main()

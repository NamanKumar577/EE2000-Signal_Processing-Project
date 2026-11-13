#!/usr/bin/env python3
"""
Local web demo for FECG v6 (hand-written RTL on the Spartan-7 + PC brain).

Upload a 4-lead abdominal recording (PhysioNet WFDB .hea + .dat, optional .fqrs/.qrs
fetal annotations, or a .zip of them; or a CSV).  The server streams it to the board
in real time, exactly like uart_host/run_v6_board_eval.py, and the page shows the live
fetal heart rate, the board status and the processing stage.

Board only: nothing is processed unless the FPGA answers the probe.

Run:  venv/Scripts/python.exe fpga_implementation/webdemo/server.py [--port COM5] [--http 8050]
Open: http://localhost:8050
"""
import argparse
import io
import json
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import serial
import wfdb
from scipy.signal import decimate, resample_poly
from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fpga_implementation" / "uart_host"))
from run_v6_board_eval import CHUNK, MODEL, frame, read_frame  # noqa: E402
import harness as H  # noqa: E402  (tools/accuracy, put on sys.path by run_v6_board_eval)
import v5c  # noqa: E402

FS = 250
SCORE0 = 5000                       # score from 20 s, as in the board evaluation
CHUNK_S = CHUNK / FS                # 0.256 s of recording per SAMPLES frame
SILENT_S = 5.0                      # FPGA silent this long during a run -> board lost
INDEX = Path(__file__).with_name("index.html")
RUNS = Path(__file__).with_name("runs")          # one folder per run: beats.csv + summary.json

C_COV, C_MDET, C_REQ_MK, C_MPK, C_SEG, C_CALDATA, C_REQ_CAL = 0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86
C_REQ_SEL, C_OUT, C_DONE = 0x8A, 0x8B, 0x8C
STAGES = [
    "Learning the maternal signal (collecting 10 s for PCA)",
    "Maternal detection + cancellation, collecting calibration data",
    "PC brain: GEVD calibration of 16 candidate fetal tracks",
    "Fetal trackers warming up",
    "Monitoring: reporting fetal beats",
]


# ───────────────────────────── event log (SSE) ─────────────────────────────
class Events:
    """All events of the current session; SSE clients replay them from the start."""

    def __init__(self):
        self.cv = threading.Condition()
        self.log = []
        self.gen = 0

    def push(self, kind, **data):
        with self.cv:
            self.log.append(json.dumps({"type": kind, **data}))
            self.cv.notify_all()

    def clear(self):
        with self.cv:
            self.log = []
            self.gen += 1
            self.cv.notify_all()


EV = Events()


# ───────────────────────────── recording loading ─────────────────────────────
def to_counts(sig, units):
    """Physical units -> device counts at 3000 LSB/mV (as in eval_cinc2013 / adfecgdb)."""
    u = (units or "uV").strip().lower().replace("µ", "u")
    return sig * {"uv": 3.0, "mv": 3000.0, "v": 3e6}.get(u, 3.0)


def to_250(sig, fs):
    fs = float(fs)
    if abs(fs - FS) < 1e-6:
        return sig, 1.0, None
    q = fs / FS
    if abs(q - round(q)) < 1e-6:                 # same causal anti-alias as the evaluations
        return decimate(sig, int(round(q)), ftype="iir", axis=0, zero_phase=False), q, None
    from fractions import Fraction
    fr = Fraction(FS / fs).limit_denominator(1000)
    note = f"{fs:g} Hz is not a multiple of 250 Hz: resampled with resample_poly (not causal)."
    return resample_poly(sig, fr.numerator, fr.denominator, axis=0), fs / FS, note


def load_wfdb(files):
    """files: {name: bytes}. Returns X (n,4) counts @250 Hz, fq or None, info dict."""
    with tempfile.TemporaryDirectory(prefix="fecg_web_") as d:     # deleted after loading
        return _load_wfdb(Path(d), files)


def _load_wfdb(d, files):
    for name, data in files.items():
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for m in z.namelist():
                    if not m.endswith("/"):
                        (d / Path(m).name).write_bytes(z.read(m))
        else:
            (d / Path(name).name).write_bytes(data)
    heas = sorted(d.glob("*.hea"))
    if not heas:
        raise ValueError("No .hea header found. Upload the .hea and .dat files (or a .zip of them).")
    rec = heas[0].with_suffix("")
    r = wfdb.rdrecord(str(rec))
    names = list(r.sig_name)
    idx = list(range(len(names)))
    notes = []
    if len(names) != 4:
        ab = [i for i, s in enumerate(names) if any(k in s.lower() for k in ("abdom", "aecg"))]
        if len(ab) != 4:
            raise ValueError(f"Need 4 abdominal leads, header has {len(names)}: {names}")
        idx = ab
        notes.append(f"Using leads {[names[i] for i in idx]}.")
    sig = np.nan_to_num(r.p_signal[:, idx])
    units = r.units[idx[0]]
    X, q, note = to_250(to_counts(sig, units), r.fs)
    if note:
        notes.append(note)
    fq = None
    for ext in ("fqrs", "qrs"):
        if (d / f"{rec.name}.{ext}").exists():
            fq = np.round(wfdb.rdann(str(rec), ext).sample / q).astype(np.int64)
            notes.append(f"Fetal annotations found (.{ext}): accuracy will be shown.")
            break
    info = {"name": rec.name, "fs_in": float(r.fs), "leads": [names[i] for i in idx], "units": units}
    return X, fq, info, notes


def load_csv(data, name, fs, units):
    txt = data.decode("utf-8", errors="replace").splitlines()
    rows = []
    for line in txt:
        parts = [p for p in line.replace(";", ",").replace("\t", ",").split(",") if p.strip()]
        try:
            rows.append([float(p) for p in parts])
        except ValueError:
            if rows:                              # a bad line inside the data is an error
                raise ValueError(f"Non-numeric line in CSV: {line[:80]!r}")
            continue                              # header line(s)
    if not rows:
        raise ValueError("CSV has no numeric rows.")
    A = np.array(rows, dtype=float)
    notes = []
    if A.shape[1] == 5 and np.all(np.diff(A[:, 0]) > 0):
        A = A[:, 1:]
        notes.append("First column is increasing: treated as time and ignored.")
    if A.shape[1] != 4:
        raise ValueError(f"CSV must have 4 lead columns (optionally a leading time column); got {A.shape[1]}.")
    X, _, note = to_250(to_counts(A, units), fs)
    if note:
        notes.append(note)
    return X, None, {"name": Path(name).stem, "fs_in": fs, "leads": ["col1", "col2", "col3", "col4"], "units": units}, notes


# ───────────────────────────── board ─────────────────────────────
class Board:
    def __init__(self, port):
        self.port = port
        self.ser = None
        self.lock = threading.Lock()          # serial writes (main loop and brain thread)
        self.plock = threading.Lock()         # one probe at a time
        self.state = "unknown"                # no_port | no_answer | connected | busy
        self.detail = ""
        self.probe_ms = None

    def _close(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None

    def ports(self):
        return [p.device for p in list_ports.comports()]

    def probe(self):
        with self.plock:
            return self._probe()

    def _probe(self):
        """RESET + one zero SAMPLES frame; a programmed v6 board answers DONE."""
        if self.port not in self.ports():
            self._close()
            self.state, self.detail = "no_port", f"{self.port} not found (USB cable / driver?)"
            return False
        try:
            if self.ser is None:
                self.ser = serial.Serial(self.port, 921600, timeout=0.2)
            with self.lock:
                self.ser.write(frame(0x01))
            time.sleep(0.05)
            self.ser.reset_input_buffer()
            t0 = time.perf_counter()
            with self.lock:
                self.ser.write(frame(0x02, bytes(CHUNK * 8)))
            while True:
                cmd, _, _ = read_frame(self._reader(1.0))
                if cmd == C_DONE:
                    break
            self.probe_ms = (time.perf_counter() - t0) * 1000
            with self.lock:
                self.ser.write(frame(0x01))
            self.state, self.detail = "connected", f"v6 RTL answering on {self.port}"
            return True
        except TimeoutError:
            self.state, self.detail = "no_answer", f"{self.port} open but the FPGA does not answer (bitstream loaded?)"
        except (serial.SerialException, OSError) as e:
            self._close()
            self.state, self.detail = "no_port", f"{self.port}: {e}"
        return False

    def _reader(self, timeout):
        def read(n):
            out = b""
            t0 = time.time()
            while len(out) < n:
                d = self.ser.read(n - len(out))
                if d:
                    out += d
                    t0 = time.time()
                elif time.time() - t0 > timeout:
                    raise TimeoutError
            return out
        return read

    def status(self):
        return {"port": self.port, "state": self.state, "detail": self.detail,
                "probe_ms": None if self.probe_ms is None else round(self.probe_ms, 1), "ports": self.ports()}


# ───────────────────────────── run ─────────────────────────────
class Session:
    def __init__(self, board):
        self.board = board
        self.rec = None                       # (X, fq, info, notes)
        self.thread = None
        self.stop = threading.Event()
        self.last_dir = None                  # folder of the last saved run

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if self.running:
            raise RuntimeError("A run is already in progress.")
        if self.rec is None:
            raise RuntimeError("Upload a recording first.")
        if not self.board.probe():
            EV.push("board", **self.board.status())
            raise RuntimeError(f"FPGA not connected: {self.board.detail}")
        self.stop.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        b = self.board
        X, fq, info, _ = self.rec
        xi = v5c.to_i16(X)
        n = len(xi)
        EV.clear()
        b.state, b.detail = "busy", f"streaming to the FPGA on {b.port}"
        EV.push("board", **b.status())
        EV.push("start", name=info["name"], n=n, fs=FS, has_truth=fq is not None,
                truth=[] if fq is None else fq[(fq >= 0) & (fq < n)].tolist())
        brain = subprocess.Popen([str(MODEL / "v6_brain.exe")], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, bufsize=0)
        n_rsp = [0]

        def brain_read(k):
            out = b""
            while len(out) < k:
                d = brain.stdout.read(k - len(out))
                if not d:
                    raise EOFError
                out += d
            return out

        def brain_to_fpga():
            try:
                while True:
                    cmd, _, raw = read_frame(brain_read)
                    with b.lock:
                        b.ser.write(raw)
                    n_rsp[0] += 1
                    EV.push("brain", cmd=cmd)
            except (EOFError, OSError, ValueError, serial.SerialException):
                pass

        threading.Thread(target=brain_to_fpga, daemon=True).start()
        beats, mpk = [], []
        stage = -1
        cal_req = False
        fhr_now = 0.0
        err = None
        done = 0
        chunk_ms = []
        started = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with b.lock:
                b.ser.write(frame(0x01))
            time.sleep(0.05)
            b.ser.reset_input_buffer()
            brain.stdin.write(frame(0x01))
            t_start = time.perf_counter()
            for ci, c0 in enumerate(range(0, n, CHUNK)):
                if self.stop.is_set():
                    break
                wait = t_start + ci * CHUNK_S - time.perf_counter()     # real-time pacing
                if wait > 0:
                    time.sleep(wait)
                blk = np.ascontiguousarray(xi[c0:c0 + CHUNK])
                t_send = time.perf_counter()
                with b.lock:
                    b.ser.write(frame(0x02, blk.astype("<i2").tobytes()))
                new_beats, new_mpk, reqs = [], [], []
                rd = b._reader(SILENT_S)
                while True:
                    cmd, p, raw = read_frame(rd)
                    if cmd == C_DONE:
                        T = int.from_bytes(p[0:4], "little")
                        break
                    if cmd == C_OUT:
                        t = int.from_bytes(p[0:4], "little")
                        f10 = p[4] | (p[5] << 8)
                        beats.append((t, f10, p[6]))
                        new_beats.append([t, f10 / 10.0, p[6]])
                        if f10 > 0:
                            fhr_now = f10 / 10.0
                        continue
                    brain.stdin.write(raw)
                    if cmd == C_MPK:
                        pp = int.from_bytes(p[0:4], "little")
                        mpk.append(pp)
                        new_mpk.append(pp)
                    elif cmd in (C_COV, C_REQ_MK, C_REQ_CAL, C_REQ_SEL):
                        reqs.append({C_COV: "maternal PCA", C_REQ_MK: "maternal train choice",
                                     C_REQ_CAL: "GEVD calibration", C_REQ_SEL: "track selection"}[cmd])
                        cal_req = cal_req or cmd == C_REQ_CAL
                fpga_ms = (time.perf_counter() - t_send) * 1000
                chunk_ms.append(fpga_ms)
                done = c0 + len(blk)
                st = (4 if beats or done >= 5027 else 2 if "GEVD calibration" in reqs
                      else 3 if cal_req else 1 if done >= 2500 else 0)
                if st != stage:
                    stage = st
                    EV.push("stage", idx=st, text=STAGES[st], t=done / FS)
                mhr = None
                if len(mpk) >= 3:
                    rr = np.diff(mpk[-6:])
                    rr = rr[(rr > 60) & (rr < 400)]
                    if len(rr):
                        mhr = round(60.0 * FS / float(np.median(rr)), 1)
                lead = blk[::2].astype(int).T.tolist()                 # 125 Hz preview of the 4 leads
                EV.push("chunk", t0=c0, done=done, T=T, fpga_ms=round(fpga_ms, 1), leads=lead,
                        beats=new_beats, mpk=new_mpk, reqs=reqs, fhr=fhr_now, mhr=mhr, n_rsp=n_rsp[0])
                if fq is not None and done >= SCORE0 + 2 * FS and ci % 8 == 0:
                    EV.push("score", **self._score(fq, beats, done))
        except TimeoutError:
            err = f"FPGA stopped answering for {SILENT_S:.0f} s (cable unplugged or board reset?)"
        except (serial.SerialException, OSError) as e:
            err = f"Serial error: {e}"
        finally:
            try:
                brain.stdin.close()
                brain.kill()
            except Exception:
                pass
        stopped = self.stop.is_set()
        res = {"stopped": stopped, "beats": len(beats)}
        if fq is not None and beats:
            res.update(self._score(fq, beats, n if not (stopped or err) else done))
        status = "error" if err else "stopped" if stopped else "complete"
        try:
            self._save(info, n, done, beats, chunk_ms, res, status, err, started, fq is not None)
        except OSError as e:
            EV.push("error", text=f"Could not save the run: {e}")
        if err:
            b._close()
            b.state, b.detail = "no_port", err
            EV.push("error", text=err)
        else:
            EV.push("end", **res)
            b.probe()
        EV.push("board", **b.status())

    def _save(self, info, n, done, beats, chunk_ms, res, status, err, started, has_truth):
        d = RUNS / f"{info['name']}_{time.strftime('%Y%m%d_%H%M%S')}"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "beats.csv", "w", newline="") as f:
            f.write("sample,time_s,fhr_bpm,track\n")
            for t, f10, src in beats:
                f.write(f"{t},{t / FS:.3f},{f10 / 10:.1f},{src}\n")
        ms = np.array(chunk_ms) if chunk_ms else np.zeros(1)
        summary = {
            "record": info["name"], "input_fs_hz": info["fs_in"], "leads": info["leads"], "units": info["units"],
            "started": started, "status": status, "error": err, "port": self.board.port,
            "recording_s": n / FS, "processed_s": done / FS, "fetal_beats": len(beats),
            "annotations": has_truth,
            "accuracy": {k: res[k] for k in ("f1", "se", "ppv", "fhr_mae", "tp", "fp", "fn", "upto_s") if k in res} or None,
            "fpga_ms_per_chunk": {"chunk_s": CHUNK_S, "mean": round(float(ms.mean()), 2),
                                  "median": round(float(np.median(ms)), 2), "max": round(float(ms.max()), 2)},
        }
        (d / "summary.json").write_text(json.dumps(summary, indent=2))
        self.last_dir = d
        EV.push("saved", dir=str(d), files=["beats.csv", "summary.json"])

    @staticmethod
    def _score(fq, beats, n):
        bb = np.array(beats, dtype=np.int64).reshape(-1, 3)
        pk, fhr = v5c.beats_to_stream(bb, n)
        r = H.score(fq[fq < n], pk[pk < n], fhr, n, SCORE0)
        return {k: (None if not np.isfinite(r[k]) else round(float(r[k]), 2))
                for k in ("f1", "se", "ppv", "fhr_mae", "tp", "fp", "fn")} | {"upto_s": n / FS}


# ───────────────────────────── HTTP ─────────────────────────────
def parse_multipart(ctype, body):
    msg = BytesParser(policy=email_policy).parsebytes(
        b"Content-Type: " + ctype.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
    files, fields = {}, {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        fn = part.get_filename()
        data = part.get_payload(decode=True) or b""
        if fn:
            files[fn] = data
        elif name:
            fields[name] = data.decode()
    return files, fields


def make_handler(sess):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                data = INDEX.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif self.path == "/api/status":
                if not sess.running:
                    sess.board.probe()
                rec = None
                if sess.rec:
                    X, fq, info, notes = sess.rec
                    rec = {**info, "seconds": len(X) / FS, "has_truth": fq is not None, "notes": notes}
                self._json({"board": sess.board.status(), "running": sess.running, "recording": rec})
            elif self.path in ("/api/download/beats.csv", "/api/download/summary.json"):
                name = self.path.rsplit("/", 1)[1]
                if sess.last_dir is None or not (sess.last_dir / name).exists():
                    self.send_error(404, "No saved run yet")
                    return
                data = (sess.last_dir / name).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv" if name.endswith(".csv") else "application/json")
                self.send_header("Content-Disposition", f'attachment; filename="{sess.last_dir.name}_{name}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif self.path == "/api/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                i, gen = 0, None
                try:
                    while True:
                        with EV.cv:
                            if gen != EV.gen:
                                gen, i = EV.gen, 0
                                self.wfile.write(b'data: {"type":"reset"}\n\n')
                            if i >= len(EV.log):
                                EV.cv.wait(15)
                            batch = EV.log[i:]
                            i = len(EV.log)
                        out = b"".join(b"data: " + e.encode() + b"\n\n" for e in batch) or b": ping\n\n"
                        self.wfile.write(out)
                        self.wfile.flush()
                except (ConnectionError, OSError):
                    pass
            else:
                self.send_error(404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n)
            try:
                if self.path == "/api/upload":
                    if sess.running:
                        raise RuntimeError("Stop the current run before uploading.")
                    files, fields = parse_multipart(self.headers["Content-Type"], body)
                    if not files:
                        raise ValueError("No file received.")
                    csvs = [f for f in files if f.lower().endswith(".csv")]
                    if csvs:
                        fs = float(fields.get("fs") or 0)
                        if fs <= 0:
                            raise ValueError("Enter the CSV sample rate (Hz).")
                        sess.rec = load_csv(files[csvs[0]], csvs[0], fs, fields.get("units", "uV"))
                    else:
                        sess.rec = load_wfdb(files)
                    X, fq, info, notes = sess.rec
                    if len(X) < 25 * FS:
                        notes.append("Shorter than 25 s: beats only start after about 20 s.")
                    self._json({"ok": True, "recording": {**info, "seconds": len(X) / FS,
                                                          "has_truth": fq is not None, "notes": notes}})
                elif self.path == "/api/start":
                    sess.start()
                    self._json({"ok": True})
                elif self.path == "/api/stop":
                    sess.stop.set()
                    self._json({"ok": True})
                elif self.path == "/api/port":
                    if sess.running:
                        raise RuntimeError("Stop the current run first.")
                    sess.board._close()
                    sess.board.port = json.loads(body or b"{}").get("port", sess.board.port)
                    sess.board.probe()
                    self._json({"ok": True, "board": sess.board.status()})
                else:
                    self.send_error(404)
            except Exception as e:                               # report to the page
                self._json({"ok": False, "error": str(e)}, 400)

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM5")
    ap.add_argument("--http", type=int, default=8050)
    a = ap.parse_args()
    sess = Session(Board(a.port))
    sess.board.probe()
    print(f"Board: {sess.board.detail}")
    srv = ThreadingHTTPServer(("127.0.0.1", a.http), make_handler(sess))
    srv.daemon_threads = True
    print(f"Open http://localhost:{a.http}")
    srv.serve_forever()


if __name__ == "__main__":
    main()

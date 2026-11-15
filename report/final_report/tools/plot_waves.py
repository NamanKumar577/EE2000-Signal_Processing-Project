#!/usr/bin/env python3
"""
Waveform figures for the final report from the Vivado simulator (xsim) run of the v6 RTL.

Input: fpga_implementation/v6/sim/wave/wave.vcd, made by
    bash fpga_implementation/v6/sim/wave/run_wave.sh          (CinC a01, first 30 s)
which runs the unchanged system testbench (every uplink byte checked against the C model)
through the tb_wave wrapper and dumps its signals.

    venv/Scripts/python.exe report/final_report/tools/plot_waves.py
"""
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
VCD = ROOT / "fpga_implementation/v6/sim/wave/wave.vcd"
OUT = ROOT / "report/final_report/figures"
CLK_PS = 20000                     # 50 MHz
SIGNED = {"raw_lead1", "raw_lead2", "raw_lead3", "raw_lead4", "xf_lead1", "xf_lead2", "xf_lead3", "xf_lead4",
          "z_lead1", "z_lead2", "z_lead3", "z_lead4", "mat_peak_t", "sel_track", "beat_t"}
ST = {2: "IDLE", 3: "P1", 4: "P2", 5: "FE", 6: "MAT", 7: "CANC", 8: "CD0", 9: "CD1", 10: "CD2", 11: "CD3", 12: "CD4",
      13: "CD5", 14: "CD6", 15: "CD7", 16: "TK0", 17: "TRK", 18: "DONE", 19: "DN2", 20: "NEXT"}
PH = {0: "core", 1: "fe", 2: "mat", 3: "canc", 4: "trk"}
CMD = {0x80: "COV", 0x83: "MPK", 0x84: "SEG", 0x85: "CALDATA", 0x86: "REQ_CAL", 0x8A: "REQ_SEL", 0x8B: "OUT", 0x8C: "DONE",
       0x81: "MDET", 0x82: "REQ_MK", 0x87: "BEAT", 0x88: "FEAT", 0x89: "BMED"}

# Vivado-like colours
BG, FG, GRID, WAVE, BUS, LBL = "#000000", "#E0E0E0", "#2A2A2A", "#3CE63C", "#3CE63C", "#C8C8C8"


def read_vcd(path):
    ids, width, sig = {}, {}, {}
    t = 0
    with open(path) as f:
        for line in f:
            if line.startswith("$var"):
                p = line.split()
                ids[p[3]] = p[4]
                width[p[4]] = int(p[2])
                sig[p[4]] = ([], [])
            elif line.startswith("$enddefinitions"):
                break
        for line in f:
            if not line or line[0] == "$" or line[0] == "\n":
                continue
            c = line[0]
            if c == "#":
                t = int(line[1:])
            elif c == "b":
                v, i = line[1:].split()
                n = ids[i]
                if "x" in v or "z" in v:
                    continue
                x = int(v, 2)
                w = width[n]
                if n in SIGNED and x >= 1 << (w - 1):
                    x -= 1 << w
                sig[n][0].append(t)
                sig[n][1].append(x)
            elif c in "01":
                n = ids[line[1:].strip()]
                sig[n][0].append(t)
                sig[n][1].append(int(c))
    return {k: (np.array(v[0], dtype=np.int64), np.array(v[1], dtype=np.int64)) for k, v in sig.items()}


def step(s, t0, t1):
    """value changes of signal s inside [t0, t1], with the value held at t0 prepended."""
    t, v = s
    i0 = max(np.searchsorted(t, t0, "right") - 1, 0)
    i1 = np.searchsorted(t, t1, "right")
    tt, vv = t[i0:i1].copy(), v[i0:i1].copy()
    if len(tt):
        tt[0] = max(tt[0], t0)
    return tt, vv


def vivado_axes(nrows, w, h_per=0.36, label_w=1.45):
    H = nrows * h_per + 0.85
    fig = plt.figure(figsize=(w, H), facecolor=BG)
    ax = fig.add_axes([label_w / w, 0.45 / H, 1 - label_w / w - 0.02, 1 - 0.85 / H])
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_color("#555")
    ax.tick_params(colors=FG, labelsize=6.5)
    ax.set_ylim(-0.5, nrows - 0.5)
    ax.invert_yaxis()
    ax.set_yticks([])
    return fig, ax


def draw_bit(ax, row, s, t0, t1, scale, col=WAVE):
    tt, vv = step(s, t0, t1)
    if not len(tt):
        return
    x = (np.append(tt, t1) - OFF) / scale
    y = np.append(vv, vv[-1])
    ax.step(x, row + 0.3 - 0.6 * y, where="post", color=col, lw=0.8)


def draw_bus(ax, row, s, t0, t1, scale, fmt=str, col=BUS, minw=0.0):
    tt, vv = step(s, t0, t1)
    if not len(tt):
        return
    ends = np.append(tt[1:], t1)
    span = (t1 - t0) / scale
    for a, b, v in zip(tt, ends, vv):
        xa, xb = (a - OFF) / scale, (b - OFF) / scale
        d = min(0.15 * (xb - xa), span * 0.002)
        ax.plot([xa, xa + d, xb - d, xb, xb - d, xa + d, xa], [row, row - 0.3, row - 0.3, row, row + 0.3, row + 0.3, row],
                color=col, lw=0.7)
        if (xb - xa) > max(minw, span * 0.035):
            ax.text((xa + xb) / 2, row, fmt(v), color=FG, fontsize=5.6, ha="center", va="center", clip_on=True)


def draw_analog(ax, row, s, t0, t1, scale, col=WAVE, lo=None, hi=None):
    tt, vv = step(s, t0, t1)
    if not len(tt):
        return
    x = (np.append(tt, t1) - OFF) / scale
    y = np.append(vv, vv[-1]).astype(float)
    lo = np.percentile(y, 0.5) if lo is None else lo
    hi = np.percentile(y, 99.5) if hi is None else hi
    yn = np.clip((y - lo) / max(hi - lo, 1e-9), 0, 1)
    ax.step(x, row + 0.4 - 0.8 * yn, where="post", color=col, lw=0.6)


OFF = 0                            # time origin of the current figure (ps)


def finish(fig, ax, labels, t0, t1, scale, unit, title, name, marks=(), xlabel=None):
    for i, l in enumerate(labels):
        ax.text(-0.006, i, l, transform=ax.get_yaxis_transform(), ha="right", va="center", color=LBL, fontsize=6.6)
        ax.axhline(i + 0.5, color=GRID, lw=0.5)
    for x, txt in marks:
        ax.axvline(x, color="#FFD24C", lw=0.7, ls="--")
        ax.text(x, 1.005, txt, color="#FFD24C", fontsize=6, ha="center", va="bottom", transform=ax.get_xaxis_transform())
    ax.set_xlim((t0 - OFF) / scale, (t1 - OFF) / scale)
    ax.set_xlabel(xlabel or f"simulation time ({unit})", color=FG, fontsize=7)
    ax.xaxis.grid(True, color=GRID, lw=0.5)
    fig.suptitle(title, color=FG, fontsize=8, y=0.985)
    fig.savefig(OUT / name, dpi=300, facecolor=BG)
    plt.close(fig)
    print("wrote", name)


def sample_times(S):
    """sim time at which each sample T starts processing (state P2)."""
    t, v = S["seq_state"]
    tp2 = t[v == 4]
    tT, vT = S["sample_T"]
    return tp2, tT, vT


def t_of_sample(S, n):
    tT, vT = S["sample_T"]
    i = np.searchsorted(vT, n)
    return int(tT[min(i, len(tT) - 1)])


# ----------------------------------------------------------------------------------------
def fig_overview(S):
    global OFF
    OFF = 0
    t1 = int(S["sample_T"][0][-1]) + 200 * CLK_PS
    t0 = 0
    rows = [("sample_T", "analog"), ("raw_lead1", "analog"), ("xf_lead1", "analog"), ("mat_npeaks", "analog"),
            ("pca_answer", "bit"), ("gevd_answer", "bit"), ("calibrated", "bit"), ("sel_track", "bus"),
            ("fhr_x10", "analog"), ("out_beat", "bit")]
    fig, ax = vivado_axes(len(rows), 7.0)
    sc = 1e9  # ps -> ms
    for i, (n, kind) in enumerate(rows):
        if n == "out_beat":
            continue
        if kind == "analog":
            draw_analog(ax, i, S[n], t0, t1, sc)
        elif kind == "bit":
            draw_bit(ax, i, S[n], t0, t1, sc)
        else:
            draw_bus(ax, i, S[n], t0, t1, sc, fmt=lambda v: "-" if v < 0 else str(v))
    # OUT frames: msg_start with msg_cmd = 0x8B
    tm, vm = S["msg_start"]
    tc, vc = S["msg_cmd"]
    starts = tm[vm == 1]
    cmds = vc[np.clip(np.searchsorted(tc, starts, "right") - 1, 0, None)]
    for x in starts[cmds == 0x8B] / sc:
        ax.plot([x, x], [len(rows) - 1 + 0.3, len(rows) - 1 - 0.3], color=WAVE, lw=0.6)
    first = lambda c: starts[cmds == c][0] / sc
    marks = [(first(0x80), "PCA request"), (first(0x86), "GEVD request"), (first(0x8B), "first beat out")]
    labels = ["sample_T", "raw_lead1", "xf_lead1", "mat_npeaks", "pca_answer", "gevd_answer", "calibrated",
              "sel_track", "fhr_x10", "OUT frame"]
    finish(fig, ax, labels, t0, t1, sc, "ms", "xsim, v6 RTL, CinC a01 (first 30 s of recording, 7,500 samples): whole run",
           "wave_overview.png", marks)


def fig_signal(S):
    """Signal-level window (a few seconds of recording) in sample time, after calibration."""
    global OFF
    n0, n1 = 6000, 6750
    t0, t1 = t_of_sample(S, n0), t_of_sample(S, n1)
    OFF = t0
    rows = [("raw_lead1", "analog"), ("raw_lead3", "analog"), ("xf_lead1", "analog"), ("xf_lead3", "analog"),
            ("mat_npeaks", "bus"), ("beat_t", "bus"), ("fhr_x10", "bus"), ("sel_track", "bus"), ("out_beat", "bit")]
    fig, ax = vivado_axes(len(rows), 7.0)
    sc = 1e6  # ps -> us
    for i, (n, kind) in enumerate(rows):
        if n == "out_beat":
            continue
        if kind == "analog":
            draw_analog(ax, i, S[n], t0, t1, sc)
        else:
            fmt = (lambda v: f"{v / 10:.1f}") if n == "fhr_x10" else str
            draw_bus(ax, i, S[n], t0, t1, sc, fmt=fmt)
    tm, vm = S["msg_start"]
    tc, vc = S["msg_cmd"]
    starts = tm[vm == 1]
    cmds = vc[np.clip(np.searchsorted(tc, starts, "right") - 1, 0, None)]
    for x in (starts[(cmds == 0x8B) & (starts >= t0) & (starts <= t1)] - OFF) / sc:
        ax.plot([x, x], [len(rows) - 1 + 0.3, len(rows) - 1 - 0.3], color=WAVE, lw=0.8)
    labels = ["raw_lead1", "raw_lead3", "xf_lead1", "xf_lead3", "mat_npeaks", "beat_q", "fhr_x10 (bpm)", "sel_track",
              "OUT frame"]
    finish(fig, ax, labels, t0, t1, sc, "µs", f"xsim, v6 RTL: samples {n0}-{n1} ({n0 / 250:.0f}-{n1 / 250:.0f} s of the recording)",
           "wave_signals.png", xlabel=f"simulation time from the start of sample {n0} (µs)")


def fig_one_sample(S, n=6100):
    global OFF
    t0, t1 = t_of_sample(S, n) - 30 * CLK_PS, t_of_sample(S, n + 1) + 30 * CLK_PS
    OFF = t_of_sample(S, n)
    rows = ["clk", "sample_T", "seq_state", "unit_ph", "fe_go", "fe_done", "mat_go", "mat_done", "ca_go", "ca_done",
            "tk_go", "tk_done", "msg_cmd", "tx_valid", "tx_byte"]
    fig, ax = vivado_axes(len(rows), 7.0)
    sc = 1e3  # ps -> ns
    for i, r in enumerate(rows):
        if r == "clk":
            if (t1 - t0) / CLK_PS < 400:
                tt = np.arange(t0 - t0 % CLK_PS, t1, CLK_PS // 2)
                vv = (np.arange(len(tt)) % 2 == 0).astype(int)
                draw_bit(ax, i, (tt, vv), t0, t1, sc)
            else:
                ax.fill_between([(t0 - OFF) / sc, (t1 - OFF) / sc], i - 0.3, i + 0.3, color=WAVE, alpha=0.35, lw=0)
                ax.text(((t0 + t1) / 2 - OFF) / sc, i, "50 MHz (20 ns period)", color=FG, fontsize=5.6, ha="center", va="center")
        elif r in ("sample_T",):
            draw_bus(ax, i, S[r], t0, t1, sc)
        elif r == "seq_state":
            draw_bus(ax, i, S[r], t0, t1, sc, fmt=lambda v: ST.get(v, str(v)))
        elif r == "unit_ph":
            draw_bus(ax, i, S[r], t0, t1, sc, fmt=lambda v: PH.get(v, str(v)))
        elif r == "msg_cmd":
            draw_bus(ax, i, S[r], t0, t1, sc, fmt=lambda v: CMD.get(v, f"{v:02X}"))
        elif r == "tx_byte":
            draw_bus(ax, i, S[r], t0, t1, sc, fmt=lambda v: f"{v:02X}")
        else:
            draw_bit(ax, i, S[r], t0, t1, sc)
    cyc = (t_of_sample(S, n + 1) - t_of_sample(S, n)) // CLK_PS
    finish(fig, ax, rows, t0, t1, sc, "ns",
           f"xsim, v6 RTL: processing of one sample (T = {n}): front end -> maternal -> canceller -> tracks, {cyc} clock cycles",
           "wave_one_sample.png", xlabel=f"time from the start of sample {n} (ns)")


def fig_request(S):
    """PCA request at T = 2500: COV frame out, FPGA stalls, PC answer in, processing resumes."""
    tm, vm = S["msg_start"]
    tc, vc = S["msg_cmd"]
    starts = tm[vm == 1]
    cmds = vc[np.clip(np.searchsorted(tc, starts, "right") - 1, 0, None)]
    tcov = starts[cmds == 0x80][0]
    ta, va = S["pca_answer"]
    tans = ta[(va == 1) & (ta > tcov)][0]
    global OFF
    t0, t1 = tcov - 400 * CLK_PS, tans + 600 * CLK_PS
    OFF = tcov
    rows = ["sample_T", "unit_ph", "msg_start", "msg_cmd", "tx_valid", "tx_byte", "rx_valid", "rx_byte", "pca_answer",
            "mat_npeaks"]
    fig, ax = vivado_axes(len(rows), 7.0)
    sc = 1e6  # ps -> us
    for i, r in enumerate(rows):
        if r == "unit_ph":
            draw_bus(ax, i, S[r], t0, t1, sc, fmt=lambda v: PH.get(v, str(v)))
        elif r == "msg_cmd":
            draw_bus(ax, i, S[r], t0, t1, sc, fmt=lambda v: CMD.get(v, f"{v:02X}"))
        elif r in ("tx_byte", "rx_byte"):
            draw_bus(ax, i, S[r], t0, t1, sc, fmt=lambda v: f"{v:02X}")
        elif r in ("sample_T", "mat_npeaks"):
            draw_bus(ax, i, S[r], t0, t1, sc)
        else:
            draw_bit(ax, i, S[r], t0, t1, sc)
    finish(fig, ax, rows, t0, t1, sc, "µs",
           "xsim, v6 RTL: maternal PCA request at T = 2500 (COV frame to the PC, FPGA waits, answer arrives, processing resumes)",
           "wave_pca_request.png", xlabel="time from the start of the COV request (µs)")


def fig_cancellation(S, a01_fqrs=None):
    """Signal view in sample time from the RTL's own ring writes: Xf, cancelled Z, maternal peaks, beats."""
    # replay Xf and Z ring writes; Z(s) is taken when the tracks read it (T = s + 176)
    tT, vT = S["sample_T"]
    tz, vzw = S["z_we"]
    ta, va = S["z_addr"]
    tzd, vzd = S["z_lead1"]
    tx, vxw = S["xf_we"]
    txa, vxa = S["xf_addr"]
    txd, vxd = S["xf_lead1"]
    n0, n1 = 5500, 6750
    zring = np.zeros(4096)
    zsnap = np.full(n1 + 1, np.nan)
    xf = np.full(n1 + 1, np.nan)
    # events: xf writes (front end writes both rings), z writes (canceller), sample advance
    ev = []
    for t in tx[vxw == 1]:
        ev.append((t, 0))
    for t in tz[vzw == 1]:
        ev.append((t, 1))
    for t, n in zip(tT, vT):
        ev.append((t, 2, n))
    ev.sort(key=lambda e: (e[0], e[1]))

    def val(s, t):
        tt, vv = s
        return vv[max(np.searchsorted(tt, t, "right") - 1, 0)]
    for e in ev:
        t = e[0]
        if e[1] == 0:
            a = val((txa, vxa), t + 1)
            d = val((txd, vxd), t + 1)
            zring[a] = d
            Tn = val((tT, vT), t)
            if Tn <= n1:
                xf[Tn] = d
        elif e[1] == 1:
            zring[val((ta, va), t + 1)] = val((tzd, vzd), t + 1)
        else:
            s = e[2] - 176
            if n0 <= s <= n1:
                zsnap[s] = zring[s % 4096]
    tp, vp = S["mat_peak_t"]
    mpk = np.unique(vp[(vp >= n0) & (vp <= n1)])
    beats = np.loadtxt(ROOT / "fpga_implementation/v6/sim/wave/beats_model.txt", dtype=int).reshape(-1, 3)[:, 0]
    rtl_beats = np.array([t for t, _, _ in out_frames(S)])
    rtl_beats = rtl_beats[(rtl_beats >= n0) & (rtl_beats <= n1)]
    s = np.arange(n0, n1 + 1) / 250.0
    fig, axs = plt.subplots(3, 1, figsize=(7.0, 3.6), sharex=True)
    axs[0].plot(s, xf[n0:n1 + 1], color="#555", lw=0.6)
    for p in mpk:
        axs[0].axvline(p / 250, color="#4C72B0", lw=0.6, alpha=0.6)
    axs[0].set_ylabel("Xf lead 1", fontsize=7)
    axs[0].set_title("Inside the RTL (xsim): front-end output, maternal R peaks (blue) and the signal after maternal cancellation",
                     fontsize=7.5)
    axs[1].plot(s, zsnap[n0:n1 + 1], color="#2E7D32", lw=0.6)
    axs[1].set_ylabel("Z lead 1\n(cancelled)", fontsize=7)
    if a01_fqrs is not None:
        for p in a01_fqrs[(a01_fqrs >= n0) & (a01_fqrs <= n1)]:
            axs[1].axvline(p / 250, color="#55A868", lw=0.6, alpha=0.5, ls=":")
    axs[2].set_ylim(0, 3)
    for p in rtl_beats:
        axs[2].plot([p / 250] * 2, [1.6, 2.6], color="#C44E52", lw=1.2)
    for p in beats[(beats >= n0) & (beats <= n1)]:
        axs[2].plot([p / 250] * 2, [0.4, 1.4], color="#333", lw=1.2)
    axs[2].set_yticks([0.9, 2.1], ["C model", "RTL (xsim)"], fontsize=7)
    axs[2].set_xlabel("time in the recording (s)", fontsize=7)
    axs[2].set_ylabel("fetal beats", fontsize=7)
    for a in axs:
        a.tick_params(labelsize=6.5)
        a.grid(alpha=0.3)
        if a is not axs[2]:
            a.set_yticks([])
    fig.tight_layout()
    fig.savefig(OUT / "wave_cancellation.png", dpi=300, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    print("wrote wave_cancellation.png")


def out_frames(S):
    """decode the uplink byte stream (A5 5A cmd len_lo len_hi payload xor) -> OUT frames (t, fhr_x10, track)."""
    tv, vv = S["tx_valid"]
    tb, vb = S["tx_byte"]
    rise = tv[vv == 1]
    by = vb[np.clip(np.searchsorted(tb, rise, "right") - 1, 0, None)]
    out, i = [], 0
    while i + 5 <= len(by):
        if by[i] != 0xA5 or by[i + 1] != 0x5A:
            i += 1
            continue
        cmd, ln = by[i + 2], by[i + 3] | (by[i + 4] << 8)
        pl = by[i + 5:i + 5 + ln]
        if cmd == 0x8B and len(pl) == 7:
            out.append((int(pl[0] | pl[1] << 8 | pl[2] << 16 | pl[3] << 24), int(pl[4] | pl[5] << 8), int(pl[6])))
        i += 6 + ln
    return out


def cycle_stats(S):
    t, v = S["seq_state"]
    tp2 = t[v == 4]
    tnx = t[v == 20]
    m = min(len(tp2), len(tnx))
    cyc = (tnx[:m] - tp2[:m]) // CLK_PS
    T = np.arange(m)
    pre = cyc[T < 2500]
    post = cyc[T >= 4877]
    tot = int(S["sample_T"][0][-1])
    end = int(t[-1])
    print(f"samples {m}; cycles/sample median: before 10 s {np.median(pre):.0f}, after calibration {np.median(post):.0f}, "
          f"mean all {cyc.mean():.0f}, max {cyc.max()} at T={int(np.argmax(cyc))}")
    print(f"total sim time {end / 1e9:.1f} ms for {m / 250:.0f} s of recording -> {m / 250 / (end / 1e12):.0f}x real time")
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    ax.semilogy(T / 250, cyc, ".", color="#4C72B0", ms=1.2, alpha=0.6, lw=0)
    ax.axhline(4000e-6 * 50e6, color="#C44E52", lw=0.8, ls="--")
    ax.text(0.3, 4000e-6 * 50e6 * 1.25, "real-time budget: 200,000 cycles / sample", fontsize=6, color="#C44E52")
    ax.set_xlabel("time in the recording (s)", fontsize=7)
    ax.set_ylabel("clock cycles per sample", fontsize=7)
    ax.tick_params(labelsize=6.5)
    ax.grid(alpha=0.3, which="both")
    ax.set_title("RTL processing time per input sample (xsim, 50 MHz)", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "wave_cycles_per_sample.png", dpi=300, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    print("wrote wave_cycles_per_sample.png")
    return cyc


if __name__ == "__main__":
    S = read_vcd(VCD)
    fq = None
    try:
        import sys
        sys.path.insert(0, str(ROOT / "tools" / "accuracy"))
        from eval_cinc2013 import load
        _, fq = load("a01")
    except Exception as e:  # annotations are only decoration here
        print("no a01 annotations:", e)
    cycle_stats(S)
    fig_overview(S)
    fig_signal(S)
    fig_one_sample(S)
    fig_request(S)
    fig_cancellation(S, fq)

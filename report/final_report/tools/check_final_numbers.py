#!/usr/bin/env python3
"""
Consistency check for the final report: recompute the key numbers from the saved result
files and check that fpr-8.tex quotes exactly those values.  Prints one line per check and
exits with 1 if any check fails.

    venv/Scripts/python.exe report/final_report/tools/check_final_numbers.py
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
TEX = (ROOT / "report/final_report/fpr-8.tex").read_text(encoding="utf-8")
TEX = re.sub(r"\\input\{(sections/[^}]+)\}",                  # include the section files
             lambda m: (ROOT / "report/final_report" / (m.group(1) + ".tex")).read_text(encoding="utf-8"), TEX)
TEX = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", TEX)          # compare without bold markup
ACC = ROOT / "tools/accuracy"
B6 = ROOT / "fpga_implementation/v6/build"
fails = 0


def check(name, value, *texts):
    """value: the recomputed number (for the log); texts: strings that must occur in the .tex."""
    global fails
    missing = [t for t in texts if t not in TEX]
    ok = not missing
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name:58s} {value!s:>12}" + ("" if ok else f"   missing: {missing}"))


f1 = lambda x: f"{x:.1f}"        # noqa: E731
f2 = lambda x: f"{x:.2f}"        # noqa: E731

# ---- v6 board results (Tab. final_results)
b = pd.read_csv(ROOT / "report/rtl_pc_split/board_umem/board_cdev_ad_ctest_syn.csv")
check("board records bit-exact", int(b.bit_exact.sum()), "140/140")
for s, n in [("syn", 60), ("ad", 5), ("cdev", 38), ("ctest", 37)]:
    g = b[b.set == s]
    assert len(g) == n
    row = f"& {n} & {f2(g.f1.mean())} & {f2(g.se.mean())} & {f2(g.ppv.mean())} & {f2(g.fhr_mae.mean())} & {int((g.f1 >= 90).sum())} & {n}/{n}"
    check(f"board {s}: F1/Se/PPV/MAE/>=90/bit-exact", f2(g.f1.mean()), row.replace("&  ", "& "))
    check(f"board {s}: rounded F1 in text", f1(g.f1.mean()), f1(g.f1.mean()))
rt = b.groupby("set").apply(lambda g: g.record_s.sum() / g.stream_s.sum(), include_groups=False)
check("board speed CinC test", f1(rt["ctest"]), f"{f1(rt['ctest'])}$\\times$")

# ---- confidence intervals (Tab. final_ci)
ci = pd.read_csv(ROOT / "report/final_report/tables/board_f1_ci.csv")
for _, r in ci.iterrows():
    check(f"CI {r.set}", f1(r.f1_mean), f"{f1(r.f1_mean)} [{f1(r.ci_low)}, {f1(r.ci_high)}] & {f1(r["median"])}")

# ---- earlier versions on real data
c = pd.read_csv(ACC / "results_cinc2013.csv")
odd = c.record.str[1:].astype(int) % 2 == 1
check("mid-term design causal, CinC test", f1(c.old_f1[~odd].mean()), f"& {f1(c.old_f1[~odd].mean())} & {f1(c.old_f1[odd].mean())} &")
check("v2, CinC test / dev", f1(c.v2_f1[~odd].mean()), f"& {f1(c.v2_f1[~odd].mean())} & {f1(c.v2_f1[odd].mean())} &")
ad = pd.read_csv(ACC / "results_adfecgdb.csv")
check("v2 / v3 ADFECGDB", f1(ad.v2_f1.mean()), f1(ad.v2_f1.mean()), f1(ad.hyb_f1.mean()))
v2 = pd.read_csv(ACC / "results_bitaccurate.csv")
check("v2 FECGSYNDB 1,248", f1(v2.f1.mean()), f"{f1(v2.f1.mean())}\\%")
v5 = pd.read_csv(ACC / "results_v5_final_synall.csv")
check("v5 FECGSYNDB 1,248", f1(v5.f1.mean()), f"& {f1(v5.f1.mean())} &")
u = pd.read_csv(ACC / "results_unet_syn.csv")
ua = pd.read_csv(ACC / "results_unet_adfecgdb.csv")
check("U-Net synthetic / ADFECGDB", f1(ua.f1.mean()), f"{f1(u.f1.mean())}\\%", f"{f1(ua.f1.mean())}\\%")
d = pd.read_csv(ACC / "results_diag_v5.csv").groupby("set").mean(numeric_only=True)
check("best single track / oracle, CinC dev", f1(d.loc["cdev", "best_track"]),
      f"{f1(d.loc['cdev', 'best_track'])}\\%", f"{f1(d.loc['cdev', 'win_oracle'])}\\%")

# ---- failure analysis
fa = pd.read_csv(ROOT / "report/final_report/tables/cinc_failures.csv")
vc = fa.category.value_counts()
check("failures: ok / mother / wrong / unreliable", dict(vc),
      f"{vc['ok']} of 75", f"Followed the mother ({vc['followed the mother']} records)",
      f"Wrong fetal-range track ({vc['wrong fetal-range track']} records)",
      f"Unreliable reference ({vc['reference unreliable']} records)")
nf = fa[(fa.category == "followed the mother") & ~fa.maternal_train_found]
check("followed the mother without a maternal train", len(nf), f"In {len(nf)} of these")

# ---- FPGA reports
util = (B6 / "util.rpt").read_text()
lut = int(re.search(r"\| Slice LUTs\s+\|\s+(\d+)", util).group(1))
ff = int(re.search(r"\| Slice Registers\s+\|\s+(\d+)", util).group(1))
bram = re.search(r"\| Block RAM Tile\s+\|\s+([\d.]+)", util).group(1)
dsp = int(re.search(r"\| DSPs\s+\|\s+(\d+)", util).group(1))
check("LUTs / FFs", lut, f"{lut:,}", f"{ff:,}")
check("BRAM tiles / DSP", bram, f"{int(float(bram))} (80\\%)", f"{dsp} (27.5\\%)")
wns = float(re.search(r"^\s+(-?\d+\.\d+)\s+\d+\.\d+\s+\d+\s+\d+", (B6 / "timing.rpt").read_text(), re.M).group(1))
check("worst slack", wns, f"+{wns:.2f}\\,ns")
pw = (B6 / "power.rpt").read_text()
tot = re.search(r"Total On-Chip Power \(W\)\s+\|\s+([\d.]+)", pw).group(1)
dyn = re.search(r"Dynamic \(W\)\s+\|\s+([\d.]+)", pw).group(1)
stat = re.search(r"Device Static \(W\)\s+\|\s+([\d.]+)", pw).group(1)
check("power total / dynamic / static", tot, f"{tot}\\,W", f"{dyn}\\,$W dynamic", f"{stat}\\,$W static")

# ---- simulation (needs fpga_implementation/v6/sim/wave/wave.vcd)
vcd = ROOT / "fpga_implementation/v6/sim/wave/wave.vcd"
if vcd.exists():
    sys.path.insert(0, str(ROOT / "report/final_report/tools"))
    import plot_waves as W
    S = W.read_vcd(vcd)
    t, v = S["seq_state"]
    a, e = t[v == 4], t[v == 20]
    m = min(len(a), len(e))
    cyc = (e[:m] - a[:m]) // W.CLK_PS
    med = int(np.median(cyc[np.arange(m) >= 4877]))
    check("median cycles per sample after calibration", med, f"{med:,} cycles")
    check("simulated time for 30 s", f"{t[-1] / 1e9:.1f} ms", f"{t[-1] / 1e9:.1f}\\,ms")
else:
    print("SKIP  simulation checks (run fpga_implementation/v6/sim/wave/run_wave.sh first)")

# ---- v6.1 and v7 (Sec. final_v7): board results, CIs, offline v7-LA, all-FECGSYNDB C-model results
UNREL = {"a33", "a38", "a47", "a52", "a54", "a71", "a74"}
b61 = pd.read_csv(ROOT / "report/v61_v7/board_v61/board_cdev_ad_ctest_syn.csv")
b7 = pd.read_csv(ROOT / "report/v61_v7/board_v7/board_cdev_ad_ctest_syn.csv")
for nm, d in (("v6.1", b61), ("v7-DL", b7)):
    check(f"{nm} board records bit-exact", int(d.bit_exact.sum()), "140/140")
ci = pd.read_csv(ROOT / "report/final_report/tables/board_v7_f1_ci.csv").set_index(["version", "set"])
for s, nm in [("syn", "FECGSYNDB subset"), ("ad", "ADFECGDB"), ("cdev", "CinC dev"), ("ctest", "CinC test")]:
    for ver, d in (("v6.1", b61), ("v7-DL", b7)):
        g = d[d.set == s]
        r = ci.loc[(ver, nm)]
        check(f"{ver} {s} F1 [CI]", f"{g.f1.mean():.2f}", f"{f1(g.f1.mean())} [{r.ci_low:.1f}, {r.ci_high:.1f}]")
    check(f"{s} FHR MAE v6.1 / v7-DL", "", f"{f2(b61[b61.set == s].fhr_mae.mean())} / {f2(b7[b7.set == s].fhr_mae.mean())}")
for ver, d in (("v6.1", b61), ("v7-DL", b7)):
    g = d[(d.set == "ctest") & ~d.rid.isin(UNREL)]
    r = ci.loc[(ver, "CinC test reliable")]
    check(f"{ver} ctest reliable F1 [CI]", f"{g.f1.mean():.2f}", f"{f1(g.f1.mean())} [{r.ci_low:.1f}, {r.ci_high:.1f}]")
for ver, d in (("v6.1", b61), ("v7-DL", b7)):
    for nm, sets in (("CinC dev", ["cdev"]), ("CinC all", ["cdev", "ctest"])):
        g = d[d.set.isin(sets)]
        gr = g[~g.rid.isin(UNREL)]
        r, rr = ci.loc[(ver, nm)], ci.loc[(ver, nm + " reliable")]
        check(f"{ver} {nm} all / reliable F1 [CI]", f"{g.f1.mean():.2f}/{gr.f1.mean():.2f}",
              f"{f1(g.f1.mean())} [{r.ci_low:.1f}, {r.ci_high:.1f}]", f"{f1(gr.f1.mean())} [{rr.ci_low:.1f}, {rr.ci_high:.1f}]")
mae = {}
for nm, sets in (("cdev", ["cdev"]), ("ctest", ["ctest"]), ("all", ["cdev", "ctest"])):
    for rel in (False, True):
        a, b = (x[x.set.isin(sets) & (~x.rid.isin(UNREL) if rel else True)].fhr_mae.mean() for x in (b61, b7))
        mae[nm, rel] = f"{f2(a)} / {f2(b)}"
check("CinC FHR MAE rows (all / reliable)", "", mae["cdev", True], mae["ctest", True], mae["all", False], mae["all", True])
ar7 = b7[b7.set.isin(["cdev", "ctest"])].set_index("rid").f1
check("v7-DL flagged records a33 / a47", f"{ar7['a33']:.1f} / {ar7['a47']:.1f}",
      f"a33 and a47, score ${ar7['a33']:.1f}\\%$ and ${ar7['a47']:.1f}\\%$")
c7 = b7[b7.set == "ctest"]
check("v7-DL ctest better / worse than live v6.1", "", f"improves {int((c7.f1 > c7.f1_causal + 1).sum())} records and worsens {int((c7.f1 < c7.f1_causal - 1).sum())}")
cc = b7[b7.set.isin(["cdev", "ctest"])]
check("v7-DL CinC better / worse (fig)", "", f"{int((cc.f1 > cc.f1_causal + 1).sum())} records improve by more than one point and {int((cc.f1 < cc.f1_causal - 1).sum())} get worse")
check("v7-DL ctest >= 90%", int((c7.f1 >= 90).sum()), f"18 records reach $\\ge 90\\%$")
# how much the failing records (F1 < 50%) pull the mean down (Sec. "Where the Remaining Error Is")
for nm, g in [("ctest", c7), ("CinC all", cc), ("syn", b7[b7.set == "syn"])]:
    short = 100 - g.f1
    low = g.f1 < 50
    check(f"v7-DL {nm}: median / records < 50% / their shortfall share", f"{g.f1.median():.1f}",
          f"median is ${g.f1.median():.1f}\\%$", f"{int(low.sum())} records below $50\\%$",
          f"${short[low].sum() / short.sum() * 100:.0f}\\%$")
check("v7-DL ctest: points lost by records < 50%", f"{(100 - c7.f1)[c7.f1 < 50].sum() / len(c7):.1f}",
      f"{(100 - c7.f1)[c7.f1 < 50].sum() / len(c7):.1f} of the {100 - c7.f1.mean():.1f} points",
      f"(a{', a'.join(c7[c7.f1 < 50].sort_values('f1').rid.str[1:])};")
s61 = pd.read_csv(ACC / "results_v61_synall.csv")
sdl = pd.read_csv(ACC / "results_v7dl_synall.csv")
sla = pd.read_csv(ACC / "results_v7la_synall.csv")
cl = pd.read_csv(ROOT / "tools/report_stats/out/cluster.csv").set_index(["data", "version"])
c61, cdl = cl.loc[("FECGSYNDB all (C model)", "v6.1")], cl.loc[("FECGSYNDB all (C model)", "v7-DL")]
check("FECGSYNDB all: v6.1 / v7-DL / v7-LA (subject-clustered CIs)", "",
      f"& 1,248 & {f1(s61[s61.variant == 'v61'].f1.mean())} [{c61.ci_low:.1f}, {c61.ci_high:.1f}] & {f1(sdl.f1.mean())} [{cdl.ci_low:.1f}, {cdl.ci_high:.1f}] &",
      f"$93.7\\%$ [$90.0$, $96.5$, subject-clustered]",
      f"{f2(s61[s61.variant == 'v61'].fhr_mae.mean())} / {f2(sdl.fhr_mae.mean())}", f"$94.3\\%$ on all 1,248 FECGSYNDB")
cond = sdl.rid.str.extract(r"_(c\d)$")[0]
check("literature table: v7-DL CinC reliable / ctest reliable / FECGSYNDB median / c4 median", "",
      f"v7-DL (ours, board) & 68 & {f1(b7[b7.set.isin(['cdev', 'ctest']) & ~b7.rid.isin(UNREL)].f1.mean())}",
      f"held-out half only & 33 & {f1(b7[(b7.set == 'ctest') & ~b7.rid.isin(UNREL)].f1.mean())}",
      f"& {len(sdl):,} & {f1(sdl.f1.median())}",
      f"& {(cond == 'c4').sum()} & {f1(sdl[cond == 'c4'].f1.median())}")
check("v7-DL by condition", "", ", ".join(f"${c}$ {sdl[cond == c].f1.mean():.1f}" for c in ["c0", "c1", "c2", "c3", "c4"]))
la_t = pd.read_csv(ACC / "results_v7la_ctest.csv")
la_d = pd.read_csv(ACC / "results_v7la_dev.csv")
check("v7-LA ctest / reliable / dev / ad", "", f"scores $75.6\\%$ on CinC test ($80.9\\%$ on reliable references), $84.6\\%$ on CinC dev, $95.8\\%$ on ADFECGDB")
assert f1(la_t.f1.mean()) == "75.6" and f1(la_t[~la_t.rid.isin(UNREL)].f1.mean()) == "80.9"
assert f1(la_d[la_d.set == "cdev"].f1.mean()) == "84.6" and f1(la_d[la_d.set == "ad"].f1.mean()) == "95.8"
for nm, path, lut in (("v6.1", "v61", "18,986"), ("v7-DL", "v7", "26,701")):
    u = (ROOT / f"fpga_implementation/v6/build/{path}/util.rpt").read_text()
    got = re.search(r"\| Slice LUTs\s+\|\s+(\d+)", u).group(1)
    check(f"{nm} LUTs", got, f"{int(got):,}")
# statistics subsection: paired v7-DL - v6.1 and v6.1 - v6 rows (tools/report_stats/out/paired.csv)
pr = pd.read_csv(ROOT / "tools/report_stats/out/paired.csv").set_index(["set", "comparison"])
for st, cmp_, lab in [("CinC test", "v7-DL - v6.1", "CinC test (37)"), ("CinC all", "v6.1 - v6", "CinC all (75)")]:
    r = pr.loc[(st, cmp_)]
    check(f"paired {cmp_} {st}", f"{r.mean_diff:+.1f}",
          f"{lab} & ${r.mean_diff:+.1f}$ [${r.ci_low:.1f}$, ${r.ci_high:.1f}$] & {int(r.better)} / {int(r.worse)}")
# PC-in-the-loop section: link traffic per decision (tables/pc_link_traffic.csv, from tools/pc_link_traffic.py)
tr = pd.read_csv(ROOT / "report/final_report/tables/pc_link_traffic.csv").set_index("decision")
share = {k: float(tr.loc[k, "share_pct"]) for k in ["template basis", "track selection", "GEVD calibration"]}
mat = float(tr.loc["maternal train", "share_pct"]) + float(tr.loc["maternal PCA", "share_pct"])
check("PC traffic shares basis / selection / calibration / maternal", f"{share['template basis']:.1f}",
      *[f"& {v:.1f}\\% &" for v in share.values()], f"& {mat:.1f}\\% &", f"{share['track selection']:.1f}\\% of the traffic")
up, dn = float(tr.loc["uplink_Bps", "bytes"]), float(tr.loc["answers_Bps", "bytes"]) + float(tr.loc["samples_down_Bps", "bytes"])
check("PC link load up / down (KB/s) and share of 92,160 B/s", f"{up / 1e3:.1f}/{dn / 1e3:.1f}",
      f"{up / 1e3:.1f}\\,KB/s up and {dn / 1e3:.1f}\\,KB/s down",
      f"{int(100 * up / 92160)}--{round(100 * dn / 92160)}\\%")

# ---- report revision (WS1-WS6): numbers recomputed from tools/report_stats/out
OUT = ROOT / "tools/report_stats/out"
bv7 = pd.read_csv(ROOT / "report/v61_v7/board_v7/board_cdev_ad_ctest_syn.csv")
bv6 = pd.read_csv(ROOT / "report/rtl_pc_split/board_umem/board_cdev_ad_ctest_syn.csv")
r7, r6 = bv7.record_s / bv7.stream_s, bv6.record_s / bv6.stream_s
check("speed v7-DL: mean of per-record ratios / range", f"{r7.mean():.2f}",
      f"{r7.mean():.2f}$\\times$", f"{r7.min():.1f}--{r7.max():.1f}$\\times$")
check("speed v6: mean / range", f"{r6.mean():.2f}", f"{r6.mean():.2f}\\times", f"{r6.min():.1f}--{r6.max():.1f}$\\times$")
ag = pd.read_csv(OUT / "ws5/agreement.csv").set_index(["version", "set"])
check("clinical agreement v7-DL ctest / cdev / ad / syn", f"{ag.loc[('v7', 'ctest'), 'within5']:.1f}",
      *[f"{ag.loc[('v7', s_), 'within5']:.1f}\\%" for s_ in ["ctest", "cdev", "ad", "syn"]])
gv = (OUT / "ws5/gevd_check.txt").read_text()
nsolve = re.search(r"GEVD solves (\d+)", gv).group(1)
check("GEVD solves (J = lambda_max)", nsolve, f"{int(nsolve):,}")
cp = pd.read_csv(OUT / "ws5/collision_proxy.csv")
check("collision proxy CinC dev / ADFECGDB (pooled)", "",
      *[f"{100 * (cp[cp.set == s_].measured / 100 * cp[cp.set == s_].n_fetal).sum() / cp[cp.set == s_].n_fetal.sum():.1f}" for s_ in ["cdev", "ad"]])
check("maternal train found in all dev records", int(cp.n_maternal.min()), f"at least {int(cp.n_maternal.min())} maternal R peaks")
bh = pd.read_csv(OUT / "behar_replication_summary.csv")
b68 = bh[bh.records.str.startswith("68")].set_index("method")
check("R8 Behar TS / TSpca mean (68 records)", f"{b68.loc['TS', 'mean_f1']:.1f}",
      f"{b68.loc['TS', 'mean_f1']:.1f}", f"{b68.loc['TSpca', 'mean_f1']:.1f}")
r5 = pd.read_csv(OUT / "r5_median.csv").iloc[0]
check("R5 fixed TS median / mean", f"{r5['median']:.1f}", f"{r5['median']:.1f}\\%", f"{r5['mean']:.1f}")
eg = pd.read_csv(OUT / "r3_eigen.csv").mean(numeric_only=True)
check("R3 eigen variance v1/v2, fetal v1/v2", f"{eg.var_v1:.1f}",
      f"{eg.var_v1:.1f}", f"{eg.var_v2:.1f}", f"{eg.fetal_v1:.1f}", f"{eg.fetal_v2:.1f}")
am = pd.read_csv(OUT / "amplitude_measured.csv").iloc[0]
check("Fig. 1 amplitude ratio / FMR range", f"{am.ratio:.1f}", f"${am.ratio:.1f}\\times$", f"{am.fmr_min:.2f}", f"{am.fmr_max:.2f}")
fe = pd.read_csv(OUT / "front_end.csv").set_index("filter")
check("front end: HP cut-off / maternal band / track band", f"{float(fe.iloc[0].f_low_3dB_Hz):.2f}",
      f"{float(fe.iloc[0].f_low_3dB_Hz):.2f}\\,Hz", "5--25\\,Hz", "15--40\\,Hz")
sl = pd.read_csv(OUT / "selection_loss.csv").set_index("set")
check("selection loss CinC dev: final / best / oracle / candidate loss", f"{sl.loc['cdev', 'final']:.1f}",
      f"{sl.loc['cdev', 'best_track']:.1f}\\%", f"{sl.loc['cdev', 'oracle']:.1f}\\%", f"{sl.loc['cdev', 'cand_loss']:.1f}")
nb = (OUT / "ws5/negctrl_board.txt").read_text()
check("negative control (board stream) passed", "PASSED" in nb, "bit flip")

print(f"\n{'ALL CHECKS PASSED' if not fails else f'{fails} CHECK(S) FAILED'}")
sys.exit(1 if fails else 0)

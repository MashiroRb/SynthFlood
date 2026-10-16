"""Teaser figure for SynthFlood: threat schematic + three verified result panels.
Run from the repo root (paths relative to repo_clone/results_csv/)."""
import csv, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

OK = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
      "red": "#D55E00", "purple": "#CC79A7", "sky": "#56B4E9",
      "yellow": "#F0E442", "grey": "#7F7F7F"}
plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 7.6, "axes.labelsize": 7.6,
    "xtick.labelsize": 7.0, "ytick.labelsize": 7.0, "legend.fontsize": 6.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.4,
    "figure.dpi": 150,
})
R = "results_csv/"

def rows(fn, eps=None, fam=None):
    out = []
    for r in csv.DictReader(open(R + fn)):
        if not r["task_id"] or not r.get("reward"):
            continue
        if "SKIPPED" in r.get("chosen_kind", ""):
            continue
        if eps is not None and float(r["eps"]) != float(eps):
            continue
        if fam is not None and r.get("family") != fam:
            continue
        out.append(r)
    return out

def mean(xs): return sum(xs) / len(xs)
def wilson(k, n):
    p = k / n; z = 1.96; den = 1 + z*z/n
    ctr = (p + z*z/(2*n)) / den
    hw = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return p, ctr - hw, ctr + hw

# ---- panel (b): probe decomposition from p1 CSVs (clone rows only) ----
def syn_field(r):
    return r.get("chosen_is_synthetic", r.get("is_synthetic", "0"))
def clone_sigma(fn):
    rs = [r for r in rows(fn) if r.get("family") == "clone"]
    k = sum(int(syn_field(r)) for r in rs)
    return wilson(k, len(rs)), len(rs)
orig, n_orig = clone_sigma("p1_forced_choice.csv")
pp, n1 = clone_sigma("p1_probeB.csv")
rp, n2 = clone_sigma("p1_probeC.csv")
fp, n3 = clone_sigma("p1_probeBC.csv")
geo = [r for r in rows("p1_forced_choice.csv") if r.get("family") == "geo"]
geo_p = sum(int(syn_field(r)) for r in geo) / len(geo)

# ---- panel (c): dose curve (mix, seed-1 pool) ----
eps_order = [0.0, 0.25, 0.5, 0.75]
regs, rlo, rhi = [], [], []
for ep in eps_order:
    rs = rows("p4a_sweep.csv", eps=ep, fam="mix")
    d = [1 - float(r["reward"]) for r in rs]
    m = mean(d); hw = 1.96 * np.std(d, ddof=1) / math.sqrt(len(d))
    regs.append(m); rlo.append(m - hw); rhi.append(m + hw)

# ---- panel (d): defenses at eps=0.75 (40 tasks) ----
def reg_of(fn, eps="0.75"):
    rs = rows(fn, eps=eps)
    return mean([1 - float(r["reward"]) for r in rs])
d_none = reg_of("p2_sweep.csv")
d_prompt = reg_of("p4c_prompt_sweep.csv")
d_prov = reg_of("p4c_provenance_sweep.csv")
d_struct = reg_of("p4c_detector_struct_sweep.csv")
d_oracle = reg_of("p4c_oracle_sweep.csv")
clean0 = reg_of("p2_sweep.csv", eps="0.0")

fig = plt.figure(figsize=(7.05, 2.30))
gs = fig.add_gridspec(1, 4, width_ratios=[1.30, 1.0, 0.92, 1.0],
                      wspace=0.52, left=0.045, right=0.995,
                      top=0.86, bottom=0.155)

# ---------------- (a) schematic ----------------
ax = fig.add_subplot(gs[0]); ax.set_axis_off()
ax.set_xlim(0, 1); ax.set_ylim(-0.02, 1.0)
ax.text(0.46, 1.0, "(a) threat: contaminated page", ha="center", fontsize=7.6)
page = FancyBboxPatch((0.02, 0.115), 0.86, 0.85, boxstyle="round,pad=0.012",
                      fc="white", ec=OK["grey"], lw=0.8)
ax.add_patch(page)
rowh = 0.062
labels = [
    ("gen",  "lookalike lamp",        "$59",  "$\\star$4.9 (2,314)"),
    ("real", "branded lamp",          "$85",  "$\\star$4.5 (188)"),
    ("gen",  "SEO lamp page",         "$84",  "$\\star$4.8 (1,522)"),
    ("gen",  "lookalike lamp",        "$62",  "$\\star$4.9 (1,940)"),
    ("real", "generic lamp",          "$79",  "$\\star$4.2 (96)"),
    ("gen",  "review-flooded page",   "$82",  "$\\star$4.9 (2,756)"),
    ("gold", "gold listing",          "$89",  "$\\star$4.6 (312)"),
    ("gen",  "lookalike lamp",        "$65",  "$\\star$4.8 (2,108)"),
    ("gen",  "SEO lamp page",         "$86",  "$\\star$4.9 (2,402)"),
]
y0 = 0.925
for i, (kind, t, pr, st) in enumerate(labels):
    y = y0 - i * (rowh + 0.010)
    if kind == "gen":
        fc, ec = "#FDF3E7", OK["orange"]
    elif kind == "gold":
        fc, ec = "#EAF4EC", OK["green"]
    else:
        fc, ec = "#F4F4F4", OK["grey"]
    ax.add_patch(FancyBboxPatch((0.045, y - rowh + 0.008), 0.76, rowh - 0.004,
                 boxstyle="round,pad=0.003", fc=fc, ec=ec, lw=0.7))
    ax.text(0.058, y - rowh/2 + 0.005, t, fontsize=4.6, va="center")
    ax.text(0.495, y - rowh/2 + 0.005, pr, fontsize=5.0, va="center")
    ax.text(0.640, y - rowh/2 + 0.005, "\u2605" + st.split("$\\star$")[1],
            fontsize=4.2, va="center")
ax.plot([0.885, 0.885], [y0, y0 - 8 * (rowh + 0.010) - rowh + 0.008],
        lw=0.7, color=OK["orange"])
ax.text(0.945, 0.55, "synthetic: 6 of 9 slots", rotation=90, fontsize=5.2,
        color=OK["orange"], ha="center", va="center")
ax.add_patch(FancyBboxPatch((0.060, 0.020), 0.78, 0.062, boxstyle="round,pad=0.004",
             fc="#EAF2F8", ec=OK["blue"], lw=0.8))
ax.text(0.45, 0.051, "agent buys the $59 lookalike", fontsize=5.0,
        ha="center", va="center", color=OK["blue"])

# ---------------- (b) channel decomposition ----------------
ax = fig.add_subplot(gs[1])
bars = [(orig, OK["blue"], "orig."), (pp, OK["orange"], "price"),
        (rp, OK["yellow"], "rating"), (fp, OK["red"], "both")]
for i, ((p, lo, hi), c, lab) in enumerate(bars):
    ax.bar(i, p, width=0.60, color=c)
    ax.errorbar(i, (lo+hi)/2, yerr=[[(lo+hi)/2 - lo], [hi - (lo+hi)/2]],
                fmt="none", ecolor="k", elinewidth=0.8, capsize=2.5)
ax.axhline(geo_p, color=OK["grey"], ls=":", lw=1)
ax.text(3.45, geo_p + 0.012, "gloss\nbaseline", fontsize=5.4,
        color=OK["grey"], ha="right", va="bottom")
ax.axhline(0.5, color=OK["grey"], ls="--", lw=0.7, alpha=0.6)
ax.set_xticks(range(4)); ax.set_xticklabels([b[2] for b in bars], fontsize=6.4)
ax.set_ylim(0, 0.72); ax.set_ylabel(r"clone win-rate $\sigma$")
ax.set_title("(b) preference, not perception", fontsize=7.6)

# ---------------- (c) dose response ----------------
ax = fig.add_subplot(gs[2])
xs = [0.02, 0.25, 0.5, 0.75]
ax.errorbar(xs, regs, yerr=[np.array(regs)-np.array(rlo), np.array(rhi)-np.array(regs)],
            marker="s", ms=4, lw=1.4, color=OK["red"], capsize=3)
ax.axhline(regs[0], color=OK["grey"], ls=":", lw=1)
ax.text(0.10, regs[0]+0.010, "clean", fontsize=5.8, color=OK["grey"])
ax.annotate("jump, then plateau", xy=(0.37, 0.417), xytext=(0.42, 0.245),
            fontsize=5.7, ha="center",
            arrowprops=dict(arrowstyle="->", lw=0.7))
ax.set_xticks(xs); ax.set_xticklabels(["0", "0.25", "0.5", "0.75"])
ax.set_xlabel(r"contamination $\varepsilon$"); ax.set_ylabel("regret")
ax.set_ylim(0.20, 0.53); ax.set_title("(c) regret: jump & plateau", fontsize=7.6)

# ---------------- (d) defenses ----------------
ax = fig.add_subplot(gs[3])
names = ["none", "prompt", "proven.", "struct", "oracle"]
vals = [d_none, d_prompt, d_prov, d_struct, d_oracle]
cols = [OK["grey"], OK["yellow"], OK["blue"], OK["green"], OK["purple"]]
ax.bar(range(5), vals, width=0.58, color=cols)
ax.axhline(clean0, color=OK["grey"], ls=":", lw=1)
ax.text(4.45, clean0 + 0.008, "clean", fontsize=5.4, ha="right", color=OK["grey"])
for i, v in enumerate(vals):
    ax.text(i, v + 0.008, f"{v:.3f}".lstrip("0"), ha="center", fontsize=5.6)
ax.set_xticks(range(5)); ax.set_xticklabels(names, rotation=25, ha="right", fontsize=6.2)
ax.set_ylabel(r"regret at $\varepsilon{=}0.75$"); ax.set_ylim(0, 0.47)
ax.set_title("(d) ordering beats detection", fontsize=7.6)

plt.savefig("paper/figures/teaser.pdf", bbox_inches="tight")
plt.savefig("/tmp/teaser_preview.png", dpi=210, bbox_inches="tight")
print("teaser written")

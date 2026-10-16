"""Regenerate all paper figures from verified result CSVs in a consistent,
colorblind-safe style (Okabe-Ito), with CI bands and direct annotations."""
import csv, json, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OK = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
      "red": "#D55E00", "purple": "#CC79A7", "sky": "#56B4E9",
      "yellow": "#F0E442", "grey": "#7F7F7F"}
plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.4,
    "figure.dpi": 150,
})
R = "../repo_clone/results_csv/"
B = json.load(open(R + "b_analysis.json"))

def sweep(fn):
    out = {}
    for r in csv.DictReader(open(R + fn)):
        if not r["task_id"] or not r.get("reward"):
            continue
        out.setdefault(float(r["eps"]), []).append(r)
    return out

def mean(xs): return sum(xs) / len(xs)

def wilson(p, n):
    z = 1.96; den = 1 + z*z/n; ctr = (p + z*z/(2*n)) / den
    hw = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return ctr - hw, ctr + hw

def cell_stats(rows):
    n = len(rows)
    succ = mean([float(r["success_full"]) for r in rows])
    reg = mean([1 - float(r["reward"]) for r in rows])
    lo, hi = wilson(succ, n)
    z = 1.96; m = reg; sd = np.std([1 - float(r["reward"]) for r in rows], ddof=1)
    hw = z * sd / math.sqrt(n)
    return dict(n=n, succ=succ, succ_ci=(lo, hi), reg=reg, reg_ci=(m-hw, m+hw))

def ece(rows, bins=5):
    xs = [(float(r["confidence"]) if r["confidence"] not in ("None", "") else None,
           float(r["success_full"])) for r in rows]
    xs = [(c, s) for c, s in xs if c is not None]
    n = len(xs); e = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        g = [(c, s) for c, s in xs if lo <= c < hi or (b == bins-1 and c == hi)]
        if not g:
            continue
        acc = mean([s for _, s in g]); conf = mean([c for c, _ in g])
        e += len(g) / n * abs(acc - conf)
    return e

# ---------------- dose–response (two panels) ----------------
a = sweep("p4a_sweep.csv")  # seed-1 pool only, matches Table 2 and headline text
eps_order = [0.0, 0.25, 0.5, 0.75]
def pooled(ep):
    return a.get(ep, [])
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.5))
# panel 1: success + regret vs eps
xs = eps_order
succ, succ_lo, succ_hi, reg, reg_lo, reg_hi = [], [], [], [], [], []
for ep in xs:
    rows = pooled(ep); st = cell_stats(rows)
    succ.append(st["succ"]); succ_lo.append(st["succ_ci"][0]); succ_hi.append(st["succ_ci"][1])
    reg.append(st["reg"]); reg_lo.append(st["reg_ci"][0]); reg_hi.append(st["reg_ci"][1])
xs[0] = 0.02  # avoid log-ish overlap at 0
ax1.errorbar(xs, succ, yerr=[np.array(succ)-succ_lo, np.array(succ_hi)-succ],
             marker="o", ms=4, lw=1.3, color=OK["blue"], capsize=3, label="task success")
ax1.errorbar(xs, reg, yerr=[np.array(reg)-reg_lo, np.array(reg_hi)-reg],
             marker="s", ms=4, lw=1.3, color=OK["red"], capsize=3, label="regret")
ax1.annotate("$-23$ pp\n($p{=}1.3{\\times}10^{-4}$)", (0.75, 0.362), xytext=(0.34, 0.635),
             fontsize=6.8, arrowprops=dict(arrowstyle="->", lw=0.7))
ax1.annotate("regret $+69\\%$", (0.75, 0.443), xytext=(0.34, 0.505),
             fontsize=6.8, arrowprops=dict(arrowstyle="->", lw=0.7))
ax1.set_xticks(xs); ax1.set_xticklabels(["0", "0.25", "0.5", "0.75"])
ax1.set_xlabel(r"contamination level $\varepsilon$")
ax1.set_ylabel("fraction / rate")
ax1.set_title("(a) Success falls, regret outruns it")
ax1.legend(loc="lower right", frameon=False)
# panel 2: synth purchase share + confidence + ECE
share, conf, eces = [], [], []
for ep in eps_order:
    rows = pooled(ep)
    n = len(rows)
    nsyn = sum(1 for r in rows if r["chosen_is_synthetic"] in ("1", "True", "true"))
    share.append(nsyn / n * 100 if n else 0.0)
    cs = [float(r["confidence"]) for r in rows if r["confidence"] not in ("None", "")]
    conf.append(mean(cs) if cs else 0.0)
    eces.append(ece(rows) if n else 0.0)
ax2b = ax2.twinx(); ax2b.spines["top"].set_visible(False)
l1, = ax2.plot(xs, share, marker="o", ms=4, lw=1.3, color=OK["purple"], label="synthetic purchases (%)")
l2, = ax2b.plot(xs, conf, marker="^", ms=4, lw=1.2, color=OK["green"], label="confidence (right)")
l3, = ax2b.plot(xs, eces, marker="v", ms=4, lw=1.2, ls="--", color=OK["orange"], label="ECE (right)")
ax2.set_ylim(0, 100); ax2b.set_ylim(0.15, 0.95)
ax2.set_xticks(xs); ax2.set_xticklabels(["0", "0.25", "0.5", "0.75"])
ax2.set_xlabel(r"contamination level $\varepsilon$")
ax2.set_ylabel("synthetic purchases (%)", color=OK["purple"])
ax2b.set_ylabel("confidence / ECE")
ax2.set_title("(b) Purchases shift, confidence inflates")
ax2.text(0.55, 57, "purchases", fontsize=6.5, color=OK["purple"])
ax2b.text(0.38, 0.925, "confidence", fontsize=6.5, color=OK["green"])
ax2b.text(0.43, 0.175, "ECE", fontsize=6.5, color=OK["orange"])
plt.tight_layout(); plt.savefig("paper/figures/dose_response.pdf", bbox_inches="tight"); plt.close()

# ---------------- family ----------------
fams = ["geo", "clone", "reviews"]
labels = ["search-optimized\n(geo)", "specification clone", "review-inflated"]
colors = [OK["sky"], OK["red"], OK["orange"]]
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(3.4, 4.0))
for i, (f, lab, c) in enumerate(zip(fams, labels, colors)):
    d0 = B["B1_families"][f]["eps0"]; d75 = B["B1_families"][f]["eps75"]
    for ax, key in ((ax1, "success"), (ax2, "regret")):
        v0, v75 = d0[key], d75[key]
        ax.bar(i - 0.17, v0, width=0.34, color=OK["grey"],
               label=("$\\varepsilon{=}0$ (clean)" if i == 0 else None))
        ax.bar(i + 0.17, v75, width=0.34, color=c,
               label=("$\\varepsilon{=}0.75$" if i == 0 else None))
        ax.text(i - 0.17, v0 + 0.012, f"{v0:.2f}", ha="center", fontsize=6.5, color=OK["grey"])
        ax.text(i + 0.17, v75 + 0.012, f"{v75:.2f}", ha="center", fontsize=6.8)
ax1.set_xticks(range(3)); ax1.set_xticklabels([])
ax1.set_ylabel("task success"); ax1.set_title("(a) Success per family")
ax1.legend(frameon=False, loc="upper right")
ax2.set_xticks(range(3)); ax2.set_xticklabels(labels, fontsize=6.6)
ax2.set_ylabel("regret"); ax2.set_title("(b) Regret per family")
ax2.legend(frameon=False, loc="upper left")
plt.tight_layout(); plt.savefig("paper/figures/family.pdf", bbox_inches="tight"); plt.close()

# ---------------- defenses ----------------
cells = B["B3_cells"]
order = [("none", "none @0.75"), ("random", "random drop"), ("prompt", "prompt"),
         ("detector-text", "text (ppl)"), ("provenance", "provenance"),
         ("detector-struct", "struct"), ("oracle", "oracle")]
vals = [cells["none"]["regret"], cells["random"]["regret"], cells["prompt"]["regret"],
        cells["text"]["regret"], cells["provenance"]["regret"], cells["struct"]["regret"],
        cells["oracle"]["regret"]]
names = [n for _, n in order]
cols = [OK["grey"], OK["grey"], OK["yellow"], OK["red"], OK["blue"], OK["green"], OK["purple"]]
base0 = 0.338  # paired clean baseline (P2 gate run, tab:defense)
fig, ax = plt.subplots(figsize=(3.4, 2.4))
bars = ax.bar(range(7), vals, color=cols, width=0.62)
ax.axhline(base0, color=OK["grey"], ls=":", lw=1)
ax.text(6.4, base0 + 0.008, "clean baseline 0.338", fontsize=6.3, ha="right")
for i, v in enumerate(vals):
    ax.text(i, v + 0.012, f"{v:.2f}", ha="center", fontsize=6.8)
ax.set_xticks(range(7)); ax.set_xticklabels(names, rotation=28, ha="right", fontsize=6.6)
ax.set_ylabel(r"regret at $\varepsilon=0.75$")
plt.tight_layout(); plt.savefig("paper/figures/defenses.pdf", bbox_inches="tight"); plt.close()

# ---------------- defense stress tests (new, 3 panels) ----------------
fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(7.0, 2.3))
# (a) lambda sweep
lams, regs = [], []
for lam in ["0.5", "1.0", "2.0", "4.0", "6.0", "8.0"]:
    rows = [r for r in csv.DictReader(open(R + f"p4h_ppr_l{lam}_sweep.csv"))
            if r["task_id"] and r.get("reward") and float(r["eps"]) == 0.75]
    lams.append(float(lam)); regs.append(mean([1 - float(r["reward"]) for r in rows]))
ax1.plot(lams, regs, marker="o", ms=4, lw=1.3, color=OK["blue"])
ax1.axhline(0.398, color=OK["grey"], ls=":", lw=1); ax1.text(4.1, 0.407, "no defense 0.398", fontsize=6.3)
ax1.axhline(0.329, color=OK["green"], ls="--", lw=1); ax1.text(3.0, 0.312, "hard ordering 0.329", fontsize=6.3)
ax1.annotate("recovers only\nat $\\lambda{=}8$", (8, 0.335), xytext=(4.6, 0.415), fontsize=6.5,
             arrowprops=dict(arrowstyle="->", lw=0.7))
ax1.set_xlabel(r"provenance bonus weight $\lambda$"); ax1.set_ylabel("regret")
ax1.set_title("(a) Soft bonus fails until $\\lambda{=}8$")
# (b) spoof envelope
rates = [25, 35, 50, 65]
sreg = []
for s in rates:
    rows = [r for r in csv.DictReader(open(R + f"p4i_spoof{s}_sweep.csv"))
            if r["task_id"] and r.get("reward") and float(r["eps"]) == 0.75]
    sreg.append(mean([1 - float(r["reward"]) for r in rows]))
ax2.plot(rates, sreg, marker="s", ms=4, lw=1.3, color=OK["orange"])
ax2.axhline(0.329, color=OK["grey"], ls=":", lw=1); ax2.text(26, 0.336, "no forgery 0.329", fontsize=6.3, ha="left")
ax2.set_xlabel("badge forgery rate on synthetics (%)"); ax2.set_ylabel("regret")
ax2.set_title("(b) Recovery flat through 65% forgery")
# (c) stealth pool
def arm(fn):
    rows = [r for r in csv.DictReader(open(R + fn))
            if r["task_id"] and r.get("reward") and float(r["eps"]) == 0.75]
    return mean([1 - float(r["reward"]) for r in rows])
sn, ss, sp = arm("p4m_none_st_sweep.csv"), arm("p4m_struct_st_sweep.csv"), arm("p4m_prov_st_sweep.csv")
on, os_, op = 0.398, 0.250, 0.329  # original pool, same 40 tasks (P2 gate run + p4c arms)
w = 0.34
ax3.bar([0 - w/2, 1 - w/2, 2 - w/2], [on, os_, op], width=w, color=OK["grey"], label="original pool")
ax3.bar([0 + w/2, 1 + w/2, 2 + w/2], [sn, ss, sp], width=w, color=OK["blue"], label="stealth pool")
ax3.set_xticks([0, 1, 2]); ax3.set_xticklabels(["no defense", "struct", "provenance"], fontsize=6.8)
ax3.set_ylabel("regret"); ax3.set_title("(c) Stealth pool: defenses intact")
ax3.legend(frameon=False, fontsize=6.2, loc="upper right")
plt.tight_layout(); plt.savefig("paper/figures/defense_stress.pdf", bbox_inches="tight"); plt.close()
print("figures regenerated")

import csv, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OK = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
      "red": "#D55E00", "purple": "#CC79A7", "sky": "#56B4E9", "grey": "#7F7F7F"}
plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.4,
    "figure.dpi": 150,
})
R = "../repo_clone/results_csv/"

def wilson(p, n):
    z = 1.96; den = 1 + z*z/n; ctr = (p + z*z/(2*n)) / den
    hw = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return ctr - hw, ctr + hw

def sig(fn):
    rows = [r for r in csv.DictReader(open(R + fn + ".csv")) if r["family"] == "clone"]
    s = sum(int(r["is_synthetic"]) for r in rows); n = len(rows)
    lo, hi = wilson(s / n, n)
    return s / n, lo, hi

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.6))

# (a) channel decomposition
names = ["original\n(cut price,\ninflated ratings)", "price\nparity", "rating\nparity", "full\nparity", "gloss\nbaseline"]
data = [sig("p1_forced_choice"), sig("p1_probeB"), sig("p1_probeC"), sig("p1_probeBC"), (0.351, 0.263, 0.450)]
cols = [OK["red"], OK["blue"], OK["sky"], OK["green"], OK["grey"]]
for i, ((v, lo, hi), c) in enumerate(zip(data, cols)):
    ax1.bar(i, v, yerr=[[v - lo], [hi - v]], color=c, width=0.62,
            error_kw=dict(capsize=3, lw=0.9))
    ax1.text(i, hi + 0.025, f"{v:.2f}", ha="center", fontsize=7.5)
ax1.axhline(0.5, color=OK["grey"], ls=":", lw=1)
ax1.set_xlim(-0.55, 4.95)
ax1.text(4.55, 0.507, "chance", fontsize=6.5, color=OK["grey"])
ax1.annotate("each channel\n$\\approx$14 pp", xy=(1, 0.39), xytext=(1.55, 0.62),
             fontsize=6.8, arrowprops=dict(arrowstyle="->", lw=0.7))
ax1.annotate("below gloss:\nmimicry itself is\na liability", xy=(3, 0.255), xytext=(2.62, 0.60),
             fontsize=6.8, arrowprops=dict(arrowstyle="->", lw=0.7))
ax1.set_xticks(range(5)); ax1.set_xticklabels(names, fontsize=6.4)
ax1.set_ylabel(r"clone win-rate $\sigma$")
ax1.set_title("(a) Channel decomposition")
ax1.set_ylim(0, 0.82)

# (b) pricing threshold
fs = [("1.00", "p1_probeB"), ("0.90", "p1_price90"), ("0.80", "p1_price80"), ("0.70", "p1_price70")]
pts = sorted(((int(round((1 - float(f)) * 100)),) + sig(fn) for f, fn in fs), key=lambda t: t[0])
xs = [p[0] for p in pts]; vs = [p[1] for p in pts]
los = [p[2] for p in pts]; his = [p[3] for p in pts]
ax2.axhspan(0.5, 0.75, color=OK["red"], alpha=0.06)
ax2.axhline(0.5, color=OK["grey"], ls=":", lw=1)
ax2.errorbar(xs, vs, yerr=[np.array(vs) - los, np.array(his) - np.array(vs)],
             marker="o", ms=4.5, lw=1.3, color=OK["blue"], capsize=3)
ax2.axhline(0.523, color=OK["orange"], ls="--", lw=0.9)
ax2.text(21.5, 0.472, "mixed pool 0.523", fontsize=6.3, color=OK["orange"], ha="left")
ax2.annotate("majority rejects\nthe clone", (0, 0.386), xytext=(1, 0.44), fontsize=6.8,
             arrowprops=dict(arrowstyle="->", lw=0.7))
ax2.annotate("a 10% discount flips\nthe majority ($p{=}0.003$)", (10, 0.591), xytext=(13, 0.64),
             fontsize=6.8, arrowprops=dict(arrowstyle="->", lw=0.7))
ax2.text(1.0, 0.725, "majority buys clone", fontsize=6.4, color=OK["red"], ha="left")
ax2.set_xlabel("clone discount vs. gold price")
ax2.set_ylabel(r"clone win-rate $\sigma$")
ax2.set_title("(b) Pricing threshold law")
ax2.set_xticks(xs); ax2.set_xticklabels([f"{x}%" for x in xs])
ax2.set_ylim(0.3, 0.75)

plt.tight_layout()
plt.savefig("figures/mechanism.pdf", bbox_inches="tight")
print("mechanism.pdf regenerated")

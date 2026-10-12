import csv, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def wilson(p, n):
    z = 1.96; den = 1 + z*z/n; ctr = (p + z*z/(2*n)) / den
    hw = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return ctr - hw, ctr + hw

def sig(fn):
    rows = [r for r in csv.DictReader(open(f"../repo_clone/results_csv/{fn}.csv")) if r["family"] == "clone"]
    s = sum(int(r["is_synthetic"]) for r in rows); n = len(rows)
    lo, hi = wilson(s/n, n)
    return s/n, lo, hi

OK = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9"]
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.6))

# (a) channel decomposition
names = ["original\n(price -5~25%,\ninflated ratings)", "price parity", "rating parity", "both\n(full parity)", "gloss\nbaseline"]
vals = [sig("p1_forced_choice"), sig("p1_probeB"), sig("p1_probeC"), sig("p1_probeBC"), (0.351, 0.263, 0.450)]
for i, (name, (v, lo, hi)) in enumerate(zip(names, vals)):
    ax1.bar(i, v, yerr=[[v-lo], [hi-v]], color=OK[i % len(OK)], width=0.62,
            error_kw=dict(capsize=3, lw=0.9))
    ax1.text(i, hi + 0.03, f"{v:.2f}", ha="center", fontsize=8)
ax1.axhline(0.5, color="gray", ls=":", lw=1)
ax1.set_xticks(range(5)); ax1.set_xticklabels(names, fontsize=6.3)
ax1.set_ylabel(r"clone win-rate $\sigma$", fontsize=8)
ax1.set_title("(a) Channel decomposition (300 duels each)", fontsize=8.5)
ax1.set_ylim(0, 0.8); ax1.tick_params(labelsize=7.5)

# (b) discount threshold
fs = ["1.00", "0.90", "0.80", "0.70"]
fnames = ["p1_probeB", "p1_price90", "p1_price80", "p1_price70"]
xs, vs, los, his = [], [], [], []
for f, fn in zip(fs, fnames):
    v, lo, hi = sig(fn)
    xs.append(int(round((1 - float(f)) * 100))); vs.append(v); los.append(lo); his.append(hi)
order = sorted(range(4), key=lambda i: xs[i])
xs = [xs[i] for i in order]; vs = [vs[i] for i in order]; los = [los[i] for i in order]; his = [his[i] for i in order]
ax2.errorbar(xs, vs, yerr=[[v-l for v, l in zip(vs, los)], [h-v for v, h in zip(vs, his)]],
             marker="o", color=OK[0], capsize=3, lw=1.2, ms=4)
ax2.axhline(0.5, color="gray", ls=":", lw=1)
ax2.axhline(0.523, color=OK[1], ls="--", lw=0.9)
ax2.text(28, 0.523 + 0.015, "mixed-discount pool (0.523)", fontsize=6.5, color=OK[1])
ax2.annotate("majority rejects\nclone", (0, 0.386), xytext=(2, 0.44), fontsize=6.5,
             arrowprops=dict(arrowstyle="->", lw=0.7))
ax2.annotate("majority buys clone\n(-10% suffices)", (10, 0.591), xytext=(14, 0.63), fontsize=6.5,
             arrowprops=dict(arrowstyle="->", lw=0.7))
ax2.set_xlabel("clone discount vs. gold price (%)", fontsize=8)
ax2.set_ylabel(r"clone win-rate $\sigma$", fontsize=8)
ax2.set_title("(b) Pricing threshold law", fontsize=8.5)
ax2.set_xticks(xs); ax2.set_xticklabels([f"{x}%" for x in xs], fontsize=7.5)
ax2.set_ylim(0.3, 0.75); ax2.tick_params(labelsize=7.5)

for ax in (ax1, ax2):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
plt.tight_layout()
plt.savefig("figures/mechanism.pdf", bbox_inches="tight")
print("saved figures/mechanism.pdf")

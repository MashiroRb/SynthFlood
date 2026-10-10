"""Generate all paper figures from final CSVs. Okabe-Ito palette, CIs by
cluster bootstrap over tasks."""
import json
import os
import random
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synthflood.config import RESULT_DIR, FIG_DIR  # noqa: E402

OI = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00",
      "#F0E442"]


def rows(path):
    import csv
    with open(path) as f:
        return [r for r in csv.DictReader(f)
                if not r["chosen_kind"].startswith(("ERROR", "SKIPPED"))]


def by_eps(rs):
    d = {}
    for r in rs:
        d.setdefault(float(r["eps"]), []).append(r)
    return {k: v for k, v in sorted(d.items())}


def boot_ci(vals, B=2000, seed=0):
    rng = random.Random(seed)
    n = len(vals)
    if n == 0:
        return (float("nan"), float("nan"))
    ms = sorted(sum(rng.choices(vals, k=n)) / n for _ in range(B))
    return ms[int(0.025 * B)], ms[int(0.975 * B)]


def agg(rs):
    n = len(rs)
    sfull = [1.0 if r["success_full"] == "1" else 0.0 for r in rs]
    s80 = [1.0 if r["success80"] == "1" else 0.0 for r in rs]
    reg = [1.0 - float(r["reward"]) for r in rs]
    sy = [1.0 if r["chosen_is_synthetic"] == "1" else 0.0 for r in rs]
    conf = [float(r["confidence"]) for r in rs
            if r["confidence"] not in ("", "None")]
    out = {"n": n,
           "sfull": sum(sfull) / n, "sfull_ci": boot_ci(sfull),
           "s80": sum(s80) / n,
           "regret": sum(reg) / n, "regret_ci": boot_ci(reg),
           "synth_share": sum(sy) / n, "synth_ci": boot_ci(sy),
           "conf": (sum(conf) / len(conf)) if conf else None,
           "conf_ci": boot_ci(conf) if conf else (None, None)}
    # ECE over 5 equal-width bins (on rows with a confidence value)
    if conf:
        pairs = []
        for r in rs:
            c = r["confidence"]
            if c in ("", "None"):
                continue
            pairs.append((float(c), 1.0 if r["success_full"] == "1" else 0.0))
        ece = 0.0
        for b in range(5):
            lo, hi = b * 0.2, (b + 1) * 0.2
            grp = [(c, s) for c, s in pairs if lo <= c < hi or
                   (b == 4 and c >= 1.0)]
            if grp:
                mc = sum(c for c, _ in grp) / len(grp)
                ms = sum(s for _, s in grp) / len(grp)
                ece += len(grp) / len(pairs) * abs(ms - mc)
        out["ece"] = ece
    return out


def fig_dose():
    rs = by_eps(rows(os.path.join(RESULT_DIR, "p4a_sweep.csv")))
    eps = sorted(rs)
    A = [agg(rs[e]) for e in eps]
    panels = [("sfull", "Task success", "sfull_ci"),
              ("regret", "Regret (1 - reward)", "regret_ci"),
              ("synth_share", "Synthetic purchased", "synth_ci"),
              ("conf", "Mean confidence", "conf_ci")]
    fig, axes = plt.subplots(1, 4, figsize=(11, 2.6))
    for ax, (key, title, cikey) in zip(axes, panels):
        ys = [a[key] for a in A]
        lo = [y - a[cikey][0] for y, a in zip(ys, A)]
        hi = [a[cikey][1] - y for y, a in zip(ys, A)]
        ax.errorbar(eps, ys, yerr=[lo, hi], marker="o", color=OI[0],
                    capsize=3, lw=1.6)
        ax.set_xlabel(r"contamination $\varepsilon$")
        ax.set_title(title, fontsize=10)
        ax.set_ylim(0, 1)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "dose_response.pdf"))
    plt.close(fig)


def fig_family():
    fams = ["geo", "clone", "reviews"]
    base, high = {}, {}
    for f in fams:
        rs = by_eps(rows(os.path.join(
            RESULT_DIR, f"p4b_{f}_sweep.csv")))
        base[f] = agg(rs[0.0])
        high[f] = agg(rs[0.75])
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.6))
    for ax, key, cikey, title in (
            (axes[0], "sfull", "sfull_ci", "Success"),
            (axes[1], "regret", "regret_ci", "Regret")):
        xs = range(len(fams))
        v0 = [base[f][key] for f in fams]
        v1 = [high[f][key] for f in fams]
        e0 = [[y - base[f][cikey][0] for y, f in zip(v0, fams)],
              [base[f][cikey][1] - y for y, f in zip(v0, fams)]]
        e1 = [[y - high[f][cikey][0] for y, f in zip(v1, fams)],
              [high[f][cikey][1] - y for y, f in zip(v1, fams)]]
        ax.errorbar([x - 0.08 for x in xs], v0, yerr=e0, fmt="o",
                    color=OI[2], label=r"$\varepsilon=0$", capsize=3)
        ax.errorbar([x + 0.08 for x in xs], v1, yerr=e1, fmt="o",
                    color=OI[1], label=r"$\varepsilon=0.75$", capsize=3)
        ax.set_xticks(list(xs))
        ax.set_xticklabels(fams)
        ax.set_title(title, fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "family.pdf"))
    plt.close(fig)


def fig_defense():
    defs = [("none", "none"), ("random", "random"), ("prompt", "prompt"),
            ("detector_struct", "det-struct"),
            ("detector_text", "det-text"), ("provenance", "provenance"),
            ("oracle", "oracle")]
    A = {}
    for name, label in defs:
        p = os.path.join(RESULT_DIR, f"p4c_{name}_sweep.csv")
        if not os.path.exists(p):
            continue
        rs = by_eps(rows(p))
        A[label] = (agg(rs[0.0]), agg(rs[0.75]))
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    labels = list(A)
    v0 = [A[l][0]["regret"] for l in labels]
    v1 = [A[l][1]["regret"] for l in labels]
    xs = range(len(labels))
    ax.bar([x - 0.2 for x in xs], v0, 0.36, color=OI[2],
           label=r"$\varepsilon=0$")
    ax.bar([x + 0.2 for x in xs], v1, 0.36, color=OI[1],
           label=r"$\varepsilon=0.75$")
    ax.set_xticks(list(xs))
    ax.set_xticklabels(labels, rotation=28, ha="right", fontsize=8)
    ax.set_ylabel("Regret")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "defenses.pdf"))
    plt.close(fig)


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    which = sys.argv[1:] or ["dose", "family", "defense"]
    for w in which:
        globals()[f"fig_{w}"]()
        print("made", w)
    print(json.dumps({"fig_dir": FIG_DIR}))


if __name__ == "__main__":
    main()

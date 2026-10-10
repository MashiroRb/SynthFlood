"""Analysis + figures for SynthFlood (matplotlib, colorblind-safe)."""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .config import RESULT_DIR, FIG_DIR

# Okabe-Ito palette
OI = {"gold": "#0072B2", "synth": "#D55E00", "geo": "#E69F00",
      "clone": "#CC79A7", "reviews": "#009E73", "none": "#56B4E9",
      "gray": "#999999"}


def load_sweep(path):
    return pd.read_csv(path)


def dose_response(csv_path, out_pdf, metric="success_full"):
    """success (or regret) vs eps, main backbone."""
    df = load_sweep(csv_path)
    agg = df.groupby("eps")[metric].agg(["mean", "count",
                                         lambda s: s.std() / max(len(s), 1) ** .5])
    agg.columns = ["mean", "n", "se"]
    fig, ax = plt.subplots(figsize=(4.2, 2.9))
    ax.errorbar(agg.index, agg["mean"], yerr=1.96 * agg["se"], marker="o",
                color=OI["synth"], capsize=3, lw=1.6, ms=4)
    ax.set_xlabel(r"contamination level $\varepsilon$")
    ax.set_ylabel("task success rate" if metric.startswith("success")
                  else "mean regret")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=.3)
    fig.tight_layout()
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(out_pdf)
    return agg


def family_breakdown(csv_path, out_pdf):
    """Dose-response per contamination family."""
    df = load_sweep(csv_path)
    fig, ax = plt.subplots(figsize=(4.2, 2.9))
    for fam, color in [("geo", OI["geo"]), ("clone", OI["clone"]),
                       ("reviews", OI["reviews"])]:
        sub = df[df.family == fam].groupby("eps")["success_full"].agg(
            ["mean", "count", lambda s: s.std() / max(len(s), 1) ** .5])
        sub.columns = ["mean", "n", "se"]
        ax.errorbar(sub.index, sub["mean"], yerr=1.96 * sub["se"], marker="o",
                    ms=4, lw=1.6, capsize=3, color=color, label=fam)
    ax.set_xlabel(r"contamination level $\varepsilon$")
    ax.set_ylabel("task success rate")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=.3)
    fig.tight_layout()
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(out_pdf)


def defense_recovery(csv_path, out_pdf, eps_ref=None):
    """Regret by defense at a fixed eps (bars), with none = baseline."""
    df = load_sweep(csv_path)
    if eps_ref is not None:
        df = df[df.eps == eps_ref]
    agg = df.groupby("defense")["regret"].agg(["mean", "count",
                                               lambda s: s.std() / max(len(s), 1) ** .5])
    agg.columns = ["mean", "n", "se"]
    agg = agg.sort_values("mean")
    fig, ax = plt.subplots(figsize=(4.6, 2.9))
    colors = [OI["gray"] if i == "none" else OI["none"] for i in agg.index]
    ax.bar(agg.index, agg["mean"], yerr=1.96 * agg["se"], capsize=3,
           color=colors, width=.62)
    ax.set_ylabel("mean regret")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(alpha=.3, axis="y")
    fig.tight_layout()
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(out_pdf)
    return agg


def calibration_by_eps(csv_path, out_pdf):
    """ECE vs eps: does contamination inflate (mis)confidence?"""
    df = load_sweep(csv_path)
    agg = df.groupby("eps")["ece"].mean()
    fig, ax = plt.subplots(figsize=(4.2, 2.9))
    ax.plot(agg.index, agg.values, marker="s", color=OI["clone"], lw=1.6)
    ax.set_xlabel(r"contamination level $\varepsilon$")
    ax.set_ylabel("expected calibration error")
    ax.grid(alpha=.3)
    fig.tight_layout()
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(out_pdf)


def summarize(csv_path):
    """Key numbers table for the log/paper."""
    df = load_sweep(csv_path)
    out = {}
    for eps, sub in df.groupby("eps"):
        out[round(eps, 2)] = {
            "n": len(sub),
            "success_full": round(sub.success_full.mean(), 4),
            "success80": round(sub.success80.mean(), 4),
            "regret": round(sub.regret.mean(), 4),
            "ece": round(sub.ece.mean(), 4) if "ece" in sub else None,
            "tok_out_mean": round(sub.tok_out.mean(), 1) if "tok_out" in sub else None,
        }
    return out


if __name__ == "__main__":
    import sys
    print(json.dumps(summarize(sys.argv[1]), indent=1))

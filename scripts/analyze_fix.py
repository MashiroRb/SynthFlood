"""CPU analyses B1/B2/B3/B8 for the revision wave (no GPU needed).

B1: per-family paired McNemar + paired regret delta with bootstrap CI.
B2: 95% bootstrap CIs for headline (stage, eps) cells.
B3: pairwise paired comparisons between defenses at eps=0.75 (cseed=1).
B8: erosion coefficient kappa = paired d E[regret] / d eps per backbone.

Writes results_csv/b_analysis.json and prints a readable summary.
"""
import itertools
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.environ.get(
    "SYNTHFLOOD_RES",
    os.path.join(os.path.dirname(HERE), "results_csv"))
RNG = np.random.default_rng(2027)
B = 10000


def load(name):
    df = pd.read_csv(os.path.join(RES, name))
    df = df[df.get("chosen_kind") != "SKIPPED:no_synth"].copy()
    if "task_id" in df:
        df["task_id"] = df["task_id"].astype(int)
    df["eps"] = df["eps"].astype(float)
    if "reward" in df:
        df["regret"] = 1.0 - df["reward"]
    return df


def boot_ci(x, stat=np.mean):
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return (float("nan"), float("nan"))
    idx = RNG.integers(0, len(x), size=(B, len(x)))
    s = stat(x[idx], axis=1) if len(x) else np.array([np.nan])
    lo, hi = np.percentile(s, [2.5, 97.5])
    return (round(float(lo), 4), round(float(hi), 4))


def paired_delta(a, b, col):
    """Paired on task_id; returns mean delta (a-b), bootstrap CI, sign p."""
    m = a[["task_id", col]].merge(b[["task_id", col]], on="task_id",
                                  suffixes=("_a", "_b"))
    d = (m[f"{col}_a"] - m[f"{col}_b"]).values
    if len(d) == 0:
        return None
    lo, hi = boot_ci(d)
    nz = d[d != 0]
    pos = int((nz > 0).sum())
    neg = int((nz < 0).sum())
    p = stats.binomtest(min(pos, neg), pos + neg, 0.5).pvalue if pos + neg else 1.0
    return {"n": int(len(d)), "mean_delta": round(float(d.mean()), 4),
            "ci95": [lo, hi], "sign_p": round(float(p), 4),
            "pos": pos, "neg": neg}


def mcnemar(a, b, col="success_full"):
    """Exact McNemar on paired success between arms a (eps high) and b (eps 0)."""
    m = a[["task_id", col]].merge(b[["task_id", col]], on="task_id",
                                  suffixes=("_a", "_b"))
    s01 = int(((m[f"{col}_a"] == 1) & (m[f"{col}_b"] == 0)).sum())
    s10 = int(((m[f"{col}_a"] == 0) & (m[f"{col}_b"] == 1)).sum())
    n = s01 + s10
    p = stats.binomtest(min(s01, s10), n, 0.5).pvalue if n else 1.0
    return {"n01_gain": s01, "n10_loss": s10, "exact_p": round(float(p), 5)}


def cell(df, eps, defense=None, family=None, cseed=None):
    q = df[df["eps"] == eps]
    if defense is not None:
        q = q[q["defense"] == defense]
    if family is not None:
        q = q[q["family"] == family]
    if cseed is not None:
        q = q[q["cseed"] == cseed]
    return q


def summarize(rows, label):
    r = np.asarray(rows["reward"], dtype=float)
    s = np.asarray(rows["success_full"], dtype=int)
    c = np.asarray(rows["confidence"], dtype=float)
    return {"label": label, "n": int(len(r)),
            "success": round(float(s.mean()), 4),
            "success_ci": boot_ci(s),
            "regret": round(float((1 - r).mean()), 4),
            "regret_ci": boot_ci(1 - r),
            "conf": round(float(np.nanmean(c)), 4)}


def main():
    out = {}

    # ---------- B1: per-family paired erosion (cseed=1, mix vs family) ----------
    p4a = load("p4a_sweep.csv")
    fams = {}
    for fam, fn in [("clone", "p4b_clone_sweep.csv"),
                    ("geo", "p4b_geo_sweep.csv"),
                    ("reviews", "p4b_reviews_sweep.csv")]:
        f = load(fn)
        hi, lo = cell(f, 0.75), cell(f, 0.0)
        base = cell(p4a, 0.0)
        fams[fam] = {
            "eps0": summarize(lo, f"{fam}@0"),
            "eps75": summarize(hi, f"{fam}@0.75"),
            "paired_regret": paired_delta(hi, lo, "regret"),
            "mcnemar_success": mcnemar(hi, lo),
        }
    hi_mix, lo_mix = cell(p4a, 0.75), cell(p4a, 0.0)
    fams["mix"] = {
        "eps0": summarize(lo_mix, "mix@0"),
        "eps75": summarize(hi_mix, "mix@0.75"),
        "paired_regret": paired_delta(hi_mix, lo_mix, "regret"),
        "mcnemar_success": mcnemar(hi_mix, lo_mix),
    }
    out["B1_families"] = fams

    # ---------- B2: headline CIs across all cells ----------
    head = {}
    for stage, fn in [("p4a_Qwen7B", "p4a_sweep.csv"),
                      ("p4d_Llama8B", "p4d_llama_sweep.csv"),
                      ("p4f_3b", "p4f_3b_sweep.csv"),
                      ("p4f_1b5", "p4f_1b5_sweep.csv")]:
        df = load(fn)
        for eps in sorted(df["eps"].unique()):
            head[f"{stage}@{eps}"] = summarize(cell(df, eps), stage)
    out["B2_headline_ci"] = head

    # ---------- B3: defense pairwise at eps=0.75, cseed=1 ----------
    defs = {"none": cell(p4a, 0.75),
            "prompt": load("p4c_prompt_sweep.csv"),
            "provenance": load("p4c_provenance_sweep.csv"),
            "struct": load("p4c_detector_struct_sweep.csv"),
            "text": load("p4c_detector_text_sweep.csv"),
            "random": load("p4c_random_sweep.csv"),
            "oracle": load("p4c_oracle_sweep.csv")}
    defs = {k: cell(v, 0.75) if k != "none" else v[v["cseed"] == 1]
            for k, v in defs.items()}
    pairs = {}
    for (a, b) in itertools.combinations(defs, 2):
        if len(defs[a]) == 0 or len(defs[b]) == 0:
            continue
        pairs[f"{a}_vs_{b}"] = paired_delta(defs[a], defs[b], "regret")
        pairs[f"{a}_vs_{b}"]["mcnemar"] = mcnemar(defs[a], defs[b])
    out["B3_defense_pairs_eps75"] = {k: v for k, v in pairs.items()}
    out["B3_cells"] = {k: summarize(v, k) for k, v in defs.items() if len(v)}

    # ---------- B8: erosion coefficient kappa per backbone ----------
    kappa = {}
    for stage, fn in [("Qwen2.5-7B", "p4a_sweep.csv"),
                      ("Llama-3.1-8B", "p4d_llama_sweep.csv"),
                      ("Qwen2.5-3B", "p4f_3b_sweep.csv"),
                      ("Qwen2.5-1.5B", "p4f_1b5_sweep.csv")]:
        df = load(fn)
        hi, lo = cell(df, 0.75), cell(df, 0.0)
        if not len(hi) or not len(lo):
            continue
        m = hi[["task_id", "regret"]].merge(lo[["task_id", "regret"]],
                                            on="task_id",
                                            suffixes=("_hi", "_lo"))
        d = (m["regret_hi"] - m["regret_lo"]).values / 0.75
        kappa[stage] = {"n": int(len(d)),
                        "kappa_regret": round(float(d.mean()), 4),
                        "kappa_ci": boot_ci(d),
                        "success_drop": round(
                            float(cell(df, 0.0)["success_full"].mean()
                                  - cell(df, 0.75)["success_full"].mean()), 4)}
    out["B8_erosion_kappa"] = kappa

    with open(os.path.join(RES, "b_analysis.json"), "w") as f:
        json.dump(out, f, indent=1)

    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

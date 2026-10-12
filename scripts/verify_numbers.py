"""C6: verify every headline number in the paper against the result CSVs.

Builds a ledger of key statistics from results_csv/*.csv, then scans
paper/sections/*.tex for each value and reports FOUND / STALE / MISSING.
Run from the repo root: python3 scripts/verify_numbers.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "results_csv")
TEX = os.path.join(ROOT, "paper", "sections")


def rows(fn):
    import csv
    with open(os.path.join(RES, fn)) as f:
        return [r for r in csv.DictReader(f)
                if r.get("chosen_kind") != "SKIPPED:no_synth"]


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def ledger():
    L = {}
    # main dose-response (p4a mix cseed=1)
    a = [r for r in rows("p4a_sweep.csv") if r["cseed"] == "1"]
    for e in ["0.0", "0.25", "0.5", "0.75"]:
        c = [r for r in a if float(r["eps"]) == float(e)]
        L[f"mix@{e} success"] = round(mean([int(r["success_full"]) for r in c]), 3)
        L[f"mix@{e} regret"] = round(mean([1 - float(r["reward"]) for r in c]), 3)
        L[f"mix@{e} conf"] = round(mean([float(r["confidence"]) for r in c]), 3)
        L[f"mix@{e} n"] = len(c)
    # P1 forced choice per family
    p1 = rows("p1_forced_choice.csv")
    for fam in ["clone", "geo", "reviews"]:
        c = [r for r in p1 if r["family"] == fam]
        L[f"P1 sigma {fam}"] = round(mean([int(r["is_synthetic"]) for r in c]), 3)
    L["P1 sigma all"] = round(mean([int(r["is_synthetic"]) for r in p1]), 3)
    # defenses @0.75
    for name, fn in [("provenance", "p4c_provenance_sweep.csv"),
                     ("struct", "p4c_detector_struct_sweep.csv"),
                     ("prompt", "p4c_prompt_sweep.csv"),
                     ("random", "p4c_random_sweep.csv"),
                     ("text", "p4c_detector_text_sweep.csv"),
                     ("oracle", "p4c_oracle_sweep.csv")]:
        c = [r for r in rows(fn) if float(r["eps"]) == 0.75]
        L[f"defense {name} regret"] = round(mean([1 - float(r["reward"]) for r in c]), 3)
        L[f"defense {name} success"] = round(mean([int(r["success_full"]) for r in c]), 3)
    # wave-1 new arms
    for name, fn in [("sham", "p4g_sham_sweep.csv"),
                     ("spoof25", "p4i_spoof25_sweep.csv"),
                     ("spoof50", "p4i_spoof50_sweep.csv"),
                     ("reviewtrust", "p4k_revtrust_sweep.csv"),
                     ("ppr_l0.5", "p4h_ppr_l0.5_sweep.csv"),
                     ("ppr_l1.0", "p4h_ppr_l1.0_sweep.csv"),
                     ("ppr_l2.0", "p4h_ppr_l2.0_sweep.csv"),
                     ("prov_s2", "p4j_prov_s2_sweep.csv"),
                     ("struct_s2", "p4j_struct_s2_sweep.csv")]:
        try:
            rr = rows(fn)
        except FileNotFoundError:
            continue
        for e in sorted({float(r["eps"]) for r in rr}):
            c = [r for r in rr if float(r["eps"]) == e]
            L[f"{name}@{e} regret"] = round(mean([1 - float(r["reward"]) for r in c]), 3)
            L[f"{name}@{e} success"] = round(mean([int(r["success_full"]) for r in c]), 3)
    # probe B
    try:
        b = rows("p1_probeB.csv")
        cb = [r for r in b if r["family"] == "clone"]
        L["probeB sigma clone"] = round(mean([int(r["is_synthetic"]) for r in cb]), 3)
    except FileNotFoundError:
        pass
    return L


def scan_tex(L):
    text = ""
    for fn in sorted(os.listdir(TEX)):
        if fn.endswith(".tex"):
            text += open(os.path.join(TEX, fn)).read()
    found, stale, missing = [], [], []
    for k, v in L.items():
        s = f"{v:.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
        s = f"{v:.3f}" if isinstance(v, float) else str(v)
        if s in text:
            found.append((k, s))
        else:
            alt = f"{v:.2f}"
            if alt in text:
                found.append((k, alt))
            else:
                missing.append((k, s))
    return found, missing


def main():
    L = ledger()
    found, missing = scan_tex(L)
    print(json.dumps(L, indent=1, ensure_ascii=False))
    print("\n=== IN PAPER ===")
    for k, s in found:
        print(f"  {k} = {s}")
    print("=== NOT IN PAPER (new numbers to add / stale text to update) ===")
    for k, s in missing:
        print(f"  {k} = {s}")
    with open(os.path.join(RES, "numbers_ledger.json"), "w") as f:
        json.dump(L, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()

"""RA2: ambient-scale dose-response on a 50-slot results page.

Reuses run_sweep.run_cell with N_CANDIDATES=50. Absolute contaminated
counts k in {0,3,7,11} mapped to eps=k/49 (build_task places exactly
int(eps*(N-1)) synthetics). Primary comparison: k=7 at N=50 vs the
published N=10 dose point (same absolute count, 5x surface dilution).
"""
import argparse, json, os, sys, threading

sys.path.insert(0, os.path.expanduser("~/synthflood"))
sys.path.insert(0, os.path.expanduser("~/webshop_repo"))

import synthflood.run_sweep as rs
from synthflood.config import GEN_DIR, RESULT_DIR
from synthflood.select_env import load_products, build_goals
from synthflood.contaminate import load_pool

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-tasks", type=int, default=100)
    ap.add_argument("--k", default="0,3,7,11")
    ap.add_argument("--n-candidates", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args()

    rs.N_CANDIDATES = args.n_candidates
    by_asin = rs.load_products()
    goals = rs.build_goals(n_tasks=args.n_tasks)
    pool = rs.load_pool(os.path.join(GEN_DIR, "pool.json"))
    out_csv = os.path.join(RESULT_DIR, "ra2_scale_sweep.csv")
    ks = [int(x) for x in args.k.split(",")]
    lock, sem = threading.Lock(), threading.Semaphore(args.workers)
    threads = []
    for gi, goal in enumerate(goals):
        for k in ks:
            eps = k / (args.n_candidates - 1)
            t = threading.Thread(
                target=rs.run_cell,
                args=("RA2", gi, goal, by_asin, pool, eps, "mix",
                      args.seed, "none", args.model, args.port,
                      out_csv, lock, sem))
            t.start()
            threads.append(t)
    for t in threads:
        t.join()
    # summary
    import csv, statistics
    rows = list(csv.DictReader(open(out_csv)))
    out = {}
    for k in ks:
        eps = round(k / (args.n_candidates - 1), 6)
        sub = [r for r in rows if r["eps"] and abs(float(r["eps"]) - eps) < 1e-9]
        n = len(sub)
        if not n:
            out[f"k{k}"] = {"n": 0}
            continue
        reg = statistics.mean(float(r["reward"]) for r in sub if r["reward"] != "")
        s80 = statistics.mean(float(r["success80"]) for r in sub if r["success80"] != "")
        syn = statistics.mean(float(r["chosen_is_synthetic"]) for r in sub if r["chosen_is_synthetic"] != "")
        conf = statistics.mean(float(r["confidence"]) for r in sub if r["confidence"] != "")
        out[f"k{k}"] = {"n": n, "regret": round(1 - reg, 4),
                        "success80": round(s80, 4),
                        "synthetic_share": round(syn, 4),
                        "confidence": round(conf, 4)}
    print(json.dumps(out, indent=1), flush=True)
    json.dump(out, open(os.path.join(RESULT_DIR, "ra2_summary.json"), "w"))

if __name__ == "__main__":
    main()

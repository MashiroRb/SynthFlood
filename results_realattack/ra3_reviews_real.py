"""RA3: reviews-channel dose with REAL documents.

Pool entries = real same-category listings (real title/bullets/description)
+ programmatic inflation (rating 4.6-4.9, 400-3000 reviews, price=f*gold
mirroring the synthetic protocol) + REAL YelpZip filtered fake reviews
(stars=5). Contamination eps=0.75, N=10, family 'reviews_real'.
Comparable arm: synthetic reviews family at eps=0.75 (p4b_reviews).
"""
import argparse, csv, json, os, random, statistics, sys, threading

sys.path.insert(0, os.path.expanduser("~/synthflood"))
sys.path.insert(0, os.path.expanduser("~/webshop_repo"))

import synthflood.run_sweep as rs
from synthflood.config import LOG_DIR, RESULT_DIR
from synthflood.select_env import SelectEnv, load_products, build_goals, get_official_data
from synthflood.contaminate import load_pool, pick_synths, _as_candidate
from synthflood.runlog import append_summary

FIELDS = rs.FIELDS

def inflate(b, gold_price, rng):
    b = dict(b)
    b["price"] = round(gold_price * rng.uniform(0.75, 0.95), 2)
    b["rating"] = round(rng.uniform(4.6, 4.9), 1)
    b["num_reviews"] = rng.randrange(400, 3000)
    return b

def run_cell_ra3(stage, gi, goal, by_asin, pool, eps, cseed, model, port,
                 out_csv, lock, sem, n_candidates):
    sem.acquire()
    try:
        _, _, product_prices, _ = get_official_data()
        rng = random.Random(9000 + gi * 10 + cseed)
        synth_pool = [_as_candidate(inflate(b, product_prices.get(goal["asin"], 100.0), rng))
                      for b in pool.get(gi, [])]
        if not synth_pool:
            return
        candidates, info = rs.build_task(
            goal, by_asin, eps, synth_pool, seed=cseed,
            n_candidates=n_candidates)
        env = SelectEnv(goal, candidates, n_candidates=n_candidates)
        env._synth_positions = info["synth_positions"]
        client = rs.LLMClient(port, model)
        summary = rs.run_episode(
            env, client, goal["instruction_text"], defense="none",
            meta={"stage": stage, "task_id": gi, "eps": eps,
                  "family": "reviews_real", "cseed": cseed,
                  "defense": "none"},
            log_path=os.path.join(LOG_DIR, stage,
                                  f"{stage}__{gi}__e{eps:.2f}.jsonl"))
        row = {"stage": stage, "task_id": gi, "eps": eps,
               "family": "reviews_real", "cseed": cseed, "defense": "none",
               "model": model,
               "reward": round(summary["reward"], 3),
               "success_full": int(summary["success_full"]),
               "success80": int(summary["success80"]),
               "chosen_kind": summary["chosen_kind"],
               "chosen_is_synthetic": int(summary["chosen_is_synthetic"]),
               "chosen_position": summary["chosen_position"],
               "malformed": summary["malformed"], "steps": summary["steps"],
               "confidence": summary["confidence"],
               "tok_in": summary["usage"]["tokens_in"],
               "tok_out": summary["usage"]["tokens_out"],
               "wall": 0}
        with lock:
            append_summary(out_csv, row, FIELDS)
    except Exception as e:
        with lock:
            append_summary(out_csv, {**{k: "" for k in FIELDS},
                                     "stage": stage, "task_id": gi,
                                     "eps": eps, "family": "reviews_real",
                                     "cseed": cseed, "defense": "none",
                                     "model": model,
                                     "chosen_kind": f"ERROR:{type(e).__name__}"},
                           FIELDS)
    finally:
        sem.release()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-tasks", type=int, default=100)
    ap.add_argument("--eps", default="0.75")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args()
    by_asin = rs.load_products()
    goals = rs.build_goals(n_tasks=args.n_tasks)
    pool = load_pool(os.path.expanduser("~/realattack/ra3_pool.json"))
    out_csv = os.path.join(RESULT_DIR, "ra3_reviews_real.csv")
    if os.path.exists(out_csv):
        os.remove(out_csv)
    lock, sem = threading.Lock(), threading.Semaphore(args.workers)
    threads = []
    for gi, goal in enumerate(goals):
        for eps in [float(e) for e in args.eps.split(",")]:
            t = threading.Thread(target=run_cell_ra3, daemon=True,
                                 args=("RA3", gi, goal, by_asin, pool, eps,
                                       args.seed, args.model, args.port,
                                       out_csv, lock, sem, rs.N_CANDIDATES))
            t.start()
            threads.append(t)
    for t in threads:
        t.join()
    rows = [r for r in csv.DictReader(open(out_csv))
            if r["chosen_kind"] and not r["chosen_kind"].startswith("ERROR")]
    n = len(rows)
    reg = statistics.mean(1 - float(r["reward"]) for r in rows)
    s80 = statistics.mean(float(r["success80"]) for r in rows)
    syn = statistics.mean(float(r["chosen_is_synthetic"]) for r in rows)
    out = {"n": n, "regret": round(reg, 4), "success80": round(s80, 4),
           "synthetic_share": round(syn, 4)}
    print(json.dumps(out, indent=1), flush=True)
    json.dump(out, open(os.path.join(RESULT_DIR, "ra3_summary.json"), "w"))

if __name__ == "__main__":
    main()

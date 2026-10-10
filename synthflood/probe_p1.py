"""P1: forced-choice susceptibility probe.

For each task, present exactly two candidates: the gold real product and one
synthetic listing. The agent must pick one. We measure P(choose synthetic),
which is the existence proof for the mechanism: if agents show no systematic
preference for polished synthetic listings, the contamination-degradation
premise is dead and the project pivots.

Gate: susceptibility >= 0.60 with binomial p < 0.01 (300 choices).
"""
import argparse
import json
import os
import random
import threading

from .config import LOG_DIR, RESULT_DIR, GEN_DIR
from .select_env import (SelectEnv, load_products, build_goals,
                         get_official_data)
from .contaminate import load_pool, pick_synths
from .agent_react import run_episode
from .vllm_client import LLMClient
from .metrics import wilson_ci
from .runlog import append_summary

FIELDS = ["task_id", "family", "pair_seed", "chosen", "is_synthetic",
          "reward", "steps"]


def run_pair(gi, goal, by_asin, synth_pool, model, port, out_csv,
             lock, sem, n_pairs=10):
    sem.acquire()
    try:
        pool = synth_pool.get(gi, [])
        if not pool:
            return
        _, _, product_prices, _ = get_official_data()
        client = LLMClient(port, model)
        for pi in range(n_pairs):
            seed = 9000 + gi * 100 + pi
            rng = random.Random(seed)
            synths = pick_synths(pool, eps=1.0, n_candidates=2, seed=seed)
            if not synths:
                continue
            gold = {"item": by_asin[goal["asin"]], "kind": "gold",
                    "synthetic": False,
                    "price_float": product_prices.get(goal["asin"], 100.0)}
            pair = [gold, synths[0]]
            rng.shuffle(pair)
            env = SelectEnv(goal, pair, n_candidates=2)
            summary = run_episode(
                env, client, goal["instruction_text"], defense="none",
                max_steps=6,
                meta={"stage": "P1", "task_id": gi, "family":
                      synths[0].get("family"), "pair_seed": seed},
                log_path=os.path.join(
                    LOG_DIR, "p1",
                    f"p1__{gi}__{synths[0].get('family')}__{pi}.jsonl"))
            row = {"task_id": gi, "family": synths[0].get("family"),
                   "pair_seed": seed,
                   "chosen": summary["chosen_kind"],
                   "is_synthetic": int(summary["chosen_is_synthetic"]),
                   "reward": round(summary["reward"], 3),
                   "steps": summary["steps"]}
            with lock:
                append_summary(out_csv, row, FIELDS)
    finally:
        sem.release()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-tasks", type=int, default=30)
    ap.add_argument("--pairs", type=int, default=10)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--pool", default=os.path.join(GEN_DIR, "pool.json"))
    args = ap.parse_args()

    by_asin = load_products()
    goals = build_goals(n_tasks=args.n_tasks)
    pool = load_pool(args.pool)
    out_csv = os.path.join(RESULT_DIR, "p1_forced_choice.csv")
    lock, sem = threading.Lock(), threading.Semaphore(32)
    threads = []
    for gi, goal in enumerate(goals):
        t = threading.Thread(target=run_pair,
                             args=(gi, goal, by_asin, pool, args.model,
                                   args.port, out_csv, lock, sem,
                                   args.pairs))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    rows = []
    with open(out_csv) as f:
        next(f)
        for line in f:
            rows.append(line.strip().split(","))
    n = len(rows)
    k = sum(1 for r in rows if r[4] == "1")
    sus = k / n if n else float("nan")
    lo, hi = wilson_ci(k, n)
    print(json.dumps({"n": n, "k_synth": k, "susceptibility": round(sus, 4),
                      "ci95": [round(lo, 4), round(hi, 4)],
                      "gate": "GO" if sus >= 0.60 else "NO-GO"}))


if __name__ == "__main__":
    main()
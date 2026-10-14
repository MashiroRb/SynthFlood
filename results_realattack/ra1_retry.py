"""RA1 retry: rerun synth_f090 for the two tasks (88, 175) whose
episodes crashed in the original run (synth_listing returned None and
the worker thread died before writing a row). Rebuilds the task list
deterministically (same seed/path as probe_real.main) and calls
probe_real.run_one verbatim with a retrying synth_listing. Rows go to
a separate retry CSV; merge + stats recompute happen offline.
"""
import json, os, random, sys, threading, time

sys.path.insert(0, os.path.expanduser("~/synthflood"))
sys.path.insert(0, os.path.expanduser("~/webshop_repo"))
sys.path.insert(0, os.path.expanduser("~/realattack"))

import probe_real
from synthflood.vllm_client import LLMClient
from web_agent_site.engine.goal import get_human_goals
from synthflood.ws_loader import load_official_data

ORIG_SYNTH = probe_real.synth_listing


def synth_listing_retry(kind, goal, gold_item, rng, client, port,
                        tries=4, wait=5):
    last = None
    for t in range(tries):
        last = ORIG_SYNTH(kind, goal, gold_item, rng, client, port)
        if last is not None:
            return last
        print(f"attempt {t + 1} returned None; wait {wait}s", flush=True)
        time.sleep(wait)
    return last


probe_real.synth_listing = synth_listing_retry


def build_tasks():
    all_products, item_dict, product_prices, _ = load_official_data(
        os.path.expanduser("~/data"))
    random.seed(1)
    goals_all = get_human_goals(all_products, product_prices)
    goals_by_asin = {}
    for g in goals_all:
        goals_by_asin.setdefault(g["asin"], g)
    by_asin = item_dict
    recs = json.load(open(os.path.expanduser(
        "~/realattack/realattack_pairs.json")))
    rng = random.Random(1000)
    rng.shuffle(recs)
    tasks = []
    for rec in recs:
        g = rec["gold_asin"]
        if g not in by_asin or rec["clone_asin"] not in by_asin:
            continue
        if g not in goals_by_asin:
            continue
        gp = product_prices.get(g)
        if not gp or gp <= 0:
            continue
        tasks.append((rec, goals_by_asin[g], by_asin[g], gp))
        if len(tasks) >= 250:
            break
    return tasks, by_asin


def main():
    targets = {int(a) for a in sys.argv[1:]} or {88, 175}
    tasks, by_asin = build_tasks()
    assert len(tasks) == 250, len(tasks)
    out_csv = os.path.expanduser("~/realattack/ra1_retry.csv")
    if os.path.exists(out_csv):
        os.remove(out_csv)
    lock, sem = threading.Lock(), threading.Semaphore(1)
    for pi in sorted(targets):
        rec, goal, gold_item, gp = tasks[pi]
        print(f"running task {pi} gold={rec['gold_asin']} "
              f"clone={rec['clone_asin']}", flush=True)
        probe_real.run_one(pi, rec, goal, gold_item, gp, by_asin,
                           "synth_f090", "Qwen/Qwen2.5-7B-Instruct",
                           8000, out_csv, lock, sem)
    print(open(out_csv).read() if os.path.exists(out_csv) else "NO-ROWS",
          flush=True)
    print("RETRY-DONE", flush=True)


if __name__ == "__main__":
    main()

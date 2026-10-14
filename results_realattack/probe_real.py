"""RA1: Real-clone forced-choice probe (external-validity Plan 1).

Tasks from REAL lookalike pairs mined from the full 1.18M-item WebShop
catalog (real Amazon scrape): gold = pricier member with an official
human instruction (official get_human_goals semantics); clone = real
lookalike listing (title-token Jaccard in [0.80,0.95), natural discount
>= 10%). Arms: real_f090 / real_f080 (real text, price=f*gold),
real_nat (real text, natural price), synth_f090 (our generator's clone
for the SAME gold, paired comparison).
Output: results/ra1_real_clone_probe.csv + ra1_summary.json
"""
import argparse, csv, json, os, random, sys, threading

sys.path.insert(0, os.path.expanduser("~/synthflood"))
sys.path.insert(0, os.path.expanduser("~/webshop_repo"))

from synthflood.config import LOG_DIR, RESULT_DIR
from synthflood.select_env import SelectEnv
from synthflood.agent_react import run_episode
from synthflood.vllm_client import LLMClient
from synthflood.runlog import append_summary
from synthflood.contaminate import synth_listing
from web_agent_site.engine.goal import get_human_goals
from synthflood.ws_loader import load_official_data

FIELDS = ["task_id", "arm", "chosen_kind", "chose_clone",
          "reward", "steps", "jaccard", "natural_disc", "clone_price",
          "gold_price"]


def run_one(pi, rec, goal, gold_item, gold_price, by_asin, arm, model, port,
            out_csv, lock, sem):
    sem.acquire()
    try:
        rng = random.Random(41000 + pi)
        client = LLMClient(port, model)
        if arm == "synth_f090":
            b = synth_listing("clone", goal, gold_item, rng, client, port)
            b["price"] = round(gold_price * 0.9, 2)
            cand = {"asin": b["asin"], "kind": "synthetic_clone",
                    "synthetic": True,
                    "item": {k: b.get(k) for k in
                             ("asin", "Title", "price", "rating",
                              "num_reviews", "Brand", "product_category",
                              "query", "BulletPoints", "Description",
                              "Attributes")},
                    "price_float": b["price"],
                    "reviews": b.get("reviews", [])}
        else:
            item = dict(by_asin[rec["clone_asin"]])
            if arm == "real_nat":
                price = rec["clone_price"]
            else:
                price = round(gold_price * (0.9 if arm == "real_f090" else 0.8), 2)
                item["price"] = price
            cand = {"asin": rec["clone_asin"], "kind": "real_clone",
                    "synthetic": False, "item": item,
                    "price_float": price}
        gold = {"asin": rec["gold_asin"], "kind": "gold", "synthetic": False,
                "item": gold_item, "price_float": gold_price}
        pair = [gold, cand]
        rng.shuffle(pair)
        env = SelectEnv(goal, pair, n_candidates=2)
        summary = run_episode(
            env, client, goal["instruction_text"], defense="none",
            max_steps=6,
            meta={"stage": "RA1", "task_id": pi, "family": arm,
                  "pair_seed": 41000 + pi},
            log_path=os.path.join(LOG_DIR, "ra1", f"ra1__{arm}__{pi}.jsonl"))
        row = {"task_id": pi, "arm": arm,
               "chosen_kind": summary["chosen_kind"],
               "chose_clone": int(summary["chosen_kind"] in
                                  ("real_clone", "synthetic_clone")),
               "reward": round(summary["reward"], 3),
               "steps": summary["steps"],
               "jaccard": rec["jaccard"],
               "natural_disc": rec["natural_discount"],
               "clone_price": cand["price_float"],
               "gold_price": gold_price}
        with lock:
            append_summary(out_csv, row, FIELDS)
    finally:
        sem.release()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=250)
    ap.add_argument("--arms", default="real_f090,real_f080,real_nat,synth_f090")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    all_products, item_dict, product_prices, _ = load_official_data(
        os.path.expanduser("~/data"))
    import random as _r
    _r.seed(args.seed)          # official price sampling via global RNG
    goals_all = get_human_goals(all_products, product_prices)
    goals_by_asin = {}
    for g in goals_all:
        goals_by_asin.setdefault(g["asin"], g)
    by_asin = item_dict

    recs = json.load(open(os.path.expanduser(
        "~/realattack/realattack_pairs.json")))
    rng = random.Random(1000 * args.seed)
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
        if len(tasks) >= args.pairs:
            break
    print("tasks:", len(tasks), "scanned:", len(recs), flush=True)
    diag = {"goals_total": len(goals_all), "prices_zero": 0}
    for rec in recs:
        g = rec["gold_asin"]
        if g not in goals_by_asin: diag.setdefault("no_goal", []).append(g)
        elif not (product_prices.get(g) or 0) > 0: diag["prices_zero"] += 1
    diag["no_goal_n"] = len(diag.get("no_goal", []))
    print("diag:", {k: v for k, v in diag.items() if not isinstance(v, list)}, flush=True)
    json.dump([{"task_id": i, "gold": t[0]["gold_asin"],
                "clone": t[0]["clone_asin"],
                "jaccard": t[0]["jaccard"],
                "natural_disc": t[0]["natural_discount"],
                "gold_price": t[3],
                "instruction": t[1]["instruction_text"]}
               for i, t in enumerate(tasks)],
              open(os.path.expanduser("~/realattack/ra1_task_manifest.json"), "w"))

    os.makedirs(RESULT_DIR, exist_ok=True)
    out_csv = os.path.join(RESULT_DIR, "ra1_real_clone_probe.csv")
    if os.path.exists(out_csv):
        os.remove(out_csv)
    lock, sem = threading.Lock(), threading.Semaphore(args.workers)
    threads = []
    for arm in args.arms.split(","):
        for pi, (rec, goal, gold_item, gp) in enumerate(tasks):
            t = threading.Thread(target=run_one, daemon=True,
                                 args=(pi, rec, goal, gold_item, gp, by_asin,
                                       arm, args.model, args.port, out_csv,
                                       lock, sem))
            t.start()
            threads.append(t)
    for t in threads:
        t.join()

    rows = list(csv.DictReader(open(out_csv)))
    out = {}
    for arm in args.arms.split(","):
        sub = [r for r in rows if r["arm"] == arm]
        n, k = len(sub), sum(int(r["chose_clone"]) for r in sub)
        out[arm] = {"n": n, "k": k, "sigma": round(k / n, 4) if n else None}
    print(json.dumps(out, indent=1), flush=True)
    json.dump(out, open(os.path.join(RESULT_DIR, "ra1_summary.json"), "w"))


if __name__ == "__main__":
    main()

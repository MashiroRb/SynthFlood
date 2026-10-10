"""Reprice the contamination pool: synthetic price = gold_price * U(0.75, 0.95).

Fixes the $50-anchor bug (gold Price was a '$x.xx' string, so the generator
fell back to 50.0). Listing text, judge scores, ratings, reviews stay as
generated; only prices change, deterministically per listing asin.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synthflood.select_env import get_official_data  # noqa: E402


def parse_price(v):
    try:
        return float(str(v).replace("$", "").split(" to ")[0])
    except (ValueError, TypeError):
        return None


def main():
    from synthflood.config import GEN_DIR
    pool_path = os.path.join(GEN_DIR, "pool.json")
    goals_path = os.path.join(GEN_DIR, "goals.json")
    _, _, product_prices, _ = get_official_data()
    with open(goals_path) as f:
        goals = json.load(f)
    with open(pool_path) as f:
        pool = json.load(f)

    n_changed, n_kept = 0, 0
    for gi_str, listings in pool.items():
        gi = int(gi_str)
        gold_price = product_prices.get(goals[gi]["asin"])
        if not gold_price:
            continue
        for b in listings:
            old = parse_price(b.get("price"))
            # deterministic per-listing draw; avoids re-rolling anything else
            r = random.Random(hash(str(b["asin"])) & 0xFFFF)
            new = round(gold_price * r.uniform(0.75, 0.95), 2)
            if old is not None and abs(old - new) < 0.005:
                n_kept += 1
            else:
                n_changed += 1
            b["price"] = new
            b["price_anchored"] = True

    with open(pool_path, "w") as f:
        json.dump(pool, f, ensure_ascii=False)
    print(json.dumps({"pool": pool_path, "repriced": n_changed,
                      "already_ok": n_kept}))


if __name__ == "__main__":
    main()

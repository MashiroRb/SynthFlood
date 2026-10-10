"""Merge pool_ext.json (goals 40..99) into pool.json, then reprice new items.

pool_ext keys are goal indices 0..59 relative to goals_ext.json; after merge
they become 40..99 in the canonical pool. Repricing is deterministic per
listing asin, so already-repriced old listings are kept (already_ok).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synthflood.config import GEN_DIR  # noqa: E402


def parse_price(v):
    try:
        return float(str(v).replace("$", "").split(" to ")[0])
    except (ValueError, TypeError):
        return None


def main():
    pool_path = os.path.join(GEN_DIR, "pool.json")
    ext_path = os.path.join(GEN_DIR, "pool_ext.json")
    goals100_path = os.path.join(GEN_DIR, "goals100.json")
    with open(pool_path) as f:
        pool = json.load(f)
    with open(ext_path) as f:
        ext = json.load(f)
    with open(goals100_path) as f:
        goals100 = json.load(f)

    from synthflood.select_env import get_official_data
    _, _, product_prices, _ = get_official_data()
    import random

    added = 0
    for k, listings in ext.items():
        gi = int(k) + 40
        gold_price = product_prices.get(goals100[gi]["asin"])
        for b in listings:
            r = random.Random(hash(str(b["asin"])) & 0xFFFF)
            if gold_price:
                b["price"] = round(gold_price * r.uniform(0.75, 0.95), 2)
                b["price_anchored"] = True
        pool[str(gi)] = listings
        added += 1
    with open(pool_path, "w") as f:
        json.dump(pool, f, ensure_ascii=False)
    n = sum(len(v) for v in pool.values())
    print(json.dumps({"merged_tasks": added, "total_tasks": len(pool),
                      "total_listings": n}))


if __name__ == "__main__":
    main()

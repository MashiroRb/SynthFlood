"""E4: price dose-response pools for the clone price channel.

Generates pool_price{90,80,70}.json where every clone-family listing gets
price = gold_price * f exactly (uniform across listings, factor f in
{0.9, 0.8, 0.7}). Combined with probeB (f=1.0, sigma=0.386) and the
original pool (f~U(0.75,0.95), sigma=0.523), this traces sigma(f).
Rating/reviews stay as generated (social-proof channel held fixed).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synthflood.select_env import get_official_data  # noqa: E402
from synthflood.config import GEN_DIR  # noqa: E402


def main():
    _, item_dict, product_prices, _ = get_official_data()
    with open(os.path.join(GEN_DIR, "goals100.json")) as f:
        goals = json.load(f)
    with open(os.path.join(GEN_DIR, "pool.json")) as f:
        pool = json.load(f)

    factors = {"90": 0.9, "80": 0.8, "70": 0.7}
    outs = {k: {} for k in factors}
    n_set = {k: 0 for k in factors}
    for gi_str, listings in pool.items():
        gi = int(gi_str)
        gold_price = product_prices.get(goals[gi]["asin"])
        for k, f in factors.items():
            row = []
            for b in listings:
                bb = dict(b)
                if b.get("family") == "clone" and gold_price:
                    bb["price"] = round(gold_price * f, 2)
                    bb["price_anchored"] = f"gold_x{f}"
                    n_set[k] += 1
                row.append(bb)
            outs[k][gi_str] = row
    for k in factors:
        with open(os.path.join(GEN_DIR, f"pool_price{k}.json"), "w") as fp:
            json.dump(outs[k], fp)
    print(json.dumps({"clone_price_set": n_set}))


if __name__ == "__main__":
    main()

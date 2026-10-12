"""Build clone-decoupling probe pools for A2/A3 (factor isolation).

Variant B (pool_probeB.json): clone-family listings get price = gold price
  exactly (price channel neutralized; text/ratings/reviews as generated).
Variant C (pool_probeC.json): clone-family listings get rating="" and
  num_reviews=0 (social-proof channel neutralized; text/price as generated).

Only clone-family entries change; geo/reviews entries pass through so a
single pool file stays drop-in compatible with probe_p1 --pool.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synthflood.select_env import get_official_data  # noqa: E402
from synthflood.config import GEN_DIR  # noqa: E402


def main():
    _, item_dict, product_prices, _ = get_official_data()
    # pool.json covers 100 goal indices; goals.json only freezes the first 40.
    with open(os.path.join(GEN_DIR, "goals100.json")) as f:
        goals = json.load(f)
    with open(os.path.join(GEN_DIR, "pool.json")) as f:
        pool = json.load(f)

    poolB, poolC, poolBC = {}, {}, {}
    n_b = n_c = n_bc = n_clone = 0
    for gi_str, listings in pool.items():
        gi = int(gi_str)
        gold = goals[gi]
        gold_price = product_prices.get(gold["asin"])
        gold_item = item_dict.get(gold["asin"], {})
        gold_rating = gold_item.get("rating", "")
        gold_nrev = gold_item.get("num_reviews", 0)
        outB, outC, outBC = [], [], []
        for b in listings:
            bB, bC, bBC = dict(b), dict(b), dict(b)
            if b.get("family") == "clone":
                n_clone += 1
                if gold_price:
                    bB["price"] = gold_price
                    bB["price_anchored"] = "gold_exact"
                    bBC["price"] = gold_price
                    bBC["price_anchored"] = "gold_exact"
                    n_b += 1
                bC["rating"] = gold_rating
                bC["num_reviews"] = gold_nrev
                bC["social_proof"] = "gold_matched"
                bBC["rating"] = gold_rating
                bBC["num_reviews"] = gold_nrev
                bBC["social_proof"] = "gold_matched"
                n_c += 1
                n_bc += 1
            outB.append(bB)
            outC.append(bC)
            outBC.append(bBC)
        poolB[gi_str] = outB
        poolC[gi_str] = outC
        poolBC[gi_str] = outBC

    for name, data in [("pool_probeB.json", poolB), ("pool_probeC.json", poolC),
                       ("pool_probeBC.json", poolBC)]:
        with open(os.path.join(GEN_DIR, name), "w") as f:
            json.dump(data, f)
    print(json.dumps({"clone_total": n_clone, "B_price_anchored": n_b,
                      "C_social_stripped": n_c, "BC_double_knockout": n_bc}))


if __name__ == "__main__":
    main()

"""Export a human-auditable sample of the generated contamination pool.

Writes a JSON + plain-text digest with the goal, the gold listing, and the
synthetic candidates (all three families), for manual plausibility review.
"""
import argparse
import json
import os
import random

from .config import GEN_DIR, RESULT_DIR
from .select_env import load_products, build_goals
from .contaminate import load_pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default=os.path.join(GEN_DIR, "pool.json"))
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    pool = load_pool(args.pool)
    rng = random.Random(args.seed)
    gids = sorted(pool.keys())
    rng.shuffle(gids)
    sample = []
    for gi in gids[:args.n]:
        for b in pool[gi]:
            sample.append({"task_id": gi, "family": b.get("family"),
                           "judge_score": b.get("judge_score"),
                           "title": b.get("Title"),
                           "bullets": b.get("BulletPoints"),
                           "specs": b.get("Attributes"),
                           "description": b.get("Description"),
                           "price": b.get("price"),
                           "rating": b.get("rating"),
                           "num_reviews": b.get("num_reviews"),
                           "n_reviews_attached": len(b.get("reviews", []))})
    os.makedirs(RESULT_DIR, exist_ok=True)
    with open(os.path.join(RESULT_DIR, "audit_sample.json"), "w") as f:
        json.dump(sample, f, ensure_ascii=False, indent=1)
    with open(os.path.join(RESULT_DIR, "audit_sample.txt"), "w") as f:
        for s in sample:
            f.write(f"--- [{s['family']}] task {s['task_id']} "
                    f"(judge {s['judge_score']}) ${s['price']} "
                    f"{s['rating']}* ({s['num_reviews']}) ---\n")
            f.write(f"TITLE: {s['title']}\n")
            for b in (s["bullets"] or [])[:5]:
                f.write(f"  - {b}\n")
            for sp in (s["specs"] or [])[:5]:
                f.write(f"  spec: {sp}\n")
            f.write(f"  DESC: {(s['description'] or '')[:200]}\n\n")
    stats = {}
    for b in [x for v in pool.values() for x in v]:
        stats[b.get("family")] = stats.get(b.get("family"), 0) + 1
    print(json.dumps({"n_pool": sum(len(v) for v in pool.values()),
                      "per_family": stats,
                      "sampled": len(sample)}))


if __name__ == "__main__":
    main()
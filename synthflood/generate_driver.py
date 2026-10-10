"""CLI driver for the contamination pool generation."""
import argparse
import json
import os

from .config import GEN_DIR
from .select_env import load_products, build_goals
from .contaminate import generate_pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-tasks", type=int, default=40,
                    help="goals to prepare synthetic pools for")
    ap.add_argument("--per-task", type=int, default=4,
                    help="listings per family per task")
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--judge-port", type=int, default=8000,
                    help="judge model port (different from generator)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--goals-file", default=None,
                    help="json with goal list (keeps tasks aligned)")
    args = ap.parse_args()

    by_asin = load_products()
    if args.goals_file and os.path.exists(args.goals_file):
        with open(args.goals_file) as f:
            goals = json.load(f)
    else:
        goals = build_goals(n_tasks=args.n_tasks)
        os.makedirs(GEN_DIR, exist_ok=True)
        with open(os.path.join(GEN_DIR, "goals.json"), "w") as f:
            json.dump(goals, f, ensure_ascii=False)
    gold_items = [by_asin[g["asin"]] for g in goals]
    out = args.out or os.path.join(GEN_DIR, "pool.json")
    pool = generate_pool(goals, gold_items, out, args.port, args.model,
                         per_task_per_family=args.per_task,
                         judge_port=args.judge_port)
    n = sum(len(v) for v in pool.values())
    print(f"generated {n} synthetic listings -> {out}")


if __name__ == "__main__":
    main()
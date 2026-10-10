"""P0: pipeline sanity check on a clean (eps=0) slice.

Gate:
  1. agent action parsing works (malformed rate low)
  2. clean success rate plausible for the model class (7B ~ 30-50%)
  3. exact reproducibility: rerunning the same tasks gives identical rewards
"""
import argparse
import json
import os
import threading

from .config import LOG_DIR, RESULT_DIR, N_CANDIDATES
from .select_env import (SelectEnv, load_products, build_goals,
                         build_task, sample_distractors)
from .agent_react import run_episode
from .vllm_client import LLMClient
from .runlog import append_summary

FIELDS = ["task_id", "eps", "reward", "success_full", "success80",
          "chosen_kind", "steps", "malformed", "tok_in", "tok_out"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-tasks", type=int, default=20)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--repeat", type=int, default=1,
                    help="rerun to verify determinism")
    args = ap.parse_args()

    by_asin = load_products()
    goals = build_goals(n_tasks=args.n_tasks)
    out_csv = os.path.join(RESULT_DIR, "p0_sanity.csv")
    lock, sem = threading.Lock(), threading.Semaphore(args.workers)

    def work(gi, goal, rep):
        sem.acquire()
        try:
            distractors = sample_distractors(goal, by_asin, N_CANDIDATES - 1,
                                             seed=1)
            candidates = [{"item": by_asin[goal["asin"]], "kind": "gold",
                           "synthetic": False}] + [
                {"item": d, "kind": "real", "synthetic": False}
                for d in distractors]
            env = SelectEnv(goal, candidates, n_candidates=N_CANDIDATES)
            client = LLMClient(args.port, args.model)
            s = run_episode(
                env, client, goal["instruction_text"],
                meta={"stage": "P0", "task_id": gi, "repeat": rep},
                log_path=os.path.join(LOG_DIR, "p0",
                                      f"p0__{gi}__r{rep}.jsonl"))
            with lock:
                append_summary(out_csv, {
                    "task_id": gi, "eps": 0.0,
                    "reward": round(s["reward"], 3),
                    "success_full": int(s["success_full"]),
                    "success80": int(s["success80"]),
                    "chosen_kind": s["chosen_kind"], "steps": s["steps"],
                    "malformed": s["malformed"],
                    "tok_in": s["usage"]["tokens_in"],
                    "tok_out": s["usage"]["tokens_out"]}, FIELDS)
        finally:
            sem.release()

    threads = []
    for rep in range(args.repeat):
        for gi, goal in enumerate(goals):
            t = threading.Thread(target=work, args=(gi, goal, rep))
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
    succ = sum(1 for r in rows if r[3] == "1")
    mal = sum(int(r[7]) for r in rows if r[7])
    print(json.dumps({"n": n, "success_full_rate": round(succ / max(n, 1), 3),
                      "malformed_total": mal}))


if __name__ == "__main__":
    main()
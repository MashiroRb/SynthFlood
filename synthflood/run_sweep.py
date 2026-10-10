"""Generic sweep runner for P0/P2/P4: task x eps x family x defense cells,
threaded against one vLLM server (continuous batching does the rest)."""
import argparse
import json
import os
import threading
import time

from .config import LOG_DIR, RESULT_DIR, N_CANDIDATES, EPS_GRID
from .select_env import (SelectEnv, load_products, build_goals,
                         build_task, product_fields)
from .contaminate import load_pool, pick_synths
from .agent_react import run_episode
from .vllm_client import LLMClient
from .runlog import append_summary
from .defenses import apply_defense

FIELDS = ["stage", "task_id", "eps", "family", "cseed", "defense", "model",
          "reward", "success_full", "success80", "chosen_kind",
          "chosen_is_synthetic", "chosen_position", "malformed", "steps",
          "confidence", "tok_in", "tok_out", "wall"]


def run_cell(stage, gi, goal, by_asin, pool, eps, family, cseed, defense,
             model, port, out_csv, lock, sem):
    sem.acquire()
    t0 = time.time()
    try:
        synth_pool = pick_synths(pool.get(gi, []), eps, N_CANDIDATES, cseed,
                                 family=family)
        if eps > 0 and not synth_pool:
            with lock:
                append_summary(out_csv, {**{k: "" for k in FIELDS},
                                         "stage": stage, "task_id": gi,
                                         "eps": eps, "family": family,
                                         "cseed": cseed, "defense": defense,
                                         "model": model,
                                         "chosen_kind": "SKIPPED:no_synth"},
                               FIELDS)
            return
        candidates, info = build_task(
            goal, by_asin, eps, synth_pool, seed=cseed,
            n_candidates=N_CANDIDATES)
        env = SelectEnv(goal, candidates, n_candidates=N_CANDIDATES)
        env._synth_positions = info["synth_positions"]
        client = LLMClient(port, model)
        ppl_fn = (lambda text: client.perplexity(text)
                  ) if defense == "detector_text" else None
        # defense preprocessing: rerank/drop/annotate candidates
        candidates2 = apply_defense(defense, candidates, goal,
                                    perplexity_fn=ppl_fn)
        env.candidates = candidates2
        env.n = len(candidates2)
        summary = run_episode(
            env, client, goal["instruction_text"], defense=defense,
            meta={"stage": stage, "task_id": gi, "eps": eps,
                  "family": family, "cseed": cseed, "defense": defense},
            log_path=os.path.join(
                LOG_DIR, stage,
                f"{stage}__{gi}__e{eps:.2f}__{family}__{defense}.jsonl"))
        row = {"stage": stage, "task_id": gi, "eps": eps, "family": family,
               "cseed": cseed, "defense": defense, "model": model,
               "reward": round(summary["reward"], 3),
               "success_full": int(summary["success_full"]),
               "success80": int(summary["success80"]),
               "chosen_kind": summary["chosen_kind"],
               "chosen_is_synthetic": int(summary["chosen_is_synthetic"]),
               "chosen_position": summary["chosen_position"],
               "malformed": summary["malformed"], "steps": summary["steps"],
               "confidence": summary["confidence"],
               "tok_in": summary["usage"]["tokens_in"],
               "tok_out": summary["usage"]["tokens_out"],
               "wall": round(time.time() - t0, 1)}
        with lock:
            append_summary(out_csv, row, FIELDS)
    except Exception as e:  # keep the sweep alive; log the failure
        with lock:
            append_summary(out_csv, {**{k: "" for k in FIELDS},
                                     "stage": stage, "task_id": gi,
                                     "eps": eps, "family": family,
                                     "cseed": cseed, "defense": defense,
                                     "model": model,
                                     "chosen_kind": f"ERROR:{type(e).__name__}"},
                           FIELDS)
        with open(os.path.join(LOG_DIR, "errors.log"), "a") as f:
            import traceback
            f.write(f"{stage} {gi} {eps} {family} {defense}: {e}\n")
            f.write(traceback.format_exc() + "\n")
    finally:
        sem.release()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="P2")
    ap.add_argument("--n-tasks", type=int, default=50)
    ap.add_argument("--eps", default="0,0.25,0.75")
    ap.add_argument("--family", default="mix")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--defense", default="none")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--pool", default=None)
    args = ap.parse_args()

    pool_path = args.pool or os.path.join(
        __import__("synthflood.config", fromlist=["x"]).GEN_DIR, "pool.json")
    by_asin = load_products()
    goals = build_goals(n_tasks=args.n_tasks)
    gold_items = [by_asin[g["asin"]] for g in goals]
    pool = load_pool(pool_path)
    out_csv = os.path.join(RESULT_DIR, f"{args.stage.lower()}_sweep.csv")
    eps_list = [float(e) for e in args.eps.split(",")]
    lock, sem = threading.Lock(), threading.Semaphore(args.workers)
    threads = []
    for gi, goal in enumerate(goals):
        for eps in eps_list:
            t = threading.Thread(
                target=run_cell,
                args=(args.stage, gi, goal, by_asin, pool, eps, args.family,
                      args.seed, args.defense, args.model, args.port,
                      out_csv, lock, sem))
            t.start()
            threads.append(t)
    for t in threads:
        t.join()
    print(json.dumps({"stage": args.stage, "done": True,
                      "csv": out_csv}))


if __name__ == "__main__":
    main()
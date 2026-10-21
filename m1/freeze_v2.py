"""Prepare all v2 tasks once on a Slurm CPU node; GPU jobs need no raw catalog."""
import copy
import hashlib
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SYNTHFLOOD_PRODUCT_CACHE", "0")
from m1_run import load_everything, EXAM_IDX, PARITY_IDX, gold_candidate
from synthflood.select_env import build_task, product_fields
from synthflood.contaminate import _as_candidate

SEEDS = list(range(2030, 2038))
DEST = ROOT / "data/m1_v2"


def file_digest(path):
    hasher=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(8*1024*1024):
            hasher.update(block)
    return hasher.hexdigest()


def show_price(candidate):
    candidate = copy.deepcopy(candidate)
    value = candidate["price_float"]
    candidate["item"]["Price"] = f"${value:.2f}"
    candidate["item"]["price"] = value
    return candidate


def prepare():
    DEST.mkdir(parents=True, exist_ok=True)
    if (DEST / "context.json").exists():
        raise RuntimeError("Frozen context exists. Preserve it; use a new destination for a new instrument.")
    by_asin, prices, goals, goals_by_asin = load_everything()
    pairs = json.loads((ROOT / "data/official/realattack_pairs.json").read_text())
    historical = json.loads((ROOT / "results_realattack/ra1_task_manifest.json").read_text())
    ra1_order=list(pairs)
    random.Random(1000).shuffle(ra1_order)  # probe_real.py default seed=1
    matches = sum(ra1_order[x["task_id"]]["gold_asin"] == x["gold"] and
                  ra1_order[x["task_id"]]["clone_asin"] == x["clone"] for x in historical)
    if len(pairs) != 467 or matches != len(historical):
        raise RuntimeError(f"Reconstructed pair ordering differs: {len(pairs)} pairs; {matches}/{len(historical)} RA1 matches")
    exp, wash = goals[100:120], goals[120:140]
    used = {pairs[i]["gold_asin"] for i in EXAM_IDX + PARITY_IDX}
    excluded_gold=used & {g["asin"] for g in exp + wash}
    caches = {}
    for phase, indices, factor in (("exam", EXAM_IDX, .9), ("parity", PARITY_IDX, 1.0)):
        original = json.loads((ROOT / f"data/contamination/m1_{phase}_clones.json").read_text())
        selected = {}
        for i in indices:
            if str(i) not in original:
                continue
            record = pairs[i]
            clone = copy.deepcopy(original[str(i)])
            clone["price_float"] = round(prices[record["gold_asin"]] * factor, 2)
            clone["item"]["options"] = copy.deepcopy(by_asin[record["gold_asin"]].get("options", {}))
            selected[str(i)] = show_price(clone)
        caches[phase] = selected
    full_caches=copy.deepcopy(caches)
    excluded_pairs={phase:[int(i) for i in cache if pairs[int(i)]['gold_asin'] in excluded_gold]
                    for phase,cache in caches.items()}
    caches={phase:{i:clone for i,clone in cache.items() if int(i) not in excluded_pairs[phase]}
            for phase,cache in caches.items()}
    pool = json.loads((ROOT / "data/contamination/m1_pool.json").read_text())
    # The released pools are keyed by the same exposure goal indices.
    old_goals = json.loads((ROOT / "data/contamination/goals_m1.json").read_text())["exposure"]
    if [g["asin"] for g in exp] != [g["asin"] for g in old_goals]:
        raise RuntimeError("Frozen v2 exposure goals do not match the archived pool")
    episode_tasks = {}
    for seed in SEEDS:
        tasks = {}
        offset = (seed - 2027) * 100000
        for phase, phase_goals in (("warmup", exp), ("washout", wash)):
            for ep, goal in enumerate(phase_goals):
                draw = (50000 if phase == "warmup" else 60000) + ep + offset
                clean, _ = build_task(goal, by_asin, 0.0, [], draw, n_candidates=10)
                clean = [show_price(c) for c in clean]
                order = list(range(10))
                random.Random(draw + 999999).shuffle(order)
                if phase == "washout":
                    tasks[f"washout:{ep}"] = [clean[i] for i in order]
                    continue
                treated = copy.deepcopy(clean)
                synths = []
                for family_id, family in enumerate(("geo", "clone", "reviews")):
                    family_pool = [b for b in pool[str(ep)] if b["family"] == family]
                    if len(family_pool) < 2:
                        raise RuntimeError(f"Insufficient {family} listings at task {ep}")
                    chosen = random.Random(draw + family_id * 1000).sample(family_pool, 2)
                    synths.extend(show_price(_as_candidate(b)) for b in chosen)
                replace = random.Random(draw).sample(list(range(1, 10)), 6)
                for slot, candidate in zip(replace, synths):
                    treated[slot] = candidate
                tasks[f"warmup_clean:{ep}"] = [clean[i] for i in order]
                tasks[f"warmup_treated:{ep}"] = [treated[i] for i in order]
        episode_tasks[str(seed)] = tasks
    keep = used | {g["asin"] for g in exp + wash}
    ctx = {"protocol": "balanced_v2", "pairs": pairs,
           "exposure_goals": exp, "washout_goals": wash,
           "by_asin": {key: by_asin[key] for key in keep},
           "product_prices": {key: prices[key] for key in keep},
           "goals_by_asin": {key: goals_by_asin[key] for key in keep},
           "exam_clones": caches["exam"], "parity_clones": caches["parity"],
           "diagnostic_parity_clones":full_caches['parity'],
           "episode_tasks": episode_tasks}
    # Exact displayed gold price equals the price used by official reward.
    for key in keep:
        item = copy.deepcopy(ctx["by_asin"][key])
        item["Price"] = f"${prices[key]:.2f}"
        item["price"] = prices[key]
        ctx["by_asin"][key] = item
    payload = json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()
    (DEST / "context.json").write_bytes(payload)
    manifest = {"protocol": "balanced_v2", "seeds": SEEDS,
                "context_sha256": hashlib.sha256(payload).hexdigest(),
                "reconstructed_pairs": len(pairs), "RA1_shuffled250_identity_matches": matches,
                "historical_exam_equivalence": "not claimed; historical full goals and pair-file hash were not archived",
                "exam_pairs": list(caches["exam"]), "parity_pairs": list(caches["parity"]),
                "exam_unique_gold_asins": len({pairs[int(i)]["gold_asin"] for i in caches["exam"]}),
                "parity_unique_gold_asins": len({pairs[int(i)]["gold_asin"] for i in caches["parity"]}),
                "instrument_goal_seed": 2027, "price_seed": 2027,
                "exposure_pool": "archived seed1, fixed across v2 trajectories",
                "generation": "none; archived clone text with frozen corrected price/options",
                "checkpoints": [0,4,10,20]}
    manifest['excluded_exposed_gold_asins']=sorted(excluded_gold)
    manifest['excluded_pair_indices']=excluded_pairs
    manifest['diagnostic_parity_pairs']=list(full_caches['parity'])
    manifest['source_sha256']={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
        for directory in ('m1','synthflood') for path in sorted((ROOT/directory).glob('*.py'))}
    manifest['protocol_sha256']=hashlib.sha256((ROOT/'m1/PRE_REG_M1_V2.md').read_bytes()).hexdigest()
    manifest['run_script_sha256']=hashlib.sha256((ROOT/'m1/slurm/run.sbatch').read_bytes()).hexdigest()
    manifest['official_input_sha256']={name:file_digest(ROOT/'data/official'/name)
        for name in ('items_shuffle.json','items_ins_v2.json','items_human_ins.json','realattack_pairs.json')}
    manifest['archived_cache_sha256']={name:file_digest(ROOT/'data/contamination'/name)
        for name in ('m1_pool.json','m1_exam_clones.json','m1_parity_clones.json')}
    manifest['model_revision']='Qwen2.5-7B-Instruct/a09a35458c702b33eeacc393d103063234e8bc28'
    historical_ids={(record['gold'],record['clone']) for record in historical}
    manifest['previous_RA1_reuse']={phase:sum((pairs[int(i)]['gold_asin'],pairs[int(i)]['clone_asin']) in historical_ids
        for i in caches[phase]) for phase in ('exam','parity')}
    manifest['webshop_commit']=(ROOT/'.runtime/webshop-commit.txt').read_text().strip()
    manifest['official_reward_sha256']={name:file_digest(ROOT/'.runtime/WebShop/web_agent_site/engine'/name)
        for name in ('goal.py','normalize.py')}
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    prepare()

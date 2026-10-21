"""Expanded frozen parity instrument; original B0 timeline, read-only M0 states."""
import argparse
import copy
import csv
import hashlib
import json
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/m1_expanded'
RESULTS = ROOT / 'results_m1_expanded'
SEEDS = list(range(2030, 2038))
CHECKPOINTS = (0, 20)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def prepare():
    from validate_v2 import validate_inputs
    validate_inputs(ROOT)
    if (DATA / 'context.json').exists():
        raise RuntimeError('Expanded context already exists; refusing overwrite')
    from m1_run import load_everything
    from freeze_v2 import show_price
    from synthflood.select_env import SelectEnv
    by_asin, prices, goals, goals_by_asin = load_everything()
    base = read(ROOT / 'data/m1_v2/context.json')
    cache = read(ROOT / 'data/contamination/m1_parity_clones.json')
    exposed = {g['asin'] for g in base['exposure_goals'] + base['washout_goals']}
    selected, dispositions, quality = {}, [], {}
    for pi, pair in enumerate(base['pairs']):
        key, asin = str(pi), pair['gold_asin']
        reasons = []
        if key not in cache:
            reasons.append('no_archived_parity_clone')
        if asin not in goals_by_asin or asin not in by_asin:
            reasons.append('no_official_goal_or_product')
        if asin in exposed:
            reasons.append('gold_is_shopping_target')
        dispositions.append({'pair_idx': pi, 'gold_asin': asin, 'excluded_reasons': reasons})
        if reasons:
            continue
        if asin in base['goals_by_asin'] and goals_by_asin[asin] != base['goals_by_asin'][asin]:
            raise ValueError(f'Goal changed since v2: {asin}')
        if asin in base['product_prices'] and prices[asin] != base['product_prices'][asin]:
            raise ValueError(f'Price changed since v2: {asin}')
        clone = copy.deepcopy(cache[key])
        clone['price_float'] = round(prices[asin], 2)
        clone['item']['options'] = copy.deepcopy(by_asin[asin].get('options', {}))
        selected[key] = show_price(clone)
        gold = {'item': copy.deepcopy(by_asin[asin]), 'kind': 'gold', 'synthetic': False,
                'price_float': prices[asin]}
        gold = show_price(gold)
        values = []
        for candidate in (gold, selected[key]):
            env = SelectEnv(goals_by_asin[asin], [candidate], n_candidates=1)
            env.step('select[1]')
            values.append(env.reward()[0])
        quality[key] = {'gold_asin': asin, 'gold_reward': values[0], 'clone_reward': values[1]}
    if not set(base['parity_clones']) <= set(selected):
        raise ValueError('Old 36-pair subset is not preserved')
    for key, clone in base['parity_clones'].items():
        if clone != selected[key]:
            raise ValueError(f'Old candidate changed: {key}')
    for key in selected:
        asin = base['pairs'][int(key)]['gold_asin']
        gold = copy.deepcopy(by_asin[asin])
        gold['Price'] = f'${prices[asin]:.2f}'
        gold['price'] = prices[asin]
        base['by_asin'][asin] = gold
        base['product_prices'][asin] = prices[asin]
        base['goals_by_asin'][asin] = goals_by_asin[asin]
    base['parity_clones'] = selected
    base['protocol'] = 'original_B0_timeline_expanded_parity'
    # Check exact old-subset input hashes before any new inference is scheduled.
    from m1_run import duel_env
    old36 = list(read(ROOT / 'data/m1_v2/context.json')['parity_clones'])
    hash_checks = 0
    for seed in SEEDS:
        old_rows = list(csv.DictReader((ROOT/f'results_m1_v2/seed{seed}/m1_exams.csv').open()))
        hashes = {(r['arm'],r['checkpoint'],r['pair_idx']):r['input_sha256']
                  for r in old_rows if r['phase']=='parity'}
        for arm,cp in [('PRE',-1),('M0',0),('M0',20)]:
            memory = '' if arm=='PRE' else read(ROOT/f'results_m1_v2/seed{seed}/checkpoint_M0_{cp:02d}.json')['injected_context']
            for key in old36:
                pair=base['pairs'][int(key)];asin=pair['gold_asin']
                env=duel_env(pair,base['goals_by_asin'][asin],base['by_asin'][asin],
                             selected[key],base['product_prices'],random.Random(41000+int(key)))
                audit={'goal':base['goals_by_asin'][asin],'candidates':env.candidates,'memory':memory}
                actual=hashlib.sha256(json.dumps(audit,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                if actual!=hashes[arm,str(cp),key]:
                    raise ValueError(f'Old-subset input hash mismatch before inference: {seed}/{arm}/{cp}/{key}')
                hash_checks+=1
    sentinel = sorted(random.Random(2027).sample(list(selected), 16), key=int)
    sources = ['m1/expanded_parity.py', 'm1/expanded_summary.py', 'm1/EXPANDED_PARITY_PROTOCOL.md',
               'm1/slurm/expanded_run.sbatch', 'm1/slurm/expanded_prepare.sbatch',
               'm1/slurm/expanded_summary.sbatch', 'm1/m1_run.py', 'm1/m1_memory.py',
               'synthflood/select_env.py', 'synthflood/agent_react.py', 'synthflood/config.py',
               'synthflood/vllm_client.py', 'synthflood/ws_loader.py', 'm1/freeze_v2.py',
               'm1/summarize_v2.py', 'm1/audit_figure6.py',
               '.runtime/WebShop/web_agent_site/engine/goal.py',
               '.runtime/WebShop/web_agent_site/engine/normalize.py',
               'data/m1_v2/context.json', 'data/m1_v2/manifest.json',
               'data/contamination/m1_parity_clones.json']
    for seed in SEEDS:
        for cp in CHECKPOINTS:
            sources.append(f'results_m1_v2/seed{seed}/checkpoint_M0_{cp:02d}.json')
        sources.append(f'results_m1_v2/seed{seed}/m1_exams.csv')
    manifest = {'seeds': SEEDS, 'checkpoints': list(CHECKPOINTS), 'n_pairs': len(selected),
                'n_gold_asins': len({q['gold_asin'] for q in quality.values()}),
                'old36': list(read(ROOT / 'data/m1_v2/context.json')['parity_clones']),
                'sentinel_pairs': sentinel, 'dispositions': dispositions, 'quality': quality,
                'source_sha256': {name: digest(ROOT / name) for name in sources},
                'M0_source': 'read-only v2 checkpoint states; exams never update memory',
                'B0_source': 'fresh empty memory, washout20 only; no warmup',
                'no_new_pollution_generation': True,
                'old36_input_hash_checks': hash_checks,
                'backend': read(ROOT / 'data/m1_v2/manifest.json')['model_revision']}
    DATA.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(base, sort_keys=True, ensure_ascii=False).encode()
    (DATA / 'context.json').write_bytes(payload)
    manifest['context_sha256'] = hashlib.sha256(payload).hexdigest()
    (DATA / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: manifest[k] for k in ('n_pairs', 'n_gold_asins', 'context_sha256')}) + '\nPREPARED', flush=True)


def validate_inputs():
    manifest = read(DATA / 'manifest.json')
    if digest(DATA / 'context.json') != manifest['context_sha256']:
        raise ValueError('Expanded context changed')
    for name, expected in manifest['source_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f'Frozen source changed: {name}')
    return manifest


def validate_run(directory, manifest, seed):
    rows = list(csv.DictReader((directory / 'm1_exams.csv').open()))
    pairs = {str(d['pair_idx']) for d in manifest['dispositions'] if not d['excluded_reasons']}
    expected = {(arm, 'parity', str(cp), pi) for arm in ('M0', 'B0') for cp in CHECKPOINTS for pi in pairs}
    expected |= {('EMPTY_SENTINEL', 'sentinel', str(cp), pi) for cp in (-1, -2) for pi in manifest['sentinel_pairs']}
    keys = [(r['arm'], r['phase'], r['checkpoint'], r['pair_idx']) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('Missing/duplicate/unexpected exam rows')
    old = list(csv.DictReader((ROOT / f'results_m1_v2/seed{seed}/m1_exams.csv').open()))
    fields = ('chosen_kind', 'chose_clone', 'reward', 'purchased', 'input_sha256')
    old_index = {(r['arm'], r['phase'], r['checkpoint'], r['pair_idx']): tuple(r[k] for k in fields) for r in old}
    for r in rows:
        if r['phase'] != 'parity' or r['pair_idx'] not in manifest['old36']:
            continue
        old_key = ('M0', 'parity', r['checkpoint'], r['pair_idx']) if r['arm'] == 'M0' else ('PRE', 'parity', '-1', r['pair_idx'])
        if r['arm'] == 'B0' and r['checkpoint'] != '0':
            continue
        if tuple(r[k] for k in fields) != old_index[old_key]:
            raise ValueError(f'Old-subset input/outcome changed: {r["arm"]}/{r["checkpoint"]}/{r["pair_idx"]}')
    groups = {}
    for r in rows:
        groups.setdefault(r['input_sha256'], set()).add(tuple(r[k] for k in fields[:-1]))
    if any(len(values) > 1 for values in groups.values()):
        raise ValueError('Identical inputs produced inconsistent outcomes')
    episodes = list(csv.DictReader((directory / 'm1_episodes.csv').open()))
    if len(episodes) != 20 or {r['arm'] for r in episodes} != {'B0'} or {r['phase'] for r in episodes} != {'clean'}:
        raise ValueError('B0 timeline differs from clean20 only')
    zero = read(directory / 'checkpoint_B0_00.json')
    if zero['entries'] or zero['injected_context']:
        raise ValueError('B0 clean0 must be empty')
    return rows


def run():
    import m1_run as runner
    from m1_memory import MemoryStore
    manifest = validate_inputs()
    seed = int(os.environ['M1_SEED_BASE'])
    if seed not in SEEDS:
        raise ValueError('Unspecified seed')
    directory = Path(runner.OUT)
    if (directory / 'm1_exams.csv').exists() or (directory / 'mem_B0.json').exists():
        raise RuntimeError('Refusing to append/overwrite existing experiment')
    directory.mkdir(parents=True, exist_ok=True)
    ctx = read(DATA / 'context.json')
    indices = sorted(map(int, ctx['parity_clones']))
    cfg = {'notes': True, 'inject': True, 'lessons': True, 'correct': False}
    mem = MemoryStore(str(directory / 'mem_B0.json'), 'B0')
    client = runner.RateClient(runner.PORT, runner.MODEL)
    def exam(arm, cp, memory):
        runner.run_exams(ctx, arm, 'parity', cp, indices, ctx['parity_clones'], memory)
    def sentinel(cp):
        runner.run_exams(ctx, 'EMPTY_SENTINEL', 'sentinel', cp,
                         list(map(int, manifest['sentinel_pairs'])), ctx['parity_clones'], '')
    sentinel(-1)
    runner.save_checkpoint(mem, 'B0', 0, cfg)
    exam('B0', 0, '')
    for cp in CHECKPOINTS:
        source = ROOT / f'results_m1_v2/seed{seed}/checkpoint_M0_{cp:02d}.json'
        snapshot = read(source)
        (directory / f'checkpoint_M0_{cp:02d}.json').write_bytes(source.read_bytes())
        exam('M0', cp, snapshot['injected_context'])
        if cp == 0:
            for episode in range(20):
                runner.run_clean_episode(ctx, 'B0', cfg, episode, mem, client)
            runner.save_checkpoint(mem, 'B0', 20, cfg)
            exam('B0', 20, runner.memory_context(cfg, mem))
    sentinel(-2)
    rows = validate_run(directory, manifest, seed)
    (directory / 'COMPLETE.json').write_text(json.dumps({'seed': seed, 'main_exams': 4*len(indices),
        'sentinel_exams': 32, 'all_rows': len(rows), 'B0_episodes': 20, 'validated': True}, indent=2)+'\n')
    print('EXPANDED_RUN_COMPLETE', seed, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'validate', 'run'])
    args = parser.parse_args()
    {'prepare': prepare, 'validate': validate_inputs, 'run': run}[args.mode]()

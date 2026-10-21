"""Continue archived pollution40 with paired clean40; original empty B0."""
import argparse
import copy
import csv
import hashlib
import json
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/m1_washout40'
OUT = ROOT / 'results_m1_washout40'
SEEDS = list(range(2030, 2038))
CHECKPOINTS = tuple(range(0, 41, 2))
FIELDS = ('chosen_kind', 'chose_clone', 'reward', 'purchased', 'input_sha256')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def prepare():
    from exposure_length import validate_inputs as validate_previous, validate_results
    previous = validate_previous()
    if (DATA / 'context.json').exists():
        raise RuntimeError('Refusing to overwrite frozen washout40')
    for seed in SEEDS:
        directory = ROOT / f'results_m1_exposure_length/seed{seed}'
        if not read(directory / 'COMPLETE.json')['validated']:
            raise ValueError('Missing pollution40 source')
        validate_results(directory, previous, seed)
    from m1_run import load_everything
    from synthflood.select_env import build_task
    from freeze_v2 import show_price
    by_asin, prices, goals, goals_by_asin = load_everything()
    ctx = read(ROOT / 'data/m1_exposure_length/context.json')
    forbidden = {q['gold_asin'] for q in previous['quality'].values()}
    forbidden |= {g['asin'] for g in ctx['exposure_goals'] + ctx['washout_goals']}
    selected = []
    seen = set(forbidden)
    for index, goal in enumerate(goals):
        asin = goal['asin']
        if asin not in seen and asin in by_asin and asin in goals_by_asin:
            selected.append({'goal_index': index, 'asin': asin})
            seen.add(asin)
            if len(selected) == 20:
                break
    if len(selected) != 20:
        raise ValueError('Not enough new clean goals')
    new = [copy.deepcopy(goals_by_asin[g['asin']]) for g in selected]
    ctx['washout_goals'] += new
    for goal in new:
        asin = goal['asin']
        ctx['by_asin'][asin] = copy.deepcopy(by_asin[asin])
        ctx['product_prices'][asin] = prices[asin]
        ctx['goals_by_asin'][asin] = goal
    for seed in SEEDS:
        tasks = ctx['episode_tasks'][str(seed)]
        for ep in range(20, 40):
            draw = 60000 + ep + (seed - 2027) * 100000
            clean, _ = build_task(ctx['washout_goals'][ep], by_asin, 0.0, [], draw, n_candidates=10)
            clean = [show_price(c) for c in clean]
            order = list(range(10))
            random.Random(draw + 999999).shuffle(order)
            tasks[f'washout:{ep}'] = [clean[i] for i in order]
        for ep in range(40):
            clean = tasks[f'washout:{ep}']
            if len(clean) != 10 or any(c['synthetic'] for c in clean) or sum(c['kind'] == 'gold' for c in clean) != 1:
                raise ValueError('Clean candidates malformed/contaminated')
            if any(c['item']['Price'] != f"${c['price_float']:.2f}" for c in clean):
                raise ValueError('Price mismatch')
    old = read(ROOT / 'data/m1_expanded/context.json')
    for name in ('pairs', 'parity_clones'):
        assert ctx[name] == old[name]
    assert ctx['washout_goals'][:20] == old['washout_goals']
    assert len({g['asin'] for g in ctx['washout_goals']}) == 40
    for seed in SEEDS:
        for ep in range(20):
            assert ctx['episode_tasks'][str(seed)][f'washout:{ep}'] == old['episode_tasks'][str(seed)][f'washout:{ep}']
    ctx['protocol'] = 'pollution40_clean40_M0_B0'
    sources = dict(previous['source_sha256'])
    additional = ['m1/washout40.py', 'm1/washout40_summary.py', 'm1/WASHOUT40_PROTOCOL.md',
        'm1/slurm/washout40_prepare.sbatch', 'm1/slurm/washout40_run.sbatch', 'm1/slurm/washout40_summary.sbatch',
        'data/m1_exposure_length/context.json', 'data/m1_exposure_length/manifest.json']
    for seed in SEEDS:
        additional += [f'results_m1_exposure_length/seed{seed}/exposure_M0_040.json',
            f'results_m1_exposure_length/seed{seed}/m1_exams.csv']
    sources.update({name: sha(ROOT / name) for name in additional})
    payload = json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()
    manifest = {key: previous[key] for key in ('quality', 'old36', 'sentinel_pairs', 'n_pairs', 'n_gold_asins')}
    manifest.update({'seeds': SEEDS, 'checkpoints': CHECKPOINTS, 'context_sha256': hashlib.sha256(payload).hexdigest(),
        'source_sha256': sources, 'new_clean_targets': selected,
        'M0_start': 'archived measured pollution40 snapshot; no new pollution calls',
        'B0_start': 'empty; no prephase', 'new_clean_episodes_per_seed': 80,
        'new_main_exams_per_seed': 2 * len(CHECKPOINTS) * previous['n_pairs'], 'new_sentinels_per_seed': 32})
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / 'context.json').write_bytes(payload)
    (DATA / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    validate_inputs()
    print(json.dumps({key: manifest[key] for key in ('n_pairs', 'n_gold_asins', 'context_sha256', 'new_clean_targets')}) + '\nWASHOUT40_PREPARED', flush=True)


def validate_inputs():
    manifest = read(DATA / 'manifest.json')
    if sha(DATA / 'context.json') != manifest['context_sha256']:
        raise ValueError('Frozen washout context changed')
    for name, expected in manifest['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f'Frozen source changed: {name}')
    return manifest


def references(seed):
    old = rows(ROOT / f'results_m1_expanded/seed{seed}/m1_exams.csv')
    length = rows(ROOT / f'results_m1_exposure_length/seed{seed}/m1_exams.csv')
    return {arm: {r['pair_idx']: tuple(r[k] for k in FIELDS) for r in source
        if r['arm'] == arm and r['phase'] == 'parity' and r['checkpoint'] == cp}
        for arm, source, cp in [('M0', length, '40'), ('B0', old, '0')]}


def check_reference(measured, seed, sentinels_only=False):
    refs = references(seed)
    for r in measured:
        arm = 'B0' if r['phase'] == 'sentinel' else r['arm']
        if r['phase'] == 'sentinel' or (not sentinels_only and r['checkpoint'] == '0'):
            if tuple(r[k] for k in FIELDS) != refs[arm][r['pair_idx']]:
                raise ValueError(f'Archived baseline mismatch: {seed}/{arm}/{r["pair_idx"]}')


def validate_results(directory, manifest, seed):
    measured = rows(directory / 'm1_exams.csv')
    pairs = set(manifest['quality'])
    expected = {(a, 'parity', str(cp), pi) for a in ('M0', 'B0') for cp in CHECKPOINTS for pi in pairs}
    expected |= {('EMPTY_SENTINEL', 'sentinel', str(cp), pi) for cp in (-1, -2) for pi in manifest['sentinel_pairs']}
    keys = [(r['arm'], r['phase'], r['checkpoint'], r['pair_idx']) for r in measured]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('Missing/duplicate/unplanned exams')
    episodes = rows(directory / 'm1_episodes.csv')
    epkeys = [(r['arm'], r['phase'], int(r['ep_idx'])) for r in episodes]
    if len(epkeys) != 80 or set(epkeys) != {(a, 'clean', ep) for a in ('M0', 'B0') for ep in range(40)}:
        raise ValueError('Incorrect clean shopping timeline')
    source = read(ROOT / f'results_m1_exposure_length/seed{seed}/exposure_M0_040.json')['entries']
    for arm in ('M0', 'B0'):
        for cp in CHECKPOINTS:
            snapshot = read(directory / f'checkpoint_{arm}_{cp:02d}.json')
            entries = snapshot['entries']
            prefix = source if arm == 'M0' else []
            if entries[:len(prefix)] != prefix:
                raise ValueError('Pollution40 prefix changed')
            tail = entries[len(prefix):]
            if [e['t'] for e in tail if e['type'] == 'observation'] != list(range(1000, 1000 + cp)):
                raise ValueError('Missing/unexpected clean observations')
            if len(tail) != cp + cp // 5 or sum(e['type'] == 'lesson' for e in tail) != cp // 5:
                raise ValueError('Incorrect lesson count')
            from m1_memory import MemoryStore
            mem = MemoryStore('/nonexistent/washout40_validation', arm)
            mem.entries = entries
            if snapshot['injected_context'] != mem.inject_context():
                raise ValueError('Snapshot does not describe actual memory')
    if read(directory / 'checkpoint_B0_00.json')['entries']:
        raise ValueError('B0 must start empty')
    check_reference(measured, seed)
    groups = {}
    for r in measured:
        groups.setdefault(r['input_sha256'], set()).add(tuple(r[k] for k in FIELDS[:-1]))
    if any(len(v) > 1 for v in groups.values()):
        raise ValueError('Inconsistent identical model inputs')
    return measured


def run():
    import m1_run as runner
    from m1_memory import MemoryStore
    manifest = validate_inputs()
    seed = int(os.environ['M1_SEED_BASE'])
    if seed not in SEEDS:
        raise ValueError('Unplanned seed')
    directory = Path(runner.OUT)
    if (directory / 'm1_exams.csv').exists() or any((directory / f'mem_{a}.json').exists() for a in ('M0', 'B0')):
        raise RuntimeError('Refusing overwrite/append')
    directory.mkdir(parents=True, exist_ok=True)
    ctx = read(DATA / 'context.json')
    cfg = dict(notes=True, inject=True, lessons=True, correct=False)
    client = runner.RateClient(runner.PORT, runner.MODEL)
    memories = {a: MemoryStore(str(directory / f'mem_{a}.json'), a) for a in ('M0', 'B0')}
    source = ROOT / f'results_m1_exposure_length/seed{seed}/exposure_M0_040.json'
    initial = read(source)
    memories['M0'].entries = copy.deepcopy(initial['entries'])
    if memories['M0'].inject_context() != initial['injected_context']:
        raise ValueError('Initial M0 state differs')
    (directory / 'initial_source.json').write_text(json.dumps({'path': str(source.relative_to(ROOT)), 'sha256': sha(source)}, indent=2) + '\n')
    def sentinel(cp):
        runner.run_exams(ctx, 'EMPTY_SENTINEL', 'sentinel', cp, list(map(int, manifest['sentinel_pairs'])), ctx['parity_clones'], '')
    sentinel(-1)
    check_reference(rows(directory / 'm1_exams.csv'), seed, sentinels_only=True)
    done = 0
    for cp in CHECKPOINTS:
        while done < cp:
            for arm in ('M0', 'B0'):
                runner.run_clean_episode(ctx, arm, cfg, done, memories[arm], client)
            done += 1
        for arm in ('M0', 'B0'):
            runner.save_checkpoint(memories[arm], arm, cp, cfg)
            runner.run_exams(ctx, arm, 'parity', cp, sorted(map(int, ctx['parity_clones'])), ctx['parity_clones'], memories[arm].inject_context())
        if cp == 0:
            check_reference(rows(directory / 'm1_exams.csv'), seed)
    sentinel(-2)
    measured = validate_results(directory, manifest, seed)
    (directory / 'COMPLETE.json').write_text(json.dumps({'seed': seed, 'validated': True, 'new_clean_episodes': 80,
        'new_main_exams': manifest['new_main_exams_per_seed'], 'new_sentinels': 32, 'all_rows': len(measured)}, indent=2) + '\n')
    print('WASHOUT40_RUN_COMPLETE', seed, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'validate', 'run'))
    mode = parser.parse_args().mode
    {'prepare': prepare, 'validate': validate_inputs, 'run': run}[mode]()

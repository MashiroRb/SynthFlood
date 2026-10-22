"""Two-pass catalog selection using bounded memory, with unchanged loader semantics."""
import collections
import copy
import json
import random
import re
from decimal import Decimal
from pathlib import Path

from .common import ROOT, DATA, OUT, SEEDS, COUNTS, ROTATIONS, LANES, EXCLUDED, ARMS, REVISION
from .common import rng, uniform, digest, file_sha, read, write, candidates


def array_items(path, chunk_size=4 * 1024 * 1024):
    decoder = json.JSONDecoder()
    with Path(path).open() as stream:
        buffer = ''; offset = 0; started = False; ended = False
        while True:
            if not started:
                buffer += stream.read(chunk_size)
                offset = len(buffer) - len(buffer.lstrip())
                if offset == len(buffer):
                    raise ValueError('Empty JSON input')
                if buffer[offset] != '[':
                    raise ValueError('Expected array')
                offset += 1; started = True
            while offset < len(buffer) and buffer[offset] in ' \r\n\t,':
                offset += 1
            if offset < len(buffer) and buffer[offset] == ']':
                return
            try:
                item, end = decoder.raw_decode(buffer, offset)
            except json.JSONDecodeError:
                if ended:
                    raise
                buffer = buffer[offset:]
                offset = 0
                addition = stream.read(chunk_size)
                ended = not addition
                buffer += addition
                continue
            yield item
            offset = end
            if offset >= chunk_size:
                buffer = buffer[offset:]
                offset = 0


def pricing_values(value):
    if not value:
        return [100.0]
    return [float(Decimal(re.sub(r'[^\d.]', '', s))) for s in value.split('$')[1:]][:2]


def prepare():
    if (DATA / 'manifest.json').exists() or OUT.exists():
        raise RuntimeError('Refusing to overwrite frozen inputs or results')
    DATA.mkdir(parents=True, exist_ok=True)
    goals_all = read(ROOT / 'data/contamination/goals100.json')
    pool = read(ROOT / 'data/contamination/pool.json')
    eligible = [i for i in range(100) if len({b['asin'] for b in pool.get(str(i), [])}) >= 6]
    if len(eligible) != 98 or set(range(100)) - set(eligible) != set(EXCLUDED):
        raise ValueError('Eligibility changed; review protocol before inference')
    fine_needed = {goals_all[i]['product_category'] for i in eligible}
    coarse_needed = {goals_all[i]['category'] for i in eligible}
    fine = collections.defaultdict(list); coarse = collections.defaultdict(list)
    seen = set(); prices = {}; categories = {}
    price_rng = random.Random(2027)
    raw_path = ROOT / 'data/official/items_shuffle.json'
    for raw in array_items(raw_path):
        asin = raw['asin']
        if asin == 'nan' or len(asin) > 10 or asin in seen:
            continue
        seen.add(asin)
        values = pricing_values(raw.get('pricing'))
        # Consume the price stream in the full official, deduplicated order.
        price = (100.0 if not values else values[0] if len(values) == 1 else price_rng.uniform(*values))
        if raw['category'] in coarse_needed or raw['product_category'] in fine_needed:
            prices[asin] = price
            categories[asin] = (raw['product_category'], raw['category'])
        if raw['product_category'] in fine_needed:
            fine[raw['product_category']].append(asin)
        if raw['category'] in coarse_needed:
            coarse[raw['category']].append(asin)
    selected = {goals_all[i]['asin'] for i in eligible}
    draws = {}
    for seed in SEEDS:
        for gi in eligible:
            goal = goals_all[gi]; gold = goal['asin']
            options = [a for a in fine[goal['product_category']] if a != gold]
            if len(options) < 9:
                options += [a for a in coarse[goal['category']] if a != gold and categories[a][0] != goal['product_category']]
            if len(options) < 9:
                raise ValueError(f'Too few real candidates: {gi}')
            sampled = rng('real_candidates', seed, gi).sample(options, 9)
            draws[seed, gi] = sampled
            selected.update(sampled)
    print('CATALOG_INDEXED', len(seen), 'selected', len(selected), flush=True)
    # Release broad indexes before normalization of the selected catalog.
    del fine, coarse, categories, seen
    selected_raw = []; found = set()
    for raw in array_items(raw_path):
        asin = raw['asin']
        if asin in selected and asin not in found:
            selected_raw.append(raw); found.add(asin)
    if found != selected:
        raise ValueError('Missing selected product')
    selected_file = DATA / 'selected_raw.json'
    write(selected_file, selected_raw)
    del selected_raw
    from synthflood.ws_loader import load_products
    _, products, _, _ = load_products(str(selected_file), str(ROOT / 'data/official/items_ins_v2.json'),
        str(ROOT / 'data/official/items_human_ins.json'))
    from synthflood.contaminate import _as_candidate
    from synthflood.select_env import SelectEnv
    blocks = []
    def real_candidate(asin, kind, gi, seed):
        item = copy.deepcopy(products[asin])
        value = round(prices[asin], 2)
        item['Price'] = f'${value:.2f}'; item['price'] = value
        return {'cid': f'real:{asin}', 'item': item, 'kind': kind, 'synthetic': False,
            'price_float': value, 'source_u': uniform('source', seed, gi, asin)}
    def reward(goal, candidate):
        env = SelectEnv(goal, [candidate], n_candidates=1)
        env.step('select[1]')
        return env.reward()[0]
    for seed in SEEDS:
        for gi in eligible:
            goal = copy.deepcopy(goals_all[gi])
            base = [real_candidate(goal['asin'], 'gold', gi, seed)]
            base += [real_candidate(a, 'real', gi, seed) for a in draws[seed, gi]]
            original = {b['asin']: b for b in pool[str(gi)]}
            ids = list(original)
            rng('synthetics', seed, gi).shuffle(ids)
            synthetics = []
            for asin in ids[:6]:
                raw = original[asin]
                candidate = _as_candidate(copy.deepcopy(raw))
                # User constraint: neither inherit nor repair missing options.
                if candidate['item'].get('options') != raw.get('options'):
                    raise ValueError('Synthetic options changed')
                value = round(candidate['price_float'], 2)
                candidate['price_float'] = value
                candidate['item']['Price'] = f'${value:.2f}'
                candidate['item']['price'] = value
                candidate['cid'] = f'synthetic:{asin}'
                candidate['source_u'] = uniform('source', seed, gi, asin)
                synthetics.append(candidate)
            if len(synthetics) != 6 or len({c['cid'] for c in synthetics}) != 6:
                raise ValueError('Repeated or missing synthetic listing')
            block = {'seed': seed, 'task_id': gi, 'goal': goal, 'base': base, 'synthetics': synthetics,
                'replace_order': rng('replace_slots', seed, gi).sample(list(range(1, 10)), 9)}
            block['reward_by_cid'] = {c['cid']: reward(goal, c) for c in base + synthetics}
            block['gold_reward'] = block['reward_by_cid'][base[0]['cid']]
            blocks.append(block)
    rng('lane_assignment', 2027).shuffle(blocks)
    lanes = {i: [] for i in range(LANES)}
    for index, block in enumerate(blocks):
        lanes[index % LANES].append(block)
    for lane, subset in lanes.items():
        write(DATA / f'lane{lane}.json', subset)
    # Check slot identity, synthetic nesting, all ten ranks, and gold presence.
    checks = 0
    for block in blocks:
        for rotation in ROTATIONS:
            clean = candidates(block, 0, rotation)
            previous = {}
            for k in COUNTS:
                current = candidates(block, k, rotation)
                changed = [i for i, (a, b) in enumerate(zip(clean, current)) if a['cid'] != b['cid']]
                assert len(changed) == k
                assert sum(c['kind'] == 'gold' for c in current) == 1
                for i, a in enumerate(clean):
                    if i not in changed:
                        assert a == current[i]
                where = {c['cid']: i for i, c in enumerate(current) if c['synthetic']}
                assert all(where[cid] == position for cid, position in previous.items())
                previous = where; checks += 1
        for k in COUNTS:
            ranks = collections.defaultdict(set)
            for rotation in ROTATIONS:
                for rank, candidate in enumerate(candidates(block, k, rotation)):
                    ranks[candidate['cid']].add(rank)
            assert all(len(v) == 10 for v in ranks.values())
    sources = [p for p in (ROOT / 'paired_sweep').rglob('*') if p.is_file() and p.suffix in ('.py','.md','.sbatch','.sh')]
    sources += [ROOT / 'synthflood' / n for n in ('select_env.py','ws_loader.py','agent_react.py','vllm_client.py','runlog.py','config.py','defenses.py','contaminate.py')]
    sources += [ROOT / 'data/contamination' / n for n in ('goals100.json','pool.json')]
    sources += [ROOT / 'm1/server_ready.py']
    sources += [ROOT / '.runtime/WebShop/web_agent_site/engine' / n for n in ('goal.py','normalize.py')]
    manifest = {'protocol': 'paired_sweep/PROTOCOL.md', 'n_tasks': 98, 'eligible_task_ids': eligible,
        'excluded_task_ids': list(EXCLUDED), 'seeds': list(SEEDS), 'counts': list(COUNTS), 'rotations': list(ROTATIONS),
        'nominal_eps': [0,.25,.5,.75], 'actual_fraction_nongold': [k/9 for k in COUNTS],
        'lanes': LANES, 'arms': list(ARMS), 'model_revision': REVISION,
        'main_rows': len(blocks)*len(COUNTS)*10, 'defense_rows': len(blocks)*2*10*len(ARMS),
        'main_rows_by_lane': {str(i): len(v)*40 for i,v in lanes.items()},
        'defense_rows_by_lane': {str(i): len(v)*20*len(ARMS) for i,v in lanes.items()},
        'lane_sha256': {str(i): file_sha(DATA/f'lane{i}.json') for i in lanes},
        'source_sha256': {str(p.relative_to(ROOT)): file_sha(p) for p in sources},
        'official_inputs_sha256': {n: file_sha(ROOT/'data/official'/n) for n in ('items_shuffle.json','items_ins_v2.json','items_human_ins.json')},
        'options_policy': 'No repair, no inheritance, unchanged reward and best_variant_options implementation',
        'slot_invariant_checks': checks, 'duplicate_topups': 0,
        'price_policy': 'Official full-catalog seeded2027 stream, rounded to cents; displayed candidate scalar equals reward price',
        'sampling_policy': 'Distinct seeded per-task draws; same fine category, coarse fallback only if short',
        'source_bits': 'One fixed uniform per task/seed/candidate; real coverage .85, default synthetic .15'}
    write(DATA / 'manifest.json', manifest)
    print('PAIRED_N98_FROZEN', json.dumps({k: manifest[k] for k in ('n_tasks','main_rows','defense_rows','slot_invariant_checks')}), flush=True)


if __name__ == '__main__':
    prepare()

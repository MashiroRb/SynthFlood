"""All catalog work runs in a CPU Slurm job with bounded catalog memory."""
import collections
import copy
import random

from .common import *
from .audit import audit


def synthetic(raw, seed, gi):
    from synthflood.contaminate import _as_candidate
    c = _as_candidate(copy.deepcopy(raw))
    c['cid'] = 'synthetic:' + raw['asin']
    c['price_float'] = round(c['price_float'], 2)
    c['item']['Price'] = f"${c['price_float']:.2f}"
    c['item']['price'] = c['price_float']
    c['source_u'] = uniform('source', seed, gi, raw['asin'])
    assert c['item'].get('options') == raw.get('options')
    return c


def clone_variant(items, gold, condition):
    from synthflood.product_metadata import rating_and_count
    result = copy.deepcopy(items)
    rating = rating_and_count(gold['item'])[0]
    for c in result:
        if condition in ('price100', 'joint', 'price90', 'price80', 'price70'):
            ratio = {'price90': .9, 'price80': .8, 'price70': .7}.get(condition, 1.)
            value = round(gold['price_float'] * ratio, 2)
            c['price_float'] = value
            c['item']['price'] = value
            c['item']['Price'] = f'${value:.2f}'
        if condition in ('rating', 'joint'):
            # Clear every recognized rating alias so missing gold cannot fall back
            # to an original clone rating. Counts and review text stay identical.
            for key in ('Rating', 'average_rating', 'star5_ratios', 'rating'):
                if key in c['item'] or key == 'Rating':
                    c['item'][key] = rating
    return result


def check_candidates(items, n, synth_count):
    assert len(items) == n
    assert len({c['item']['asin'] for c in items}) == n
    assert sum(c['kind'] == 'gold' for c in items) == 1
    assert sum(bool(c['synthetic']) for c in items) == synth_count
    for c in items:
        assert c['item']['Price'] == f"${c['price_float']:.2f}"


def prepare():
    if (DATA / 'prepared.json').exists() or (DATA / 'manifest.json').exists():
        raise RuntimeError('Refusing to overwrite versioned prepared inputs')
    audit()
    eligibility = read(DATA / 'eligibility_audit.json')
    pool = read(ROOT / 'data/contamination/pool.json')
    blocks = []
    for lane in range(8):
        subset = read(PARENT / f'lane{lane}.json')
        for b in subset:
            b['lane'] = lane
        blocks += subset
    lookup = {(b['seed'], b['task_id']): b for b in blocks}
    typed = {}
    for b in blocks:
        gi, seed = b['task_id'], b['seed']
        typed[f'{seed}:{gi}'] = {}
        unique = {p['asin']: p for p in pool[str(gi)]}
        for f in FAMILIES:
            if gi not in eligibility['eligible'][f]:
                continue
            ids = [a for a, p in unique.items() if p['family'] == f]
            rng('single_type', seed, gi, f).shuffle(ids)
            values = [synthetic(unique[a], seed, gi) for a in ids[:4]]
            typed[f'{seed}:{gi}'][f] = values
            for rotation in range(10):
                check_candidates(replace(b, values, rotation), 10, 4)
            if f == 'clone':
                for condition in ('original', 'price100', 'rating', 'joint', 'price90', 'price80', 'price70'):
                    varied = clone_variant(values, b['base'][0], condition)
                    for old, new in zip(values, varied):
                        assert old['reviews'] == new['reviews']
                        assert old['cid'] == new['cid']
                        assert {k:v for k,v in old.items() if k not in ('item','price_float')} == {k:v for k,v in new.items() if k not in ('item','price_float')}
                        permitted = {'price','Price'} if condition in ('price100','price90','price80','price70') else set()
                        if condition in ('rating','joint'):
                            permitted |= {'Rating','rating','average_rating','star5_ratios'}
                        if condition == 'joint':
                            permitted |= {'price','Price'}
                        assert {k:v for k,v in old['item'].items() if k not in permitted} == {k:v for k,v in new['item'].items() if k not in permitted}
    probes = []
    for gi in eligibility['tasks']:
        b = lookup[1, gi]
        for pi in range(10):
            pair_seed = 9000 + gi*100 + pi
            # Exactly the existing P1 selection and order RNG streams.
            raw = list(pool[str(gi)])
            random.Random(pair_seed).shuffle(raw)
            pair = [copy.deepcopy(b['base'][0]), synthetic(raw[0], pair_seed, gi)]
            random.Random(pair_seed).shuffle(pair)
            check_candidates(pair, 2, 1)
            probes.append(dict(task_id=gi, pair_seed=pair_seed, family=raw[0]['family'], goal=b['goal'], candidates=pair))
    pollution_ids = rng('washout_pollution_targets', 20261023).sample(eligibility['washout_eligible'], 40)
    clean_ids = rng('washout_clean_targets', 20261023).sample([i for i in eligibility['tasks'] if i not in pollution_ids], 40)
    assert not set(pollution_ids) & set(clean_ids)
    write(DATA / 'blocks.json', blocks)
    write(DATA / 'typed.json', typed)
    write(DATA / 'probes.json', probes)
    # Index only identities/categories/prices; normalize selected products only.
    from paired_sweep.freeze import array_items, pricing_values
    human = read(ROOT / 'data/official/items_human_ins.json')
    target_asins = {b['goal']['asin'] for b in blocks}
    needed_goals = {i: lookup[1, i]['goal'] for i in pollution_ids + clean_ids}
    fines = {g['product_category'] for g in needed_goals.values()}
    coarses = {g['category'] for g in needed_goals.values()}
    fine = collections.defaultdict(list)
    coarse = collections.defaultdict(list)
    cats = {}
    prices = {}
    human_raw = {}
    seen = set()
    price_rng = random.Random(2027)
    raw_path = ROOT / 'data/official/items_shuffle.json'
    for p in array_items(raw_path):
        a = p['asin']
        if a == 'nan' or len(a) > 10 or a in seen:
            continue
        seen.add(a)
        vs = pricing_values(p.get('pricing'))
        value = vs[0] if len(vs) == 1 else price_rng.uniform(*vs)
        if p['product_category'] in fines or p['category'] in coarses or a in human:
            prices[a] = round(value, 2)
            cats[a] = (p['product_category'], p['category'])
        if p['product_category'] in fines:
            fine[p['product_category']].append(a)
        if p['category'] in coarses:
            coarse[p['category']].append(a)
        if a in human and a not in target_asins and any(x.get('instruction_attributes') for x in human[a]):
            human_raw[a] = p
    del seen
    # Greedy category matching to shuffled N98 target category slots; the two
    # extra slots use seeded N98 draws. Report every coarse/global fallback.
    targets = [lookup[1, i]['goal'] for i in eligibility['tasks']]
    rng('exam_category_slots', 20261023).shuffle(targets)
    targets += rng('exam_extra_slots', 20261023).sample(targets, 2)
    available = list(human_raw)
    rng('exam_target_selection', 20261023).shuffle(available)
    chosen = []
    matching = []
    for g in targets:
        exact = [a for a in available if cats[a][0] == g['product_category']]
        same = [a for a in available if cats[a][1] == g['category']]
        candidates = exact or same or available
        if not candidates:
            raise ValueError('Insufficient distinct official exam targets')
        a = candidates[0]
        chosen.append(a)
        matching.append(dict(asin=a, desired=g['product_category'], actual=cats[a][0],
                             match='fine' if exact else 'coarse' if same else 'global'))
        available.remove(a)
    assert len(set(chosen)) == 100 and not set(chosen) & target_asins
    selected = set(chosen)
    draws = {}
    for seed in SEEDS:
        for gi, g in needed_goals.items():
            options = [a for a in fine[g['product_category']] if a != g['asin']]
            if len(options) < 9:
                options += [a for a in coarse[g['category']] if a != g['asin'] and cats[a][0] != g['product_category']]
            if len(options) < 9:
                raise ValueError('Too few real distractors')
            draws[seed, gi] = rng('real_candidates', seed, gi).sample(options, 9)
            selected.update(draws[seed, gi])
            selected.add(g['asin'])
    del fine, coarse, cats
    selected_raw = []
    found = set()
    for p in array_items(raw_path):
        if p['asin'] in selected and p['asin'] not in found:
            selected_raw.append(p)
            found.add(p['asin'])
    assert found == selected
    write(DATA / 'selected_raw.json', selected_raw)
    del selected_raw, human_raw
    from synthflood.ws_loader import load_products
    all_products, products, _, _ = load_products(str(DATA / 'selected_raw.json'),
        str(ROOT / 'data/official/items_ins_v2.json'), str(ROOT / 'data/official/items_human_ins.json'))
    def real(a, kind, gi, seed):
        item = copy.deepcopy(products[a])
        item['price'] = prices[a]
        item['Price'] = f'${prices[a]:.2f}'
        return dict(cid='real:'+a, item=item, kind=kind, synthetic=False,
                    price_float=prices[a], source_u=uniform('source', seed, gi, a))
    wash = {}
    for seed in SEEDS:
        phases = {}
        for phase, ids in [('pollution', pollution_ids), ('clean', clean_ids)]:
            plans = []
            for ep, gi in enumerate(ids):
                goal = needed_goals[gi]
                b = dict(seed=seed, task_id=gi, goal=goal,
                    base=[real(goal['asin'], 'gold', gi, seed)] + [real(a, 'real', gi, seed) for a in draws[seed, gi]],
                    replace_order=rng('replace_slots', seed, gi).sample(list(range(1,10)), 9))
                synths = []
                if phase == 'pollution':
                    unique = {p['asin']:p for p in pool[str(gi)]}
                    for f in FAMILIES:
                        ids_f = [a for a,p in unique.items() if p['family'] == f]
                        rng('washout_typed', seed, gi, f).shuffle(ids_f)
                        synths += [synthetic(unique[a], seed, gi) for a in ids_f[:2]]
                values = replace(b, synths, ep % 10)
                check_candidates(values, 10, 6 if phase == 'pollution' else 0)
                plans.append(dict(task_id=gi, goal=goal, candidates=values, rotation=ep%10,
                                  base=b['base'], replace_order=b['replace_order']))
            phases[phase] = plans
        wash[str(seed)] = phases
    random.seed(20261023)
    from web_agent_site.engine.goal import get_human_goals
    selected_products = [products[a] for a in chosen]
    official_goals = get_human_goals(selected_products, prices)
    by_asin = collections.defaultdict(list)
    for g in official_goals:
        by_asin[g['asin']].append(g)
    exam_targets = []
    for i, a in enumerate(chosen):
        g = copy.deepcopy(rng('exam_instruction', 20261023, a).choice(by_asin[a]))
        exam_targets.append(dict(task_id=i, goal=g, gold=real(a, 'gold', i, 20261023)))
    write(DATA / 'exam_targets.json', exam_targets)
    write(DATA / 'washout.json', wash)
    write(DATA / 'sampling.json', dict(pollution_ids=pollution_ids, clean_ids=clean_ids,
        exam_category_matches=matching, sampling_seed=20261023,
        exam_category_counts=dict(collections.Counter(t['goal']['product_category'] for t in exam_targets)),
        rotation_plan=[i%10 for i in range(40)]))
    write(DATA / 'prepared.json', dict(parent_manifest_sha256=file_sha(PARENT/'manifest.json'),
        official_sha256={n:file_sha(ROOT/'data/official'/n) for n in ('items_shuffle.json','items_ins_v2.json','items_human_ins.json')},
        counts=dict(main=7840, probe=980, single_clean=4800, single_polluted=4800,
                    clone_additional=9000, defense=58800, washout_shopping=960, exam=100800)))
    print('V3_PREPARED', flush=True)


if __name__ == '__main__':
    prepare()

"""Case definitions are deterministic and independent of purchase outcomes."""
from .common import *
from .prepare import clone_variant


def cases(blocks, typed, probes, eligibility, lane):
    for b in blocks:
        if b['lane'] != lane:
            continue
        gi, seed = b['task_id'], b['seed']
        for k in (0, 2, 4, 6):
            for r in range(10):
                yield dict(phase='main', condition=f'k{k}', task_id=gi, seed=seed, rotation=r, k=k,
                           family='mix', block=b, candidates=replace(b, b['synthetics'][:k], r), arm='none')
        for f in FAMILIES:
            if gi not in eligibility['eligible'][f]:
                continue
            synths = typed[f'{seed}:{gi}'][f]
            for k in (0, 4):
                for r in range(10):
                    yield dict(phase='single', condition=f'{f}:k{k}', task_id=gi, seed=seed, rotation=r,
                               k=k, family=f, block=b, candidates=replace(b, synths[:k], r), arm='none')
            if f == 'clone':
                for condition in ('original', 'price100', 'rating', 'joint', 'price90', 'price80', 'price70'):
                    values = clone_variant(synths, b['base'][0], condition)
                    for r in range(10):
                        yield dict(phase='clone', condition=condition, task_id=gi, seed=seed, rotation=r,
                                   k=4, family=f, block=b, candidates=replace(b, values, r), arm='none')
    for p in probes:
        # A probe is an independent frozen pair; pair_seed is not an extra
        # environment replicate and does not multiply its planned 980 records.
        if p['task_id'] % 8 == lane:
            yield dict(phase='probe', condition=p['family'], task_id=p['task_id'], seed=p['pair_seed'],
                       rotation=0, k=1, family=p['family'], block=dict(goal=p['goal']),
                       candidates=p['candidates'], arm='none')


def key(case):
    return ':'.join(str(case[x]) for x in ('phase', 'condition', 'task_id', 'seed', 'rotation'))


def request_definition(case, final, extra, memory=''):
    from .executor import SYSTEM
    # Complete deterministic request-generating state, not merely candidate IDs.
    return dict(goal=case['block']['goal'], candidates=final, extra=extra, memory=memory,
                model=MODEL, revision=REVISION, temperature=0, request_seed=0,
                system=SYSTEM, effective_view_budget=6 if case['phase'] in ('probe','exam') else 30,
                corrections=3, max_tokens=300, context=CONTEXT if case['phase'] in ('exam','shopping') else STATELESS_CONTEXT,
                rope_scaling=dict(type='yarn', factor=4.0, original_max_position_embeddings=32768))

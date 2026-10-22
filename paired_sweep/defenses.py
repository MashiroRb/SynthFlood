"""Controlled postprocessing; all methods consume independent frozen copies."""
import copy
import math

from synthflood.defenses import structural_score, _page_text
from synthflood.agent_react import DEFENSE_PROMPT
from synthflood.select_env import product_fields
from .common import COMMON_PROMPT, rng, digest


def visible_number(candidate, field):
    try:
        value = float(product_fields(candidate['item'])[field])
        return value if math.isfinite(value) else 0.0
    except (ValueError, TypeError):
        return 0.0


def kept_by_score(items, scores, threshold):
    ids = {c['cid'] for c in items if scores[c['cid']] < threshold}
    fallback = len(ids) < 2
    if fallback:
        ranked = sorted(items, key=lambda c: (scores[c['cid']], digest(c['cid'])))
        ids = {c['cid'] for c in ranked[:2]}
    return [c for c in items if c['cid'] in ids], fallback


def transform(block, raw, k, rotation, arm, ppl):
    items = copy.deepcopy(raw)
    extra = COMMON_PROMPT
    metadata = {'arm': arm, 'fallback': False, 'input_count': len(items)}
    if arm == 'none':
        return items, extra, metadata
    if arm == 'prompt':
        return items, extra + DEFENSE_PROMPT['prompt'], metadata
    if arm in ('detector_struct', 'random_struct'):
        scores = {c['cid']: structural_score(c['item'], c.get('reviews', [])) for c in items}
        kept, fallback = kept_by_score(items, scores, .55)
        metadata.update(fallback=fallback, filter_scores=scores)
        if arm == 'detector_struct':
            return kept, extra, metadata
        n_keep = len(kept)
    elif arm in ('detector_text', 'random_text'):
        scores = {c['cid']: ppl[c['cid']]['ppl'] for c in items}
        kept, fallback = kept_by_score(items, scores, 15.0)
        metadata.update(fallback=fallback, filter_scores=scores)
        if arm == 'detector_text':
            return kept, extra, metadata
        n_keep = len(kept)
    elif arm == 'random30':
        n_keep = len(items) - int(.3 * len(items))
    else:
        n_keep = None
    if n_keep is not None:
        # No protected position or gold exemption. Select on candidate identity.
        ordered = sorted(items, key=lambda c: c['cid'])
        selected = rng('random_deletion', block['seed'], block['task_id'], k, rotation, arm).sample(ordered, n_keep)
        ids = {c['cid'] for c in selected}
        return [c for c in items if c['cid'] in ids], extra, metadata
    if arm == 'reviewtrust':
        return sorted(items, key=lambda c: -(visible_number(c, 'rating') * math.log1p(max(0, visible_number(c, 'nrev'))))), extra, metadata
    if arm not in ('provenance','provenance_order','provenance_badge','oracle') and not arm.startswith(('ppr_', 'spoof')):
        raise ValueError(f'Unknown arm: {arm}')
    rate = int(arm[5:]) / 100 if arm.startswith('spoof') else .15
    def verified(c):
        return not c['synthetic'] if arm == 'oracle' else c['source_u'] < (rate if c['synthetic'] else .85)
    badge = arm != 'provenance_order'
    for c in items:
        if badge and verified(c):
            c['prov_badge'] = True
    if arm == 'provenance_badge':
        ranked = items
    elif arm.startswith('ppr_'):
        weight = float(arm.split('_')[1])
        ranked = sorted(items, key=lambda c: -(visible_number(c, 'rating') + weight * verified(c)))
    else:
        ranked = [c for c in items if verified(c)] + [c for c in items if not verified(c)]
    if {c['cid'] for c in ranked} != {c['cid'] for c in raw}:
        raise ValueError('Reranker changed candidate identities')
    return ranked, extra, metadata

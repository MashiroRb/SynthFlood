"""CPU-only Slurm audit; no inference and no edits to parent inputs."""
import collections
from .common import *


def audit():
    manifest = read(PARENT / 'manifest.json')
    pool = read(ROOT / 'data/contamination/pool.json')
    goals = read(ROOT / 'data/contamination/goals100.json')
    for name in ('data/contamination/pool.json', 'data/contamination/goals100.json'):
        assert file_sha(ROOT / name) == manifest['source_sha256'][name], name
    blocks = []
    for lane in range(8):
        path = PARENT / f'lane{lane}.json'
        assert file_sha(path) == manifest['lane_sha256'][str(lane)]
        blocks += read(path)
    task_ids = sorted({b['task_id'] for b in blocks})
    assert len(blocks) == 196 and len(task_ids) == 98
    details = []
    eligible = {f: [] for f in FAMILIES}
    washout = []
    from synthflood.product_metadata import rating_and_count, restore_raw_metadata
    from synthflood.select_env import product_fields, item_page, results_page
    raw = {p['asin']: p for p in read(PARENT / 'selected_raw.json')}
    coverage = collections.Counter()
    for b in blocks:
        assert b['goal'] == goals[b['task_id']]
        for c in b['base']:
            restored = restore_raw_metadata(c['item'], raw[c['item']['asin']])
            assert c['item'] == restored, 'Parent metadata repair missing'
            rating, count = rating_and_count(restored)
            fields = product_fields(restored)
            assert fields['rating'] == (rating if rating is not None else 'n/a')
            assert fields['nrev'] == (count if count is not None else 'n/a')
            assert f"Rating: {fields['rating']} ({fields['nrev']} reviews)" in item_page(c)
            assert 'rating:' in results_page([c])
            coverage['real_instances'] += 1
            coverage['known_rating'] += rating is not None
            coverage['known_review_count'] += count is not None
    for gi in task_ids:
        unique = {p['asin']: p for p in pool[str(gi)]}
        counts = {f: sum(p.get('family') == f for p in unique.values()) for f in FAMILIES}
        details.append({'task_id': gi, 'target_asin': goals[gi]['asin'], 'distinct_by_type': counts})
        for f in FAMILIES:
            if counts[f] >= 4:
                eligible[f].append(gi)
        if all(counts[f] >= 2 for f in FAMILIES):
            washout.append(gi)
    assert {f: len(ids) for f, ids in eligible.items()} == dict(geo=82, clone=75, reviews=83)
    assert len(washout) == 85
    result = {'parent_manifest_sha256': file_sha(PARENT / 'manifest.json'),
        'pool_sha256': file_sha(ROOT / 'data/contamination/pool.json'),
        'tasks': task_ids, 'eligible': eligible, 'washout_eligible': washout,
        'counts': {f: len(ids) for f, ids in eligible.items()},
        'metadata_coverage': dict(coverage), 'details': details}
    DATA.mkdir(parents=True, exist_ok=True)
    write(DATA / 'eligibility_audit.json', result)
    print(json.dumps({k: result[k] for k in ('counts', 'metadata_coverage')}) , flush=True)


if __name__ == '__main__':
    audit()

"""Offline protocol invariants; execute only via the CPU Slurm gate."""
import collections
from .common import *
from .plans import cases,key
from .prepare import check_candidates


def test_inputs():
    blocks=read(DATA/'blocks.json')
    typed=read(DATA/'typed.json')
    probes=read(DATA/'probes.json')
    eligibility=read(DATA/'eligibility_audit.json')
    counts=collections.Counter()
    seen=set()
    for lane in range(8):
        for case in cases(blocks,typed,probes,eligibility,lane):
            k=key(case)
            assert k not in seen
            seen.add(k)
            counts[case['phase']]+=1
            check_candidates(case['candidates'],2 if case['phase']=='probe' else 10,case['k'])
    assert dict(counts)==dict(main=7840,single=9600,clone=10500,probe=980),counts
    for b in blocks:
        parent=next(x for x in read(PARENT/f"lane{b['lane']}.json") if (x['seed'],x['task_id'])==(b['seed'],b['task_id']))
        assert {k:v for k,v in b.items() if k!='lane'}==parent
        for r in range(10):
            old={}
            clean=replace(b,[],r)
            for k in (0,2,4,6):
                current=replace(b,b['synthetics'][:k],r)
                assert sum(x['cid']!=y['cid'] for x,y in zip(clean,current))==k
                where={c['cid']:i for i,c in enumerate(current) if c['synthetic']}
                assert all(where[cid]==pos for cid,pos in old.items())
                old=where
        for k in (0,2,4,6):
            positions=collections.defaultdict(set)
            for r in range(10):
                for pos,c in enumerate(replace(b,b['synthetics'][:k],r)):
                    positions[c['cid']].add(pos)
            assert all(len(v)==10 for v in positions.values())
    wash=read(DATA/'washout.json')
    sample=read(DATA/'sampling.json')
    assert len(sample['pollution_ids'])==len(sample['clean_ids'])==40
    assert not set(sample['pollution_ids'])&set(sample['clean_ids'])
    for seed in SEEDS:
        w=wash[str(seed)]
        assert [p['task_id'] for p in w['pollution']]==sample['pollution_ids']
        assert [p['task_id'] for p in w['clean']]==sample['clean_ids']
        for phase in ('pollution','clean'):
            for ep,p in enumerate(w[phase]):
                check_candidates(p['candidates'],10,6 if phase=='pollution' else 0)
                assert p['rotation']==ep%10
                if phase=='pollution':
                    assert collections.Counter(c['family'] for c in p['candidates'] if c['synthetic'])==dict(geo=2,clone=2,reviews=2)
    # Missing gold rating must stay unknown after clone rating alignment.
    from .prepare import clone_variant
    from synthflood.product_metadata import rating_and_count
    candidate={'cid':'s','item':{'rating':4.8,'num_reviews':123},'reviews':[{'text':'kept'}]}
    aligned=clone_variant([candidate],{'item':{'Rating':'N.A.'}},'rating')[0]
    assert rating_and_count(aligned['item'])[0] is None
    assert aligned['item']['num_reviews']==123 and aligned['reviews']==candidate['reviews']
    write(DATA/'input_validation.json',dict(validated=True,counts=dict(counts),main_slot_checks=7840,
        washout_seed_count=8,pollution_clean_disjoint=True,missing_rating_alignment_checked=True))
    print('V3_INPUT_INVARIANTS_PASS',dict(counts),flush=True)


if __name__=='__main__':
    test_inputs()

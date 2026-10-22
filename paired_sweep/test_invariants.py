"""Meaningful CPU tests of new design and defense isolation; no model calls."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from .common import candidates, rng, digest, COMMON_PROMPT
from .freeze import array_items, pricing_values
from .defenses import transform
from .worker import input_hash


def block_fixture():
    def c(i, synthetic=False):
        return {'cid':str(i),'item':{'asin':str(i),'Title':'ordinary item','BulletPoints':[],
            'Attributes':[],'Description':'','rating':4,'options':{'size':['large']}},
            'kind':'synthetic:clone' if synthetic else 'gold' if i==0 else 'real',
            'synthetic':synthetic,'source_u':.05 if i%2==0 else .95,'price_float':10}
    return {'seed':1,'task_id':7,'goal':{'asin':'0','instruction_text':'buy it'},
        'base':[c(i) for i in range(10)], 'synthetics':[c(i,True) for i in range(10,16)],
        'replace_order':[7,2,9,1,6,3,8,4,5]}


class Invariants(unittest.TestCase):
    def test_stream_handles_chunk_boundaries_unicode_and_nested_arrays(self):
        data=[{'name':'商品','v':[1,{'x':'a,b]'}]}, {'s':'escaped "quotes"'},{}]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.json';path.write_text(json.dumps(data,ensure_ascii=False))
            for size in (1,2,7,16,10000):
                self.assertEqual(list(array_items(path,size)),data)

    def test_price_ranges_use_official_parse(self):
        self.assertEqual(pricing_values('$1,234.50 to $2,000.00'),[1234.5,2000.])
        self.assertEqual(pricing_values(None),[100.])

    def test_same_task_dose_nesting_and_all_ranks(self):
        b=block_fixture()
        positions={}
        for rotation in range(10):
            clean=candidates(b,0,rotation)
            previous={}
            for k in (0,2,4,6):
                current=candidates(b,k,rotation)
                self.assertEqual(sum(a!=c for a,c in zip(clean,current)),k)
                self.assertEqual(sum(c['kind']=='gold' for c in current),1)
                syn={c['cid']:i for i,c in enumerate(current) if c['synthetic']}
                self.assertTrue(all(syn[cid]==rank for cid,rank in previous.items()))
                previous=syn
                if k==6:
                    for rank,c in enumerate(current):positions.setdefault(c['cid'],set()).add(rank)
        self.assertTrue(all(len(ranks)==10 for ranks in positions.values()))

    def test_task_and_seed_have_independent_stable_streams(self):
        def draw(seed,task):return rng('slots',seed,task).sample(list(range(9)),9)
        self.assertEqual(draw(1,7),draw(1,7))
        self.assertNotEqual(draw(1,7),draw(1,8))
        self.assertNotEqual(draw(1,7),draw(2,7))

    def test_rankers_preserve_identity_options_and_dont_mutate_input(self):
        b=block_fixture();raw=candidates(b,6,0);original=copy.deepcopy(raw)
        for arm in ('provenance','provenance_order','provenance_badge','oracle','ppr_2.0','reviewtrust','spoof65'):
            final,extra,_=transform(b,raw,6,0,arm,{})
            self.assertEqual({c['cid'] for c in final},{c['cid'] for c in raw})
            self.assertEqual(raw,original)
            self.assertEqual(extra,COMMON_PROMPT)
            for c in final:self.assertEqual(c['item']['options'],{'size':['large']})

    def test_provenance_group_order_tracks_input_and_no_output_rotation(self):
        b=block_fixture();raw=candidates(b,0,3)
        final,_,_=transform(b,raw,0,3,'provenance',{})
        verified=[c['cid'] for c in raw if c['source_u']<.85]
        others=[c['cid'] for c in raw if c['source_u']>=.85]
        self.assertEqual([c['cid'] for c in final],verified+others)

    def test_random_matched_deletion_counts_and_no_gold_exemption(self):
        b=block_fixture();raw=candidates(b,0,0)
        ppl={c['cid']:{'ppl':20.} for c in raw}
        filtered,_,_=transform(b,raw,0,0,'detector_text',ppl)
        gold_dropped=False
        for rotation in range(10):
            mixed=candidates(b,0,rotation)
            final,_,_=transform(b,mixed,0,rotation,'random_text',ppl)
            self.assertEqual(len(final),len(filtered))
            gold_dropped |= '0' not in {c['cid'] for c in final}
        self.assertTrue(gold_dropped)

    def test_input_hash_covers_badges_order_options_and_prompts(self):
        b=block_fixture();raw=candidates(b,0,0)
        base=input_hash(b,raw,COMMON_PROMPT)
        for mode in ('badge','order','options','prompt'):
            modified=copy.deepcopy(raw);extra=COMMON_PROMPT
            if mode=='badge':modified[0]['prov_badge']=True
            if mode=='order':modified.reverse()
            if mode=='options':modified[0]['item']['options']={}
            if mode=='prompt':extra+='Additional instruction'
            self.assertNotEqual(base,input_hash(b,modified,extra))


if __name__=='__main__':
    unittest.main(verbosity=2)

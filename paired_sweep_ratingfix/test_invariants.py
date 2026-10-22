"""Regression checks for actual metadata loading, rendering and paired design."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from synthflood.product_metadata import rating_and_count, restore_raw_metadata
from synthflood.select_env import product_fields, results_page, item_page
from synthflood.ws_loader import load_products
from .common import ARMS, candidates, COMMON_PROMPT
from .defenses import transform
from .worker import input_hash


def fixture():
    def c(i,synthetic=False):
        return {'cid':str(i),'item':{'asin':str(i),'Title':'ordinary item','BulletPoints':[],
            'Attributes':[],'Description':'','rating':4.8 if synthetic else 4.7,
            'num_reviews':100,'options':{'size':['large']}},'price_float':10,
            'kind':'synthetic:clone' if synthetic else 'gold' if i==0 else 'real',
            'synthetic':synthetic,'source_u':.05 if i%2==0 else .95}
    return {'seed':1,'task_id':7,'goal':{'asin':'0','instruction_text':'buy it'},
        'base':[c(i) for i in range(10)],'synthetics':[c(i,True) for i in range(10,16)],
        'replace_order':[7,2,9,1,6,3,8,4,5]}


class Invariants(unittest.TestCase):
    def test_raw_fields_reach_rendered_pages(self):
        c=fixture()['base'][0]
        c['item']={'Title':'real item','Rating':'N.A.','average_rating':'4.7','total_reviews':'16,671'}
        self.assertEqual(rating_and_count(c['item']),(4.7,16671))
        self.assertIn('rating: 4.7 (16671 reviews)',results_page([c]))
        self.assertIn('Rating: 4.7 (16671 reviews)',item_page(c))

    def test_missing_is_unknown_and_zero_count_is_preserved(self):
        self.assertEqual(product_fields({'average_rating':'','total_reviews':''})['rating'],'n/a')
        self.assertEqual(product_fields({'average_rating':'','total_reviews':''})['nrev'],'n/a')
        self.assertEqual(rating_and_count({'num_reviews':0,'total_reviews':120}),(None,0))
        for value in ('NaN','inf',-1,6,True):
            self.assertIsNone(rating_and_count({'average_rating':value})[0])
        for value in ('NaN','inf',-1,1.5,True):
            self.assertIsNone(rating_and_count({'total_reviews':value})[1])

    def test_loader_preserves_raw_metadata_and_does_not_make_review_bodies(self):
        raw={'asin':'REAL1','category':'a','query':'item','product_category':'b',
            'name':'real product','full_description':'ordinary product','small_description':['feature'],
            'pricing':'$10.00','customization_options':{},'images':['image'],
            'average_rating':'4.6','total_reviews':'1,234'}
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory)
            (d/'items.json').write_text(json.dumps([raw]))
            (d/'attrs.json').write_text(json.dumps({'REAL1':{'attributes':[]}}))
            (d/'human.json').write_text('{}')
            _,items,_,_=load_products(str(d/'items.json'),str(d/'attrs.json'),str(d/'human.json'))
        item=items['REAL1']
        self.assertEqual(product_fields(item)['rating'],4.6)
        self.assertEqual(product_fields(item)['nrev'],1234)
        self.assertEqual(item['total_reviews'],'1,234')
        self.assertEqual(item['Reviews'],[])

    def test_restore_changes_only_numeric_metadata(self):
        item={'Title':'x','average_rating':'4.8','Rating':'N.A.','options':{'size':['XL']},'Description':'body'}
        original=copy.deepcopy(item)
        fixed=restore_raw_metadata(item,{'average_rating':'4.8','total_reviews':'12'})
        self.assertEqual(item,original)
        self.assertEqual(fixed['options'],item['options'])
        self.assertEqual(fixed['Description'],item['Description'])
        self.assertEqual(rating_and_count(fixed),(4.8,12))

    def test_no_ppr_arms_or_callable_ppr_strategy(self):
        self.assertEqual(len(ARMS),15)
        self.assertFalse(any(a.startswith('ppr') for a in ARMS))
        b=fixture()
        with self.assertRaises(ValueError):transform(b,b['base'],0,0,'ppr_1.0',{})

    def test_fixed_slots_nested_doses_and_ten_positions(self):
        b=fixture();ranks={}
        for rotation in range(10):
            clean=candidates(b,0,rotation);previous={}
            for k in (0,2,4,6):
                current=candidates(b,k,rotation)
                self.assertEqual(sum(a!=c for a,c in zip(clean,current)),k)
                self.assertEqual(sum(c['kind']=='gold' for c in current),1)
                syn={c['cid']:i for i,c in enumerate(current) if c['synthetic']}
                self.assertTrue(all(syn[cid]==rank for cid,rank in previous.items()))
                previous=syn
                if k==6:
                    for rank,c in enumerate(current):ranks.setdefault(c['cid'],set()).add(rank)
        self.assertTrue(all(len(v)==10 for v in ranks.values()))

    def test_source_ranking_preserves_set_options_and_stable_group_order(self):
        b=fixture();raw=candidates(b,0,3);original=copy.deepcopy(raw)
        final,extra,_=transform(b,raw,0,3,'provenance',{})
        expected=[c['cid'] for c in raw if c['source_u']<.85]+[c['cid'] for c in raw if c['source_u']>=.85]
        self.assertEqual([c['cid'] for c in final],expected)
        self.assertEqual(raw,original)
        self.assertEqual(extra,COMMON_PROMPT)
        for c in final:self.assertEqual(c['item']['options'],{'size':['large']})

    def test_random_deletion_matches_filter_size_without_gold_protection(self):
        b=fixture();ppl={c['cid']:{'ppl':20} for c in b['base']}
        dropped=False
        for rotation in range(10):
            raw=candidates(b,0,rotation)
            filtered,_,_=transform(b,raw,0,rotation,'detector_text',ppl)
            random,_,_=transform(b,raw,0,rotation,'random_text',ppl)
            self.assertEqual(len(filtered),len(random))
            dropped|='0' not in {c['cid'] for c in random}
        self.assertTrue(dropped)

    def test_reviewtrust_uses_recovered_rating_and_count(self):
        b=fixture();raw=b['base'][:2]
        raw[0]['item']={'Rating':'N.A.','average_rating':'4.9','total_reviews':'1000'}
        raw[1]['item']={'rating':4.8,'num_reviews':100}
        final,_,_=transform(b,raw,0,0,'reviewtrust',{})
        self.assertEqual(final[0]['cid'],raw[0]['cid'])

    def test_input_hash_changes_when_visible_metadata_changes(self):
        b=fixture();raw=b['base'];before=input_hash(b,raw,COMMON_PROMPT)
        changed=copy.deepcopy(raw);changed[0]['item']['rating']=4.9
        self.assertNotEqual(before,input_hash(b,changed,COMMON_PROMPT))


if __name__=='__main__':
    unittest.main(verbosity=2)

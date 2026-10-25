import collections
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import fill_exam_candidates as flow
from .generation_queries import generation_goal,retain_input


class Tests(unittest.TestCase):
    def fixtures(self):
        targets=[dict(task_id=i,goal=dict(query=f'original{i}',index=i),gold=dict(item={})) for i in range(2)]
        queries={str(i):dict(original_query=f'original{i}',generation_query=f'repaired{i}') for i in range(2)}
        return targets,queries

    def test_query_separation(self):
        targets,queries=self.fixtures()
        value=generation_goal(targets[0],queries)
        self.assertEqual(value['query'],'repaired0')
        self.assertEqual(targets[0]['goal']['query'],'original0')
        self.assertFalse(retain_input(dict(task_id=0),queries))
        self.assertTrue(retain_input(dict(task_id=0,generation_query='repaired0'),queries))

    def run_flow(self,failures,passes):
        targets,queries=self.fixtures();calls=[];counts=collections.Counter()
        def listing(family,goal,*args,**kwargs):
            key=goal['index'],family;counts[key]+=1;calls.append(key)
            if key==(0,'geo') and counts[key]<=failures:
                return None
            return dict(asin=f'synth-{key[0]}-{family}',query=goal['query'])
        def reviews(raw,goal,r,client,port,n):
            self.assertEqual(raw['query'],f'original{goal["index"]}')
            self.assertEqual(goal['query'],f'repaired{goal["index"]}')
            return [dict(text='review') for _ in range(n)]
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(flow,'DATA',Path(temp)),patch('synthflood.contaminate.synth_listing',listing),patch('synthflood.contaminate.judge_plausible',return_value=4),patch('synthflood.contaminate.attach_reviews',reviews):
                if failures>=passes:
                    with self.assertRaises(RuntimeError):
                        flow.fill_candidates(targets,{},None,queries,passes=passes,attempts_per_pass=1)
                    result=json.loads((Path(temp)/'exam_generated_partial.json').read_text())
                else:
                    result=flow.fill_candidates(targets,{},None,queries,passes=passes,attempts_per_pass=1)
        return result,calls

    def test_missing_type_does_not_block_other_tasks(self):
        result,calls=self.run_flow(2,3)
        self.assertEqual(len(result),6)
        self.assertTrue(all((1,f) in calls[:6] for f in ('geo','clone','reviews')))
        self.assertEqual(calls[6:],[(0,'geo'),(0,'geo')])
        self.assertEqual(len({r['listing']['asin'] for r in result}),6)

    def test_unresolved_preserves_other_candidates(self):
        result,calls=self.run_flow(3,2)
        self.assertEqual(len(result),5)
        self.assertEqual({r['family'] for r in result if r['task_id']==1},{'geo','clone','reviews'})
        self.assertNotIn((0,'geo'),[(r['task_id'],r['family']) for r in result])


if __name__=='__main__':
    unittest.main()

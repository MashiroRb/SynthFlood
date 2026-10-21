"""CPU regression checks for experimental invariants; no model or raw catalog."""
import ast
import copy
import importlib.util
import json
import random
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def function(path, name, namespace):
    tree = ast.parse((ROOT / path).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


class ReproducibilityTests(unittest.TestCase):
    def test_zero_choice_rate_is_valid_and_duplicate_cells_are_rejected(self):
        sigma=function('m1/m1_run.py','_sigma',{})
        rows=[{'arm':'B0','phase':'exam','checkpoint':'20','pair_idx':str(i),'chose_clone':'0'} for i in range(2)]
        self.assertEqual(sigma(rows,'B0','exam',20),(0.0,2))
        self.assertEqual(sigma(rows,'M0','exam',20),(None,0))
        with self.assertRaises(ValueError):
            sigma(rows+rows[:1],'B0','exam',20)

    def test_concurrent_exam_logging_has_one_header_and_no_lost_rows(self):
        import csv
        import os
        with tempfile.TemporaryDirectory() as directory:
            ns={'os':os,'csv':csv,'OUT':directory,'CSV_LOCK':threading.RLock()}
            append=function('m1/m1_run.py','_append_csv',ns)
            with ThreadPoolExecutor(16) as executor:
                futures=[executor.submit(append,'exam.csv',{'pair':i},['pair']) for i in range(100)]
                for future in futures:
                    future.result()
            with open(directory+'/exam.csv') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual({int(row['pair']) for row in rows},set(range(100)))
            self.assertEqual(len(rows),100)

    def test_write_only_memory_is_never_injected(self):
        class Memory:
            def inject_context(self):
                return 'written observations'
        get_context=function('m1/m1_run.py','memory_context',{})
        self.assertEqual(get_context({'notes':True,'inject':False},Memory()),'')
        self.assertEqual(get_context({'notes':True},Memory()),'written observations')

    def test_candidate_conversion_keeps_variant_options(self):
        tree=ast.parse((ROOT/'synthflood/contaminate.py').read_text())
        fields=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_SYNTH_FIELDS' for t in n.targets))
        ns={}
        exec(compile(ast.Module(body=[fields],type_ignores=[]),'fields','exec'),ns)
        convert=function('synthflood/contaminate.py','_as_candidate',ns)
        source={'asin':'SYN-test','price':10,'options':{'size':['large']}}
        self.assertEqual(convert(source)['item']['options'],source['options'])

    def test_indexed_distractors_preserve_sampling(self):
        ns={'random':random,'_DISTRACTOR_INDEX':None,'_DISTRACTOR_SOURCE':None}
        sample=function('synthflood/select_env.py','sample_distractors',ns)
        catalog={str(i):{'asin':str(i),'category':'coarse','product_category':('fine' if i<4 else 'other')} for i in range(30)}
        goal={'asin':'0','category':'coarse','product_category':'fine'}
        for seed in range(20):
            rng=random.Random(seed)
            fine=[p for p in catalog.values() if p['product_category']=='fine' and p['asin']!='0']
            extra=[p for p in catalog.values() if p['product_category']!='fine' and p['asin']!='0']
            rng.shuffle(extra);fine+=extra;rng.shuffle(fine)
            self.assertEqual(sample(goal,catalog,8,seed),fine[:8])

    def test_price_stream_is_local_and_fixed(self):
        generate = function("synthflood/ws_loader.py", "generate_product_prices", {"random": random})
        catalog = [{"asin": str(i), "pricing": [10.0, 50.0]} for i in range(20)]
        random.seed(19)
        state = random.getstate()
        first = generate(catalog)
        self.assertEqual(state, random.getstate())
        random.seed(87)
        self.assertEqual(first, generate(catalog))
        self.assertNotEqual(first, generate(catalog, seed=2028))

    def test_clone_generation_cannot_mutate_goal(self):
        class Client:
            def chat(self, *args, **kwargs):
                return '{}', {}
        ns = {"product_fields": lambda _: {"brand": "b", "title": "title", "attrs": [], "price": 10.0},
              "CLONE_PROMPT": "{title} {specs} {violate}", "STEALTH_CLONE_PROMPT": "", "GEN_TEMP": .9,
              "_extract_json": lambda _: {"title": "clone"}}
        generate = function("synthflood/contaminate.py", "synth_listing", ns)
        goal = {"attributes": list('abcdef'), "product_category": "cat", "query": "q"}
        original = copy.deepcopy(goal)
        for seed in range(12):
            generate("clone", goal, {}, random.Random(seed), Client(), 8000)
        self.assertEqual(goal, original)

    def test_pool_seed_controls_output_and_thread_failures_propagate(self):
        import os
        def listing(family, goal, gold, rng, *a, **kw):
            return {"asin": str(rng.randrange(10**12)), "family": family}
        ns = {"GEN_SEED": 2027, "random": random, "threading": threading,
              "ThreadPoolExecutor": ThreadPoolExecutor, "LLMClient": lambda *a: None,
              "synth_listing": listing, "judge_plausible": lambda *a: 5,
              "attach_reviews": lambda *a, **kw: [], "FAMILIES": ["geo", "clone", "reviews"],
              "json": json, "os": os}
        generate = function("synthflood/contaminate.py", "generate_pool", ns)
        with tempfile.TemporaryDirectory() as d:
            goal = {"attributes": list('abcdef')}
            original = copy.deepcopy(goal)
            a = generate([goal], [{}], d+'/a.json', 0, 'test', seed=2027)
            b = generate([goal], [{}], d+'/b.json', 0, 'test', seed=2027)
            c = generate([goal], [{}], d+'/c.json', 0, 'test', seed=2028)
            self.assertEqual(a, b)
            self.assertNotEqual(a, c)
            self.assertEqual(goal, original)
            def fail(*a, **kw):
                raise RuntimeError('generation failure')
            ns['synth_listing'] = fail
            with self.assertRaisesRegex(RuntimeError, 'generation failure'):
                generate([goal], [{}], d+'/bad.json', 0, 'test')

    def test_recent_memory_evicts_exposure_and_does_not_invent_purchase(self):
        spec = importlib.util.spec_from_file_location('memory', ROOT/'m1/m1_memory.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            memory = module.MemoryStore(d+'/memory.json', 'M0')
            memory.add_observation(19, 'EXPOSURE_SENTINEL', 'synthetic:clone', .1, 1)
            memory.add_lesson(19, 'EXPOSURE_LESSON')
            for i in range(3):
                memory.add_observation(1000+i, 'clean', 'none', 0, None)
            self.assertNotIn('EXPOSURE', memory.inject_context())
            self.assertIn('No purchase completed', memory.inject_context())

    def test_pair_test_phase_separation_and_direction(self):
        ns = {"_binom_p_two_sided": lambda k, n: (k, n)}
        compare = function("m1/m1_run.py", "mcnemar", ns)
        rows = [{"arm": arm, "checkpoint": str(c), "pair_idx": '1',
                 "phase": phase, "chose_clone": str(choice)}
                for arm, c, phase, choice in [("M0",0,"exam",1),("PRE",-1,"exam",0),
                                               ("M0",0,"parity",0),("PRE",-1,"parity",1)]]
        self.assertEqual(compare(rows, 'M0',0,'PRE',-1)[:2], (1,0))
        self.assertEqual(compare(rows, 'M0',0,'PRE',-1,phase='parity')[:2], (0,1))


if __name__ == '__main__':
    unittest.main(verbosity=2)

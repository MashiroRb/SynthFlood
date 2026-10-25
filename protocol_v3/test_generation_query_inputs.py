import unittest
from .common import DATA,read,write,file_sha
from .generation_queries import fallback_query


class Tests(unittest.TestCase):
    def target(self,category,title='Actual product'):
        return dict(task_id=0,goal=dict(product_category=category),gold=dict(item=dict(Title=title)))

    def test_trailing_delimiters(self):
        self.assertEqual(fallback_query(self.target('Beauty › Hair Clippers › ')),'Hair Clippers')
        self.assertEqual(fallback_query(self.target('Beauty › Hair Clippers › › ')),'Hair Clippers')

    def test_empty_category(self):
        self.assertEqual(fallback_query(self.target(' › ')),'Actual product')

    def test_normal_category(self):
        self.assertEqual(fallback_query(self.target('Beauty › Hair Clippers')),'Hair Clippers')

    def test_all100_frozen_inputs(self):
        targets=read(DATA/'exam_targets.json')
        values=[dict(task_id=t['task_id'],category=t['goal'].get('product_category'),fallback_query=fallback_query(t)) for t in targets]
        self.assertEqual(len(values),100)
        self.assertTrue(all(v['fallback_query'].strip() for v in values))
        write(DATA/'generation_query_input_validation.json',dict(validated=True,n_tasks=100,
            target_sha256=file_sha(DATA/'exam_targets.json'),queries=values))


if __name__=='__main__':
    unittest.main()

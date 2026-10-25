import unittest
from mem24_common import target,ordered_devices,verify_prefix
class MigrationSafety(unittest.TestCase):
    def test_only_assigned_jobs(self):
        self.assertEqual(target(0)['old_target'],'150039_0')
        self.assertEqual(target(1)['old_target'],'150775')
        for shard in (-1,2,3,150039):
            with self.assertRaises(ValueError):target(shard)
    def test_preserve_order(self):
        self.assertEqual(ordered_devices(['b','a'],['a','b'],'2,3'),'3,2')
        self.assertEqual(ordered_devices(['a','b'],['a','b'],'2,3'),'2,3')
    def test_refuse_different_gpu(self):
        with self.assertRaises(ValueError):ordered_devices(['c','a'],['a','b'],'2,3')
    def test_retained_rows(self):
        verify_prefix(b'old\n',b'old\nnew\n')
        with self.assertRaises(ValueError):verify_prefix(b'old\n',b'changed\n')
if __name__=='__main__':unittest.main()

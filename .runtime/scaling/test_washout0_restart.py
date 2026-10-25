import unittest
from washout0_restart_common import cancel_target,verify_devices,verify_prefix,descendants
class RestartSafety(unittest.TestCase):
    def test_exact_array_element(self):
        self.assertEqual(cancel_target(150049),'150039_0')
        for value in (150039,150775,150294):
            with self.assertRaises(ValueError):cancel_target(value)
    def test_hardware_identity_and_order(self):
        verify_devices(['a','b'],['a','b'])
        with self.assertRaises(ValueError):verify_devices(['b','a'],['a','b'])
        with self.assertRaises(ValueError):verify_devices(['a','c'],['a','b'])
    def test_preserved_completed_prefix(self):
        verify_prefix(b'old\n',b'old\nnew\n')
        with self.assertRaises(ValueError):verify_prefix(b'old\n',b'changed\n')
    def test_server_tree_excludes_waiting_parent_and_other_client(self):
        ps=[dict(pid=1,ppid=0),dict(pid=2,ppid=1),dict(pid=3,ppid=2),dict(pid=4,ppid=1),dict(pid=5,ppid=9)]
        self.assertEqual(descendants(2,ps),{2,3})
if __name__=='__main__':unittest.main()

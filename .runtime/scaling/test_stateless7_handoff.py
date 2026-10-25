import os
from pathlib import Path
import signal
import shlex
import subprocess
import sys
import tempfile
import time
import unittest

from stateless7_handoff import identify_chain,inspect_process,pause_single_waiting_parent,retire_stopped_parent,release_target,completion_valid


class RoutingTests(unittest.TestCase):
    def fixture(self):
        return [dict(pid=1,ppid=0,job='150046',state='S',argv=['/bin/bash','/var/spool/slurm/job150046/slurm_script']),
            dict(pid=2,ppid=1,job='150046',state='S',argv=['bash','protocol_v3/slurm/launch.sh','worker','1']),
            dict(pid=3,ppid=2,job='150046',state='S',argv=['python','-m','protocol_v3.worker','1']),
            dict(pid=4,ppid=2,job='150046',state='S',argv=['python','-m','vllm.entrypoints.openai.api_server'])]

    def test_exact_process_chain(self):
        value=identify_chain(self.fixture())
        self.assertEqual(value['batch']['pid'],1)
        self.assertEqual(value['worker']['pid'],3)

    def test_refuse_other_job_or_child(self):
        for mutate in ('job','parent','worker'):
            p=self.fixture()
            if mutate=='job':p[0]['job']='150045'
            elif mutate=='parent':p[1]['ppid']=99
            else:p[2]['argv'][-1]='7'
            with self.assertRaises(RuntimeError):identify_chain(p)

    def test_release_only_exact_element(self):
        self.assertEqual(release_target('150037_1'),'150037_1')
        for value in ('150037','150037_0','150046','150038_1'):
            with self.assertRaises(RuntimeError):release_target(value)

    def test_require_complete_current_work(self):
        good=dict(validated=True,lane=1,nondefense_rows=3410,defense_rows=7500)
        self.assertTrue(completion_valid(good))
        for field,value in (('validated',False),('lane',7),('nondefense_rows',3409),('defense_rows',7499)):
            bad={**good,field:value};self.assertFalse(completion_valid(bad))

    def test_stopping_waiting_parent_preserves_child(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);counter=path/'counter';unwanted=path/'unwanted'
            child=path/'child.py'
            child.write_text('import time\nfrom pathlib import Path\np=Path('+repr(str(counter))+')\nfor n in range(60):\n q=p.with_suffix(".tmp");q.write_text(str(n));q.replace(p);time.sleep(.03)\n')
            script=path/'parent.sh'
            script.write_text(shlex.quote(sys.executable)+' '+shlex.quote(str(child))+'\necho duplicate > '+shlex.quote(str(unwanted))+'\n')
            process=subprocess.Popen(['bash',str(script)])
            try:
                for _ in range(100):
                    if counter.exists():break
                    time.sleep(.02)
                before=int(counter.read_text())
                saved=inspect_process(process.pid)
                pause_single_waiting_parent(saved)
                time.sleep(.3)
                self.assertGreater(int(counter.read_text()),before)
                self.assertIn(inspect_process(process.pid)['state'],('T','t'))
                time.sleep(2)
                self.assertFalse(unwanted.exists())
                retire_stopped_parent(saved)
                process.wait()
                self.assertFalse(unwanted.exists())
            finally:
                process.kill();process.wait()


if __name__=='__main__':unittest.main()

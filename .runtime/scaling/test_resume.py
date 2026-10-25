import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from protocol_v3 import worker
from protocol_v3.common import digest
from resume_core import ResumeEvaluator,install_replay_client,read_rows,read_request_prefix
from resume_washout import recover_lesson,validated_release_target


class Tokenizer:
    def apply_chat_template(self,messages,**kwargs):return list(range(len(json.dumps(messages))))


class Env:
    def __init__(self,goal,candidates,n_candidates):
        self.candidates=candidates;self.n=n_candidates;self.reset()
    def reset(self):self.done=False;self.chosen=None;return 'Candidates'
    def step(self,action):
        if action.startswith('select'):
            self.chosen=self.candidates[int(action[7:-1])-1];self.done=True
        return 'Page',self.done,{}
    def reward(self):return (1. if self.done else 0.),{}


class Client:
    responses=[];network_successes=0
    def __init__(self,*args):self.calls=0;self.tokens_in=0;self.tokens_out=0
    def chat(self,messages,**kwargs):
        if not self.responses:raise RuntimeError('Simulated interruption')
        action=self.responses.pop(0);self.calls+=1;Client.network_successes+=1
        return f'Thought: Compare.\naction: {action}\nconfidence: 0.8',{}


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.runtime',prefix='resume-test-')
        self.directory=Path(self.temp.name)
        self.items=[dict(cid='gold',kind='gold',synthetic=False),dict(cid='other',kind='real',synthetic=False)]
        self.case=dict(phase='shopping',condition='M0:pollution',task_id=1,seed=2034,rotation=0,k=0,
            family='mix',block=dict(goal=dict(instruction_text='goal'),gold_reward=1.),candidates=self.items,arm='M0',episode=1)
        self.old_checked=worker.CheckedClient;install_replay_client()
        Client.network_successes=0
        self.env=patch('synthflood.select_env.SelectEnv',Env);self.env.start()
        self.base=patch('synthflood.vllm_client.LLMClient',Client);self.base.start()
    def tearDown(self):
        self.env.stop();self.base.stop();worker.CheckedClient=self.old_checked;self.temp.cleanup()
    def test_completed_case_is_not_recomputed_or_duplicated(self):
        Client.responses=['select[2]']
        ev=ResumeEvaluator(self.directory,Tokenizer(),'same-backend')
        first=ev.evaluate(self.case,self.items,'extra')
        ev=ResumeEvaluator(self.directory,Tokenizer(),'same-backend')
        second=ev.evaluate(self.case,self.items,'extra')
        self.assertEqual(first,second)
        self.assertEqual(Client.network_successes,1)
        self.assertEqual(len(read_rows(self.directory/'shopping.jsonl')),1)
        with self.assertRaisesRegex(RuntimeError,'memory mismatch'):
            ev.evaluate(self.case,self.items,'extra',memory='changed')
    def test_partial_episode_replays_archived_prefix_without_network_call(self):
        Client.responses=['view[1]']
        ev=ResumeEvaluator(self.directory,Tokenizer(),'same-backend')
        with self.assertRaisesRegex(RuntimeError,'Simulated interruption'):
            ev.evaluate(self.case,self.items,'extra')
        self.assertFalse((self.directory/'shopping.jsonl').exists())
        Client.responses=['select[2]']
        ev=ResumeEvaluator(self.directory,Tokenizer(),'same-backend')
        result=ev.evaluate(self.case,self.items,'extra')
        self.assertTrue(result['valid']);self.assertEqual(result['effective_views'],1)
        self.assertEqual(result['new_model_calls'],2)
        self.assertEqual(Client.network_successes,2)
        log=ROOT/result['request_log']
        records=read_request_prefix(log)
        self.assertEqual(len(records),2)
        self.assertEqual(result['request_sha256'],[r['request_sha256'] for r in records])
        self.assertEqual(len(read_rows(self.directory/'shopping.jsonl')),1)
        self.assertTrue(list(log.parent.glob(log.name+'.before-repair-*')))
    def test_incomplete_result_tail_preserves_complete_rows(self):
        path=self.directory/'exam.jsonl';path.write_bytes(b'{"case_key":"kept"}\n{"case')
        self.assertEqual(read_rows(path,repair=True),[dict(case_key='kept')])
        self.assertEqual(path.read_bytes(),b'{"case_key":"kept"}\n')
        self.assertTrue(list(self.directory.glob('exam.jsonl.before-repair-*')))
    def test_lesson_after_request_before_memory_save_is_recovered(self):
        directory=self.directory/'seed2034';directory.mkdir()
        record=dict(t=5,response='{"lesson":"Keep requirements in mind", "tags":["requirements"]}')
        (directory/'lesson_calls_M0.jsonl').write_text(json.dumps(record)+'\n')
        recovered=recover_lesson(self.directory,2034,'M0',5,[])
        self.assertEqual(recovered['text'],'Keep requirements in mind')
        self.assertEqual(recovered['tags'],['requirements'])
        self.assertEqual(Client.network_successes,0)
    def test_release_cannot_cancel_the_other_array_element(self):
        for target in (None,'150039','150039_0'):
            with self.assertRaisesRegex(RuntimeError,'parent-array'):
                validated_release_target(150039,target)
        self.assertEqual(validated_release_target(150039,'150039_1'),'150039_1')
        self.assertEqual(validated_release_target(150049),'150049')

if __name__=='__main__':unittest.main()

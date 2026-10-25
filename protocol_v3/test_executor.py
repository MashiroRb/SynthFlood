import unittest
import tempfile
import gzip
import json
from pathlib import Path
from .executor import parse, run_episode, CheckedClient


def reply(action, confidence='0.8'):
    return f'Thought: I compared the requirements.\naction: {action}\nconfidence: {confidence}'


class Env:
    n = 2
    candidates = [dict(cid='a', kind='gold'), dict(cid='b', kind='synthetic:clone', synthetic=True)]
    def reset(self):
        self.done = False
        self.chosen = None
        return 'Candidates'
    def step(self, action):
        if action.startswith('select'):
            self.done = True
            self.chosen = self.candidates[int(action[7:-1])-1]
        return 'Page', self.done, {}
    def reward(self):
        return 1., {}


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.messages = []
    def chat(self, messages, **kwargs):
        self.messages.append(list(messages))
        return next(self.responses), {}


class Tests(unittest.TestCase):
    def test_parser(self):
        for n in (2,10):
            self.assertIsNotNone(parse(reply(f'select[{n}]'),n,0)[0])
        for text in (reply('select[3]'),reply('select[0]'),reply('view[1] select[2]'),
                     reply('select[1]')+'\naction: select[2]',
                     'Thought: I might select[1], but have not decided.'):
            self.assertIsNone(parse(text,2,6)[0],text)
        self.assertIsNone(parse(reply('view[1]'),2,0)[0])
        for confidence in ('nan','1.5','90','n/a'):
            self.assertIsNone(parse(reply('select[1]',confidence),2,0)[0][2])

    def test_relaxed_presentations(self):
        responses=['```\n'+reply('select[1]')+'\n```',
            'Explanation\n**Action:** `SELECT [ 1 ]`\nConfidence: 80%\nExtra explanation',
            '{"thought":"Compared", "action":"select[1]", "confidence":0.8}',
            'action: select[1]', ' select[1] ',
            reply('select[1]').replace('I compared the requirements.','I considered view[2].')]
        for text in responses:
            action,error=parse(text,2,6)
            self.assertIsNone(error,text)
            self.assertEqual(action[:2],('select',1))
        self.assertEqual(parse('Action: select [ 2 ]\nConfidence: 90%',2,0)[0][2],.9)
        self.assertIsNone(parse('Action: select[1]\nConfidence: 0.7\nConfidence: 0.9',2,0)[0][2])
        for text in ('action: view[1]\nselect[2]', '{"action":"select[1] select[2]"}',
                     'action: select[1]\naction: select[1]',
                     '{"action":"select[1]","action":"select[2]"}'):
            self.assertIsNone(parse(text,2,6)[0])

    def test_repeated_page_reminder_preserves_budget(self):
        client=Client([reply('view[1]')]*3+[reply('select[2]','n/a')])
        result=run_episode(Env(),client,'goal',budget=6)
        self.assertTrue(result['valid'])
        self.assertEqual(result['effective_views'],3)
        self.assertEqual(result['repeat_view_events'],2)
        self.assertIsNone(result['confidence'])
        self.assertIn('same unchanged page',client.messages[2][-1]['content'])
        self.assertIn('Remaining effective views: 4',client.messages[2][-1]['content'])

    def test_last_view_gets_select(self):
        for budget in (6, 30):
            client = Client([reply('view[1]', 'n/a')]*budget + [reply('select[2]')])
            result = run_episode(Env(), client, 'goal', budget=budget)
            self.assertTrue(result['valid'])
            self.assertEqual(result['effective_views'], budget)
            self.assertIn('Submission phase', client.messages[-1][-1]['content'])

    def test_trailing_action_whitespace(self):
        for action in ('view[1]', 'select[2]'):
            text=reply(action).replace(f'action: {action}\n',f'action: {action} \t\n')
            parsed,error=parse(text,2,6)
            self.assertIsNone(error)
            self.assertEqual(parsed[:2],(action.split('[')[0],int(action[-2])))
        client=Client([reply('view[1] '),reply('select[2]\t')])
        result=run_episode(Env(),client,'goal',budget=6)
        self.assertTrue(result['valid'])
        self.assertEqual(result['malformed'],0)
        self.assertEqual(result['effective_views'],1)
        for action in ('view[1] select[2] ', 'select[2] extra '):
            self.assertIsNone(parse(reply(action),2,6)[0])

    def test_cumulative_retries(self):
        client = Client(['bad', reply('view[1]'), 'bad', reply('view[2]'), 'bad', reply('select[1]')])
        result = run_episode(Env(), client, 'goal', budget=6)
        self.assertTrue(result['valid'])
        self.assertEqual(result['malformed'], 3)
        self.assertEqual(result['effective_views'], 2)
        result = run_episode(Env(), Client(['bad', reply('view[1]'), 'bad', 'bad', 'bad']), 'goal', budget=6)
        self.assertFalse(result['valid'])
        self.assertIsNone(result['reward'])
        self.assertEqual(result['effective_views'], 1)

    def test_submission_retry(self):
        result = run_episode(Env(), Client([reply('view[1]')]*6+[reply('view[2]'), reply('select[1]', 'unknown')]), 'goal', budget=6)
        self.assertTrue(result['valid'])
        self.assertEqual(result['malformed'], 1)
        self.assertIsNone(result['confidence'])

    def test_no_context_truncation(self):
        class Tokenizer:
            def apply_chat_template(self,messages,**kwargs):
                return list(range(30))
        base=Client([])
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'requests.jsonl.gz'
            checked=CheckedClient(base,Tokenizer(),path,context=32)
            messages=[dict(role='user',content='Complete memory stays intact')]
            with self.assertRaises(RuntimeError):
                checked.chat(messages,max_tokens=3)
            self.assertEqual(base.messages,[])
            with gzip.open(path,'rt') as stream:
                record=json.loads(stream.readline())
            self.assertEqual(record['request']['messages'],messages)
            self.assertEqual(record['prompt_tokens'],30)

    def test_full_memory(self):
        from .washout import full_memory
        class Memory:
            entries=[dict(type='observation',text=f'note {i}') for i in range(80)]
            entries+=[dict(type='lesson',text=f'lesson {i}') for i in range(16)]
        text=full_memory(Memory())
        self.assertEqual(text.count('- [observation]'),80)
        self.assertEqual(text.count('- [lesson]'),16)
        self.assertIn('note 0\n',text)
        self.assertIn('lesson 15',text)


if __name__ == '__main__':
    unittest.main()

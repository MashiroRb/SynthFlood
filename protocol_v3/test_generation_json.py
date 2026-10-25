import json
import unittest
from .generation_json import extract_json


class Tests(unittest.TestCase):
    def test_valid_is_unchanged(self):
        value=dict(title='Hair system 8x10"',specs=['Size: 8x10"'],price=123)
        self.assertEqual(extract_json(json.dumps(value),log=False),value)

    def test_unescaped_inches(self):
        raw='{"title": "Hair system (#2 Dark Brown, 8x10")", "specs": ["Size: 8x10"], "description": "Plain text"}'
        value=extract_json(raw,log=False)
        self.assertIsNotNone(value)
        self.assertEqual(value['title'],'Hair system (#2 Dark Brown, 8x10")')
        self.assertEqual(value['specs'],['Size: 8x10'])
        self.assertEqual(value['description'],'Plain text')

    def test_unescaped_quoted_word(self):
        self.assertEqual(extract_json('{"title": "A "premium" product"}',log=False),dict(title='A "premium" product'))

    def test_incomplete_is_rejected(self):
        self.assertIsNone(extract_json('{"title": "broken',log=False))
        self.assertIsNone(extract_json('no object',log=False))


if __name__=='__main__':
    unittest.main()

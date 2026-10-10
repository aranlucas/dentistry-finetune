"""The answer explorer uses frozen records and never fabricates missing outputs."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class ComparisonChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.dataset = self.root / 'datasets/pilot-v1'
        self.dataset.mkdir(parents=True)
        (self.root / 'runs').mkdir()
        example = {'id': 'synthetic-0', 'kind': 'supported', 'note': 'The blue lamp',
                   'expected': {'answer': 'is on the desk.', 'citation': 'S1'},
                   'passages': [{'doc_id': 1, 'citation': 'S1',
                                 'text': 'The blue lamp is on the desk.'}]}
        raw = (json.dumps(example) + '\n').encode()
        (self.dataset / 'heldout.jsonl').write_bytes(raw)
        manifest = {'splits': {'test': {'file': 'heldout.jsonl',
                                      'sha256': hashlib.sha256(raw).hexdigest()}},
                    'documents': [{'local_id': 1, 'title': 'Synthetic reference',
                                   'publisher_url': 'https://example.com/reference'}]}
        (self.dataset / 'manifest.json').write_text(json.dumps(manifest))

    def read(self):
        with patch.object(server, 'ROOT', self.root):
            return server.comparison_data()

    def test_absent_outputs_are_explicitly_unavailable(self):
        result = self.read()
        self.assertIsNone(result['cases'][0]['outputs']['base_rag'])
        self.assertEqual(result['available_outputs']['adapter_rag'], 0)
        self.assertEqual(result['cases'][0]['expected']['citation'], 'S1')
        self.assertFalse(result['reproduction'])

    def test_reproduction_answers_do_not_replace_original_answers(self):
        replay = self.root / '.local/reproduction'
        (replay / 'runs').mkdir(parents=True)
        (replay / 'data').mkdir()
        (replay / 'data/heldout.jsonl').write_bytes((self.dataset / 'heldout.jsonl').read_bytes())
        record = {'id': 'synthetic-0', 'raw': 'a recorded response',
                  'schema_valid': False, 'semantic_exact': False, 'json_valid': False}
        (replay / 'runs/base_rag-predictions.jsonl').write_text(json.dumps(record) + '\n')
        (self.root / '.local/comparison-run.json').write_text(json.dumps({'directory': '.local/reproduction'}))
        result = self.read()
        self.assertEqual(result['cases'][0]['outputs']['base_rag']['raw'], 'a recorded response')
        self.assertIsNone(result['cases'][0]['original_outputs']['base_rag'])
        self.assertTrue(result['reproduction'])

    def test_changed_snapshot_is_rejected(self):
        (self.dataset / 'heldout.jsonl').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            self.read()

    def test_unrelated_predictions_are_rejected(self):
        (self.root / 'runs/base_rag-predictions.jsonl').write_text('{"id":"unrelated"}\n')
        with self.assertRaisesRegex(ValueError, 'frozen case order'):
            self.read()

    def test_reproduction_path_cannot_escape_local_directory(self):
        (self.root / '.local').mkdir()
        (self.root / '.local/comparison-run.json').write_text('{"directory":"../other-project"}')
        with self.assertRaisesRegex(ValueError, 'must be local'):
            self.read()


if __name__ == '__main__':
    unittest.main()

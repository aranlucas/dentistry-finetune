"""Resume regression checks use synthetic fixtures, never the study corpus or MLX."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluate
from task import messages, canonical, score


class ResumeChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for folder in ['data', 'runs', 'adapters/pilot']:
            (self.root / folder).mkdir(parents=True)
        self.example = {
            'id': 'synthetic-0', 'kind': 'supported', 'input': 'synthetic input',
            'passages': [{'citation': 'S1', 'text': 'The blue lamp is on the desk.'}],
            'expected': {'answer': 'is on the desk.', 'citation': 'S1'},
        }
        self.example['messages'] = messages(self.example['input'])
        heldout = self.root / 'data/heldout.jsonl'
        heldout.write_text(json.dumps(self.example) + '\n')
        self.meta = {'file': 'heldout.jsonl', 'sha256': hashlib.sha256(heldout.read_bytes()).hexdigest()}
        (self.root / 'data/manifest.json').write_text(json.dumps({'splits': {'test': self.meta}}))
        self.adapter = self.root / 'adapters/pilot/adapters.safetensors'
        self.adapter.write_bytes(b'synthetic adapter fingerprint, not model weights')
        self.fingerprint = {
            'condition': 'adapter_rag', 'test_sha256': self.meta['sha256'],
            'revision': evaluate.CFG['revision'], 'max_new_tokens': evaluate.CFG['max_new_tokens'],
            'temperature': 0, 'adapter_sha256': hashlib.sha256(self.adapter.read_bytes()).hexdigest(),
        }
        (self.root / 'runs/adapter_rag-fingerprint.json').write_text(json.dumps(self.fingerprint))
        raw = canonical(self.example['expected'])
        self.row = {'id': self.example['id'], 'kind': self.example['kind'], 'raw': raw, 'seconds': 0.2,
                    **score(raw, self.example)}
        # Fields present in the evaluator's complete records.
        self.row.update({'text_exact': True, 'correct_citation': True})
        self.predictions = self.root / 'runs/adapter_rag-predictions.jsonl'
        self.predictions.write_text(json.dumps(self.row) + '\n')
        self.summary = self.root / 'runs/adapter_rag-summary.json'

    def resume(self):
        with patch.object(evaluate, 'ROOT', self.root), \
             patch('sys.argv', ['evaluate.py', '--condition', 'adapter_rag', '--resume']), \
             patch.object(evaluate, 'load_local', side_effect=AssertionError('Model must not load')), \
             patch.object(evaluate, 'new_guard', side_effect=AssertionError('Guard must not start')), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            evaluate.main()
            return json.loads(output.getvalue())

    def test_completed_resume_preserves_files_and_original_timing(self):
        original = evaluate.result_summary('adapter_rag', self.meta, [self.row], 17.5, 350.0)
        self.summary.write_text(json.dumps(original, indent=2))
        before = {p: p.read_bytes() for p in [self.summary, self.predictions]}
        result = self.resume()
        self.assertEqual(result['status'], 'already_complete')
        self.assertEqual(result['report']['wall_seconds'], 17.5)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_completed_predictions_recover_missing_summary_without_inference(self):
        result = self.resume()
        self.assertIsNone(result['report']['wall_seconds'])
        self.assertIsNone(result['report']['mlx_peak_mib'])
        self.assertEqual(result['report']['metrics']['semantic_exact']['count'], 1)
        self.assertIn('unavailable', result['report']['timing_note'])
        self.assertTrue(self.summary.exists())

    def test_changed_adapter_refuses_resume_before_model_load(self):
        self.adapter.write_bytes(b'different synthetic bytes')
        with self.assertRaisesRegex(ValueError, 'settings changed'):
            self.resume()

    def test_nonprefix_predictions_refuse_resume(self):
        self.row['id'] = 'unrelated-case'
        self.predictions.write_text(json.dumps(self.row) + '\n')
        with self.assertRaisesRegex(ValueError, 'exact prefix'):
            self.resume()

    def test_runtime_prompt_change_refuses_resume(self):
        with patch.object(evaluate, 'messages', return_value=[{'role': 'system', 'content': 'changed'}]):
            with self.assertRaisesRegex(ValueError, 'Runtime prompt differs'):
                self.resume()

    def test_missing_original_fingerprint_refuses_resume(self):
        (self.root / 'runs/adapter_rag-fingerprint.json').unlink()
        with self.assertRaisesRegex(ValueError, 'original fingerprint'):
            self.resume()


if __name__ == '__main__':
    unittest.main()

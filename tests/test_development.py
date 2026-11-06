"""The development response identifies the run it actually read, independent of labels/order."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class DevelopmentChecks(unittest.TestCase):
    def test_selected_run_is_not_inferred_from_registry_order_or_label(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / '.local/curated'
            run.mkdir(parents=True)
            (run / 'runs').mkdir()
            (run / 'questions.jsonl').write_text('')
            (run / 'config.json').write_text('{"temperature": 0, "iters": 40}')
            manifest = {
                'model_run': '.local/curated', 'limits': 'Synthetic development only',
                'questions_sha256': hashlib.sha256(b'').hexdigest(),
                'config_sha256': hashlib.sha256((run / 'config.json').read_bytes()).hexdigest(),
            }
            (run / 'manifest.json').write_text(json.dumps(manifest))
            registry = {'other': {'directory': '.local/other', 'label': 'Same label'},
                        'curated': {'directory': '.local/curated', 'label': 'Same label'}}
            (root / '.local/development-run-history.json').write_text(json.dumps(registry))
            with patch.object(server, 'ROOT', root), patch('qa.local_directory', side_effect=lambda p: root / p):
                response = server.development_data('curated')
            self.assertEqual(response['run_id'], 'curated')
            self.assertEqual(response['runs'][0]['id'], 'other')
            self.assertEqual(response['planned_steps'], 40)

    def test_resume_requires_original_fingerprint_for_both_development_modes(self):
        import development
        import grounded
        import contextlib
        for module in (development, grounded):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / 'runs').mkdir()
                (root / 'questions.jsonl').write_text('{"id":"old"}\n')
                (root / 'runs/base-predictions.jsonl').write_text('{"id":"old"}\n')
                manifest = {'model_run': str(root), 'questions_sha256': 'digest',
                            'config_sha256': 'digest', 'retrieval_documents_sha256': 'digest',
                            'retrieval_implementation_sha256': 'digest'}
                (root / 'manifest.json').write_text(json.dumps(manifest))
                (root / 'runs/training-summary.json').write_text('{"adapter_sha256":"digest"}')
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.dict('os.environ', {'DENTISTRY_BOUNDED_JOB': '1'}))
                    for name, value in [('config', {}), ('local_directory', root),
                                        ('verify', None), ('digest', 'digest')]:
                        stack.enter_context(patch.object(module, name, return_value=value))
                    stack.enter_context(patch.object(module, 'load', side_effect=AssertionError('No model load')))
                    with self.assertRaisesRegex(ValueError, 'original fingerprint'):
                        module.evaluate(root, 'base', True)
                self.assertFalse((root / 'runs/base-fingerprint.json').exists())
                self.assertEqual((root / 'runs/base-predictions.jsonl').read_text(), '{"id":"old"}\n')

    def test_curated_training_rejects_tampered_review_before_loading_tokenizer(self):
        import curated_dataset
        from judgment_journal import append
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            append(root, [{'id': 'candidate', 'decision': 'defer', 'review_mode': 'assistant_direct'}])
            journal = root / 'judgments.jsonl'
            journal.write_text(journal.read_text().replace('defer', 'keep_candidate'))
            (root / 'candidates.jsonl').write_text('{"id":"candidate"}\n')
            spec = root / 'spec.json'
            spec.write_text('{"reviewer":"Codex assistant in this conversation"}')
            with patch.object(curated_dataset, 'verify'), patch.object(curated_dataset, 'verify_candidates'):
                with self.assertRaisesRegex(ValueError, 'Logged judgment changed'):
                    curated_dataset.prepare(root, root, root, spec, root / 'destination')
            self.assertFalse((root / 'destination').exists())

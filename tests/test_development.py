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

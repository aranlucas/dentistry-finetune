"""Source archives retain authored verification files without local artifacts."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import export_source


class ExportSourceChecks(unittest.TestCase):
    def test_website_checks_are_reproducible_from_the_source_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            required = (
                export_source.TOP + export_source.AGGREGATE
                + export_source.APPROVED_DATASET + export_source.AUTHORED_TRANSCRIPTS
                + ['src/oral_dataset_extract.mjs', 'web/index.html', 'web/package.json',
                   'web/package-lock.json', 'web/tsconfig.json', 'web/vite.config.ts',
                   'web/.gitignore', 'web/.oxlintrc.json', 'web/oxfmt.config.ts',
                   'web/src/main.tsx', 'web/test/router.test.ts']
            )
            for name in required:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('synthetic authored fixture\n')
            # Immutable snapshot bytes must survive even when authored on Windows.
            (root / export_source.APPROVED_DATASET[0]).write_bytes(b'{"note":"fixture"}\r\n')
            for name in ['web/node_modules/dependency/index.ts', 'web/dist/index.js',
                         'web/coverage/result.json', '.local/private.json']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('local artifact must stay local\n')

            with patch.object(export_source, 'ROOT', root), \
                 contextlib.redirect_stdout(io.StringIO()):
                export_source.export()

            target = root / '.local/source-export'
            receipt = json.loads((target / 'EXPORT-MANIFEST.json').read_text())
            self.assertEqual(set(receipt), set(required))
            with zipfile.ZipFile(root / '.local/oral-board-local-lab-source.zip') as archive:
                for name in required:
                    original = (root / name).read_bytes()
                    self.assertEqual((target / name).read_bytes(), original)
                    self.assertEqual(archive.read('oral-board-local-lab/' + name), original)
                    self.assertEqual(receipt[name]['sha256'], hashlib.sha256(original).hexdigest())
                    self.assertEqual(receipt[name]['bytes'], len(original))


if __name__ == '__main__':
    unittest.main()

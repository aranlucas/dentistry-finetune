"""Prevent sample transcripts from borrowing held-out sources or masquerading as model results."""
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'examples/transcripts-v1'


class TranscriptChecks(unittest.TestCase):
    def test_authorship_and_source_boundary(self):
        index = json.loads((SAMPLES / 'index.json').read_text())
        manifest = json.loads((ROOT / 'datasets/pilot-v1/manifest.json').read_text())
        docs = {doc['local_id']: doc for doc in manifest['documents']}
        self.assertEqual(index['authorship'], 'assistant_authored')
        self.assertTrue(index['synthetic_cases'])
        for key in ['actual_model_outputs', 'clinical_expert_reviewed',
                    'included_in_model_training', 'included_in_benchmark']:
            self.assertIs(index[key], False)
        self.assertEqual(index['original_pilot_results_sha256'],
                         hashlib.sha256((ROOT / 'runs/results.json').read_bytes()).hexdigest())
        self.assertEqual(len(index['transcripts']), 5)
        self.assertEqual({row['file'] for row in index['transcripts']},
                         {path.name for path in SAMPLES.glob('[0-9][0-9]-*.md')})
        for sample in index['transcripts']:
            self.assertTrue(sample['source_ids'])
            self.assertEqual(sample['source_ids'], [s['source_id'] for s in sample['sources']])
            raw = (SAMPLES / sample['file']).read_bytes()
            self.assertEqual(sample['sha256'], hashlib.sha256(raw).hexdigest())
            text = raw.decode()
            self.assertIn('All case details are fictional.', text)
            self.assertIn('Not a base/adapter generation.', text)
            self.assertEqual(len(re.findall(r'^\*\*Examiner:\*\*', text, re.M)), 3)
            self.assertEqual(len(re.findall(r'^\*\*Candidate(?: \([^\n]+\))?:\*\*', text, re.M)), 3)
            self.assertIn('## Debrief', text)
            for source in sample['sources']:
                doc = docs[source['source_id']]
                self.assertEqual(doc['split'], 'train')
                self.assertEqual(source['original_pilot_split'], 'train')
                self.assertEqual(source['publisher_url'], doc['publisher_url'])
                self.assertIn(source['publisher_url'], text)
                self.assertTrue(all(isinstance(p, int) and p > 0 for p in source['pdf_viewer_pages']))
            if sample['response_style'] == 'weak_opening_then_correction':
                self.assertIn('Candidate (deliberately weak opening)', text)
                self.assertIn('negative example', text)

    def test_samples_do_not_copy_pilot_excerpts_or_identifier_patterns(self):
        snippets = []
        for path in (ROOT / 'datasets/pilot-v1').glob('*.jsonl'):
            for line in path.read_text().splitlines():
                snippets.extend(p['text'] for p in json.loads(line)['passages'])
        patterns = [r'\b\d{3}-\d{2}-\d{4}\b',
                    r'(?i)\b(?:DOB|date of birth)\s*[:=]\s*\d',
                    r'(?i)\b(?:MRN|patient\s+(?:ID|name))\s*[:#]\s*\S+',
                    r'(?:/Users/|/home/|/private/|/var/folders/)',
                    r'(?:gh[pousr]_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})',
                    r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
                    r'\b\d{3}[-.]\d{3}[-.]\d{4}\b']
        for path in SAMPLES.iterdir():
            if not path.is_file():
                continue
            text = path.read_text()
            for snippet in snippets:
                self.assertNotIn(snippet, text, f'Copied pilot excerpt in {path.name}')
            for pattern in patterns:
                self.assertIsNone(re.search(pattern, text), f'Screen match in {path.name}')


if __name__ == '__main__':
    unittest.main()

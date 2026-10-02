"""Approved pilot snapshot integrity/privacy checks; no model execution."""
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATASET=ROOT/'datasets/pilot-v1'


class DatasetChecks(unittest.TestCase):
    def test_snapshot_bytes_counts_and_source_separation(self):
        manifest=json.loads((DATASET/'manifest.json').read_text())
        integrity=json.loads((DATASET/'INTEGRITY.json').read_text())
        expected={'train':(144,120,12,12),'valid':(16,12,2,2),'test':(24,16,4,4)}
        sources={};snippets={}
        for split,counts in expected.items():
            meta=manifest['splits'][split];path=DATASET/meta['file'];raw=path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),meta['sha256'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),integrity[path.name]['sha256'])
            self.assertEqual(len(raw),integrity[path.name]['bytes'])
            rows=[json.loads(line) for line in raw.decode().splitlines()]
            self.assertEqual((len(rows),sum(r['kind']=='supported' for r in rows),
                              sum(r['kind']=='missing_context' for r in rows),
                              sum(r['kind']=='unsupported_or_malformed' for r in rows)),counts)
            sources[split]={d['local_id'] for d in manifest['documents'] if d['split']==split}
            snippets[split]={p['text'].lower() for r in rows for p in r['passages']}
            self.assertTrue(all(p['doc_id'] in sources[split] for r in rows for p in r['passages']))
            for row in rows:
                if row['kind']=='supported':
                    gold=row['expected']
                    self.assertTrue(any(p['citation']==gold['citation'] and p['text'].endswith(gold['answer']) for p in row['passages']))
                else:self.assertEqual(row['expected'],{'answer':'ABSTAIN','citation':'NONE'})
        for left,right in [('train','valid'),('train','test'),('valid','test')]:
            self.assertFalse(sources[left]&sources[right]);self.assertFalse(snippets[left]&snippets[right])
        self.assertEqual([len(sources[k]) for k in ['train','valid','test']],[6,2,4])
        for name,meta in integrity.items():
            raw=(DATASET/name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),meta['sha256'])
            self.assertEqual(len(raw),meta['bytes'])

    def test_export_has_no_identifier_secret_or_local_path_pattern(self):
        patterns=[r'\b\d{3}-\d{2}-\d{4}\b',r'(?i)\b(?:DOB|date of birth)\s*[:=]\s*\d',
                  r'(?i)\b(?:MRN|patient\s+(?:ID|name)|medical\s+record\s+number)\s*[:#]\s*\S+',
                  r'(?:/Users/|/home/|/private/|/var/folders/)',
                  r'(?:gh[pousr]_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)',
                  r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',r'\b\d{3}[-.]\d{3}[-.]\d{4}\b']
        for path in list(DATASET.glob('*.jsonl'))+[DATASET/'manifest.json']:
            text=path.read_text()
            for pattern in patterns:self.assertIsNone(re.search(pattern,text),f'Screen match in {path.name}')


if __name__=='__main__':unittest.main()

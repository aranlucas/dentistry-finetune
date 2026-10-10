"""Append-only local assistant judgments and source packets; no inference API."""
import argparse
import collections
import hashlib
import json
import math
import re
import sqlite3
import time
from pathlib import Path
from qa import ROOT, digest, local_directory
from qa_dataset import verify, normalized


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def append(review, entries):
    path = review / 'judgments.jsonl'; old = rows(path)
    seen = {r['id'] for r in old}; previous = old[-1]['entry_sha256'] if old else None
    with path.open('a') as stream:
        for entry in entries:
            if entry['id'] in seen: raise ValueError('Existing judgment is immutable')
            value = {**entry, 'sequence': len(seen) + 1, 'previous_sha256': previous,
                     'time_unix': time.time()}
            previous = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            value['entry_sha256'] = previous
            stream.write(json.dumps(value, ensure_ascii=False) + '\n'); stream.flush()
            seen.add(entry['id'])


def initialize(dataset, review):
    verify(dataset)
    if review.exists(): raise ValueError('Choose a new review directory')
    review.mkdir(parents=True)
    metadata = {'dataset': str(dataset.relative_to(ROOT)), 'dataset_integrity_sha256': digest(dataset/'INTEGRITY.json'),
                'reviewer': 'Codex assistant in this conversation', 'external_inference_api': False,
                'rubric': ['standalone answerable question', 'answer addresses question',
                           'publisher evidence supports claims', 'conditions and exceptions retained',
                           'no invented citation, dose or unsupported claim', 'no repetition or truncation'],
                'limits': ['Model review is not clinical certification.',
                           'Structural triage is not semantic answer review.',
                           'No automatic training promotion; original snapshot remains unchanged.']}
    (review/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    decisions = []
    for row in rows(dataset/'candidates.jsonl'):
        reason = row['blocking_reasons']
        if reason:
            decisions.append({'id': row['id'], 'kind': row['kind'], 'decision': 'defer',
                              'review_mode': 'structural_triage', 'content_reviewed': False,
                              'reason': 'Resolve the per-record blockers before assessing this answer: '+ '; '.join(reason),
                              'blocking_reasons': reason, 'clinical_certification': False})
        elif row['kind']=='note_section' and row['question'].startswith('In the study notes on '):
            decisions.append({'id': row['id'], 'kind': row['kind'], 'decision': 'rewrite_question',
                              'review_mode': 'question_template_review', 'content_reviewed': False,
                              'reason': 'The prompt requests a named study-note section instead of a specific standalone dentistry answer. Author a question from its actual teaching point and review the whole answer; preserve all conditions.',
                              'clinical_certification': False})
    for row in rows(dataset/'excluded.jsonl'):
        decisions.append({'id': row['id'], 'kind': row['kind'], 'decision': 'exclude',
                          'review_mode': 'exclusion_metadata_only', 'content_reviewed': False,
                          'reason': '; '.join(row['reasons']), 'clinical_certification': False})
    append(review, decisions)
    print(json.dumps({'review':str(review),'logged':len(decisions), 'pending_direct_review':len(rows(dataset/'candidates.jsonl'))-sum(d['decision']!='exclude' for d in decisions)}))


def packet(row, connection):
    queries = collections.Counter(re.findall(r'\b[a-z0-9]+\b', (row['question']+' '+row['answer']).lower()))
    stop = set('a an the and or of to in for with is are be as that this it on at by from what how when should can study notes which do does not'.split())
    chunks = []
    for ref in row['publisher_references']:
        body = connection.execute('SELECT doc FROM content WHERE hash=?', (ref['content_hash'],)).fetchone()
        if not body: raise ValueError('Pinned local publisher content is missing')
        text = re.sub(r'^(?:PDF:|Source:|PDF SHA-256:).*$', '', body[0], flags=re.M)
        text = re.split(r'#+\s*(?:\*\*)?References\b', text, maxsplit=1, flags=re.I)[0]
        text = re.sub(r'<sup>.*?</sup>|<!--.*?-->', '', text, flags=re.S)
        words = text.split(); candidates = []
        for start in range(0,len(words),65):
            excerpt = ' '.join(words[start:start+100]); bag=set(re.findall(r'\b[a-z0-9]+\b',excerpt.lower()))
            candidates.append((bag,start,excerpt))
        frequency=collections.Counter(w for bag,_,_ in candidates for w in bag)
        candidates=[(sum(min(queries[w],3)*math.log(1+len(candidates)/(1+frequency[w]))
                         for w in bag if w not in stop),start,excerpt) for bag,start,excerpt in candidates]
        for score,start,excerpt in sorted(candidates, reverse=True)[:2]:
            chunks.append({'publisher_url':ref['url'], 'content_hash':ref['content_hash'],
                           'word_offset':start,'retrieval_score':score,'excerpt':excerpt})
    return {'id':row['id'],'kind':row['kind'],'question':row['question'],'answer':row['answer'],
            'publisher_excerpts':chunks,'limits':'Lexical excerpts are partial evidence, not an independent clinical verification.'}


def batch(dataset, review, source, limit):
    verify(dataset); log = rows(review/'judgments.jsonl'); seen={r['id'] for r in log}
    pending=[r for r in rows(dataset/'candidates.jsonl') if r['id'] not in seen][:limit]
    with sqlite3.connect(f'file:{source / "search.sqlite"}?mode=ro',uri=True) as connection:
        packets=[packet(row,connection) for row in pending]
    batchfile=review/f'packet-{len(log):05d}.json'
    if batchfile.exists():
        if json.loads(batchfile.read_text())!=packets:raise ValueError('Source packet changed')
    else:batchfile.write_text(json.dumps(packets,ensure_ascii=False,indent=2)+'\n')
    for item in packets:print(json.dumps(item,ensure_ascii=False))
    print(json.dumps({'packet_file':str(batchfile),'pending_total':len(rows(dataset/'candidates.jsonl'))-sum(r['decision']!='exclude' for r in log)}))


def record(dataset, review, decisions):
    by_id={r['id']:r for r in rows(dataset/'candidates.jsonl')}
    entries=[]
    for d in decisions:
        if d['id'] not in by_id or d['decision'] not in ['keep_candidate','revise_answer','rewrite_question','defer']:
            raise ValueError('Invalid direct judgment')
        if not d.get('reason') or not d.get('source_assessment'):raise ValueError('A reason and evidence assessment are required')
        entries.append({**d,'kind':by_id[d['id']]['kind'],'review_mode':'assistant_direct',
                        'content_reviewed':True,'clinical_certification':False,
                        'candidate_sha256':hashlib.sha256(json.dumps(by_id[d['id']],sort_keys=True,ensure_ascii=False).encode()).hexdigest()})
    append(review,entries);print(json.dumps({'logged_direct_judgments':len(entries)}))


def summary(dataset, review):
    verify(dataset); log=rows(review/'judgments.jsonl'); previous=None
    for sequence,item in enumerate(log,1):
        value=dict(item); sha=value.pop('entry_sha256')
        if value['sequence']!=sequence or value['previous_sha256']!=previous:raise ValueError('Journal order changed')
        if hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()!=sha:
            raise ValueError('Journal judgment changed')
        previous=sha
    total=len(rows(dataset/'candidates.jsonl'))+len(rows(dataset/'excluded.jsonl'))
    result={'logged':len(log),'total':total,'pending':total-len(log),
            'decisions':dict(collections.Counter(r['decision'] for r in log)),
            'review_modes':dict(collections.Counter(r['review_mode'] for r in log)),
            'last_entry_sha256':previous,'clinical_certification':False}
    (review/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['init','batch','record','summary'])
    parser.add_argument('--dataset-dir',default='.local/datasets/qa-v2-20261009-01')
    parser.add_argument('--review-dir',default='.local/qa-v2-review-20261009-01')
    parser.add_argument('--source-project',default=str(ROOT.parent/'oral-boards'))
    parser.add_argument('--limit',type=int,default=8);parser.add_argument('--decisions-file')
    args=parser.parse_args();dataset=local_directory(args.dataset_dir);review=local_directory(args.review_dir)
    if args.operation=='init':initialize(dataset,review)
    elif args.operation=='batch':batch(dataset,review,Path(args.source_project).resolve(),args.limit)
    elif args.operation=='record':record(dataset,review,json.loads(local_directory(args.decisions_file).read_text()))
    else:summary(dataset,review)

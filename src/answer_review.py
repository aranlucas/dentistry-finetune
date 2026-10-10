"""Record explicit assistant answer decisions; this code never judges semantics."""
import argparse
import collections
import hashlib
import json
from qa import digest, local_directory
from judge_review import append, rows

RUBRIC = {
    'pass':'Required facts and qualifiers present, no unsupported claims or unusable repetition.',
    'partial':'Relevant correct content, but required facts or qualifiers are missing.',
    'fail':'Contradiction, materially unsupported claim, wrong answer, or unusable response.'}


def verify_journal(run):
    previous=None
    for index,item in enumerate(rows(run/'judgments.jsonl'),1):
        value=dict(item);sha=value.pop('entry_sha256')
        if value['sequence']!=index or value['previous_sha256']!=previous:
            raise ValueError('Judgment sequence changed')
        if hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()!=sha:
            raise ValueError('Logged judgment changed')
        answer=next((r for r in rows(run/f"runs/{item['condition']}-predictions.jsonl") if r['id']==item['question_id']),None)
        if answer is None or hashlib.sha256(json.dumps(answer,sort_keys=True).encode()).hexdigest()!=item['answer_sha256']:
            raise ValueError('Judged answer changed')
        previous=sha


def record(run, decisions):
    verify_journal(run)
    manifest=json.loads((run/'manifest.json').read_text())
    if digest(run/'questions.jsonl')!=manifest['questions_sha256']:raise ValueError('Frozen questions changed')
    questions={r['id']:r for r in rows(run/'questions.jsonl')};entries=[]
    for decision in decisions:
        condition=decision['condition'];question_id=decision['question_id']
        if condition not in ('base','adapter') or decision['decision'] not in RUBRIC:
            raise ValueError('Invalid explicit judgment')
        if question_id not in questions or not decision.get('reason'):raise ValueError('Question and specific reason required')
        fingerprint=json.loads((run/f'runs/{condition}-fingerprint.json').read_text())
        if fingerprint['questions_sha256']!=manifest['questions_sha256'] or fingerprint['config_sha256']!=manifest['config_sha256']:
            raise ValueError('Wrong evaluation recipe')
        answers={r['id']:r for r in rows(run/f'runs/{condition}-predictions.jsonl')}
        answer=answers[question_id]
        entries.append({**decision,'id':condition+':'+question_id,
                        'answer_sha256':hashlib.sha256(json.dumps(answer,sort_keys=True).encode()).hexdigest(),
                        'question_sha256':hashlib.sha256(json.dumps(questions[question_id],sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                        'review_mode':'assistant_direct', 'reviewer':'Codex assistant in this conversation',
                        'blinded':False, 'clinical_certification':False})
    existing={r['id'] for r in rows(run/'judgments.jsonl')};ids=[r['id'] for r in entries]
    if len(set(ids))!=len(ids) or existing & set(ids):raise ValueError('Never overwrite or duplicate judgments')
    append(run,entries)
    summary(run)


def summary(run):
    verify_journal(run)
    judgments=rows(run/'judgments.jsonl');n=len(rows(run/'questions.jsonl'));counts={}
    for condition in ('base','adapter'):
        counts[condition]=dict(collections.Counter(r['decision'] for r in judgments if r['condition']==condition))
        counts[condition]['pending']=n-sum(counts[condition].values())
    result={'questions':n,'counts':counts,'rubric':RUBRIC,
            'limits':json.loads((run/'manifest.json').read_text())['limits'],
            'clinical_certification':False}
    (run/'judge-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['record','summary'])
    parser.add_argument('--run-dir',required=True);parser.add_argument('--decisions-file');args=parser.parse_args()
    run=local_directory(args.run_dir)
    if args.operation=='record':
        if not args.decisions_file:parser.error('--decisions-file required')
        record(run,json.loads(local_directory(args.decisions_file).read_text()))
    else:summary(run)

"""Ephemeral local reference reading using a completed, provenance-checked model."""
import argparse
import json
import os
import re
import sys
from qa import PII, digest, generate_response, load, local_directory, verify
from resources import Guard


def predict(run):
    if os.environ.get('DENTISTRY_BOUNDED_JOB') != '1':
        raise ValueError('Use src/bounded.py')
    request = json.loads(sys.stdin.read(4096))
    if not isinstance(request, dict) or set(request) != {'question', 'reference', 'condition'}:
        raise ValueError('Expected a question, publisher excerpt and model condition')
    question, reference, condition = (request[k] for k in ('question', 'reference', 'condition'))
    if (not isinstance(question, str) or not question.strip() or len(question) > 500
            or not isinstance(reference, str) or not reference.strip() or len(reference) > 2000
            or condition not in ('base', 'adapter')):
        raise ValueError('Invalid local reference request')
    if any(re.search(pattern, question + ' ' + reference) for pattern in PII.values()):
        raise ValueError('Identifier-form content is excluded')
    cfg, _ = verify(run)
    completed = json.loads((run / 'runs/training-summary.json').read_text())
    if digest(run / 'adapters/qa/adapters.safetensors') != completed['adapter_sha256']:
        raise ValueError('Completed adapter changed')
    prompt = ('Answer using these publisher excerpts. Preserve conditions and uncertainty. '
              'If the excerpts do not support an answer, say they are insufficient.\n\n'
              '[S1] ' + reference.strip() + '\n\nStudy question: ' + question.strip())
    guard = Guard(cfg, run / 'runs/reference-demo-resources.jsonl', 45)
    model, tokenizer = load(run, cfg, condition == 'adapter')
    guard.check(force=True)
    response = generate_response(model, tokenizer, cfg, prompt, cfg['seed'], guard)
    guard.check(force=True)
    # Prompt/answer are returned only to the local caller, never added to datasets.
    print(json.dumps({'condition': condition, 'review_status': 'unjudged', **response}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', required=True)
    args = parser.parse_args()
    predict(local_directory(args.run_dir))

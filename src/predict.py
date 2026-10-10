"""One local request in a short-lived process; prompts are never written to disk."""
import json
import fcntl
import sys
import time
from runtime import ROOT, CFG, load_local, infer
from resources import Guard
from task import user_prompt, parse_strict
from evaluate import retrieval_answer

def main():
    request = json.loads(sys.stdin.read(4096))
    condition = request.get('condition', 'retrieval')
    if condition not in ['retrieval','base_rag','adapter_rag']:
        raise ValueError('Unknown condition')
    note = request.get('note', '')
    passages = request.get('passages', [])
    if not isinstance(note, str) or len(note) > 240 or not isinstance(passages,list) or len(passages)>2:
        raise ValueError('Input exceeds local demo bounds')
    for index, passage in enumerate(passages):
        if not isinstance(passage,dict) or not isinstance(passage.get('text'),str) or len(passage['text'])>450:
            raise ValueError('Invalid passage')
        passage['citation'] = f'S{index+1}'
    started = time.perf_counter()
    example = {'note': note, 'passages': passages}
    if condition == 'retrieval':
        raw = retrieval_answer(example)
    else:
        (ROOT/'.local').mkdir(exist_ok=True)
        model_lock=(ROOT/'.local/model-job.lock').open('a')
        try:fcntl.flock(model_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Another bounded model job is already running')
        guard = Guard(CFG, ROOT/'runs/demo-resources.jsonl', 45)
        model, tokenizer = load_local(condition == 'adapter_rag')
        guard.check(force=True)
        raw = infer(model, tokenizer, user_prompt(note,passages))
        guard.check(force=True)
    value, valid = parse_strict(raw)
    grounded = bool(valid and value['answer']!='ABSTAIN' and any(p['citation']==value['citation'] and value['answer'] in p['text'] for p in passages))
    print(json.dumps({'condition':condition,'raw':raw,'schema_valid':valid,
                      'supported_quote':grounded,'seconds':time.perf_counter()-started}))

if __name__=='__main__': main()

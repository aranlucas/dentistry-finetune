"""Local, explicitly developmental model comparisons; not held-out benchmarks."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from qa import ROOT, config, digest, generate_response, load, local_directory, verify


def evaluate(run, condition, resume=False):
    if os.environ.get('DENTISTRY_BOUNDED_JOB')!='1':raise ValueError('Use src/bounded.py')
    manifest=json.loads((run/'manifest.json').read_text());cfg=config(run)
    parent=local_directory(manifest['model_run']);verify(parent)
    questions=run/'questions.jsonl'
    if digest(questions)!=manifest['questions_sha256'] or digest(run/'config.json')!=manifest['config_sha256']:
        raise ValueError('Frozen development recipe changed')
    training=json.loads((parent/'runs/training-summary.json').read_text())
    adapter=parent/'adapters/qa/adapters.safetensors'
    if digest(adapter)!=training['adapter_sha256']:raise ValueError('Completed adapter changed')
    items=[json.loads(l) for l in questions.read_text().splitlines()]
    fingerprint={'condition':condition,'questions_sha256':manifest['questions_sha256'],
                 'config_sha256':manifest['config_sha256'],'implementation_sha256':digest(Path(__file__)),
                 'generation_implementation_sha256':digest(ROOT/'src/qa.py'),
                 'model_provenance_sha256':digest(parent/'model-provenance.json'),
                 'adapter_sha256':training['adapter_sha256'] if condition=='adapter' else None,
                 'development_only':True,'reference_excerpts':False,'repair':False}
    folder=run/'runs';folder.mkdir(exist_ok=True)
    fp=folder/f'{condition}-fingerprint.json';output=folder/f'{condition}-predictions.jsonl'
    if output.exists() and not resume:raise ValueError('Never overwrite completed answers')
    if fp.exists():
        if json.loads(fp.read_text())!=fingerprint:raise ValueError('Development fingerprint changed')
    else:fp.write_text(json.dumps(fingerprint,indent=2)+'\n')
    saved=[json.loads(l) for l in output.read_text().splitlines()] if output.exists() else []
    if [r['id'] for r in saved]!=[r['id'] for r in items[:len(saved)]]:raise ValueError('Saved answer prefix changed')
    if len(saved)==len(items):return
    from resources import Guard
    guard=Guard(cfg,folder/f'{condition}-resources.jsonl',300)
    started=time.perf_counter();model,tokenizer=load(parent,cfg,condition=='adapter');guard.check(force=True)
    for item in items[len(saved):]:
        seed=(cfg['seed']+int(hashlib.sha256(item['id'].encode()).hexdigest()[:8],16))%(2**32)
        response=generate_response(model,tokenizer,cfg,item['question'],seed,guard)
        row={'id':item['id'],'condition':condition,**response}
        with output.open('a') as stream:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        saved.append(row)
        print(json.dumps({'condition':condition,'completed':len(saved),'finish_reason':row['finish_reason']}),flush=True)
        time.sleep(cfg['cooldown_seconds_per_batch'])
    guard.check(force=True)
    import mlx.core as mx
    (folder/f'{condition}-summary.json').write_text(json.dumps({'status':'complete','n':len(saved),
        'wall_seconds':time.perf_counter()-started,'mlx_peak_mib':mx.get_peak_memory()/1048576},indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['evaluate'])
    parser.add_argument('--run-dir',required=True);parser.add_argument('--condition',choices=['base','adapter'],required=True)
    parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    evaluate(local_directory(args.run_dir),args.condition,args.resume)

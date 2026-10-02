"""Local-only raw predictions; only aggregates may be exported."""
import argparse,hashlib,json,time
from runtime import ROOT,CFG,load_local,infer
from resources import Guard
from task import score,canonical,user_prompt
METRICS=['json_valid','schema_valid','semantic_exact','text_exact','citation_valid','grounded_quote','correct_citation','abstained','unsupported_answer']

def retrieval_answer(example):
    """Lexical extraction from supplied candidate passages; no model or gold labels."""
    templates=['Complete this study note: ','Finish the source sentence: ','Fill in the omitted ending: ',
               'What words finish this source note? ','Supply the exact missing ending for review: ',
               'For my practice notes, complete the citation-backed sentence: ']
    note=example['note'];lead=next((t for t in templates if note.startswith(t)),None)
    if lead is None:return canonical({'answer':'ABSTAIN','citation':'NONE'})
    prefix=note[len(lead):];matches=[p for p in example['passages'] if p['text'].startswith(prefix+' ')]
    if len(matches)!=1:return canonical({'answer':'ABSTAIN','citation':'NONE'})
    return canonical({'answer':matches[0]['text'][len(prefix):].strip(),'citation':matches[0]['citation']})

def summarize(rows):
    n=len(rows)
    return {'n':n,**{k:{'count':sum(r[k] for r in rows),'total':n,'rate':sum(r[k] for r in rows)/n if n else None} for k in METRICS}}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--condition',choices=['retrieval','base_rag','adapter_rag','adapter_closed'],required=True)
    ap.add_argument('--resume',action='store_true',help='Continue an interrupted immutable evaluation; never retry a generated answer')
    a=ap.parse_args();tag=a.condition
    prediction_path=ROOT/f'runs/{tag}-predictions.jsonl'
    if prediction_path.exists() and not a.resume:raise SystemExit('Refusing to overwrite frozen predictions; --resume continues only missing cases')
    started=time.perf_counter();guard=None if tag=='retrieval' else Guard(CFG,ROOT/f'runs/{tag}-resources.jsonl',300)
    meta=json.loads((ROOT/'data/manifest.json').read_text())['splits']['test'];path=ROOT/'data'/meta['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==meta['sha256'];examples=[json.loads(line) for line in path.read_text().splitlines()]
    fingerprint={'condition':tag,'test_sha256':meta['sha256'],'revision':CFG['revision'],
                 'max_new_tokens':CFG['max_new_tokens'],'temperature':0,
                 'adapter_sha256':hashlib.sha256((ROOT/'adapters/pilot/adapters.safetensors').read_bytes()).hexdigest() if tag.startswith('adapter') else None}
    fingerprint_path=ROOT/f'runs/{tag}-fingerprint.json'
    if fingerprint_path.exists():assert json.loads(fingerprint_path.read_text())==fingerprint,'Immutable evaluation settings changed'
    else:fingerprint_path.write_text(json.dumps(fingerprint,indent=2))
    rows=[json.loads(line) for line in prediction_path.read_text().splitlines()] if prediction_path.exists() else []
    assert [r['id'] for r in rows]==[e['id'] for e in examples[:len(rows)]], 'Resume records must be an exact prefix'
    if tag!='retrieval':model,tokenizer=load_local(tag.startswith('adapter'));guard.check(force=True)
    for e in examples[len(rows):]:
        if guard:guard.check()
        tic=time.perf_counter();used=dict(e)
        if tag=='adapter_closed':
            used['passages']=[];used['expected']={'answer':'ABSTAIN','citation':'NONE'};used['input']=user_prompt(e['note'],[])
        raw=retrieval_answer(used) if tag=='retrieval' else infer(model,tokenizer,used['input'])
        row={'id':e['id'],'kind':e['kind'],'raw':raw,'seconds':time.perf_counter()-tic,**score(raw,used)};rows.append(row)
        with (ROOT/f'runs/{tag}-predictions.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        if len(rows)%8==0:print(json.dumps({'condition':tag,'completed':len(rows),'exact_so_far':sum(r['semantic_exact'] for r in rows)}),flush=True)
        if guard:time.sleep(0.35)
    if guard:guard.check(force=True)
    peak=None
    if guard:
        import mlx.core as mx
        peak=mx.get_peak_memory()/1024**2
    report={'condition':tag,'test_sha256':meta['sha256'],'model_revision':CFG['revision'],
            'decoding':{'temperature':0,'max_new_tokens':CFG['max_new_tokens'],'repair':False},
            'metrics':summarize(rows),'supported':summarize([r for r in rows if r['kind']=='supported']),
            'abstention_cases':summarize([r for r in rows if r['kind']!='supported']),
            'wall_seconds':time.perf_counter()-started,'mlx_peak_mib':peak}
    (ROOT/f'runs/{tag}-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'condition':tag,'metrics':report['metrics'],'wall_seconds':report['wall_seconds'],'mlx_peak_mib':peak},indent=2))
if __name__=='__main__':main()

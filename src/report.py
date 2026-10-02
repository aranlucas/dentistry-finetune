"""Recompute important metrics independently from raw local outputs; export aggregates only."""
import json
from pathlib import Path
from runtime import ROOT,CFG

def independent(raw,example):
    duplicate=False
    def pairs(items):
        nonlocal duplicate
        duplicate=duplicate or len({k for k,v in items})!=len(items)
        return dict(items)
    try:v=json.loads(raw,object_pairs_hook=pairs);parsed=True
    except (TypeError,ValueError):v=None;parsed=False
    valid=(parsed and not duplicate and type(v)==dict and sorted(v)==['answer','citation']
           and type(v['answer'])==str and 0<len(v['answer'])<=400 and v['citation'] in ['S1','S2','NONE']
           and ((v['answer']=='ABSTAIN')==(v['citation']=='NONE')))
    abstained=bool(valid and v['answer']=='ABSTAIN')
    grounded=bool(valid and not abstained and any(p['citation']==v['citation'] and v['answer'] in p['text'] for p in example['passages']))
    return {'json_valid':parsed,'schema_valid':bool(valid),'semantic_exact':bool(valid and v==example['expected']),
            'citation_valid':bool(valid and (v['citation']=='NONE' or any(p['citation']==v['citation'] for p in example['passages']))),
            'grounded_quote':grounded,'abstained':abstained,'unsupported_answer':bool(valid and not abstained and not grounded)}

def aggregate(rows):
    n=len(rows)
    if not rows:
        return {'n':0,'semantic_exact':{'count':0,'total':0,'rate':None},'schema_valid':{'count':0,'total':0,'rate':None}}
    return {'n':n,**{k:{'count':sum(r[k] for r in rows),'total':n,'rate':sum(r[k] for r in rows)/n if n else None} for k in rows[0] if isinstance(rows[0][k],bool)}}

def main():
    examples=[json.loads(l) for l in (ROOT/'data/heldout.jsonl').read_text().splitlines()]
    conditions={};scored={}
    for condition in ['retrieval','base_rag','adapter_rag','adapter_closed']:
        path=ROOT/f'runs/{condition}-predictions.jsonl'
        if not path.exists():continue
        predictions=[json.loads(l) for l in path.read_text().splitlines()];rows=[]
        assert [p['id'] for p in predictions]==[e['id'] for e in examples[:len(predictions)]]
        for p,e in zip(predictions,examples):
            used=dict(e)
            if condition=='adapter_closed':used['passages']=[];used['expected']={'answer':'ABSTAIN','citation':'NONE'}
            recomputed=independent(p['raw'],used)
            for key,value in recomputed.items():assert p[key]==value,f'Independent metric discrepancy: {condition}/{key}'
            rows.append({'id':p['id'],'kind':e['kind'],**recomputed})
        scored[condition]=rows
        summary_path=ROOT/f'runs/{condition}-summary.json'
        summary=json.loads(summary_path.read_text()) if summary_path.exists() else {}
        conditions[condition]={'status':'complete' if len(rows)==len(examples) else 'resource_guard_interrupted',
                               'planned_cases':len(examples),'metrics':aggregate(rows),
                               'supported':aggregate([r for r in rows if r['kind']=='supported']),
                               'abstention_cases':aggregate([r for r in rows if r['kind']!='supported']),
                               'wall_seconds':summary.get('wall_seconds'),'mlx_peak_mib':summary.get('mlx_peak_mib')}
    paired_n=min(len(scored[k]) for k in ['retrieval','base_rag','adapter_rag'])
    paired={k:aggregate(scored[k][:paired_n]) for k in ['retrieval','base_rag','adapter_rag']}
    adapter=conditions['adapter_rag'];base=conditions['base_rag'];retrieval=conditions['retrieval']
    finding=(f"On {paired_n} paired cases, lexical extraction scored {paired['retrieval']['semantic_exact']['count']}/{paired_n}; "
             f"base + excerpts {paired['base_rag']['semantic_exact']['count']}/{paired_n}; "
             f"LoRA + excerpts {paired['adapter_rag']['semantic_exact']['count']}/{paired_n}. "
             'This small extractive benchmark does not establish clinical reliability or broad oral-board reasoning.')
    resources={}
    for tag in ['base_rag','train','adapter_rag','adapter_closed']:
        path=ROOT/f'runs/{tag}-resources.jsonl'
        if not path.exists():continue
        samples=[json.loads(l) for l in path.read_text().splitlines()]
        episodes=[]
        for sample in samples:
            if 'elapsed_seconds' not in sample or not episodes:episodes.append([])
            episodes[-1].append(sample)
        resources[tag]={'min_free_percent':min(s['free_percent'] for s in samples),'max_rss_mib':max(s['rss_mib'] for s in samples),
                        'episodes':[{'elapsed_seconds':episode[-1].get('elapsed_seconds',0),
                                     'system_swapout_growth_mib':(episode[-1]['system_swapouts_bytes']-episode[0]['system_swapouts_bytes'])/1024**2}
                                    for episode in episodes],
                        'thermal_status':'No warning recorded in sampled pmset output; actual temperature unknown'}
        if tag in conditions:
            conditions[tag]['wall_seconds_including_interrupted_segments']=sum(e['elapsed_seconds'] for e in resources[tag]['episodes'])
            conditions[tag]['wall_seconds_note']='wall_seconds in the evaluator summary is the final segment only when resumed'
    report={'finding':finding,'paired_n':paired_n,'paired_metrics':paired,'conditions':conditions,
            'training':json.loads((ROOT/'runs/training-summary.json').read_text()),
            'stopped_training_attempt':json.loads((ROOT/'runs/stopped-summary.json').read_text()) if (ROOT/'runs/stopped-summary.json').exists() else None,
            'corpus_summary':json.loads((ROOT/'runs/corpus-summary.json').read_text()),'resources':resources,
            'qualitative_failures':{tag:json.loads((ROOT/f'runs/{tag}-failure-summary.json').read_text())
                                    for tag in ['base_rag','adapter_rag'] if (ROOT/f'runs/{tag}-failure-summary.json').exists()},
            'model':{'name':CFG['upstream'],'revision':CFG['revision'],'license':'Apache-2.0'},
            'limitations':['Cloze questions expose the beginning of the target sentence; lexical matching is intentionally strong.',
                           'Each supported model prompt receives two excerpts including the gold sentence; corpus retrieval recall is not measured.',
                           'Exact target completion is a narrow factual proxy. No clinician reviewed answers or clinical reasoning.',
                           'Source documents and exact snippets are disjoint across train/validation/test; shared terminology and semantic overlap can remain.',
                           'The model saw 40 updates in the saved run; no checkpoint or hyperparameter was selected on held-out outcomes.',
                           'System-wide swap counters include other tasks; no claim of experiment-wide zero swapping.',
                           'Publisher copyrights retained. Source freshness and clinical conflicts not independently resolved.'],
            'privacy':'No corpus text, source document titles, examples, predictions, or weights included in this report'}
    (ROOT/'runs/results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(finding)
    print(json.dumps({'paired_n':paired_n,'conditions':{k:v['status'] for k,v in conditions.items()}},indent=2))

if __name__=='__main__':main()

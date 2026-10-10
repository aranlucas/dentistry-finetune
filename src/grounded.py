"""Frozen local publisher retrieval for a separate, excerpt-assisted development check."""
import argparse
import collections
import hashlib
import json
import math
import os
import re
import sqlite3
import time
from pathlib import Path
from qa import ROOT, config, digest, generate_response, load, local_directory, offline, StudyTokenizer, messages, verify


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def terms(text):
    stop=set('a an the and or of to in for with is are be as that this it on at by from what how when should can which do does not its only alone all has have child children patient dental aapd policy guidance guideline study fictional proposed before after'.split())
    return collections.Counter(t for t in re.findall(r'\b[a-z0-9]+\b',text.lower()) if t not in stop)


def prepare(source_run, parent, destination, source_project, phrase_boost=0.0):
    if destination.exists():raise ValueError('Choose a new frozen local version')
    verify(parent)
    prior=json.loads((source_run/'manifest.json').read_text())
    if digest(source_run/'questions.jsonl')!=prior['questions_sha256']:raise ValueError('Prior frozen questions changed')
    questions=read_rows(source_run/'questions.jsonl');cfg=config(parent)
    refs={r['content_hash']:r for row in read_rows(parent/'data/train.jsonl') for r in row['publisher_references']}
    chunks=[];documents=[]
    with sqlite3.connect(f'file:{source_project / "search.sqlite"}?mode=ro',uri=True) as connection:
        for sha,ref in sorted(refs.items()):
            if not ref['active'] or ref['identifier_form_flag']:raise ValueError('Unapproved publisher reference')
            found=connection.execute('SELECT doc FROM content WHERE hash=?',(sha,)).fetchone()
            if not found:raise ValueError('Pinned local publisher document missing')
            body=found[0];documents.append({'content_hash':sha,'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'url':ref['url']})
            text=re.sub(r'^(?:PDF:|Source:|PDF SHA-256:).*$', '',body,flags=re.M)
            text=re.split(r'#+\s*(?:\*\*)?References\b',text,maxsplit=1,flags=re.I)[0]
            text=re.sub(r'<sup>.*?</sup>|<!--.*?-->', '',text,flags=re.S)
            words=text.split()
            for start in range(0,len(words),40):
                excerpt=' '.join(words[start:start+80])
                chunks.append({'content_hash':sha,'url':ref['url'],'title':ref['title'],'word_offset':start,'text':excerpt})
    # Only the original question and training-publisher text enter retrieval.
    # No reference answer, criteria, model response or judgment is used as a query.
    bags=[terms(c['text']) for c in chunks];df=collections.Counter(t for b in bags for t in b)
    offline()
    from mlx_lm.utils import load_tokenizer
    tokenizer=StudyTokenizer(load_tokenizer(parent/cfg['model']))
    frozen=[]
    for item in questions:
        query=terms(item['question'])
        scores=[sum(min(query[t],2)*math.log(1+len(chunks)/(1+df[t]))*min(b[t],2) for t in query if t in b) for b in bags]
        if phrase_boost:
            words=re.findall(r'\b[a-z0-9]+\b',item['question'].lower())
            phrases={tuple(words[j:j+n]) for n in (2,3) for j in range(len(words)-n+1)
                     if sum(t in query for t in words[j:j+n])>=2}
            for i,chunk in enumerate(chunks):
                text=' '+' '.join(re.findall(r'\b[a-z0-9]+\b',chunk['text'].lower()))+' '
                scores[i]+=phrase_boost*sum(sum(math.log(1+len(chunks)/(1+df[t])) for t in phrase if t in query)
                                             for phrase in phrases if ' '+' '.join(phrase)+' ' in text)
        ranked=sorted(range(len(chunks)),key=lambda i:(-scores[i],chunks[i]['content_hash'],chunks[i]['word_offset']))
        chosen=[dict(chunks[i],retrieval_score=scores[i]) for i in ranked[:2]]
        # Freeze the largest of these explicit excerpt windows that fits the
        # unchanged prompt budget; no answer target is ever truncated.
        for width in (80,70,60,50,40):
            passages=[{**c,'text':' '.join(c['text'].split()[:width])} for c in chosen]
            evidence='\n'.join(f"[S{i}] {c['text']}" for i,c in enumerate(passages,1))
            prompt='Answer using these publisher excerpts. Preserve conditions and uncertainty. If the excerpts do not support an answer, say they are insufficient.\n\n'+evidence+'\n\nStudy question: '+item['question']
            n=len(tokenizer.apply_chat_template(messages(prompt),tokenize=True,add_generation_prompt=True))
            if n<=cfg['max_seq_length']:break
        else:raise ValueError('Reference-assisted input exceeds unchanged token budget')
        frozen.append({**item,'input':prompt,'retrieved_passages':passages,'input_tokens':n})
    destination.mkdir();(destination/'runs').mkdir()
    (destination/'config.json').write_bytes((parent/'config.json').read_bytes())
    (destination/'questions.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in frozen))
    (destination/'retrieval-documents.json').write_text(json.dumps(documents,indent=2)+'\n')
    (destination/'retrieval-implementation.py').write_bytes(Path(__file__).read_bytes())
    manifest={'mode':'development_only','input_mode':'Question with retrieved publisher excerpts',
        'model_run':str(parent.relative_to(ROOT)),'question_count':len(frozen),
        'questions_sha256':digest(destination/'questions.jsonl'),'config_sha256':digest(destination/'config.json'),
        'retrieval_documents_sha256':digest(destination/'retrieval-documents.json'),
        'retrieval_implementation_sha256':digest(Path(__file__)),
        'retrieval_recipe':{'phrase_boost':phrase_boost,'window_words':80,'stride_words':40,'passages':2},
        'original_questions_sha256':prior['questions_sha256'], 'publisher_documents':len(documents),
        'retrieval_sources':'Training-publisher documents only. No original held-out or validation source.',
        'retrieval_query':'Question text only; no authored gold, criteria, predictions or judgments.',
        'freeze':'All retrieval selections and model inputs frozen before either condition generates.',
        'limits':'Separate excerpt-assisted development on known training facts. Directly compare base and adapter under the same supplied excerpts; scores are not comparable to question-only runs as an isolated training gain. Partial lexical windows may omit needed evidence. Not an independent benchmark or clinical certification. Everything local.'}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'questions':len(frozen),'publisher_documents':len(documents),'max_input_tokens':max(r['input_tokens'] for r in frozen)}))


def evaluate(run,condition,resume):
    if os.environ.get('DENTISTRY_BOUNDED_JOB')!='1':raise ValueError('Use src/bounded.py')
    manifest=json.loads((run/'manifest.json').read_text());cfg=config(run);parent=local_directory(manifest['model_run']);verify(parent)
    for name,key in [('questions.jsonl','questions_sha256'),('config.json','config_sha256'),('retrieval-documents.json','retrieval_documents_sha256')]:
        if digest(run/name)!=manifest[key]:raise ValueError('Frozen grounded recipe changed')
    if digest(run/'retrieval-implementation.py')!=manifest['retrieval_implementation_sha256']:raise ValueError('Archived retrieval implementation changed')
    training=json.loads((parent/'runs/training-summary.json').read_text())
    if digest(parent/'adapters/qa/adapters.safetensors')!=training['adapter_sha256']:raise ValueError('Completed adapter changed')
    fingerprint={'condition':condition,'questions_sha256':manifest['questions_sha256'],'config_sha256':manifest['config_sha256'],
        'implementation_sha256':digest(Path(__file__)),'generation_implementation_sha256':digest(ROOT/'src/qa.py'),
        'model_provenance_sha256':digest(parent/'model-provenance.json'),
        'adapter_sha256':training['adapter_sha256'] if condition=='adapter' else None,
        'development_only':True,'reference_excerpts':True,'repair':False}
    folder=run/'runs';fp=folder/f'{condition}-fingerprint.json';output=folder/f'{condition}-predictions.jsonl'
    if output.exists() and not resume:raise ValueError('Never overwrite saved answers')
    if fp.exists():
        if json.loads(fp.read_text())!=fingerprint:raise ValueError('Grounded fingerprint changed')
    else:fp.write_text(json.dumps(fingerprint,indent=2)+'\n')
    items=read_rows(run/'questions.jsonl');saved=read_rows(output) if output.exists() else []
    if [r['id'] for r in saved]!=[r['id'] for r in items[:len(saved)]]:raise ValueError('Saved answer prefix changed')
    if len(saved)==len(items):return
    from resources import Guard
    guard=Guard(cfg,folder/f'{condition}-resources.jsonl',300)
    started=time.perf_counter();model,tokenizer=load(parent,cfg,condition=='adapter');guard.check(force=True)
    for item in items[len(saved):]:
        seed=(cfg['seed']+int(hashlib.sha256(item['id'].encode()).hexdigest()[:8],16))%(2**32)
        answer=generate_response(model,tokenizer,cfg,item['input'],seed,guard)
        with output.open('a') as stream:stream.write(json.dumps({'id':item['id'],'condition':condition,**answer},ensure_ascii=False)+'\n')
        saved.append(answer);print(json.dumps({'condition':condition,'completed':len(saved),'finish_reason':answer['finish_reason']}),flush=True)
        time.sleep(cfg['cooldown_seconds_per_batch'])
    guard.check(force=True)
    import mlx.core as mx
    (folder/f'{condition}-summary.json').write_text(json.dumps({'status':'complete','n':len(saved),'wall_seconds':time.perf_counter()-started,'mlx_peak_mib':mx.get_peak_memory()/1048576},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['prepare','evaluate']);p.add_argument('--run-dir',required=True)
    p.add_argument('--source-run');p.add_argument('--parent');p.add_argument('--source-project',default=str(ROOT.parent/'oral-boards'))
    p.add_argument('--condition',choices=['base','adapter']);p.add_argument('--resume',action='store_true')
    p.add_argument('--phrase-boost',type=float,choices=[0.0,5.0],default=0.0);a=p.parse_args()
    if a.operation=='prepare':
        if not a.source_run or not a.parent:p.error('source-run and parent required')
        prepare(local_directory(a.source_run),local_directory(a.parent),local_directory(a.run_dir),Path(a.source_project).resolve(),a.phrase_boost)
    else:
        if not a.condition:p.error('condition required')
        evaluate(local_directory(a.run_dir),a.condition,a.resume)

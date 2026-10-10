"""Freeze explicitly authored local study rows; never automatically approve candidates."""
import argparse
import hashlib
import json
import random
import re
import shutil
from pathlib import Path
from qa import ROOT, SYSTEM, PII, StudyTokenizer, digest, messages, offline, verify, local_directory
from qa_dataset import verify as verify_candidates
from qa_long import verify_long
from judge_review import append, rows


def prepare(parent, dataset, review, specification, destination):
    verify(parent); verify_candidates(dataset)
    if destination.exists(): raise ValueError('Choose a new immutable run')
    spec = json.loads(specification.read_text())
    if spec['reviewer'] != 'Codex assistant in this conversation': raise ValueError('Explicit assistant authorship required')
    candidates = {r['id']:r for r in rows(dataset/'candidates.jsonl')}
    kept = {r['id'] for r in rows(review/'judgments.jsonl')
            if r['decision']=='keep_candidate' and r['review_mode']=='assistant_direct'}
    cfg = json.loads((parent/'config.json').read_text())
    recipe=spec.get('training',{})
    epochs=recipe.get('epochs',12)
    if not isinstance(epochs,int) or not 1<=epochs<=24:raise ValueError('Invalid fixed pass count')
    learning_rate=recipe.get('learning_rate',0.0002)
    if learning_rate not in (0.00005,0.0001,0.0002):raise ValueError('Unsupported local learning rate')
    cfg.update(seed=recipe.get('seed',20261013), epochs=epochs, learning_rate=learning_rate, temperature=0.0,
               segment_steps=64, checkpoint_every=8, schedule='qa-long-v1')
    layers=recipe.get('num_layers',cfg['num_layers']);rank=recipe.get('rank',cfg['lora_parameters']['rank'])
    if layers not in (4,8) or rank not in (8,16):raise ValueError('Unsupported local adapter capacity')
    cfg['num_layers']=layers;cfg['lora_parameters']={**cfg['lora_parameters'],'rank':rank}
    offline()
    from mlx_lm.utils import load_tokenizer
    tokenizer = StudyTokenizer(load_tokenizer(parent/cfg['model']))
    splits = {'train':[], 'valid':[], 'test':[]}; journal=[]; pairs=set()
    for fact in spec['facts']:
        origin = candidates[fact['origin_candidate_id']]
        if origin['id'] not in kept or origin['blocking_reasons']:
            raise ValueError('Every origin must have a direct keep recommendation and no blockers')
        if not fact.get('source_assessment'): raise ValueError('An authored source assessment is required')
        split = fact['split']
        if split not in ('train','valid'): raise ValueError('No held-out rows may be authored here')
        for index, question in enumerate(fact['questions']):
            answer=fact['answer']; pair=(question.strip().lower(),answer.strip().lower())
            if pair in pairs: raise ValueError('Duplicate pair')
            pairs.add(pair)
            if any(re.search(p, question+' '+answer) for p in PII.values()): raise ValueError('Identifier form excluded')
            chat=messages(question)+[{'role':'assistant','content':answer}]
            tokens=tokenizer.apply_chat_template(chat,tokenize=True)
            if len(tokens)>cfg['max_seq_length']: raise ValueError('Never truncate targets')
            row={'id':fact['id']+f'-{index+1:02d}', 'question':question, 'answer':answer, 'messages':chat,
                 'source_group':origin['source_group'], 'origin_candidate_id':origin['id'],
                 'publisher_references':origin['publisher_references'], 'sequence_tokens':len(tokens),
                 'review_status':'assistant_authored_source_relative_study_review',
                 'clinical_certification':False}
            splits[split].append(row)
            journal.append({'id':row['id'], 'decision':'include_local_study_only',
                            'review_mode':'assistant_author_review', 'content_reviewed':True,
                            'source_assessment':fact['source_assessment'], 'origin_candidate_id':origin['id'],
                            'row_sha256':hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                            'clinical_certification':False})
    groups={k:sorted({r['source_group'] for r in v}) for k,v in splits.items()}
    if set(groups['train']) & set(groups['valid']): raise ValueError('Source group overlap')
    cfg['total_steps']=len(splits['train'])*cfg['epochs']
    destination.mkdir(parents=True); (destination/'data').mkdir(); (destination/'runs').mkdir()
    def write(path,value): path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    write(destination/'config.json',cfg)
    shutil.copy2(parent/'model-provenance.json',destination/'model-provenance.json')
    (destination/'models').symlink_to((parent/'models').resolve(),target_is_directory=True)
    shutil.copy2(specification,destination/'data/author-specification.json')
    schedule=[]
    for epoch in range(cfg['epochs']):
        indices=list(range(len(splits['train'])));random.Random(cfg['seed']+epoch).shuffle(indices);schedule.extend(indices)
    write(destination/'data/schedule.json',schedule)
    manifest={'experiment':'curated-qa-v3-local', 'system':SYSTEM, 'seed':cfg['seed'],
              'config_sha256':digest(destination/'config.json'),
              'model_provenance_sha256':digest(destination/'model-provenance.json'),
              'schedule_sha256':digest(destination/'data/schedule.json'),
              'specification_sha256':digest(specification), 'candidate_integrity_sha256':digest(dataset/'INTEGRITY.json'),
              'review_journal_sha256':digest(review/'judgments.jsonl'),
              'source_db_sha256':json.loads((parent/'data/manifest.json').read_text())['source_db_sha256'],
              'source_groups':groups, 'previous_heldout_topics_excluded':[], 'splits':{},
              'source_exclusion_policy':'All origins are nonblocked qa-v2 candidates, which exclude every original validation and held-out publisher family.',
              'evaluation_limit':'Iterative development on seen facts. Not a held-out generalization benchmark or clinical certification.',
              'rights':'Local only; no corpus, dataset, outputs, or weight sharing authorized.',
              'training_origin':'Fresh pinned base; no previous adapter continued.'}
    for split,examples in splits.items():
        path=destination/'data'/('heldout.jsonl' if split=='test' else split+'.jsonl')
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in examples))
        manifest['splits'][split]={'file':path.name,'count':len(examples),'sha256':digest(path)}
    write(destination/'data/manifest.json',manifest)
    append(destination/'data',journal)
    write(destination/'STATUS.json',{'status':'prepared','detail':f'Concise source-reviewed authored study subset; fixed {epochs}-pass schedule, development only.'})
    verify_long(destination)
    print(json.dumps({'rows':{k:len(v) for k,v in splits.items()},'steps':cfg['total_steps'],'max_sequence':max(r['sequence_tokens'] for v in splits.values() for r in v)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--parent',required=True);p.add_argument('--dataset',required=True)
    p.add_argument('--review',required=True);p.add_argument('--specification',required=True);p.add_argument('--run-dir',required=True)
    a=p.parse_args();prepare(*[local_directory(v) for v in (a.parent,a.dataset,a.review,a.specification,a.run_dir)])

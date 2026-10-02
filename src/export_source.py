"""Explicit code/aggregate/dataset/sample allowlist; no raw corpus, predictions, or weights."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TOP=['README.md','LICENSE','AGENTS.md','.gitignore','pyproject.toml','requirements.lock']
AGGREGATE=['runs/results.json','runs/training-summary.json','runs/train-metrics.jsonl']
APPROVED_DATASET=['datasets/pilot-v1/'+name for name in
                  ['train.jsonl','valid.jsonl','heldout.jsonl','manifest.json','INTEGRITY.json','DATASET_CARD.md']]
AUTHORED_TRANSCRIPTS=['examples/transcripts-v1/'+name for name in
                     ['README.md','index.json','01-consent.md','02-behavior-guidance.md',
                      '03-caries-risk.md','04-antibiotic-stewardship.md','05-protective-stabilization.md']]

def export():
    target=ROOT/'.local/source-export'
    if target.exists():shutil.rmtree(target)
    target.mkdir(parents=True)
    files=[ROOT/name for name in TOP+AGGREGATE]
    files+=list((ROOT/'src').glob('*.py'))+list((ROOT/'configs').glob('*.json'))
    files+=list((ROOT/'docs').glob('*.json'))+list((ROOT/'docs').glob('*.md'))+[ROOT/'web/index.html']
    files+=list((ROOT/'tests').glob('*.py'))+list((ROOT/'.github/workflows').glob('*.yml'))
    files+=[ROOT/name for name in APPROVED_DATASET+AUTHORED_TRANSCRIPTS]
    for path in files:
        if not path.is_file():raise FileNotFoundError(f'Required deliverable missing: {path.name}')
    # Exact source snippets are permitted only in the approved pilot snapshot.
    # Source titles/URLs may also appear in the requested authored transcript
    # bibliographies, but that does not permit exporting source paragraphs there.
    local=ROOT/'data/manifest.json'
    forbidden_metadata=[];forbidden_snippets=[]
    if local.exists():
        manifest=json.loads(local.read_text())
        forbidden_metadata += [d['title'] for d in manifest['documents']]
        forbidden_metadata += [d['publisher_url'] for d in manifest['documents']]
        for meta in manifest['splits'].values():
            rows=[json.loads(l) for l in (ROOT/'data'/meta['file']).read_text().splitlines()]
            forbidden_snippets += [p['text'] for row in rows for p in row['passages']]
    receipt={}
    for path in sorted(set(files)):
        text=path.read_text()
        name=str(path.relative_to(ROOT))
        forbidden=[] if name in APPROVED_DATASET else forbidden_snippets
        if name not in APPROVED_DATASET+AUTHORED_TRANSCRIPTS:forbidden=forbidden+forbidden_metadata
        if any(value and value in text for value in forbidden):
            raise ValueError(f'Unapproved local document content found in export: {path.name}')
        if path.suffix in ['.safetensors','.bin','.sqlite','.gguf']:raise ValueError('Model/corpus file forbidden')
        relative=path.relative_to(ROOT);output=target/relative;output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(text);receipt[str(relative)]={'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
    (target/'EXPORT-MANIFEST.json').write_text(json.dumps(receipt,indent=2)+'\n')
    archive=ROOT/'.local/oral-board-local-lab-source.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(target.rglob('*')):
            if path.is_file():z.write(path,Path('oral-board-local-lab')/path.relative_to(target))
    print(json.dumps({'source_files':len(receipt),'zip_bytes':archive.stat().st_size,'archive':str(archive)},indent=2))

if __name__=='__main__':export()

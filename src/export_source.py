"""Explicit code/aggregate allowlist. Never export local corpus, predictions, or weights."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TOP=['README.md','LICENSE','AGENTS.md','.gitignore','pyproject.toml','requirements.lock']
AGGREGATE=['runs/results.json','runs/training-summary.json','runs/train-metrics.jsonl']

def export():
    target=ROOT/'.local/source-export'
    if target.exists():shutil.rmtree(target)
    target.mkdir(parents=True)
    files=[ROOT/name for name in TOP+AGGREGATE]
    files+=list((ROOT/'src').glob('*.py'))+list((ROOT/'configs').glob('*.json'))
    files+=list((ROOT/'docs').glob('*.json'))+list((ROOT/'docs').glob('*.md'))+[ROOT/'web/index.html']
    files+=list((ROOT/'tests').glob('*.py'))+list((ROOT/'.github/workflows').glob('*.yml'))
    for path in files:
        if not path.is_file():raise FileNotFoundError(f'Required deliverable missing: {path.name}')
    # Detect accidental copied snippets before shipping. Titles/URLs/provenance are
    # also confined to the local manifest, rather than included in the export.
    local=ROOT/'data/manifest.json'
    forbidden=[]
    if local.exists():
        manifest=json.loads(local.read_text())
        forbidden += [d['title'] for d in manifest['documents']]
        forbidden += [d['publisher_url'] for d in manifest['documents']]
        for meta in manifest['splits'].values():
            rows=[json.loads(l) for l in (ROOT/'data'/meta['file']).read_text().splitlines()]
            forbidden += [p['text'] for row in rows for p in row['passages']]
    receipt={}
    for path in sorted(set(files)):
        text=path.read_text()
        if any(value and value in text for value in forbidden):raise ValueError(f'Local document content found in export: {path.name}')
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

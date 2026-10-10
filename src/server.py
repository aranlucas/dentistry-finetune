"""Loopback-only study demo; no source text, requests, or outputs are logged."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs

ROOT=Path(__file__).resolve().parents[1]
BUSY=threading.Lock()
STATIC={'/lab.css':'text/css','/lab.js':'text/javascript'}

def qa_run(choice=None):
    from qa import local_directory
    if choice is None:
        selection=json.loads((ROOT/'.local/qa-run.json').read_text())['directory']
    else:
        if choice not in ['short','long']:raise ValueError('Unknown Q&A experiment')
        selection=json.loads((ROOT/'.local/qa-run-history.json').read_text())[choice]
    return local_directory(selection)

def comparison_data():
    """Read frozen cases and optional original outputs; never generate replacements."""
    dataset = ROOT / 'datasets/pilot-v1'
    manifest = json.loads((dataset / 'manifest.json').read_text())
    meta = manifest['splits']['test']
    raw = (dataset / meta['file']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != meta['sha256']:
        raise ValueError('Frozen pilot snapshot changed')
    examples = [json.loads(line) for line in raw.decode().splitlines()]
    documents = {d['local_id']: d for d in manifest['documents']}
    run_root = ROOT
    selection = ROOT / '.local/comparison-run.json'
    replay = selection.exists()
    if replay:
        relative = json.loads(selection.read_text())['directory']
        run_root = (ROOT / relative).resolve()
        if not run_root.is_relative_to((ROOT / '.local').resolve()):
            raise ValueError('Comparison reproduction must be local')
        if (run_root / 'data/heldout.jsonl').read_bytes() != raw:
            raise ValueError('Reproduction cases differ from the frozen pilot')
    def read_predictions(folder):
        result = {}
        for condition in ['retrieval', 'base_rag', 'adapter_rag']:
            path = folder / f'runs/{condition}-predictions.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
            if [r['id'] for r in rows] != [e['id'] for e in examples[:len(rows)]]:
                raise ValueError('Predictions must match the frozen case order')
            result[condition] = {r['id']: r for r in rows}
        return result

    predictions = read_predictions(run_root)
    original_predictions = read_predictions(ROOT) if replay else predictions
    def outputs_for(example, records):
        outputs = {}
        for condition, predictions_by_id in records.items():
            record = predictions_by_id.get(example['id'])
            outputs[condition] = None if record is None else {
                'raw': record['raw'],
                'schema_valid': record['schema_valid'],
                'semantic_exact': record['semantic_exact'],
                'json_valid': record['json_valid'],
                'seconds': record.get('seconds'),
            }
        return outputs
    cases = []
    for example in examples:
        cases.append({
            'id': example['id'], 'kind': example['kind'], 'note': example['note'],
            'expected': example['expected'], 'outputs': outputs_for(example, predictions),
            'original_outputs': outputs_for(example, original_predictions),
            'passages': [{**p, 'title': documents[p['doc_id']]['title'],
                          'url': documents[p['doc_id']]['publisher_url']}
                         for p in example['passages']],
        })
    metrics = run_root / 'runs/train-metrics.jsonl'
    loss = [json.loads(line) for line in metrics.read_text().splitlines()] if metrics.exists() else []
    original_metrics = ROOT / 'runs/train-metrics.jsonl'
    original_loss = [json.loads(line) for line in original_metrics.read_text().splitlines()] if original_metrics.exists() else []
    report_path = run_root / 'runs/results.json'
    report = json.loads(report_path.read_text()) if report_path.exists() else None
    if replay and report is None:
        from task import score
        def aggregate(rows):
            keys = ['json_valid', 'schema_valid', 'semantic_exact']
            return {'n': len(rows), **{k: {'count': sum(r[k] for r in rows),
                                          'total': len(rows),
                                          'rate': sum(r[k] for r in rows) / len(rows) if rows else None}
                                      for k in keys}}
        conditions = {}
        for condition, records in predictions.items():
            scored = [{**score(records[e['id']]['raw'], e), 'kind': e['kind']}
                      for e in examples if e['id'] in records]
            conditions[condition] = {
                'status': 'complete' if len(scored) == len(examples) else 'pending',
                'metrics': aggregate(scored),
                'abstention_cases': aggregate([r for r in scored if r['kind'] != 'supported']),
            }
        training_path = run_root / 'runs/training-summary.json'
        status_path = run_root / 'STATUS.json'
        status = json.loads(status_path.read_text()) if status_path.exists() else {}
        report = {'conditions': conditions, 'planned_cases': len(examples),
                  'paired_n': min(len(v) for v in predictions.values()),
                  'training': json.loads(training_path.read_text()) if training_path.exists() else None,
                  'reproduction_status': status.get('status', 'in_progress'),
                  'reproduction_detail': status.get('detail')}
    return {'cases': cases, 'loss': loss, 'original_loss': original_loss, 'reproduction': replay,
            'report': report,
            'demo_model_available': (ROOT / 'models/smollm2-135m/config.json').is_file(),
            'demo_adapter_available': (ROOT / 'adapters/pilot/adapters.safetensors').is_file(),
            'available_outputs': {k: len(v) for k, v in predictions.items()},
            'original_available_outputs': {k: len(v) for k, v in original_predictions.items()}}

def development_data(choice):
    from qa import digest, local_directory
    registry=json.loads((ROOT/'.local/development-run-history.json').read_text())
    if choice not in registry:raise ValueError('Unknown development run')
    run=local_directory(registry[choice]['directory'])
    manifest=json.loads((run/'manifest.json').read_text())
    if digest(run/'questions.jsonl')!=manifest['questions_sha256'] or digest(run/'config.json')!=manifest['config_sha256']:raise ValueError('Frozen development recipe changed')
    questions=[json.loads(l) for l in (run/'questions.jsonl').read_text().splitlines()]
    records={}; judgments={}
    journal=run/'judgments.jsonl';previous=None
    if journal.exists():
        for index,line in enumerate(journal.read_text().splitlines(),1):
            item=json.loads(line);value=dict(item);sha=value.pop('entry_sha256')
            if value['sequence']!=index or value['previous_sha256']!=previous:raise ValueError('Judgment order changed')
            if hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()!=sha:raise ValueError('Judgment changed')
            judgments[item['id']]=item;previous=sha
    counts={}
    for condition in ('base','adapter'):
        path=run/f'runs/{condition}-predictions.jsonl'
        saved=[json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
        if [r['id'] for r in saved]!=[q['id'] for q in questions[:len(saved)]]:raise ValueError('Answer order changed')
        if saved:
            fp=json.loads((run/f'runs/{condition}-fingerprint.json').read_text())
            if fp['questions_sha256']!=manifest['questions_sha256'] or fp['config_sha256']!=manifest['config_sha256']:raise ValueError('Answers belong to a different recipe')
        records[condition]={};counts[condition]={'pass':0,'partial':0,'fail':0,'pending':len(questions)}
        for item in saved:
            judgment=judgments.get(condition+':'+item['id'])
            if judgment:
                answer_sha=hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()
                if answer_sha!=judgment['answer_sha256']:raise ValueError('Judged answer changed')
                counts[condition]['pending']-=1;counts[condition][judgment['decision']]+=1
            records[condition][item['id']]={**item,'judgment':judgment}
    parent=local_directory(manifest['model_run']);progress=parent/'runs/progress.json'
    training=parent/'runs/training-summary.json';cfg=json.loads((parent/'config.json').read_text())
    return {'runs':[{'id':k,'label':v['label']} for k,v in registry.items()], 'label':registry[choice]['label'],
            'limits':manifest['limits'], 'input_mode':manifest.get('input_mode','Question alone'),
            'counts':counts, 'temperature':json.loads((run/'config.json').read_text())['temperature'],
            'training':json.loads(training.read_text()) if training.exists() else None,
            'steps':json.loads(progress.read_text())['steps'] if progress.exists() else 0,
            'planned_steps':cfg.get('total_steps',cfg['iters']),
            'cases':[{**q,'outputs':{c:records[c].get(q['id']) for c in records}} for q in questions]}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,status,body,kind='application/json'):
        self.send_response(status)
        self.send_header('Content-Type',kind+'; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)
    def origin_ok(self):
        host=self.headers.get('Host','')
        origin=self.headers.get('Origin')
        return host in self.server.allowed_hosts and (origin is None or origin in self.server.allowed_origins)
    def do_GET(self):
        if not self.origin_ok():return self.send(403,b'{}')
        route=urlparse(self.path).path
        if route=='/':return self.send(200,(ROOT/'web/index.html').read_bytes(),'text/html')
        if route=='/qa':return self.send(200,(ROOT/'web/qa.html').read_bytes(),'text/html')
        if route=='/development':return self.send(200,(ROOT/'web/development.html').read_bytes(),'text/html')
        if route=='/api/development':
            try:
                choice=parse_qs(urlparse(self.path).query).get('run',['curated'])
                if len(choice)!=1:raise ValueError('Invalid selection')
                return self.send(200,json.dumps(development_data(choice[0])).encode())
            except (OSError,ValueError,KeyError):
                return self.send(503,b'{"error":"Local development comparison is missing or inconsistent."}')
        if route in STATIC:return self.send(200,(ROOT/'web'/route[1:]).read_bytes(),STATIC[route])
        if route=='/api/qa':
            try:
                from qa import comparison_data as qa_comparison
                choices=parse_qs(urlparse(self.path).query).get('run',[None])
                if len(choices)!=1:raise ValueError('Invalid selection')
                run=qa_run(choices[0]);data=qa_comparison(run)
                cfg=json.loads((run/'config.json').read_text())
                data['schedule']=cfg.get('schedule','short')
                data['planned_steps']=cfg.get('total_steps',cfg['iters'])
                progress=run/'runs/progress.json'
                data['committed_steps']=json.loads(progress.read_text())['steps'] if progress.exists() else data['training']['steps'] if data['training'] else 0
                data['evaluation_limit']=json.loads((run/'data/manifest.json').read_text()).get('evaluation_limit','Clinical review pending.')
                return self.send(200,json.dumps(data).encode())
            except (OSError,ValueError,KeyError):
                return self.send(503,b'{"error":"The local Q&A experiment is unavailable or inconsistent."}')
        if route=='/api/results':return self.send(200,(ROOT/'runs/results.json').read_bytes())
        if route=='/api/comparison':
            try:return self.send(200,json.dumps(comparison_data()).encode())
            except (OSError,ValueError,KeyError):
                return self.send(503,b'{"error":"Frozen comparison files are missing or inconsistent."}')
        if route=='/api/practice':
            path=ROOT/'data/heldout.jsonl'
            if not path.exists():return self.send(404,b'{"error":"Local corpus unavailable"}')
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            safe=[{'id':r['id'],'note':r['note'],'passages':r['passages']} for r in rows if r['kind']=='supported']
            return self.send(200,json.dumps(safe).encode())
        return self.send(404,b'{}')
    def do_POST(self):
        if not self.origin_ok():return self.send(403,b'{}')
        if self.path not in ['/api/predict','/api/qa/predict','/api/development/predict']:return self.send(404,b'{}')
        try:n=int(self.headers.get('Content-Length','0'))
        except ValueError:return self.send(400,b'{}')
        if not 0<n<=4096:return self.send(413,b'{"error":"Request too large"}')
        if not BUSY.acquire(blocking=False):return self.send(429,b'{"error":"One inference at a time"}')
        try:
            request=self.rfile.read(n)
            if self.path in ['/api/qa/predict','/api/development/predict']:
                payload=json.loads(request)
                if not isinstance(payload,dict):raise ValueError('Invalid question')
                choice=payload.pop('run',None)
                experiment='qa-v1'
                if self.path=='/api/development/predict':
                    from qa import local_directory
                    registry=json.loads((ROOT/'.local/development-run-history.json').read_text())
                    if choice not in registry:raise ValueError('Unknown development run')
                    development=local_directory(registry[choice]['directory'])
                    manifest=json.loads((development/'manifest.json').read_text())
                    mode=manifest.get('input_mode','Question alone')
                    if mode=='Question with reviewer-selected publisher excerpts':experiment='qa-reader'
                    elif mode!='Question alone':raise ValueError('This comparison does not provide live inference')
                    run=local_directory(manifest['model_run'])
                else:run=qa_run(choice)
                request=json.dumps(payload).encode()
                command=['nice','-n','10',sys.executable,str(ROOT/'src/bounded.py'),'predict',
                         '--experiment',experiment,'--run-dir',str(run)]
                result=subprocess.run(command,input=request,capture_output=True,timeout=65,cwd=ROOT)
            else:
                result=subprocess.run([sys.executable,str(ROOT/'src/predict.py')],input=request,capture_output=True,timeout=50,cwd=ROOT)
            if result.returncode!=0:return self.send(503,b'{"error":"Local inference stopped. Check the question bounds, completed model, and available resources."}')
            output=json.loads(result.stdout)
            if self.path=='/api/development/predict':
                output['temperature']=json.loads((run/'config.json').read_text())['temperature']
            return self.send(200,json.dumps(output).encode())
        except subprocess.TimeoutExpired:return self.send(503,b'{"error":"Local inference time budget exceeded"}')
        except (ValueError,OSError):return self.send(400,b'{"error":"Invalid local request"}')
        finally:BUSY.release()

def make_server(port, proxy_url=None):
    """Bind loopback only; also accept the Portless origin when one is assigned."""
    httpd=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    httpd.allowed_origins={f'http://127.0.0.1:{httpd.server_port}',f'http://localhost:{httpd.server_port}'}
    if proxy_url:httpd.allowed_origins.add(proxy_url.rstrip('/'))
    httpd.allowed_hosts={urlparse(origin).netloc for origin in httpd.allowed_origins}
    return httpd

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=int(os.environ.get('PORT','8765')));args=ap.parse_args()
    httpd=make_server(args.port,os.environ.get('PORTLESS_URL'))
    print(f'Local study lab: {os.environ.get("PORTLESS_URL") or f"http://127.0.0.1:{httpd.server_port}"}',flush=True)
    httpd.serve_forever()

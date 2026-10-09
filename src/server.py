"""Loopback-only study demo; no source text, requests, or outputs are logged."""
import argparse
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
BUSY=threading.Lock()

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
        if route=='/api/results':return self.send(200,(ROOT/'runs/results.json').read_bytes())
        if route=='/api/practice':
            path=ROOT/'data/heldout.jsonl'
            if not path.exists():return self.send(404,b'{"error":"Local corpus unavailable"}')
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            safe=[{'id':r['id'],'note':r['note'],'passages':r['passages']} for r in rows if r['kind']=='supported']
            return self.send(200,json.dumps(safe).encode())
        return self.send(404,b'{}')
    def do_POST(self):
        if not self.origin_ok():return self.send(403,b'{}')
        if self.path!='/api/predict':return self.send(404,b'{}')
        try:n=int(self.headers.get('Content-Length','0'))
        except ValueError:return self.send(400,b'{}')
        if not 0<n<=4096:return self.send(413,b'{"error":"Request too large"}')
        if not BUSY.acquire(blocking=False):return self.send(429,b'{"error":"One inference at a time"}')
        try:
            request=self.rfile.read(n)
            result=subprocess.run([sys.executable,str(ROOT/'src/predict.py')],input=request,capture_output=True,timeout=50,cwd=ROOT)
            if result.returncode!=0:return self.send(503,b'{"error":"Local inference stopped or resources unavailable. Try retrieval."}')
            output=json.loads(result.stdout)
            return self.send(200,json.dumps(output).encode())
        except subprocess.TimeoutExpired:return self.send(503,b'{"error":"Local inference time budget exceeded"}')
        except (ValueError,OSError):return self.send(400,b'{"error":"Invalid local request"}')
        finally:BUSY.release()

def make_server(port, portless_url=None):
    """Accept one explicit local proxy origin while retaining loopback binding."""
    proxy_origin = None
    if portless_url:
        parsed = urlparse(portless_url)
        if (parsed.scheme not in {'http', 'https'} or
                not parsed.hostname or not parsed.hostname.endswith('.localhost') or
                parsed.username is not None or parsed.password is not None or
                parsed.path not in {'', '/'} or parsed.params or parsed.query or parsed.fragment):
            raise ValueError('PORTLESS_URL must be an HTTP(S) .localhost origin')
        proxy_port = parsed.port
        if proxy_port is not None and not 1 <= proxy_port <= 65535:
            raise ValueError('PORTLESS_URL must use a valid port')
        authority = parsed.hostname
        if proxy_port is not None and proxy_port != {'http': 80, 'https': 443}[parsed.scheme]:
            authority += f':{proxy_port}'
        proxy_origin = f'{parsed.scheme}://{authority}'

    httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    httpd.allowed_origins = {
        f'http://127.0.0.1:{httpd.server_port}',
        f'http://localhost:{httpd.server_port}',
    }
    if proxy_origin:
        httpd.allowed_origins.add(proxy_origin)
    httpd.allowed_hosts = {urlparse(origin).netloc for origin in httpd.allowed_origins}
    return httpd


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=os.environ.get('PORT','8765'));args=ap.parse_args()
    try:
        httpd=make_server(args.port,os.environ.get('PORTLESS_URL'))
    except ValueError as error:
        ap.error(str(error))
    print(f'Local study lab: {os.environ.get("PORTLESS_URL") or f"http://127.0.0.1:{httpd.server_port}"}',flush=True)
    httpd.serve_forever()

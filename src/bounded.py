"""Outer wall-clock deadline in addition to in-process resource checks."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('operation',choices=['train','evaluate'])
    ap.add_argument('--condition',choices=['retrieval','base_rag','adapter_rag','adapter_closed'])
    ap.add_argument('--resume',action='store_true')
    a=ap.parse_args();cfg=json.loads((ROOT/'configs/pilot.json').read_text())
    if a.operation=='evaluate' and not a.condition:ap.error('--condition is required for evaluate')
    command=[sys.executable,str(ROOT/'src'/f'{a.operation}.py')]
    if a.condition:command.extend(['--condition',a.condition])
    if a.resume:command.append('--resume')
    deadline=cfg['train_seconds']+10 if a.operation=='train' else 310
    try:
        result=subprocess.run(command,cwd=ROOT,timeout=deadline)
        raise SystemExit(result.returncode)
    except subprocess.TimeoutExpired:
        print('Stopped by outer wall-clock deadline',file=sys.stderr)
        raise SystemExit(124)

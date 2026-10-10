"""Outer wall-clock deadline in addition to in-process resource checks."""
import argparse
import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('operation',choices=['train','evaluate','predict'])
    ap.add_argument('--condition',choices=['retrieval','base_rag','adapter_rag','adapter_closed'])
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--experiment',choices=['pilot','qa-v1','qa-long-v1','qa-development','qa-grounded','qa-reader'],default='pilot')
    ap.add_argument('--run-dir')
    # Q&A uses its own condition names; existing pilot names keep their meaning.
    ap.add_argument('--qa-condition',choices=['base','adapter'])
    a=ap.parse_args();cfg=json.loads((ROOT/'configs/pilot.json').read_text())
    if a.experiment in ['qa-v1','qa-long-v1','qa-development','qa-grounded','qa-reader']:
        from qa import local_directory, config
        if not a.run_dir:ap.error('--run-dir is required for qa-v1')
        if a.condition:ap.error('Use --qa-condition for qa-v1')
        if a.operation=='evaluate' and not a.qa_condition:ap.error('--qa-condition is required')
        run=local_directory(a.run_dir);cfg=config(run)
        command=[sys.executable,str(ROOT/'src/qa.py'),a.operation,'--run-dir',a.run_dir]
        if a.experiment=='qa-development':
            if a.operation!='evaluate':ap.error('Development mode supports evaluation only')
            command=[sys.executable,str(ROOT/'src/development.py'),a.operation,'--run-dir',a.run_dir]
        if a.experiment=='qa-grounded':
            if a.operation!='evaluate':ap.error('Grounded development supports evaluation only')
            command=[sys.executable,str(ROOT/'src/grounded.py'),a.operation,'--run-dir',a.run_dir]
        if a.experiment=='qa-reader':
            if a.operation!='predict' or a.qa_condition or a.resume:ap.error('Reference reader supports ephemeral predict only')
            command=[sys.executable,str(ROOT/'src/reference_predict.py'),'--run-dir',a.run_dir]
        if a.experiment=='qa-long-v1' and a.operation=='train':
            command=[sys.executable,str(ROOT/'src/qa_long.py'),'train','--run-dir',a.run_dir]
        if a.qa_condition:command.extend(['--condition',a.qa_condition])
    else:
        if a.operation=='predict':ap.error('Bounded predict is available only for qa-v1')
        if a.qa_condition or a.run_dir:ap.error('Q&A options require --experiment qa-v1')
        if a.operation=='evaluate' and not a.condition:ap.error('--condition is required for evaluate')
        command=[sys.executable,str(ROOT/'src'/f'{a.operation}.py')]
        if a.condition:command.extend(['--condition',a.condition])
    if a.resume:command.append('--resume')
    deadline=cfg['train_seconds']+10 if a.operation=='train' else 55 if a.operation=='predict' else 310
    (ROOT/'.local').mkdir(exist_ok=True)
    lock=(ROOT/'.local/model-job.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('Another bounded model job is already running')
    try:
        result=subprocess.run(command,cwd=ROOT,timeout=deadline,
                              env={**os.environ,'DENTISTRY_BOUNDED_JOB':'1'})
        raise SystemExit(result.returncode)
    except subprocess.TimeoutExpired:
        print('Stopped by outer wall-clock deadline',file=sys.stderr)
        raise SystemExit(124)

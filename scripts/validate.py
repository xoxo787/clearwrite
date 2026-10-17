#!/usr/bin/env python3
"""Run the offline test suite and emit a machine-readable validation record.

Optional --wheel creates a disposable venv and installs that local wheel with
--no-index --no-deps. It does not download packages or call model services.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import unittest
import venv
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'reports/local-validation');p.add_argument('--wheel',type=Path);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    tests=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    start=time.perf_counter()
    with (a.out/'TESTS.txt').open('w',encoding='utf-8') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(tests)
    record={'executed_at_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'os':platform.system(),
            'tests':{'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'elapsed_seconds':round(time.perf_counter()-start,3),'passed':result.wasSuccessful()},
            'live_models':{'codex':'not_run','ollama':'not_run'},'external_detector':'not_run_by_this_command',
            'wheel':{'status':'not_run'},'semantic_equivalence':'not_established',
            'reader_experiment':{'participants':0,'status':'not_run'},
            'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src/clearwrite').glob('*.py'))}}
    if a.wheel:
        wheel=a.wheel.resolve()
        if not wheel.is_file():raise SystemExit('wheel does not exist')
        with tempfile.TemporaryDirectory(prefix='clearwrite-clean-') as tmp:
            envdir=Path(tmp)/'env';venv.EnvBuilder(with_pip=True).create(envdir)
            bindir=envdir/('Scripts' if os.name=='nt' else 'bin');python=bindir/('python.exe' if os.name=='nt' else 'python');exe=bindir/('clearwrite.exe' if os.name=='nt' else 'clearwrite')
            # Prevent PYTHONPATH source egg-info from masquerading as an installed wheel.
            clean_env=os.environ.copy()
            clean_env.pop('PYTHONPATH',None)
            clean_env.pop('PYTHONHOME',None)
            subprocess.run([str(python),'-m','pip','install','--no-index','--no-deps',str(wheel)],
                           check=True,capture_output=True,timeout=90,env=clean_env)
            proc=subprocess.run([str(exe),'analyze','-'],input='We keep the original file. We write edits to a new file.',text=True,encoding='utf-8',capture_output=True,cwd=tmp,check=True,timeout=20,env=clean_env)
            data=json.loads(proc.stdout)
            assert data['authorship']=='undetermined' and data['ai_probability'] is None
            record['wheel']={'status':'installed_and_cli_smoke_passed','file':wheel.name,'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'offline':True,'clean_venv':True}
    (a.out/'validation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))
    return 0 if result.wasSuccessful() and result.testsRun else 1

if __name__=='__main__':raise SystemExit(main())

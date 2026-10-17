#!/usr/bin/env python3
"""Opt-in publishing of a NEW repository. Never overwrite existing Git state.

Only known project files are selected. Inspect the dry-run before --publish.
No credentials are accepted as arguments; Git/gh use their existing credentials.
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {'src','scripts','tests','skills','plugins','docs','data','examples','licenses','reports','.github','.agents'}
TOP_FILES = {'README.md','README.en.md','LICENSE','THIRD_PARTY_NOTICES.md','SECURITY.md','AGENTS.md','CHANGELOG.md','CONTRIBUTING.md','pyproject.toml','requirements-build.txt','requirements-build.lock.txt','rewrite.py','.gitignore','.gitattributes'}
SKIP_PARTS = {'__pycache__','.venv','node_modules','reproduced','local','browser-local','dist','build'}
SECRET_RE = re.compile(rb'(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{25,}|\bgithub_pat_[A-Za-z0-9_]{25,}|\bsk-(?:proj-)?[A-Za-z0-9_-]{25,})')


def make_plan(repo: str, root: Path = ROOT) -> dict:
    if not isinstance(repo,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}(?:/[A-Za-z0-9][A-Za-z0-9_.-]{0,99})?',repo):
        raise ValueError('저장소 이름은 name 또는 owner/name 형식이어야 합니다.')
    if any(part in {'.','..'} for part in repo.split('/')):raise ValueError('상대 경로는 저장소 이름이 아닙니다.')
    root=root.resolve()
    if any((p/'.git').exists() for p in [root,*root.parents]):
        raise ValueError('이미 Git 저장소이거나 부모 저장소 안에 있습니다. 기존 Git 작업 흐름을 사용하세요.')
    files=[]
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root)
        if any(x in SKIP_PARTS or '.backup-' in x or x.endswith('.egg-info') for x in rel.parts):continue
        if len(rel.parts)==1 and p.name not in TOP_FILES:continue
        if len(rel.parts)>1 and rel.parts[0] not in DIRECTORIES:continue
        if p.is_symlink():raise ValueError('공개 대상에 심볼릭 링크가 있습니다: '+str(rel))
        if not p.is_file():continue
        if p.name.startswith('.env') or p.suffix in {'.pem','.key','.pyc','.log'}:continue
        if p.stat().st_size>5_000_000:raise ValueError('큰 파일을 먼저 검토하세요: '+str(rel))
        if SECRET_RE.search(p.read_bytes()):raise ValueError('비밀 정보 의심 문자열을 먼저 확인하세요: '+str(rel))
        files.append(rel.as_posix())
    if not {'README.md','LICENSE','pyproject.toml'}.issubset(files):raise ValueError('필수 프로젝트 파일이 없습니다.')
    return {'repository':repo,'visibility':'public','root':str(root),'file_count':len(files),'files':files,
            'mode':'dry-run','warning':'원문과 보고서가 공개됩니다. 자동 비밀 검사는 유출 방지를 보증하지 않습니다.',
            'commands':[['git','init','-b','main'],['git','add','--','<listed files>'],['git','commit','-m','Initial ClearWrite release'],['gh','repo','create',repo,'--public','--source','.','--remote','origin','--push']]}


def publish(plan: dict) -> None:
    root=Path(plan['root'])
    if not shutil.which('git') or not shutil.which('gh'):raise ValueError('Git과 GitHub CLI(gh)가 설치되어 있어야 합니다.')
    # Recheck files/Git state immediately before mutating; no implicit staging of
    # unrelated files. The user still owns responsibility for selected content.
    fresh=make_plan(plan['repository'],root)
    if fresh['files']!=plan['files']:raise ValueError('파일 목록이 바뀌었습니다. 계획을 다시 확인하세요.')
    def run(args: list[str], capture: bool=False):
        result=subprocess.run(args,cwd=root,check=True,text=True,encoding='utf-8',errors='replace',capture_output=capture,timeout=180)
        return result.stdout.strip() if capture else ''
    run(['gh','auth','status'])
    for key in ('user.name','user.email'):
        if not run(['git','config','--get',key],True):raise ValueError('본인의 Git '+key+' 설정이 필요합니다. 전역 값을 자동 변경하지 않습니다.')
    run(['git','init','-b','main'])
    # Batches avoid Windows command-line limits without shell interpretation.
    for i in range(0,len(plan['files']),40):run(['git','add','--',*plan['files'][i:i+40]])
    run(['git','commit','-m','Initial ClearWrite release'])
    run(['gh','repo','create',plan['repository'],'--public','--source','.','--remote','origin','--push'])


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True);p.add_argument('--publish',action='store_true');a=p.parse_args()
    try:
        plan=make_plan(a.repo);print(json.dumps(plan,ensure_ascii=False,indent=2))
        if a.publish:publish(plan);print('새 공개 저장소 생성 및 push 명령이 완료되었습니다.')
        return 0
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print('publish: '+str(exc)+'\n이미 Git/원격 저장소가 생성되었을 수 있으므로 재실행 전에 상태를 확인하세요.',file=sys.stderr);return 3

if __name__=='__main__':raise SystemExit(main())

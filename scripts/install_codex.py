#!/usr/bin/env python3
"""Cross-platform local skill/plugin installer. Dry-run unless --apply.

Only own bundle and one catalog entry are changed. No network, credentials,
Codex permission settings, AGENTS.md, shell profiles or startup hooks.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def reject_links(path: Path, base: Path) -> None:
    relative=path.relative_to(base)
    current=base
    for part in relative.parts:
        current=current/part
        if current.is_symlink():raise ValueError('심볼릭 링크가 있는 설치 경로는 거부합니다: '+str(current))


def hashes(root: Path) -> dict[str,str]:
    if not root.exists():return {}
    result={}
    for p in root.rglob('*'):
        if p.is_symlink():raise ValueError('번들 안에 심볼릭 링크가 있습니다.')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
            result[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def install(*,kind: str='skill',home: Path|None=None,project: Path|None=None,
            apply: bool=False,replace: bool=False) -> dict:
    if kind not in {'skill','plugin'}:raise ValueError('지원하지 않는 설치 형태')
    base=(project or home or Path.home()).expanduser().resolve()
    if not base.is_dir():raise ValueError('설치 기준 폴더가 없습니다.')
    if project and home:raise ValueError('--home과 --project는 같이 사용하지 않습니다.')
    source=ROOT/('skills/clearwrite' if kind=='skill' else 'plugins/clearwrite')
    if not (source/('SKILL.md' if kind=='skill' else 'plugin.json')).is_file():
        raise ValueError('배포 번들이 없습니다. python scripts/build_bundles.py 를 먼저 실행하세요.')
    if kind=='skill':target=base/'.agents/skills/clearwrite'
    else:target=base/('plugins/clearwrite' if project else '.codex/plugins/clearwrite')
    reject_links(target,base)
    desired=hashes(source);existing=hashes(target)
    changed=desired!=existing
    if existing and changed and not replace:
        raise ValueError('다른 버전의 clearwrite가 있습니다. --replace로 백업 후 교체할 수 있습니다.')
    catalog=None;data=None;catalog_changed=False
    if kind=='plugin':
        catalog=base/'.agents/plugins/marketplace.json';reject_links(catalog,base)
        if catalog.exists():
            if catalog.stat().st_size>1_000_000:raise ValueError('마켓플레이스 파일이 너무 큽니다.')
            data=json.loads(catalog.read_text(encoding='utf-8-sig'))
            if not isinstance(data,dict) or not isinstance(data.get('plugins'),list):raise ValueError('기존 마켓플레이스 형식이 다릅니다. 자동 교체하지 않았습니다.')
        else:data={'name':'clearwrite-local','plugins':[]}
        before=json.dumps(data,sort_keys=True)
        entry={'name':'clearwrite','source':{'source':'local','path':'./'+target.relative_to(base).as_posix()},'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'},'category':'Productivity'}
        matching=[i for i,x in enumerate(data['plugins']) if isinstance(x,dict) and x.get('name')=='clearwrite']
        if len(matching)>1:raise ValueError('clearwrite 마켓플레이스 항목이 중복됩니다.')
        if matching:
            idx=matching[0]
            if data['plugins'][idx].get('source')!=entry['source'] and not replace:raise ValueError('같은 이름의 다른 플러그인 경로가 있습니다. 자동 교체하지 않습니다.')
            # Preserve existing policy/metadata if source already matches.
            if data['plugins'][idx].get('source')!=entry['source']:data['plugins'][idx]=entry
        else:data['plugins'].append(entry)
        catalog_changed=before!=json.dumps(data,sort_keys=True)
    report={'kind':kind,'source':str(source),'destination':str(target),'catalog':str(catalog) if catalog else None,
            'mode':'apply' if apply else 'dry-run','bundle_change_needed':changed,
            'catalog_change_needed':catalog_changed,'permission_changes':False,'backups':[]}
    if not apply:return report
    if changed:
        target.parent.mkdir(parents=True,exist_ok=True)
        staged=Path(tempfile.mkdtemp(prefix='.clearwrite-stage-',dir=target.parent))
        shutil.rmtree(staged)
        shutil.copytree(source,staged,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        if target.exists():
            backup=target.with_name(target.name+'.backup-'+str(time.time_ns()))
            target.rename(backup);report['backups'].append(str(backup))
        staged.rename(target)
    if catalog_changed and catalog:
        catalog.parent.mkdir(parents=True,exist_ok=True)
        if catalog.exists():
            backup=catalog.with_name(catalog.name+'.backup-'+str(time.time_ns()));shutil.copy2(catalog,backup);report['backups'].append(str(backup))
        fd,temp=tempfile.mkstemp(prefix='.clearwrite-catalog-',dir=catalog.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
            os.replace(temp,catalog)
        finally:
            if os.path.exists(temp):os.unlink(temp)
    report['status']='installed' if changed or catalog_changed else 'already-current'
    report['next']='새 Codex 세션에서 $clearwrite를 사용하세요.' if kind=='skill' else 'Codex /plugins 또는 데스크톱 플러그인에서 clearwrite-local 항목을 선택해 설치/활성화하세요. 등록은 자동 활성화가 아닙니다.'
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['skill','plugin'],default='skill');p.add_argument('--apply',action='store_true');p.add_argument('--replace',action='store_true')
    where=p.add_mutually_exclusive_group();where.add_argument('--home',type=Path);where.add_argument('--project',type=Path)
    args=p.parse_args()
    try:print(json.dumps(install(**vars(args)),ensure_ascii=False,indent=2))
    except (ValueError,OSError) as e:print('install: '+str(e),file=sys.stderr);raise SystemExit(3)

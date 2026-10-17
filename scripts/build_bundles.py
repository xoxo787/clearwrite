#!/usr/bin/env python3
"""Generate byte-identical vendored skills/plugins from the audited source package."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def build() -> Path:
    skill=ROOT/'skills/clearwrite'
    vendored=skill/'scripts/clearwrite'
    if vendored.exists():shutil.rmtree(vendored)
    shutil.copytree(ROOT/'src/clearwrite',vendored,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for filename in ['LICENSE','THIRD_PARTY_NOTICES.md']:
        shutil.copy2(ROOT/filename,skill/filename)
    licenses=skill/'licenses'
    if licenses.exists():shutil.rmtree(licenses)
    licenses.mkdir()
    for filename in ['im-not-ai-MIT.txt','humanizer-MIT.txt']:
        shutil.copy2(ROOT/'licenses'/filename,licenses/filename)
    plugin=ROOT/'plugins/clearwrite'
    if plugin.exists():shutil.rmtree(plugin)
    (plugin/'skills').mkdir(parents=True)
    shutil.copytree(skill,plugin/'skills/clearwrite')
    for filename in ['LICENSE','THIRD_PARTY_NOTICES.md','SECURITY.md']:
        shutil.copy2(ROOT/filename,plugin/filename)
    shutil.copytree(skill/'licenses',plugin/'licenses')
    manifest={'$schema':'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json',
      'name':'clearwrite','version':'0.3.0','description':'한국어·영어 글의 읽기 부담을 줄이는 최소 윤문과 문체·원문 보존 검사. AI 저자 판별을 보증하지 않습니다.',
      'author':{'name':'ClearWrite contributors'},'license':'MIT',
      'keywords':['writing','editing','korean','readability','privacy']}
    (plugin/'plugin.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Supported Codex compatibility overlay; same identity as portable manifest.
    (plugin/'.codex-plugin').mkdir()
    overlay={'name':'clearwrite','version':'0.3.0','description':manifest['description'],'skills':'./skills/',
      'interface':{'displayName':'ClearWrite · 맑은글','shortDescription':'한국어·영어 윤문과 문체·보존 검사',
                   'longDescription':'현재 모델로 최소 편집을 제안하고 포함된 Python 엔진으로 숫자·인용·코드·수정량을 검사합니다. 별도 API 키 없이 Codex에서 사용하며, 코드 실행 환경이 없는 경우 정량 검수 미실행을 표시합니다.',
                   'developerName':'ClearWrite contributors','category':'Productivity',
                   'defaultPrompt':['이 글을 뜻은 유지하면서 읽기 편하게 다듬고 검수해 줘.']}}
    (plugin/'.codex-plugin/plugin.json').write_text(json.dumps(overlay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    market=ROOT/'.agents/plugins';market.mkdir(parents=True,exist_ok=True)
    (market/'marketplace.json').write_text(json.dumps({'name':'clearwrite-local','plugins':[{'name':'clearwrite','source':{'source':'local','path':'./plugins/clearwrite'},'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'},'category':'Productivity'}]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    expected={p.relative_to(ROOT/'src/clearwrite').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src/clearwrite').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    (ROOT/'data/bundle-source-hashes.json').write_text(json.dumps(expected,indent=2)+'\n',encoding='utf-8')
    return plugin

if __name__=='__main__':
    print(build())

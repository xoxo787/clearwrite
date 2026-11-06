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


def tree_files(directory: Path) -> dict[str, Path]:
    return {p.relative_to(directory).as_posix(): p for p in directory.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def write_json(path: Path, value: dict) -> None:
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sync_tree(source: Path, destination: Path) -> None:
    """Update generated files without deleting a directory or unknown files."""
    expected = tree_files(source)
    extra = sorted(set(tree_files(destination)) - set(expected))
    if extra:
        raise ValueError(f'Unexpected bundle files in {destination}: {extra}. '
                         'Preserved; inspect and archive them before rebuilding.')
    shutil.copytree(source, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


def check_bundles() -> list[str]:
    """Read-only comparison of authoritative code and both complete skills."""
    differences = []
    skill = ROOT / 'skills/clearwrite'
    for source, destination in (
        (ROOT / 'src/clearwrite', skill / 'scripts/clearwrite'),
        (skill, ROOT / 'plugins/clearwrite/skills/clearwrite'),
    ):
        originals, copies = tree_files(source), tree_files(destination)
        for name in sorted(set(originals) | set(copies)):
            if name not in originals or name not in copies or originals[name].read_bytes() != copies[name].read_bytes():
                differences.append(str(destination / name))
    expected = {name: hashlib.sha256(path.read_bytes()).hexdigest()
                for name, path in tree_files(ROOT / 'src/clearwrite').items()}
    hashes = ROOT / 'data/bundle-source-hashes.json'
    if not hashes.exists() or json.loads(hashes.read_text(encoding='utf-8')) != expected:
        differences.append(str(hashes))
    return differences


def build() -> Path:
    skill=ROOT/'skills/clearwrite'
    vendored=skill/'scripts/clearwrite'
    sync_tree(ROOT/'src/clearwrite',vendored)
    for filename in ['LICENSE','THIRD_PARTY_NOTICES.md']:
        shutil.copy2(ROOT/filename,skill/filename)
    licenses=skill/'licenses'
    licenses.mkdir(exist_ok=True)
    for filename in ['im-not-ai-MIT.txt','humanizer-MIT.txt']:
        shutil.copy2(ROOT/'licenses'/filename,licenses/filename)
    plugin=ROOT/'plugins/clearwrite'
    (plugin/'skills').mkdir(parents=True,exist_ok=True)
    sync_tree(skill,plugin/'skills/clearwrite')
    for filename in ['LICENSE','THIRD_PARTY_NOTICES.md','SECURITY.md']:
        shutil.copy2(ROOT/filename,plugin/filename)
    sync_tree(skill/'licenses',plugin/'licenses')
    manifest={'$schema':'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json',
      'name':'clearwrite','version':'0.4.0','description':'한국어·영어 글의 읽기 부담을 줄이는 최소 윤문과 문체·원문 보존 검사. AI 저자 판별을 보증하지 않습니다.',
      'author':{'name':'ClearWrite contributors'},'license':'MIT',
      'keywords':['writing','editing','korean','readability','privacy']}
    write_json(plugin/'plugin.json', manifest)
    # Supported Codex compatibility overlay; same identity as portable manifest.
    (plugin/'.codex-plugin').mkdir(exist_ok=True)
    overlay={'name':'clearwrite','version':'0.4.0','description':manifest['description'],'skills':'./skills/',
      'interface':{'displayName':'ClearWrite · 맑은글','shortDescription':'한국어·영어 윤문과 문체·보존 검사',
                   'longDescription':'현재 모델로 최소 편집을 제안하고 포함된 Python 엔진으로 숫자·인용·코드·수정량을 검사합니다. 별도 API 키 없이 Codex에서 사용하며, 코드 실행 환경이 없는 경우 정량 검수 미실행을 표시합니다.',
                   'developerName':'ClearWrite contributors','category':'Productivity',
                   'defaultPrompt':['이 글을 뜻은 유지하면서 읽기 편하게 다듬고 검수해 줘.']}}
    write_json(plugin/'.codex-plugin/plugin.json', overlay)
    market=ROOT/'.agents/plugins';market.mkdir(parents=True,exist_ok=True)
    write_json(market/'marketplace.json', {'name':'clearwrite-local','plugins':[{'name':'clearwrite','source':{'source':'local','path':'./plugins/clearwrite'},'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'},'category':'Productivity'}]})
    expected={p.relative_to(ROOT/'src/clearwrite').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src/clearwrite').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    write_json(ROOT/'data/bundle-source-hashes.json', expected)
    return plugin

if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check bundle contents without writing files')
    args = parser.parse_args()
    if not args.check:
        print(build())
    differences = check_bundles()
    if differences:
        print('Bundle mismatch:\n' + '\n'.join(differences), file=sys.stderr)
        raise SystemExit(1)
    print('Bundle contents and source hashes match.')

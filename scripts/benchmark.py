#!/usr/bin/env python3
"""Reproduce the shipped demonstration. It is not an authorship accuracy benchmark."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import platform
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from clearwrite import __version__
from clearwrite.core import analyze, apply_plan, make_plan, resolve_proposals, text_hash
from clearwrite.io import strict_json


def load_jsonl(path: Path) -> list[dict]:
    return [strict_json(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def run(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    docs = load_jsonl(ROOT / 'data/corpus.jsonl')
    proposals = {p['id']: p for p in load_jsonl(ROOT / 'data/editorial_proposals.jsonl')}
    ids = [d['id'] for d in docs]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate corpus IDs')
    rows, traces = [], []
    for d in docs:
        text = d['text']
        if text_hash(text) != d['sha256']:
            raise ValueError('Corpus source hash mismatch: ' + d['id'])
        plans = [('noop', {'schema_version':'1.0','source_sha256':d['sha256'],'edits':[]}),
                 ('builtin', make_plan(text, mode='personal'))]
        if d['id'] in proposals:
            plans.append(('session_editorial_replay', resolve_proposals(text, proposals[d['id']]['proposal'])))
        for treatment, plan in plans:
            result = apply_plan(text, plan)
            b,a = result['before'],result['after']
            rows.append(dict(id=d['id'],group=d['group'],language=d['language'],genre=d['genre'],
                treatment=treatment,status=result['status'],characters_before=len(text),characters_after=len(result['text']),
                markers_before=len(b['findings']),markers_after=len(a['findings']),
                style_before=b['ai_style_score'],style_after=a['ai_style_score'],
                burden_before=b['reading_burden_proxy'],burden_after=a['reading_burden_proxy'],
                change_rate=result['verification']['character_change_rate'],
                protected_checks_passed=result['verification']['passed'],
                edits_applied=len(result['applied_edits']),source_sha256=d['sha256'],output_sha256=text_hash(result['text'])))
            traces.append(dict(id=d['id'],treatment=treatment,source=text,result=result))
    groups=[]
    # Keep language and authorship provenance separate; do not pool stress into efficacy.
    for treatment in sorted({r['treatment'] for r in rows}):
        for lang in ('ko','en'):
            for group in ('human_historical','human_reference','ai_generated','stress_fixture'):
                selected=[r for r in rows if r['treatment']==treatment and r['language']==lang and r['group']==group]
                if not selected:continue
                mean=lambda k:round(statistics.mean(r[k] for r in selected),3)
                groups.append(dict(treatment=treatment,language=lang,group=group,n=len(selected),
                    mean_style_before=mean('style_before'),mean_style_after=mean('style_after'),
                    mean_burden_before=mean('burden_before'),mean_burden_after=mean('burden_after'),
                    edited=sum(r['status']=='edited' for r in selected),blocked=sum(r['status']=='blocked' for r in selected),
                    unchanged=sum(r['status']=='unchanged' for r in selected),
                    mechanical_checks_passed=sum(r['protected_checks_passed'] for r in selected)))
    now=datetime.now(timezone.utc).isoformat()
    summary={'project_version':__version__,'executed_at_utc':now,'python':platform.python_version(),
      'platform':platform.system(),'corpus_documents':len(docs),
      'corpus_sha256':hashlib.sha256((ROOT/'data/corpus.jsonl').read_bytes()).hexdigest(),
      'human_historical':sum(d['group']=='human_historical' for d in docs),
      'human_reference':sum(d['group']=='human_reference' for d in docs),
      'ai_generated':sum(d['group']=='ai_generated' for d in docs),
      'stress_fixtures':sum(d['group']=='stress_fixture' for d in docs),
      'groups':groups,'executed_treatments':['noop','builtin','session_editorial_replay'],
      'session_editorial_replay':'Actual assistant-authored proposals saved during development and applied by the engine. No live Codex/Ollama call. Not independent or blinded.',
      'live_codex_tests':False,'live_ollama_tests':False,
      'human_reader_experiment':{'status':'not_run','participants':0,'fatigue_reduction':None},
      'model_style_assessment':'not_run; offline replay benchmark only',
      'warnings':['Small illustrative corpus; no detector training or classification accuracy estimate.',
       'Length, date, author and genre are confounded. English/Korean scores are not directly comparable.',
       'Lower internal style score is circular evidence because the edits target the same rules.',
       'Historical rhetoric and technical precision should not be removed simply to lower a score.',
       'Passing mechanical guards does not prove semantic equivalence.',
       'Stress fixtures are excluded from effectiveness summaries.',
       'Contemporary documentation authorship is a reference label, not an independently certified ground truth.']}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'traces.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in traces),encoding='utf-8')
    with (out/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    markdown=['# ClearWrite 비교 실험 기록','',f'실행: {now} · Python {platform.python_version()} · {platform.system()}',
      '', '## 실험에 들어간 자료', '',
      f'웹 원문 8개(역사적 사람 저작물 4, 사람 편집 문서 참고군 4), 새 AI 글 8개, 별도 스트레스 예문 4개. 총 {len(docs)}개.',
      '원문·출처·라이선스·해시는 `data/corpus.jsonl`에, 수정 제안은 `data/editorial_proposals.jsonl`에 보관했다.',
      '', '비교군은 원문 유지(noop), 기본 규칙(builtin), 이번 대화에서 AI가 작성한 문맥 편집 제안을 엔진으로 적용한 재현군(session_editorial_replay)이다. 마지막 군은 Codex/Ollama 실호출 결과가 아니다.',
      '', '## 실제 측정값', '',
      '| 처리 | 언어 | 자료군 | n | 문체 후보 전→후 | 읽기 부담 참고 전→후 | 수정/그대로/차단 |',
      '|---|---|---|---:|---:|---:|---:|']
    for g in groups:
        if g['treatment']=='noop':continue
        markdown.append(f"| {g['treatment']} | {g['language']} | {g['group']} | {g['n']} | {g['mean_style_before']} → {g['mean_style_after']} | {g['mean_burden_before']} → {g['mean_burden_after']} | {g['edited']}/{g['unchanged']}/{g['blocked']} |")
    zero_ai=[d['id'] for d in docs if d['group']=='ai_generated' and analyze(d['text'])['ai_style_score']==0]
    markdown+=['','## 결과 해석','',f'AI가 생성했어도 문체 후보 점수가 0인 글: {", ".join(zero_ai) or "없음"}. 0점은 사람 작성 인증이 아니다.',
      '기본 규칙은 제한된 연결 표현만 바꾸므로 문맥 편집보다 수정 폭이 작다. 문맥 편집의 내부 점수 하락은 독립 품질 평가가 아니다. 이 실험만으로 인지 피로 감소, 모든 장르의 품질 개선, AI 탐지 회피율을 주장할 수 없다.',
      '보호 검사 통과는 문자·수치·일부 조건이 유지됐다는 뜻이다. 원문 속 주체·인과·암묵적 의미 전체를 검증했다는 뜻은 아니다.',
      '', '## 모델 문체 평가', '',
      '이 명령은 오프라인 편집 재현만 실행하며 Codex/Claude 문체 분석을 호출하지 않는다. 모델 문체 평가는 AI 작성 확률이 아니다.',
      '', '## 재현', '', '```sh', 'python scripts/benchmark.py --out reports/reproduced', '```',
      '', '## 아직 검증하지 않은 것','',
      '실제 독자의 이해도·재독 횟수·피로도, 실시간 Codex/Ollama 생성, Windows/macOS 네이티브 실행, 외부 탐지기의 한국어 정확도는 미검증이다. `blind-review.html`은 수집 양식이며 현재 참여자 수는 0이다.']
    (out/'BENCHMARK.md').write_text('\n'.join(markdown)+'\n',encoding='utf-8')
    # Readable, fully offline before/after report; never render input as HTML.
    cards=[]
    for trace in traces:
        if trace['treatment']!='session_editorial_replay':continue
        r=trace['result'];d=next(x for x in docs if x['id']==trace['id'])
        source=f'<a href="{html.escape(d["source_url"],quote=True)}" rel="noreferrer">원문 출처</a>' if d['source_url'] else '이번 대화에서 새로 생성한 AI 글'
        cards.append(f'<article><h2>{html.escape(d["title"])}</h2><p>{html.escape(d["id"])} · {source} · 문체 후보 {r["before"]["ai_style_score"]} → {r["after"]["ai_style_score"]} · 수정 {len(r["applied_edits"])}곳</p><div class="pair"><section><h3>원문</h3><pre>{html.escape(trace["source"])}</pre></section><section><h3>제안 적용 결과</h3><pre>{html.escape(r["text"])}</pre></section></div></article>')
    css='body{font:16px/1.85 system-ui,sans-serif;max-width:1160px;padding:28px;margin:auto;background:#f6f5ef;color:#24352c}.pair{display:grid;grid-template-columns:1fr 1fr;gap:28px}article{background:white;margin:26px 0;padding:26px;border:1px solid #d5dcd6;border-radius:8px}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}h2{font-size:22px}h3{font-size:16px}a{color:#215e49}@media(max-width:750px){.pair{grid-template-columns:1fr}}'
    document=f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ClearWrite 전후 비교</title><style>{css}</style><h1>ClearWrite · 원문과 윤문 결과</h1><p>웹 사람 글 참고군과 새 AI 글의 비교입니다. 내부 점수는 AI 작성 확률이 아닙니다. 이번 대화에서 작성한 AI 편집 제안을 실제 엔진으로 적용한 결과이며, 독립적인 독자 실험은 아직 하지 않았습니다.</p>'+''.join(cards)+'</html>'
    (out/'comparison.html').write_text(document,encoding='utf-8')
    write_blind_packet(out,docs,traces)
    return summary


def write_blind_packet(out: Path, docs: list[dict], traces: list[dict]) -> None:
    # A/B blind to casual readers, NOT cryptographically blinded to developers.
    rng=random.Random(20261017)
    selected=[t for t in traces if t['treatment']=='session_editorial_replay' and t['result']['status']=='edited']
    rng.shuffle(selected)
    cards=[];key=[]
    for i,t in enumerate(selected,1):
        flip=rng.choice([False,True]);texts=[t['source'],t['result']['text']]
        if flip:texts.reverse()
        key.append({'item':i,'source_id':t['id'],'A':'edited' if flip else 'original','B':'original' if flip else 'edited'})
        cards.append(f'<article data-item="{i}"><h2>항목 {i}</h2><div class="pair"><section><h3>A</h3><pre>{html.escape(texts[0])}</pre></section><section><h3>B</h3><pre>{html.escape(texts[1])}</pre></section></div><label>읽기 편한 쪽 <select class="preference"><option value="">미평가</option>A</option><option>B</option><option>비슷함</option></select></label> <label>A 부담(1~5) <input class="burden-a" type="number" min="1" max="5"></label> <label>B 부담(1~5) <input class="burden-b" type="number" min="1" max="5"></label><p><textarea class="note" placeholder="빠진 정보·다시 읽은 구간·이해하기 어려운 부분"></textarea></p></article>')
    (out/'blind-key.json').write_text(json.dumps(key,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    script='''document.getElementById('save').onclick=()=>{const rows=[...document.querySelectorAll('article')].map(a=>({item:Number(a.dataset.item),preference:a.querySelector('.preference').value,burden_A:a.querySelector('.burden-a').value||null,burden_B:a.querySelector('.burden-b').value||null,note:a.querySelector('.note').value}));const blob=new Blob([JSON.stringify({instrument:'ClearWrite exploratory within-item preference; no comprehension test',rated_at:new Date().toISOString(),ratings:rows},null,2)],{type:'application/json'});const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download='clearwrite-reader-ratings.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};'''
    (out/'blind-review.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ClearWrite 읽기 비교</title><style>body{max-width:1150px;margin:auto;padding:24px;font:16px/1.9 system-ui}.pair{display:grid;grid-template-columns:1fr 1fr;gap:30px}pre{font:inherit;white-space:pre-wrap}article{border-top:1px solid;padding:20px 0}input{width:45px}textarea{width:90%;height:70px}@media(max-width:700px){.pair{grid-template-columns:1fr}}</style><h1>어느 쪽이 읽기 편한가요?</h1><p>문체 점수나 작성 주체를 보지 않고 비교하세요. 같은 내용을 두 번 읽으면 학습효과가 생깁니다. 이 양식은 선호도 탐색용이며 엄밀한 피로도 실험은 아닙니다. 개인정보는 쓰지 마세요. 결과는 전송되지 않고 JSON으로 직접 저장합니다.</p>'+''.join(cards)+'<button id="save">평가 JSON 저장</button><script>'+script+'</script></html>',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'reports/demo')
    a=p.parse_args()
    summary=run(a.out)
    print(json.dumps({'out':str(a.out),'documents':summary['corpus_documents'],'groups':summary['groups']},ensure_ascii=False,indent=2))

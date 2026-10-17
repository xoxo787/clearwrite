"""Explicit offline HTTP fixture for manual browser error/partial/cancel QA.

No CLI is started and no external detector is called. Not a product entry point.
Run: python tests/fixtures/serve_ui_fixture.py --port 0 --metadata <path>
"""
# ruff: noqa: E402
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from clearwrite import ui
from clearwrite.core import apply_plan, make_plan, resolve_proposals, text_hash
from clearwrite.model_cli import ModelCancelled
from clearwrite.providers import ProviderError


def fake_plan(text, *, cancel, **kwargs):
    if '오류 테스트' in text:
        raise ProviderError('모의 모델 오류입니다. 원문은 유지합니다.')
    if text.startswith('삭제 검증:'):
        return resolve_proposals(text, {'schema_version': '1.0', 'source_sha256': text_hash(text), 'edits': [
            {'original': '정말 맑은', 'replacement': '맑은', 'reason': '삭제 위치 회귀 검증', 'rule': 'fixture'}]})
    if cancel.wait(15):
        raise ModelCancelled('모의 요청을 취소했습니다.')
    return make_plan(text, mode='preserve')


def fake_style(text, *, candidate=None, backend='codex', cancel, **kwargs):
    if '실패 검증' in text or kwargs.get('model') == 'fixture-failure':
        raise ProviderError('모의 문체 분석 오류입니다. 점수는 표시하지 않습니다.')
    if ('취소 검증' in text or kwargs.get('model') == 'fixture-wait') and cancel.wait(15):
        raise ModelCancelled('모의 문체 분석을 취소했습니다.')
    from clearwrite.style import prepare_style, validate_style, INTERPRETATION
    def assess(content):
        return {'dimensions': {'repetition': 6, 'formulaic': 9, 'uniformity': 4, 'abstraction': 2},
                'summary': '모의 문체 평가 · 실제 모델 점수가 아닙니다.',
                'reasons': [{'category': 'formulaic', 'quote': content[:28],
                             'reason': '화면 표시와 인용 처리 검증용 모의 판단 이유입니다.'}]}
    task = prepare_style(text, candidate)
    assessment = validate_style({'source_sha256': task['source_sha256'],
                                'candidate_sha256': task['candidate_sha256'],
                                'before': assess(text), 'after': assess(candidate) if candidate is not None else None}, text, candidate)
    return {**assessment, 'status':'completed', 'backend':backend, 'model':'OFFLINE-FIXTURE',
            'interpretation':INTERPRETATION, 'calibrated':False, 'authorship':'undetermined',
            'source_sha256':task['source_sha256'], 'candidate_sha256':task['candidate_sha256'],
            'reused_identical_text':candidate==text, 'cli_runs':0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--replay-report', type=Path, help='Replay a saved plan locally; no new model request')
    args = parser.parse_args()
    if args.replay_report:
        report = json.loads(args.replay_report.read_text(encoding='utf-8'))
        saved = apply_plan(report['source_text'], report['proposed_plan'])
        saved.update(ui.comparison(report['source_text'], saved))
        saved.update(backend='demo', demonstration=True, source_text=report['source_text'], model_requests=0)
        ui.demo = lambda: saved
    ui.model_plan = fake_plan
    ui.model_style = fake_style
    ui.backend_status = lambda: {
        'default_backend': 'codex', 'backends': [
            {'id': 'codex', 'name': 'Codex (OFFLINE FIXTURE)', 'version': 'mock', 'installed': True,
             'ready': True, 'message': '모의 응답 · 모델 호출 없음'},
            {'id': 'claude', 'name': 'Claude Code', 'version': None, 'installed': False,
             'ready': False, 'message': '모의 설치 안 됨'}], 'model_requests': 0}
    ui.PAGE = ui.PAGE.replace('<body>', '<body><p role="note">OFFLINE UI TEST · 저장된 계획/모의 응답 재생 · 외부 요청 없음</p>')
    with ui.Server(args.port) as server:
        args.metadata.write_text(json.dumps({'url': server.origin}), encoding='utf-8')
        server.serve_forever()

"""Offline CLI protocol fixture. Never calls a model or external service."""
import json
from pathlib import Path
import sys
import time

task = json.load(sys.stdin)
scenario = task.get('voice_sample', '')
if scenario == 'wait':
    time.sleep(20)
if scenario == 'fail':
    print('private-fixture-message-must-not-be-returned', file=sys.stderr)
    raise SystemExit(9)
proposal = {'schema_version': '1.0', 'source_sha256': task['source_sha256'], 'edits': []}
if 'candidate_sha256' in task:
    def assess(text):
        return {'dimensions': {'repetition': 4, 'formulaic': 5, 'uniformity': 3, 'abstraction': 2},
                'summary': '오프라인 프로토콜 검증용 모의 평가입니다.',
                'reasons': [{'category': 'repetition', 'quote': text[:20],
                             'reason': '실제 모델이 아닌 모의 인용 근거입니다.'}]}
    proposal = {'source_sha256': task['source_sha256'], 'candidate_sha256': task['candidate_sha256'],
                'before': assess(task['text']),
                'after': assess(task['candidate']) if task['candidate'] is not None else None}
if '--output-last-message' in sys.argv:
    path = Path(sys.argv[sys.argv.index('--output-last-message') + 1])
    path.write_text('x' * 2_000_001 if scenario == 'oversize' else
                    ('not json' if scenario == 'malformed' else json.dumps(proposal)), encoding='utf-8')
else:
    print(json.dumps({'structured_output': proposal, 'is_error': False}))

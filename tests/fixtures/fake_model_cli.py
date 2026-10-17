"""Offline CLI protocol fixture. Never calls a model or external service."""
import json
import sys
import time

if '--fixture-pipe-pressure' in sys.argv:
    print('x' * 500_000, file=sys.stderr, flush=True)
    print(json.dumps({'type': 'thread.started', 'padding': 'x' * 500_000}), flush=True)

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
if scenario == 'oversize':
    print('x' * 2_000_001)
elif scenario == 'oversize-stderr':
    print('x' * 2_000_001, file=sys.stderr)
elif scenario == 'malformed':
    print('not json')
elif 'exec' in sys.argv:
    print(json.dumps({'type': 'thread.started', 'thread_id': 'offline-fixture'}))
    print(json.dumps({'type': 'item.completed', 'item': {
        'id': 'item_1', 'type': 'reasoning', 'text': 'Offline fixture, not a model.'}}))
    print(json.dumps({'type': 'item.completed', 'item': {
        'id': 'item_2', 'type': 'agent_message', 'text': json.dumps(proposal)}}))
    print(json.dumps({'type': 'turn.completed', 'usage': {}}))
else:
    print(json.dumps({'structured_output': proposal, 'is_error': False}))

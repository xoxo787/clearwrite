"""Build display-only change segments from the edits that actually passed."""
from __future__ import annotations

import difflib
from typing import Any

from .core import InputError


def comparison(original: str, result: dict[str, Any]) -> dict[str, Any]:
    edits = result['applied_edits']
    before: list[dict] = []
    after: list[dict] = []
    changes = []
    cursor = 0
    output_cursor = 0

    def append(target: list, text: str, change_id: int | None = None, kind: str = 'same') -> None:
        if text:
            target.append({'text': text, 'change_id': change_id, 'kind': kind})

    for change_id, edit in enumerate(edits, 1):
        a, b = edit['start'], edit['end']
        if a < cursor or original[a:b] != edit['original']:
            raise InputError('비교할 편집 위치가 원문과 다릅니다.')
        unchanged = original[cursor:a]
        append(before, unchanged)
        append(after, unchanged)
        output_cursor += len(unchanged)
        changes.append({'id': change_id, 'start': a, 'end': b, 'output_start': output_cursor,
                        'output_end': output_cursor + len(edit['replacement']),
                        'original': edit['original'], 'replacement': edit['replacement'],
                        'reason': edit['reason'], 'rule': edit['rule']})
        matcher = difflib.SequenceMatcher(None, edit['original'], edit['replacement'],
                                         autojunk=max(len(edit['original']), len(edit['replacement'])) > 4000)
        for tag, i, j, x, y in matcher.get_opcodes():
            if tag == 'insert':
                before.append({'text': '', 'change_id': change_id, 'kind': 'insertion_marker'})
            if tag == 'delete':
                after.append({'text': '', 'change_id': change_id, 'kind': 'deletion_marker'})
            append(before, edit['original'][i:j], None if tag == 'equal' else change_id,
                   'same' if tag == 'equal' else 'removed')
            append(after, edit['replacement'][x:y], None if tag == 'equal' else change_id,
                   'same' if tag == 'equal' else 'added')
        output_cursor += len(edit['replacement'])
        cursor = b
    append(before, original[cursor:])
    append(after, original[cursor:])
    if ''.join(s['text'] for s in before) != original or ''.join(s['text'] for s in after) != result['text']:
        raise InputError('비교 표시와 실제 결과가 일치하지 않습니다.')
    removed = sum(len(part['text']) for part in before if part['kind'] == 'removed')
    added = sum(len(part['text']) for part in after if part['kind'] == 'added')
    denominator = len(original) + len(result['text'])
    statistics = {'removed_characters': removed, 'added_characters': added,
                  'original_characters': len(original), 'result_characters': len(result['text']),
                  'rate_percent': round(100 * (removed + added) / denominator, 4) if denominator else 0.0,
                  'method': '(removed + added) / (original + result) * 100; applied edit character diffs',
                  'includes_whitespace': True, 'unit': 'unicode_codepoints'}
    return {'before_segments': before, 'after_segments': after, 'changes': changes,
            'change_statistics': statistics,
            'offset_unit': 'unicode_codepoints'}

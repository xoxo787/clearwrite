"""Meaning-sensitive edits and useful edits must both survive regression checks.

These synthetic examples test mechanical gates, not human reading quality.
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from clearwrite import cli
from clearwrite.core import apply_plan, number_signature, resolve_proposals, text_hash, verify


def proposal(text, *pairs):
    return {'schema_version': '1.0', 'source_sha256': text_hash(text), 'edits': [
        {'original': original, 'replacement': replacement,
         'reason': '문맥을 유지하는 편집 후보', 'rule': 'editorial-context'}
        for original, replacement in pairs
    ]}


class QuantityPreservationTests(unittest.TestCase):
    def test_changed_units_and_magnitudes_are_blocked(self):
        cases = [('10mg', '10g'), ('10mL', '10L'), ('10cm', '10mm'),
                 ('10mg/L', '10mg/mL'), ('10GB', '10Gb'),
                 ('3천 원', '3만 원'), ('1억 5천만 원', '1억 5백만 원'),
                 ('10시간', '10시'), ('10개월', '10월'), ('10배', '10점')]
        for original, replacement in cases:
            with self.subTest(original=original, replacement=replacement):
                text = f'기록한 값은 {original}입니다. 이 값은 원본 기록에 그대로 남깁니다.'
                candidate = text.replace(original, replacement)
                self.assertIn('numbers_units_or_order_changed', verify(text, candidate)['failures'])
                result = apply_plan(text, resolve_proposals(text, proposal(text, (original, replacement))))
                self.assertEqual(result['status'], 'blocked')
                self.assertEqual(result['text'], text)

    def test_full_quantity_is_reported_and_spacing_can_change(self):
        text = '값은 1억 5천만 원, 10 mg/L, 10시간, 1,000.5 kg, -10~20℃입니다.'
        self.assertEqual(number_signature(text),
                         ['1억5천만원', '10mg/L', '10시간', '1,000.5kg', '-10~20℃'])
        self.assertTrue(verify(text, text.replace('10 mg/L', '10mg/L'))['passed'])

    def test_units_do_not_consume_the_start_of_english_words(self):
        text = 'We recorded 10 general observations and 20 milliseconds of latency.'
        candidate = text.replace('general observations', 'ordinary observations')
        self.assertTrue(verify(text, candidate)['passed'])
        self.assertEqual(number_signature(text), ['10', '20'])

    def test_changing_a_unit_in_a_separate_patch_is_still_blocked(self):
        text = 'The recorded concentration is 10mg/L in this example.'
        result = apply_plan(text, resolve_proposals(text, proposal(text, ('mg/L', 'mg/mL'))))
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('numbers_units_or_order_changed', result['verification']['failures'])


class ClaimPreservationTests(unittest.TestCase):
    def test_changed_claim_markers_are_blocked(self):
        cases = [
            ('일부 사용자는 이 기능을 이용합니다.', '모든 사용자는 이 기능을 이용합니다.'),
            ('모든 사용자는 이 기능을 이용합니다.', '일부 사용자는 이 기능을 이용합니다.'),
            ('대부분의 사용자는 이 기능을 이용합니다.', '모든 사용자는 이 기능을 이용합니다.'),
            ('작업에는 약 10분이 걸립니다.', '작업에는 10분이 걸립니다.'),
            ('Retry if the check fails.', 'Retry unless the check fails.'),
            ('Use the files except the draft.', 'Use the files only the draft.'),
            ('Use some records to check the result.', 'Use all records to check the result.'),
            ('We recorded approximately 10 samples.', 'We recorded 10 samples.'),
            ('그 결과에는 상관관계가 있습니다.', '그 결과에는 인과관계가 있습니다.'),
            ('The variables show correlation in this example.', 'The variables show causation in this example.'),
            ('초안은 검토 대상에서 제외합니다.', '초안은 검토 대상에 포함합니다.'),
        ]
        for before, after in cases:
            with self.subTest(before=before, after=after):
                self.assertIn('claim_qualifier_changed', verify(before, after, max_change=.5)['failures'])
                result = apply_plan(before, resolve_proposals(before, proposal(before, (before, after))), max_change=.5)
                self.assertEqual(result['status'], 'blocked')
                self.assertEqual(result['text'], before)

    def test_preserving_qualifiers_allows_real_editing(self):
        cases = [
            ('일부 사용자는 이와 같은 도구를 사용하여 결과를 기록합니다.', '이와 같은', '이런'),
            ('대부분의 사용자는 이 도구를 이용하여 결과를 기록합니다.', '이용하여', '이용해'),
            ('약 10mg을 사용하여 관찰 결과를 기록합니다.', '사용하여', '사용해'),
            ('값은 대략 10입니다. 이 기록을 그대로 보관합니다.', '대략', '약'),
            ('We utilize some records to check the result.', 'utilize', 'use'),
            ('Unless it fails, we utilize the same procedure.', 'utilize', 'use'),
            ('그 결과에는 상관관계가 있습니다. 조건은 그대로 기록합니다.', '있습니다.', '있어요.'),
            ('These findings are about the report.', 'about the report', 'concerning the report'),
            ('약을 사용하여 관찰 결과를 기록합니다.', '사용하여', '사용해'),
            ('상관없이 이와 같은 기록을 그대로 보관합니다.', '이와 같은', '이런'),
        ]
        for text, original, replacement in cases:
            with self.subTest(text=text):
                result = apply_plan(text, resolve_proposals(text, proposal(text, (original, replacement))))
                self.assertEqual(result['status'], 'edited', result['rejected_edits'])
                self.assertEqual(result['text'], text.replace(original, replacement))

    def test_safe_subset_rejects_the_changed_claim_only(self):
        text = '일부 사용자는 이와 같은 도구를 사용하여 결과를 기록합니다.'
        plan = resolve_proposals(text, proposal(text, ('일부', '모든'), ('사용하여', '사용해')))
        result = apply_plan(text, plan, policy='safe-subset')
        self.assertEqual(result['text'], text.replace('사용하여', '사용해'))
        self.assertEqual(result['rejected_edits'][0]['reason'], 'claim_qualifier_changed')
        self.assertEqual(result['verification']['semantic_equivalence'], 'not_established')

    def test_boundary_spanning_marker_change_is_still_blocked(self):
        text = 'We use some records to check the result.'
        # The patch itself has no full marker; the final-document check must catch it.
        plan = resolve_proposals(text, proposal(text, ('ome records', 'ame records')))
        result = apply_plan(text, plan)
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('claim_qualifier_changed', result['verification']['failures'])

    def test_subject_swaps_remain_an_explicit_limit(self):
        before, after = '민수가 지수를 도왔습니다.', '지수가 민수를 도왔습니다.'
        result = verify(before, after, max_change=.5)
        self.assertEqual(result['semantic_equivalence'], 'not_established')


class SkillCommandPreservationTests(unittest.TestCase):
    def test_prepare_apply_and_verify_share_quantity_protection(self):
        # Keep artifacts for inspection; never delete a run directory here.
        directory = Path(tempfile.mkdtemp(prefix='clearwrite-preservation-'))
        source = directory / 'input.txt'
        text = '일부 사용자는 10mg을 사용하여 관찰 결과를 기록합니다.'
        source.write_text(text, encoding='utf-8')
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(cli.main(['prepare', str(source), '--proposals']), 0)
        task = json.loads(stream.getvalue())
        self.assertEqual(task['source_sha256'], text_hash(text))
        changes = directory / 'proposals.json'
        changes.write_text(json.dumps(proposal(text, ('10mg', '10g'))), encoding='utf-8')
        output, report = directory / 'edited.txt', directory / 'report.json'
        self.assertEqual(cli.main(['apply', str(source), '--proposals', str(changes),
                                   '-o', str(output), '--report', str(report)]), 2)
        self.assertEqual(output.read_text(encoding='utf-8'), text)
        self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['status'], 'blocked')
        candidate = directory / 'candidate.txt'
        candidate.write_text(text.replace('10mg', '10g'), encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['verify', str(source), str(candidate)]), 2)


if __name__ == '__main__':
    unittest.main()

"""Grammar styles: ending registers chosen apart from personas, and conformance counts."""
# ruff: noqa: E402
from __future__ import annotations
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from clearwrite import cli
from clearwrite.core import InputError, prepare, resolve_proposals, text_hash
from clearwrite.personas import edit_budget, get_persona, resolve_style
from clearwrite.styles import STYLES, conformance, ending_class, get_style
from clearwrite.ui import PAGE, rewrite_job

TEXT = '백업은 매일 새벽에 실행됩니다. 실패하면 알림을 보냅니다.'


class EndingTests(unittest.TestCase):
    def test_endings_are_classified_by_register(self):
        cases = {'실행됩니다.': 'hamnida', '확인하시겠습니까?': 'hamnida', '확인하십시오.': 'hamnida',
                 '실행돼요.': 'haeyo', '그렇죠?': 'haeyo', '실행된다.': 'handa', '무엇인가?': 'handa',
                 '확인하라.': 'handa', '어떨까?': 'handa', '어떨까요?': 'haeyo', '실행돼.': 'other', 'It runs.': None, '버전 3.': None}
        for sentence, expected in cases.items():
            with self.subTest(sentence=sentence):
                self.assertEqual(ending_class(sentence), expected)

    def test_conformance_skips_quotes_code_headings_and_english(self):
        text = '## 백업 설정\n백업은 매일 실행돼요. 팀장은 "바꾸지 않을 수 없다."라고 했어요. 실패하면 알린다! Logs are kept.\n`run.sh`를 써요.'
        report = conformance(text, 'haeyo')
        self.assertEqual((report['sentences'], report['matching']), (4, 3))
        self.assertEqual(report['rate'], .75)
        self.assertEqual(report['mismatched_examples'], ['실패하면 알린다!'])

    def test_keep_has_no_conformance_and_unknown_style_fails(self):
        self.assertIsNone(conformance(TEXT, 'keep'))
        for value in ('banmal', 3):
            with self.subTest(value=value), self.assertRaises(InputError):
                get_style(value)


class ResolutionTests(unittest.TestCase):
    def test_personas_keep_their_previous_register_by_default(self):
        self.assertEqual(resolve_style(get_persona('formal')).id, 'hamnida')
        self.assertEqual(resolve_style(get_persona('friendly')).id, 'haeyo')
        self.assertEqual(resolve_style(get_persona(None)).id, 'keep')

    def test_explicit_style_overrides_persona(self):
        self.assertEqual(resolve_style(get_persona('friendly'), 'keep').id, 'keep')
        self.assertEqual(resolve_style(get_persona('columnist'), 'haeyo').id, 'haeyo')

    def test_style_conversion_gets_a_safe_budget(self):
        light = get_persona('proofreader')
        self.assertEqual(edit_budget(light, get_style('keep')), (.15, 'atomic'))
        self.assertEqual(edit_budget(light, get_style('handa')), (.35, 'safe-subset'))
        self.assertEqual(edit_budget(get_persona('columnist'), get_style('handa')), (.5, 'safe-subset'))
        self.assertEqual(edit_budget(light, get_style('handa'), .2, 'atomic'), (.2, 'atomic'))

    def test_prompt_carries_the_style(self):
        task = prepare(TEXT, persona='columnist', style='handa')
        self.assertEqual(task['style']['id'], 'handa')
        self.assertIn('문법 스타일: 한다체', task['instruction'])
        self.assertIn('다른 지침보다 우선', task['instruction'])
        self.assertNotIn('문법 스타일', prepare(TEXT)['instruction'])
        self.assertNotIn('문법 스타일', prepare(TEXT, mode='preserve', style='haeyo')['instruction'])


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.source = self.root / 'in.txt'
        self.source.write_text(TEXT, encoding='utf-8')

    def tearDown(self):
        self.folder.cleanup()

    def run_cli(self, *argv):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            return cli.main(list(argv))

    def test_apply_reports_conformance_before_and_after(self):
        proposals = self.root / 'p.json'
        proposals.write_text(json.dumps({'schema_version': '1.0', 'source_sha256': text_hash(TEXT), 'edits': [
            {'original': '실행됩니다.', 'replacement': '실행돼요.', 'reason': '해요체', 'rule': 'style'}]},
            ensure_ascii=False), encoding='utf-8')
        report = self.root / 'r.json'
        self.assertEqual(self.run_cli('apply', str(self.source), '--proposals', str(proposals), '--style', 'haeyo',
                                      '-o', str(self.root / 'o.txt'), '--report', str(report)), 0)
        data = json.loads(report.read_text(encoding='utf-8'))
        self.assertEqual(data['style']['id'], 'haeyo')
        self.assertEqual(data['edit_budget']['policy'], 'safe-subset')
        self.assertEqual(data['style_conformance']['before']['matching'], 0)
        self.assertEqual(data['style_conformance']['after']['matching'], 1)
        self.assertEqual(data['style_conformance']['after']['mismatched_examples'], ['실패하면 알림을 보냅니다.'])

    def test_builtin_rejects_style_conversion(self):
        self.assertEqual(self.run_cli('rewrite', str(self.source), '--style', 'handa'), 3)
        self.assertEqual(self.run_cli('rewrite', str(self.source), '--style', 'keep', '-o', str(self.root / 'o.txt')), 0)

    def test_prepare_exports_the_style(self):
        out = self.root / 'task.json'
        self.assertEqual(self.run_cli('prepare', str(self.source), '--persona', 'friendly', '-o', str(out)), 0)
        self.assertEqual(json.loads(out.read_text(encoding='utf-8'))['style']['id'], 'haeyo')

    def test_page_offers_every_style_with_persona_default_selected(self):
        self.assertIn('<option value="" selected>페르소나 기본값</option>', PAGE)
        for style in STYLES:
            self.assertIn(f'value="{style}"', PAGE)
        self.assertIn('data-style="hamnida"', PAGE)
        self.assertNotIn('__STYLE_OPTIONS__', PAGE)

    def test_rewrite_job_passes_style_and_reports_conformance(self):
        plan = resolve_proposals(TEXT, {'schema_version': '1.0', 'source_sha256': text_hash(TEXT), 'edits': [
            {'original': '실행됩니다.', 'replacement': '실행된다.', 'reason': '한다체', 'rule': 'style'},
            {'original': '보냅니다.', 'replacement': '보낸다.', 'reason': '한다체', 'rule': 'style'}]})
        with patch('clearwrite.ui.model_plan', return_value=plan) as model:
            result = rewrite_job({'text': TEXT, 'backend': 'claude', 'persona': 'editor', 'style': 'handa',
                                  'allow_model': True}, threading.Event())
        self.assertEqual(model.call_args.kwargs['style'], 'handa')
        self.assertEqual(result['style_conformance']['after']['rate'], 1.0)
        with self.assertRaises(InputError):
            rewrite_job({'text': TEXT, 'backend': 'claude', 'style': 'banmal', 'allow_model': True}, threading.Event())


if __name__ == '__main__':
    unittest.main()

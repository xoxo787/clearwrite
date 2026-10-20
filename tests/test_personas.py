"""Editor personas: register guidance, intervention budgets and every entry point."""
# ruff: noqa: E402
from __future__ import annotations
import contextlib
import http.client
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
from clearwrite.model_cli import CLIInfo, model_plan
from clearwrite.personas import BUILTIN_PERSONAS, DEFAULT_PERSONA, PERSONAS, catalog, get_persona
from clearwrite.providers import ollama_plan
from clearwrite.ui import PAGE, Server, rewrite_job

TEXT = '이와 같은 표현을 사용하여 문서를 확인한다. 원본 파일은 12개를 별도로 보관한다.'
GOOD = {'original': '이와 같은', 'replacement': '이런', 'reason': '지시 표현 정리', 'rule': 'context'}
BAD = {'original': '12개를', 'replacement': '21개를', 'reason': '잘못된 제안', 'rule': 'context'}


def proposals(*edits):
    return {'schema_version': '1.0', 'source_sha256': text_hash(TEXT), 'edits': list(edits)}


class CatalogTests(unittest.TestCase):
    def test_budgets_stay_inside_engine_limits(self):
        for persona in PERSONAS.values():
            with self.subTest(persona=persona.id):
                self.assertIn(persona.intensity, {'light', 'medium', 'strong'})
                self.assertIn(persona.policy, {'atomic', 'safe-subset'})
                self.assertTrue(0 < persona.max_change <= .5)
                self.assertTrue(persona.summary and persona.guidance)

    def test_default_keeps_the_previous_budget(self):
        editor = get_persona(None)
        self.assertEqual(editor.id, DEFAULT_PERSONA)
        self.assertEqual((editor.max_change, editor.policy), (.35, 'atomic'))

    def test_intensities_cover_light_to_strong(self):
        self.assertEqual({p['intensity'] for p in catalog()}, {'light', 'medium', 'strong'})
        self.assertTrue(any(p['changes_voice'] for p in catalog()))

    def test_unknown_persona_rejected(self):
        for value in ('unknown', 3, ['editor']):
            with self.subTest(value=value), self.assertRaises(InputError):
                get_persona(value)


class PromptTests(unittest.TestCase):
    def test_default_prompt_names_the_editor(self):
        task = prepare(TEXT)
        self.assertEqual(task['persona']['id'], 'editor')
        self.assertIn('담백한 편집자', task['instruction'])

    def test_voice_persona_overrides_voice_preservation_only_for_register(self):
        task = prepare(TEXT, mode='publish', persona='friendly')
        self.assertIn('해요체', task['instruction'])
        self.assertIn('필자 말투 유지 지침보다 우선', task['instruction'])
        # Meaning limits remain in every persona prompt.
        self.assertIn('부정·가능성·조건', task['instruction'])
        self.assertIn('인물 연기가 아니다', task['instruction'])

    def test_strong_persona_asks_for_sentence_sized_edits(self):
        self.assertIn('한 편집은 한 문장을 넘지 않게', prepare(TEXT, persona='columnist')['instruction'])
        self.assertNotIn('한 편집은 한 문장을 넘지 않게', prepare(TEXT, persona='editor')['instruction'])

    def test_voice_preserving_persona_has_no_override(self):
        self.assertNotIn('필자 말투 유지 지침보다 우선', prepare(TEXT, persona='columnist')['instruction'])

    def test_preserve_mode_ignores_persona_guidance(self):
        self.assertNotIn('편집자 페르소나', prepare(TEXT, mode='preserve', persona='friendly')['instruction'])

    def test_model_cli_receives_the_selected_persona(self):
        seen = {}
        def runner(info, prompt, directory, model, timeout, cancel):
            seen.update(json.loads(prompt))
            return proposals()
        with patch('clearwrite.model_cli.cli_info', return_value=CLIInfo('codex', ('fixture',), 'fixture')):
            model_plan(TEXT, backend='codex', allow_model=True, runner=runner, persona='formal')
        self.assertEqual(seen['persona']['id'], 'formal')
        self.assertIn('합쇼체', seen['instruction'])

    def test_ollama_receives_the_selected_persona(self):
        seen = {}
        def transport(method, url, headers, body, timeout):
            seen.update(body)
            return {'message': {'content': json.dumps(proposals())}}
        ollama_plan(TEXT, model='fixture', persona='plain', transport=transport)
        self.assertIn('쉬운 말 해설가', seen['messages'][0]['content'])


class CommandLineTests(unittest.TestCase):
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

    def report(self, name='report.json'):
        return json.loads((self.root / name).read_text(encoding='utf-8'))

    def apply(self, *extra, name='report.json'):
        plan = self.root / 'proposals.json'
        plan.write_text(json.dumps(proposals(GOOD, BAD), ensure_ascii=False), encoding='utf-8')
        return self.run_cli('apply', str(self.source), '--proposals', str(plan), '-o', str(self.root / ('out-' + name)),
                            '--report', str(self.root / name), *extra)

    def test_default_apply_is_atomic_and_blocks(self):
        self.assertEqual(self.apply(), 2)
        report = self.report()
        self.assertEqual(report['status'], 'blocked')
        self.assertEqual(report['edit_budget'], {'max_change': .35, 'policy': 'atomic'})

    def test_strong_persona_keeps_passing_edits(self):
        self.assertEqual(self.apply('--persona', 'columnist'), 0)
        report = self.report()
        self.assertEqual(report['status'], 'edited')
        self.assertEqual([e['original'] for e in report['applied_edits']], ['이와 같은'])
        self.assertEqual(report['rejected_edits'][0]['reason'], 'numbers_units_or_order_changed')
        self.assertIn('12개', report['text'])
        self.assertEqual(report['persona']['id'], 'columnist')

    def test_explicit_policy_overrides_persona(self):
        self.assertEqual(self.apply('--persona', 'columnist', '--policy', 'atomic'), 2)
        self.assertEqual(self.report()['edit_budget']['policy'], 'atomic')

    def test_explicit_max_change_overrides_persona(self):
        self.assertEqual(self.apply('--persona', 'columnist', '--max-change', '0.01'), 2)
        report = self.report()
        self.assertEqual(report['edit_budget']['max_change'], .01)
        self.assertIn('change_budget_exceeded', report['verification']['failures'])

    def test_verify_uses_the_persona_budget(self):
        candidate = self.root / 'candidate.txt'
        candidate.write_text(TEXT.replace('이와 같은 표현을 사용하여', '그런 말투로'), encoding='utf-8')
        out = self.root / 'verify.json'
        codes = {persona: self.run_cli('verify', str(self.source), str(candidate), '--persona', persona,
                                       '-o', str(out), '--force')
                 for persona in ('proofreader', 'columnist')}
        self.assertEqual(codes, {'proofreader': 2, 'columnist': 0})

    def test_prepare_rejects_unknown_persona(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(['prepare', str(self.source), '--persona', 'pirate'])

    def test_light_persona_tightens_the_change_budget(self):
        self.assertEqual(self.run_cli('rewrite', str(self.source), '--persona', 'proofreader', '-o', str(self.root / 'o.txt'),
                                      '--report', str(self.root / 'report.json')), 0)
        self.assertEqual(self.report()['edit_budget']['max_change'], .15)

    def test_builtin_rejects_register_personas(self):
        for persona in set(PERSONAS) - BUILTIN_PERSONAS:
            with self.subTest(persona=persona):
                self.assertEqual(self.run_cli('rewrite', str(self.source), '--persona', persona), 3)

    def test_prepare_exports_the_persona(self):
        out = self.root / 'task.json'
        self.assertEqual(self.run_cli('prepare', str(self.source), '--persona', 'plain', '--proposals', '-o', str(out)), 0)
        self.assertEqual(json.loads(out.read_text(encoding='utf-8'))['persona']['id'], 'plain')


class EditorTests(unittest.TestCase):
    def test_page_lists_every_persona_with_editor_selected(self):
        for persona in PERSONAS.values():
            self.assertIn(f'value="{persona.id}"', PAGE)
        self.assertIn('value="editor" data-summary', PAGE)
        self.assertIn('selected>담백한 편집자', PAGE)
        self.assertNotIn('__PERSONA_OPTIONS__', PAGE)

    def test_rewrite_job_uses_the_persona_budget(self):
        with patch('clearwrite.ui.model_plan', return_value=resolve_proposals(TEXT, proposals(GOOD, BAD))) as plan:
            result = rewrite_job({'text': TEXT, 'backend': 'claude', 'mode': 'personal', 'persona': 'friendly',
                                  'allow_model': True}, threading.Event())
        self.assertEqual(plan.call_args.kwargs['persona'], 'friendly')
        self.assertEqual(result['status'], 'edited')
        self.assertEqual(result['edit_budget'], {'max_change': .5, 'policy': 'safe-subset'})
        self.assertEqual(len(result['rejected_edits']), 1)

    def test_rewrite_job_rejects_unknown_persona(self):
        with self.assertRaises(InputError):
            rewrite_job({'text': TEXT, 'backend': 'claude', 'persona': 'pirate', 'allow_model': True}, threading.Event())

    def test_http_job_rejects_unknown_persona_before_starting(self):
        server = Server(0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            body = {'action': 'rewrite', 'text': TEXT, 'backend': 'claude', 'persona': 'pirate', 'allow_model': True}
            with patch('clearwrite.ui.model_plan') as plan:
                connection.request('POST', '/api/jobs', body=json.dumps(body).encode(), headers={
                    'Origin': server.origin, 'X-ClearWrite-Token': server.token, 'Content-Type': 'application/json'})
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                response.read()
                plan.assert_not_called()
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == '__main__':
    unittest.main()

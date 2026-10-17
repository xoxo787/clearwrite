"""Offline model contracts, real child processes, diff fidelity, and HTTP jobs."""
# Source checkout tests load the package from src before importing it.
# ruff: noqa: E402
from __future__ import annotations
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from clearwrite.comparison import comparison
from clearwrite.core import InputError, apply_plan, make_plan, resolve_proposals, text_hash
from clearwrite.jobs import BusyError, Jobs
from clearwrite.model_cli import CLIInfo, CODEX_DISABLED_FEATURES, ModelCancelled, _command, _environment, model_plan
from clearwrite.providers import ProviderError
from clearwrite.ui import Server, demo

TEXT = '이와 같은 표현을 사용하여 문서를 확인한다. 원본 파일은 별도로 보관한다.'


def proposal(text=TEXT):
    return {'schema_version': '1.0', 'source_sha256': text_hash(text), 'edits': [
        {'original': '이와 같은', 'replacement': '이런', 'reason': '지시 표현을 자연스럽게 다듬었습니다.', 'rule': 'context'}]}


class ComparisonTests(unittest.TestCase):
    def check_roundtrip(self, text, result):
        data = comparison(text, result)
        self.assertEqual(''.join(p['text'] for p in data['before_segments']), text)
        self.assertEqual(''.join(p['text'] for p in data['after_segments']), result['text'])
        return data

    def test_multiple_changes_with_emoji_and_korean(self):
        text = '🏃 ' + TEXT
        result = apply_plan(text, make_plan(text))
        data = self.check_roundtrip(text, result)
        self.assertEqual(len(data['changes']), 2)
        self.assertEqual(data['changes'][0]['start'], 2)
        for item in data['changes']:
            self.assertEqual(result['text'][item['output_start']:item['output_end']], item['replacement'])

    def test_deletion_has_a_display_marker_without_changing_output(self):
        text = '오늘은 정말 맑은 날이다. 강가에서 천천히 걷는다.'
        plan = {'schema_version':'1.0', 'source_sha256':text_hash(text), 'edits':[
            {'original':'정말 ', 'replacement':'', 'reason':'중복 강조 정리', 'rule':'context'}]}
        result = apply_plan(text, resolve_proposals(text, plan))
        self.assertEqual(result['status'], 'edited')
        data = self.check_roundtrip(text, result)
        self.assertTrue(any(p['kind'] == 'deletion_marker' for p in data['after_segments']))

    def test_blocked_plan_is_not_highlighted_as_applied(self):
        text = '수강생 12명은 원본 파일을 별도로 보관한다.'
        plan = {'schema_version':'1.0', 'source_sha256':text_hash(text), 'edits':[
            {'original':'12명', 'replacement':'21명', 'reason':'잘못된 제안', 'rule':'test'}]}
        result = apply_plan(text, resolve_proposals(text, plan))
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.check_roundtrip(text, result)['changes'], [])

    def test_inserted_space_has_original_anchor_at_the_exact_position(self):
        text = '🏃 강가에서 뛰었다.목표했던 거리는 평소와 같았다.'
        plan = {'schema_version': '1.0', 'source_sha256': text_hash(text), 'edits': [
            {'original': '뛰었다.목표했던', 'replacement': '뛰었다. 목표했던', 'reason': '공백 보완', 'rule': 'spacing'}]}
        result = apply_plan(text, resolve_proposals(text, plan))
        self.assertEqual(result['status'], 'edited')
        data = self.check_roundtrip(text, result)
        before = data['before_segments']
        index = next(i for i, part in enumerate(before) if part['kind'] == 'insertion_marker')
        self.assertEqual(len(''.join(part['text'] for part in before[:index])), text.index('목표했던'))
        self.assertEqual(before[index]['change_id'], 1)

    def test_partial_deletion_has_result_anchor_without_adding_text(self):
        text = '오늘은 정말 맑은 날이다. 강가에서 천천히 걷는다.'
        plan = {'schema_version': '1.0', 'source_sha256': text_hash(text), 'edits': [
            {'original': '정말 맑은', 'replacement': '맑은', 'reason': '강조 정리', 'rule': 'context'}]}
        result = apply_plan(text, resolve_proposals(text, plan))
        self.assertEqual(result['status'], 'edited')
        data = self.check_roundtrip(text, result)
        after = data['after_segments']
        index = next(i for i, part in enumerate(after) if part['kind'] == 'deletion_marker')
        self.assertEqual(len(''.join(part['text'] for part in after[:index])), result['text'].index('맑은'))
        self.assertEqual(after[index]['change_id'], 1)

    def test_invalid_comparison_result_rejected(self):
        result = apply_plan(TEXT, make_plan(TEXT))
        result['text'] = 'not the applied result'
        with self.assertRaises(InputError):
            comparison(TEXT, result)

    def test_example_uses_real_gates_but_no_model(self):
        result = demo()
        self.assertEqual(result['model_requests'], 0)
        self.assertTrue(result['demonstration'])
        self.assertTrue(result['verification']['passed'])
        self.assertGreater(len(result['changes']), 0)


class ModelAdapterTests(unittest.TestCase):
    def setUp(self):
        self.info = CLIInfo('codex', (sys.executable, str(ROOT / 'tests/fixtures/fake_model_cli.py')), 'fixture')

    def test_consent_required_before_discovery_or_process(self):
        with patch('clearwrite.model_cli.cli_info') as discover:
            with self.assertRaises(InputError):
                model_plan(TEXT, backend='codex')
            discover.assert_not_called()

    def test_model_name_cannot_be_an_option(self):
        with self.assertRaises(InputError):
            model_plan(TEXT, backend='codex', allow_model=True, model='--dangerous')

    def test_installed_cli_receives_only_the_prepared_text_task(self):
        def runner(info, prompt, directory, model, timeout, cancel):
            task = json.loads(prompt)
            self.assertEqual(task['text'], TEXT)
            self.assertEqual(task['source_sha256'], text_hash(TEXT))
            self.assertNotIn('start', task['output_schema']['properties']['edits']['items']['properties'])
            return proposal()
        with patch('clearwrite.model_cli.cli_info', return_value=self.info):
            plan = model_plan(TEXT, backend='codex', allow_model=True, runner=runner)
        self.assertEqual(apply_plan(TEXT, plan)['status'], 'edited')

    def test_codex_command_restricts_tools_and_does_not_include_prose(self):
        command = _command(self.info, Path(tempfile.gettempdir()) / 'clearwrite-contract', None)
        self.assertIn('--ignore-user-config', command)
        self.assertIn('read-only', command)
        self.assertIn('mcp_servers={}', command)
        self.assertIn('project_doc_max_bytes=0', command)
        for feature in CODEX_DISABLED_FEATURES:
            index = command.index(feature)
            self.assertEqual(command[index-1], '--disable')
        self.assertNotIn(TEXT, command)
        self.assertFalse(any(arg.startswith('--dangerously') for arg in command))

    def test_claude_command_removes_mcp_and_builtin_tools(self):
        command = _command(CLIInfo('claude', ('claude',)), Path(tempfile.gettempdir()), None)
        self.assertEqual(command[command.index('--tools')+1], '')
        self.assertEqual(command[command.index('--disallowedTools')+1], '*')
        self.assertIn('--bare', command)
        self.assertIn('--strict-mcp-config', command)
        self.assertIn('--no-session-persistence', command)

    def test_inherited_billable_keys_are_not_sent_to_the_cli(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':'fixture', 'ANTHROPIC_API_KEY':'fixture', 'PANGRAM_API_KEY':'fixture'}):
            env = _environment()
            self.assertNotIn('OPENAI_API_KEY', env)
            self.assertNotIn('ANTHROPIC_API_KEY', env)
            self.assertNotIn('PANGRAM_API_KEY', env)
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'fixture')

    def test_real_child_process_utf8_protocol(self):
        with patch('clearwrite.model_cli.cli_info', return_value=self.info):
            plan = model_plan(TEXT, backend='codex', allow_model=True, timeout=4)
        self.assertEqual(plan['source_sha256'], text_hash(TEXT))
        self.assertEqual(plan['edits'], [])

    def test_real_child_process_claude_envelope(self):
        info = CLIInfo('claude', self.info.argv, 'fixture')
        with patch('clearwrite.model_cli.cli_info', return_value=info):
            plan = model_plan(TEXT, backend='claude', allow_model=True, timeout=4)
        self.assertEqual(plan['edits'], [])

    def test_cli_errors_do_not_echo_process_output(self):
        with patch('clearwrite.model_cli.cli_info', return_value=self.info):
            with self.assertRaises(ProviderError) as error:
                model_plan(TEXT, backend='codex', allow_model=True, voice='fail', timeout=4)
        self.assertNotIn('private-fixture', str(error.exception))

    def test_malformed_and_oversize_outputs(self):
        with patch('clearwrite.model_cli.cli_info', return_value=self.info):
            for scenario in ('malformed', 'oversize'):
                with self.subTest(scenario=scenario), self.assertRaises(ProviderError):
                    model_plan(TEXT, backend='codex', allow_model=True, voice=scenario, timeout=4)

    def test_timeout_stops_the_process(self):
        started = time.monotonic()
        with patch('clearwrite.model_cli.cli_info', return_value=self.info):
            with self.assertRaises(ProviderError):
                model_plan(TEXT, backend='codex', allow_model=True, voice='wait', timeout=1)
        self.assertLess(time.monotonic()-started, 6)

    def test_cancel_stops_the_process(self):
        event = threading.Event()
        timer = threading.Timer(.3, event.set)
        timer.start()
        try:
            with patch('clearwrite.model_cli.cli_info', return_value=self.info):
                with self.assertRaises(ModelCancelled):
                    model_plan(TEXT, backend='codex', allow_model=True, voice='wait', cancel=event, timeout=4)
        finally:
            timer.cancel()


class JobTests(unittest.TestCase):
    def test_bounded_jobs_and_cancellation(self):
        manager = Jobs(threading.BoundedSemaphore(1))
        started = threading.Event()
        def task(cancel):
            started.set()
            cancel.wait(3)
            raise ModelCancelled('cancelled fixture')
        identifier = manager.start(task)['job_id']
        self.assertTrue(started.wait(1))
        with self.assertRaises(BusyError):
            manager.start(task)
        manager.cancel(identifier)
        manager.close()
        self.assertEqual(manager.get(identifier)['state'], 'cancelled')
        self.assertIsNone(manager.get('missing'))


class EditorHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)

    def request(self, path, data=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        values = {'Origin':self.server.origin, 'X-ClearWrite-Token':self.server.token, 'Content-Type':'application/json'}
        values.update(headers or {})
        connection.request('POST' if data is not None else 'GET', path,
                           body=None if data is None else json.dumps(data).encode(), headers=values)
        response = connection.getresponse()
        status, body = response.status, json.loads(response.read())
        connection.close()
        return status, body

    def wait_job(self, identifier):
        deadline = time.monotonic()+4
        while time.monotonic()<deadline:
            _, result = self.request('/api/jobs/'+identifier)
            if result['state'] != 'running':
                return result
            time.sleep(.02)
        self.fail('job did not finish')

    def test_rewrite_requires_explicit_model_consent(self):
        with patch('clearwrite.ui.model_plan') as model:
            status, _ = self.request('/api/jobs', {'action':'rewrite','text':TEXT,'backend':'codex'})
        self.assertEqual(status, 400)
        model.assert_not_called()

    def test_job_result_contains_only_applied_highlights(self):
        with patch('clearwrite.ui.model_plan', return_value=resolve_proposals(TEXT, proposal())):
            status, created = self.request('/api/jobs', {'action':'rewrite','text':TEXT,'backend':'codex','allow_model':True})
            result = self.wait_job(created['job_id'])
        self.assertEqual(status, 202)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(len(result['result']['changes']), 1)
        self.assertTrue(result['result']['verification']['passed'])

    def test_job_poll_requires_token_and_same_origin(self):
        status, _ = self.request('/api/jobs/'+'a'*24, headers={'X-ClearWrite-Token':''})
        self.assertEqual(status, 403)
        status, _ = self.request('/api/jobs/'+'a'*24, headers={'Origin':'https://other.invalid'})
        self.assertEqual(status, 403)



    def test_example_endpoint_has_no_model_request(self):
        with patch('clearwrite.ui.model_plan') as model:
            status, result = self.request('/api/example')
        self.assertEqual(status, 200)
        self.assertEqual(result['model_requests'], 0)
        model.assert_not_called()

    def test_preserve_job_never_calls_model(self):
        with patch('clearwrite.ui.model_plan') as model:
            _, created = self.request('/api/jobs', {'action':'rewrite','text':TEXT,'backend':'codex','mode':'preserve'})
            result = self.wait_job(created['job_id'])
        self.assertEqual(result['result']['text'], TEXT)
        self.assertEqual(result['result']['model_requests'], 0)
        model.assert_not_called()

    def test_old_ollama_web_option_cannot_invoke_a_provider(self):
        status, _ = self.request('/api/jobs', {'action':'rewrite','text':TEXT,'backend':'ollama','allow_model':True})
        self.assertEqual(status, 400)

    def test_style_requires_explicit_model_consent(self):
        with patch('clearwrite.ui.model_style') as model:
            status, _ = self.request('/api/jobs', {'action':'style','text':TEXT,'backend':'codex'})
        self.assertEqual(status, 400)
        model.assert_not_called()

    def test_style_failure_returns_no_fake_score(self):
        with patch('clearwrite.ui.model_style', side_effect=ProviderError('문체 분석 실패')):
            status, created = self.request('/api/jobs', {'action':'style','text':TEXT,'backend':'codex','allow_model':True})
            result = self.wait_job(created['job_id'])
        self.assertEqual(status, 202)
        self.assertEqual(result['state'], 'failed')
        self.assertIsNone(result['result'])

    def test_style_job_preserves_exact_candidate_without_rewriting(self):
        candidate = TEXT.replace('이와 같은', '이런')
        with patch('clearwrite.ui.model_style', return_value={'status':'completed','before':{'score':12},'after':{'score':10}}) as model:
            _, created = self.request('/api/jobs', {'action':'style','text':TEXT,'candidate':candidate,'backend':'claude','allow_model':True})
            result = self.wait_job(created['job_id'])
        self.assertEqual(result['result']['candidate_text'], candidate)
        self.assertEqual(model.call_args.kwargs['backend'], 'claude')
        self.assertEqual(model.call_args.kwargs['candidate'], candidate)

    def test_style_rejects_invalid_candidate_and_removed_detector(self):
        for data in ({'action':'style','text':TEXT,'candidate':[],'backend':'codex','allow_model':True},
                     {'action':'detect','text':TEXT,'allow_external':True},
                     {'action':'style','text':TEXT,'backend':'ollama','allow_model':True}):
            with self.subTest(data=data):
                self.assertEqual(self.request('/api/jobs', data)[0], 400)


if __name__ == '__main__':
    unittest.main()

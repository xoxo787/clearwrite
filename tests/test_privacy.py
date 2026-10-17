"""No prose on ClearWrite temp disk, bounded pipes, and idle record expiry."""
# ruff: noqa: E402
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from clearwrite.core import text_hash
from clearwrite.jobs import BusyError, Jobs
from clearwrite.model_cli import CLIInfo, ModelCancelled, _environment, _run
from clearwrite.providers import ProviderError

FIXTURE = ROOT / 'tests/fixtures/fake_model_cli.py'
CANARY = 'private-canary-원문-응답-12345'


class PipePrivacyTests(unittest.TestCase):
    def task(self, scenario=''):
        return json.dumps({'text': CANARY, 'source_sha256': text_hash(CANARY),
                           'voice_sample': scenario}, ensure_ascii=False)

    def assert_no_prose_files(self, directory):
        self.assertEqual({path.name for path in directory.iterdir()}, {'schema.json'})
        self.assertNotIn(CANARY.encode('utf-8'), (directory / 'schema.json').read_bytes())

    def test_success_keeps_only_static_schema_for_both_clis(self):
        for backend in ('codex', 'claude'):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                result = _run(CLIInfo(backend, (sys.executable, str(FIXTURE))), self.task(),
                              directory, None, 5, threading.Event())
                self.assertEqual(result['source_sha256'], text_hash(CANARY))
                self.assert_no_prose_files(directory)

    def test_failure_timeout_and_bad_outputs_leave_no_prose_files(self):
        for scenario in ('fail', 'malformed', 'oversize', 'oversize-stderr', 'wait'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                with self.assertRaises(ProviderError):
                    _run(CLIInfo('codex', (sys.executable, str(FIXTURE))), self.task(scenario),
                         directory, None, .3 if scenario == 'wait' else 5, threading.Event())
                self.assert_no_prose_files(directory)

    def test_cancelled_request_leaves_no_prose_files(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            cancel = threading.Event()
            timer = threading.Timer(.2, cancel.set)
            timer.start()
            try:
                with self.assertRaises(ModelCancelled):
                    _run(CLIInfo('codex', (sys.executable, str(FIXTURE))), self.task('wait'),
                         directory, None, 5, cancel)
            finally:
                timer.cancel()
            self.assert_no_prose_files(directory)

    def test_large_input_with_both_output_pipes_under_pressure(self):
        with tempfile.TemporaryDirectory() as folder:
            task = json.loads(self.task())
            task['text'] = CANARY * 10_000
            result = _run(CLIInfo('codex', (sys.executable, str(FIXTURE), '--fixture-pipe-pressure')),
                          json.dumps(task), Path(folder), None, 8, threading.Event())
            self.assertEqual(result['source_sha256'], text_hash(CANARY))
            self.assert_no_prose_files(Path(folder))

    def test_abrupt_parent_exit_cannot_leave_prompt_or_response_files(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            code = (
                'import os,sys,tempfile,threading\n'
                'from pathlib import Path\n'
                'import clearwrite.model_cli as m\n'
                f'tempfile.tempdir={str(directory)!r}\n'
                'original=m.subprocess.Popen\n'
                'def observe(*args,**kwargs):\n'
                ' p=original(*args,**kwargs);print(p.pid,flush=True);return p\n'
                'm.subprocess.Popen=observe\n'
                f'm.cli_info=lambda backend:m.CLIInfo(backend,(sys.executable,{str(FIXTURE)!r}))\n'
                'threading.Timer(.5,lambda:os._exit(77)).start()\n'
                f'm.model_plan({CANARY!r},backend="codex",allow_model=True,voice="wait")\n'
            )
            env = os.environ.copy()
            env['PYTHONPATH'] = str(ROOT / 'src')
            result = subprocess.run([sys.executable, '-c', code], capture_output=True, env=env,
                                    timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            child_pid = int(result.stdout.strip()) if result.stdout.strip().isdigit() else None
            try:
                self.assertEqual(result.returncode, 77, result.stderr.decode('utf-8', errors='replace'))
                self.assertIsNotNone(child_pid)
                workspaces = list(directory.glob('clearwrite-model-*'))
                self.assertEqual(len(workspaces), 1)
                self.assert_no_prose_files(workspaces[0])
            finally:
                if child_pid is not None:
                    if os.name == 'nt':
                        taskkill = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/taskkill.exe'
                        subprocess.run([str(taskkill), '/PID', str(child_pid), '/T', '/F'],
                                       capture_output=True, timeout=8, creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        try:
                            os.killpg(child_pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass

    def test_codex_api_key_is_not_inherited(self):
        with patch.dict(os.environ, {'CODEX_API_KEY': 'fixture-only'}):
            self.assertNotIn('CODEX_API_KEY', _environment())


class RetentionTests(unittest.TestCase):
    def wait_for(self, predicate, timeout=3):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= deadline:
                self.fail('Expected background cleanup did not happen')
            time.sleep(.01)

    def finished(self, manager, identifier):
        with manager.lock:
            job = manager.items.get(identifier)
            return job is not None and job.finished is not None

    def empty(self, manager):
        with manager.lock:
            return not manager.items

    def test_idle_completed_record_expires_without_new_requests(self):
        manager = Jobs(retention_seconds=.15, cleanup_interval=.01)
        try:
            identifier = manager.start(lambda cancel: {'text': CANARY})['job_id']
            self.wait_for(lambda: self.finished(manager, identifier))
            self.assertEqual(manager.get(identifier)['result']['text'], CANARY)
            # Inspect the store directly: no API/start/get request triggers expiry.
            self.wait_for(lambda: self.empty(manager))
            self.assertIsNone(manager.get(identifier))
        finally:
            manager.close()

    def test_running_job_is_not_expired_and_retention_starts_at_completion(self):
        manager = Jobs(retention_seconds=.3, cleanup_interval=.01)
        release = threading.Event()
        try:
            def task(cancel):
                release.wait(3)
                return {'text': CANARY}
            identifier = manager.start(task)['job_id']
            time.sleep(.35)
            self.assertEqual(manager.get(identifier)['state'], 'running')
            release.set()
            self.wait_for(lambda: self.finished(manager, identifier))
            self.assertEqual(manager.get(identifier)['state'], 'completed')
            self.wait_for(lambda: self.empty(manager))
        finally:
            release.set()
            manager.close()

    def test_failed_and_cancelled_records_expire_while_idle(self):
        for error in (ProviderError('fixture failure'), ModelCancelled('fixture cancel')):
            with self.subTest(error=type(error).__name__):
                manager = Jobs(retention_seconds=.1, cleanup_interval=.01)
                try:
                    def task(cancel):
                        raise error
                    identifier = manager.start(task)['job_id']
                    self.wait_for(lambda: self.finished(manager, identifier))
                    self.wait_for(lambda: self.empty(manager))
                finally:
                    manager.close()

    def test_expired_record_cannot_be_read_between_cleaner_ticks(self):
        manager = Jobs(retention_seconds=.05, cleanup_interval=60)
        try:
            identifier = manager.start(lambda cancel: {'text': CANARY})['job_id']
            self.wait_for(lambda: self.finished(manager, identifier))
            time.sleep(.08)
            self.assertIsNone(manager.get(identifier))
        finally:
            manager.close()

    def test_shutdown_forgets_records_and_late_result_cannot_restore_them(self):
        manager = Jobs(cleanup_interval=.01)
        release, started, cancelled = threading.Event(), threading.Event(), threading.Event()
        def task(cancel):
            started.set()
            cancel.wait(3)
            cancelled.set()
            release.wait(3)
            return {'text': CANARY}
        identifier = manager.start(task)['job_id']
        self.assertTrue(started.wait(2))
        closer = threading.Thread(target=manager.close)
        closer.start()
        try:
            self.assertTrue(cancelled.wait(2))
            self.assertIsNone(manager.get(identifier))
            with self.assertRaises(BusyError):
                manager.start(lambda cancel: {'text': 'must not run'})
            release.set()
            closer.join(3)
            self.assertFalse(closer.is_alive())
            self.assertIsNone(manager.get(identifier))
            self.assertFalse(manager.cleaner.is_alive())
        finally:
            release.set()
            manager.close()
            closer.join(3)


if __name__ == '__main__':
    unittest.main()

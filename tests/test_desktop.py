"""Real source-launcher lifecycle and Windows UTF-8 pipe regressions."""
# ruff: noqa: E402
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from clearwrite.core import InputError, text_hash
from clearwrite.desktop import _request, existing
from clearwrite.ui import Server


class CLIPipeTests(unittest.TestCase):
    def test_utf8_input_under_a_legacy_pipe_encoding(self):
        text = '이와 같은 표현을 사용하여 원본 파일을 확인한다.'
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'cp949'
        result = subprocess.run([sys.executable, str(ROOT / 'rewrite.py'), 'analyze', '-'],
                                input=text.encode('utf-8'), capture_output=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8'))
        self.assertEqual(json.loads(result.stdout)['input_sha256'], text_hash(text))

    def test_invalid_utf8_input_is_rejected(self):
        result = subprocess.run([sys.executable, str(ROOT / 'rewrite.py'), 'analyze', '-'],
                                input=b'\xff', capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 3)
        self.assertNotIn(b'Traceback', result.stderr)

    def test_cli_model_requires_explicit_consent(self):
        result = subprocess.run([sys.executable, str(ROOT / 'rewrite.py'), 'rewrite', '-', '--backend', 'codex'],
                                input='No model should be called.'.encode(), capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 3)
        self.assertIn('동의', result.stderr.decode('utf-8'))


class DesktopTests(unittest.TestCase):
    def test_loopback_startup_needs_no_reverse_dns(self):
        with patch('socket.getfqdn', side_effect=AssertionError('Unexpected reverse DNS')):
            with Server(0) as server:
                self.assertEqual(server.server_address[0], '127.0.0.1')
                self.assertTrue(server.server_port > 0)
                self.assertEqual(server.origin, f'http://127.0.0.1:{server.server_port}')

    def test_instance_metadata_never_redirects_to_an_external_host(self):
        with patch('clearwrite.desktop.urllib.request.build_opener') as network:
            with self.assertRaises(InputError):
                _request('https://external.invalid:8000', '/api/health')
            network.assert_not_called()

    def test_invalid_metadata_is_not_used(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / 'instance.json').write_text('not json')
            self.assertIsNone(existing(directory))

    def test_start_reuse_and_shutdown_real_server(self):
        with tempfile.TemporaryDirectory(prefix='clearwrite desktop 한글 ') as folder:
            directory = Path(folder)
            command = [sys.executable, str(ROOT / 'scripts/desktop_entry.py'), '--no-open', '--state-dir', folder]
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
            try:
                # Hosted runners can start a cold Python process slowly.
                deadline = time.monotonic()+30
                while time.monotonic()<deadline and not (directory / 'instance.json').is_file():
                    if process.poll() is not None:
                        self.fail(process.communicate()[1].decode('utf-8', errors='replace'))
                    time.sleep(.04)
                self.assertTrue((directory / 'instance.json').is_file(),
                                'Desktop startup did not write metadata within 30 seconds')
                metadata = json.loads((directory / 'instance.json').read_text(encoding='utf-8'))
                self.assertIsNotNone(existing(directory))
                second = subprocess.run(command, capture_output=True, timeout=15, creationflags=flags)
                self.assertEqual(second.returncode, 0, second.stderr.decode('utf-8', errors='replace'))
                self.assertEqual(json.loads(second.stdout)['status'], 'already_running')
                self.assertEqual(json.loads((directory / 'instance.json').read_text())['pid'], metadata['pid'])
                stop = subprocess.run([*command, '--shutdown'], capture_output=True, timeout=15, creationflags=flags)
                self.assertEqual(stop.returncode, 0, stop.stderr.decode('utf-8', errors='replace'))
                process.wait(timeout=10)
                self.assertEqual(process.returncode, 0)
                self.assertFalse((directory / 'instance.json').exists())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=3)
                process.communicate(timeout=3)


if __name__ == '__main__':
    unittest.main()

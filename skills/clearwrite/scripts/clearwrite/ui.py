"""Loopback editor: consent-gated rewriting, model style assessments and diffs."""
from __future__ import annotations
import json
from functools import partial
from pathlib import Path
import re
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer
from typing import Any
from . import __version__
from .comparison import comparison
from .core import InputError, MODES, analyze, apply_plan, checked_text, make_plan, resolve_proposals, text_hash
from .io import strict_json
from .jobs import BusyError, Jobs
from .model_cli import backend_status, model_plan, model_style
from .providers import ProviderError

WEB = Path(__file__).with_name('web')
PAGE = (WEB / 'index.html').read_text(encoding='utf-8').replace('__STYLE__', (WEB / 'app.css').read_text(encoding='utf-8')).replace('__SCRIPT__', (WEB / 'app.js').read_text(encoding='utf-8')).replace('__VERSION__', __version__)
DEMO_TEXT = ('처음 도구를 사용하는 분들은 다음 절차를 참고하여 설정을 진행할 수 있습니다. '
             '설정을 시작하기 전에는 원본 파일을 별도로 보관해야 합니다.\n\n'
             '설정이 끝나면 결과 파일을 열어 내용이 올바른지 확인하세요. '
             '문제가 있다면 원본 파일로 돌아가 다시 확인하면 됩니다.')

def demo() -> dict:
    old = '처음 도구를 사용하는 분들은 다음 절차를 참고하여 설정을 진행할 수 있습니다.'
    proposal = {'schema_version': '1.0', 'source_sha256': text_hash(DEMO_TEXT), 'edits': [
        {'original': old, 'replacement': '처음 도구를 사용하는 분들은 다음 절차를 따라 차근차근 설정할 수 있습니다.',
         'reason': '처음 사용하는 독자라는 맥락과 가능성 표현을 유지하며 동작을 직접적으로 썼습니다.', 'rule': 'demo-context'},
        {'original': '설정이 끝나면 결과 파일을 열어 내용이 올바른지 확인하세요.',
         'replacement': '설정이 끝나면 결과 파일을 열고, 내용이 올바른지 확인하세요.',
         'reason': '파일을 여는 동작과 내용을 확인하는 동작의 연결을 다듬었습니다.', 'rule': 'demo-context'}]}
    result = apply_plan(DEMO_TEXT, resolve_proposals(DEMO_TEXT, proposal))
    result.update(comparison(DEMO_TEXT, result))
    result.update(backend='demo', demonstration=True, source_text=DEMO_TEXT, model_requests=0)
    return result

def rewrite_job(data: dict, cancel: threading.Event) -> dict:
    text = checked_text(data['text'])
    backend, mode = data.get('backend'), data.get('mode', 'personal')
    if backend not in {'codex', 'claude'} or not isinstance(mode, str) or mode not in MODES:
        raise InputError('모델과 편집 기준을 확인하세요.')
    if mode != 'preserve' and data.get('allow_model') is not True:
        raise InputError('선택한 모델 서비스로 원문을 전송하는 데 동의해야 합니다.')
    model = data.get('model') or None
    if model is not None and not isinstance(model, str):
        raise InputError('모델 이름은 문자열이어야 합니다.')
    plan = make_plan(text, mode='preserve') if mode == 'preserve' else model_plan(
        text, backend=backend, allow_model=True, model=model, mode=mode, cancel=cancel)
    result = apply_plan(text, plan)
    result.update(comparison(text, result))
    result.update(backend='preserve' if mode == 'preserve' else backend, source_text=text, demonstration=False,
                  model_requests=0 if mode == 'preserve' else None, cli_runs=0 if mode == 'preserve' else 1)
    return result

def style_job(data: dict, cancel: threading.Event) -> dict:
    candidate = data.get('candidate') or None
    result = model_style(data['text'], candidate=candidate, backend=data.get('backend'),
                         allow_model=data.get('allow_model') is True, model=data.get('model') or None,
                         cancel=cancel)
    return {**result, 'source_text': data['text'], 'candidate_text': candidate}

class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, port: int = 0):
        if type(port) is not int or not 0 <= port <= 65535:
            raise InputError('유효하지 않은 포트입니다.')
        self.token, self.nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        self.processing = threading.BoundedSemaphore(2)
        self.jobs = Jobs(self.processing)
        self.instance_id = secrets.token_urlsafe(18)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'
    def server_bind(self) -> None:
        # This editor only serves loopback. HTTPServer's reverse-DNS lookup is
        # unnecessary and can delay startup on hosts with a slow resolver.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]
    def server_close(self) -> None:
        self.jobs.close()
        super().server_close()

class Handler(BaseHTTPRequestHandler):
    server_version = 'ClearWrite'
    sys_version = ''
    def log_message(self, format: str, *args: Any) -> None:
        pass
    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(10)
    def send(self, code: int, body: Any, *, page: bool = False) -> None:
        data = body.encode('utf-8') if page else json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8' if page else 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', f"default-src 'none'; script-src 'nonce-{self.server.nonce}'; style-src 'nonce-{self.server.nonce}'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass
    def valid_host(self) -> bool:
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'
    def authorized(self, *, origin_required: bool = False) -> bool:
        origin = self.headers.get('Origin')
        return (self.valid_host() and (origin == self.server.origin if origin_required else origin in (None, self.server.origin))
                and secrets.compare_digest(self.headers.get('X-ClearWrite-Token', '').encode('utf-8'), self.server.token.encode('ascii')))
    def do_GET(self) -> None:
        if not self.valid_host():
            self.send(403, {'error': 'Host 거부'})
        elif self.path == '/':
            self.send(200, PAGE.replace('__TOKEN__', self.server.token).replace('__NONCE__', self.server.nonce), page=True)
        elif self.path == '/api/health':
            self.send(200, {'app': 'ClearWrite', 'version': __version__, 'instance_id': self.server.instance_id})
        elif not self.authorized():
            self.send(403, {'error': '동일 출처와 CSRF 토큰이 필요합니다.'})
        elif self.path == '/api/status':
            self.send(200, {**backend_status(), 'style_assessment': {'backends': ['codex', 'claude'],
                            'requires_model_consent': True, 'calibrated': False}})
        elif self.path == '/api/example':
            self.send(200, demo())
        elif re.fullmatch(r'/api/jobs/[A-Za-z0-9_-]{24}', self.path):
            result = self.server.jobs.get(self.path.rsplit('/', 1)[1])
            self.send(200 if result else 404, result or {'error': '작업이 없거나 만료되었습니다.'})
        else:
            self.send(404, {'error': '없는 경로'})
    def do_POST(self) -> None:
        if not self.authorized(origin_required=True):
            self.send(403, {'error': '동일 출처와 CSRF 토큰이 필요합니다.'})
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.send(415, {'error': 'JSON만 허용됩니다.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 100_000 or self.headers.get('Transfer-Encoding'):
                self.send(413, {'error': '요청이 너무 크거나 길이가 없습니다.'})
                return
            data = strict_json(self.rfile.read(length).decode('utf-8'))
            if not isinstance(data, dict):
                raise InputError('요청 형식이 올바르지 않습니다.')
            if self.path == '/api/shutdown':
                if data:
                    raise InputError('종료 요청 형식이 올바르지 않습니다.')
                self.server.jobs.close()
                self.send(200, {'status': 'stopping'})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if re.fullmatch(r'/api/jobs/[A-Za-z0-9_-]{24}/cancel', self.path):
                result = self.server.jobs.cancel(self.path.split('/')[3])
                self.send(200 if result else 404, result or {'error': '작업이 없습니다.'})
                return
            if self.path == '/api/jobs':
                allowed = {'action', 'text', 'candidate', 'mode', 'backend', 'model', 'allow_model'}
                if set(data) - allowed or not isinstance(data.get('text'), str):
                    raise InputError('요청 형식이 올바르지 않습니다.')
                checked_text(data['text'])
                action = data.get('action')
                if action == 'rewrite':
                    if data.get('backend') not in {'codex', 'claude'} or (data.get('mode') != 'preserve' and data.get('allow_model') is not True):
                        raise InputError('모델을 선택하고 원문 전송에 동의하세요.')
                    task = partial(rewrite_job, data)
                elif action == 'style':
                    if data.get('backend') not in {'codex', 'claude'} or data.get('allow_model') is not True:
                        raise InputError('모델을 선택하고 분석할 글의 전송에 동의하세요.')
                    if data.get('candidate') is not None and not isinstance(data['candidate'], str):
                        raise InputError('수정본은 문자열이어야 합니다.')
                    if data.get('candidate'):
                        checked_text(data['candidate'])
                    task = partial(style_job, data)
                else:
                    raise InputError('허용하지 않는 작업입니다.')
                self.send(202, self.server.jobs.start(task))
                return
            if self.path != '/api/process':
                self.send(404, {'error': '없는 경로'})
                return
            allowed = {'action', 'text', 'mode', 'backend', 'model'}
            if set(data) - allowed or not isinstance(data.get('text'), str):
                raise InputError('요청 형식이 올바르지 않습니다.')
            if not self.server.processing.acquire(blocking=False):
                raise BusyError('다른 작업이 진행 중입니다.')
            try:
                if data.get('action') == 'analyze':
                    result = analyze(data['text'])
                elif data.get('action') == 'rewrite':
                    if data.get('backend', 'builtin') != 'builtin' and data.get('mode') != 'preserve':
                        raise InputError('지원하지 않는 엔진입니다.')
                    result = apply_plan(data['text'], make_plan(data['text'], mode=data.get('mode', 'personal')))
                    result.update(comparison(data['text'], result))
                else:
                    raise InputError('허용하지 않는 작업입니다.')
                self.send(200, result)
            finally:
                self.server.processing.release()
        except BusyError as exc:
            self.send(429, {'error': str(exc)})
        except (InputError, ProviderError, UnicodeError, ValueError) as exc:
            self.send(400, {'error': str(exc)})
        except (TimeoutError, OSError):
            self.send(408, {'error': '요청 시간이 초과되었습니다.'})

def serve(port: int = 0, open_browser: bool = False) -> None:
    if type(port) is not int or not (port == 0 or 1024 <= port <= 65535):
        raise InputError('포트는 0(자동) 또는 1024~65535 범위여야 합니다.')
    with Server(port) as server:
        print(f'ClearWrite: {server.origin}\n이 컴퓨터에서만 접근됩니다. 종료: Ctrl+C 또는 화면의 앱 종료', flush=True)
        if open_browser:
            webbrowser.open(server.origin)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

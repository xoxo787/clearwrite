"""Consent-gated, bounded adapters for the user's installed model CLIs.

Authentication stays with each CLI. No auth files, shell interpolation, model
downloads, permission bypasses, or current-conversation resumption are used.
"""
from __future__ import annotations

import functools
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .core import InputError, prepare, proposal_schema, resolve_proposals
from .io import strict_json
from .providers import ProviderError
from .style import INTERPRETATION, prepare_style, response_schema, validate_style

MAX_OUTPUT = 2_000_000
BACKENDS = ('codex', 'claude')
CODEX_DISABLED_FEATURES = ('shell_tool', 'unified_exec', 'apps', 'plugins', 'remote_plugin', 'hooks',
                           'memories', 'skill_search', 'multi_agent', 'browser_use', 'computer_use',
                           'image_generation', 'view_image', 'code_mode', 'code_mode_host',
                           'in_app_browser', 'workspace_dependencies')


class ModelCancelled(ProviderError):
    """The user cancelled this request."""


@dataclass(frozen=True)
class CLIInfo:
    backend: str
    argv: tuple[str, ...]
    version: str = ''
    supported: bool = True


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    # This integration uses the CLI's own login, not an inherited billable API key.
    for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
                'CLAUDE_CODE_OAUTH_TOKEN', 'PANGRAM_API_KEY'):
        env.pop(key, None)
    env.update(PYTHONIOENCODING='utf-8', NO_COLOR='1', TERM='dumb')
    return env


def _native_candidates(backend: str) -> list[tuple[str, ...]]:
    explicit = os.environ.get('CLEARWRITE_' + backend.upper() + '_PATH')
    candidates: list[tuple[str, ...]] = []
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_absolute() and path.is_file() and path.suffix.lower() not in {'.cmd', '.bat', '.ps1'}:
            candidates.append((str(path),))
        return candidates
    found = shutil.which(backend + '.exe') if os.name == 'nt' else shutil.which(backend)
    if found:
        candidates.append((found,))
    wrapper = shutil.which(backend)
    directories = [Path(wrapper).parent] if wrapper else []
    if os.name == 'nt' and os.environ.get('APPDATA'):
        directories.insert(0, Path(os.environ['APPDATA']) / 'npm')
    for directory in directories if os.name == 'nt' else []:
        if backend == 'codex':
            arch = 'arm64' if platform.machine().lower() in {'arm64', 'aarch64'} else 'x64'
            triple = 'aarch64' if arch == 'arm64' else 'x86_64'
            package = directory / 'node_modules' / '@openai' / 'codex'
            for vendor in (package / 'node_modules' / '@openai' / ('codex-win32-' + arch) / 'vendor',
                           package / 'vendor'):
                executable = vendor / (triple + '-pc-windows-msvc') / 'bin' / 'codex.exe'
                if executable.is_file():
                    candidates.insert(0, (str(executable),))
        else:
            script = directory / 'node_modules' / '@anthropic-ai' / 'claude-code' / 'cli.js'
            node = shutil.which('node.exe')
            if node and script.is_file():
                candidates.append((node, str(script)))
    if backend == 'claude' and os.name == 'nt':
        executable = Path.home() / '.local' / 'bin' / 'claude.exe'
        if executable.is_file():
            candidates.append((str(executable),))
    return list(dict.fromkeys(candidates))


@functools.lru_cache(maxsize=2)
def cli_info(backend: str) -> CLIInfo | None:
    if backend not in BACKENDS:
        raise InputError('허용하지 않는 모델 연결입니다.')
    candidates = _native_candidates(backend)
    if not candidates:
        return None
    argv = candidates[0]
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
    try:
        help_args = [*argv, 'exec', '--help'] if backend == 'codex' else [*argv, '--help']
        help_result = subprocess.run(help_args, capture_output=True, timeout=8, env=_environment(),
                                     creationflags=flags, check=False)
        help_text = help_result.stdout[:200_000].decode('utf-8', errors='replace')
        version_result = subprocess.run([*argv, '--version'], capture_output=True, timeout=8,
                                        env=_environment(), creationflags=flags, check=False)
        version = version_result.stdout[:150].decode('utf-8', errors='replace').strip()
        required = ('--ignore-user-config', '--output-schema', '--ephemeral') if backend == 'codex' else (
            '--tools', '--json-schema', '--no-session-persistence', '--strict-mcp-config',
            '--setting-sources', '--disable-slash-commands')
        supported = help_result.returncode == 0 and all(x in help_text for x in required)
        if supported and backend == 'codex':
            features = subprocess.run([*argv, 'features', 'list'], capture_output=True, timeout=8,
                                      env=_environment(), creationflags=flags, check=False)
            names = {line.split()[0] for line in features.stdout.decode('utf-8', errors='replace').splitlines() if line.split()}
            supported = features.returncode == 0 and set(CODEX_DISABLED_FEATURES) <= names
        return CLIInfo(backend, argv, version, supported)
    except (OSError, subprocess.TimeoutExpired):
        return CLIInfo(backend, argv, '', False)


def backend_status() -> dict:
    entries = []
    for name in BACKENDS:
        info = cli_info(name)
        entries.append({'id': name, 'name': 'Codex' if name == 'codex' else 'Claude Code',
                        'installed': info is not None, 'ready': bool(info and info.supported),
                        'version': info.version if info else None,
                        'login': 'not_checked',
                        'message': ('CLI 확인됨 · 로그인은 실행할 때 확인합니다.' if info and info.supported else
                                    ('지원되는 CLI 버전으로 업데이트하세요.' if info else 'CLI 설치가 필요합니다.'))})
    return {'backends': entries, 'model_requests': 0,
            'credentials_read_by_clearwrite': False,
            'default_backend': next((e['id'] for e in entries if e['ready']), 'codex')}


def _command(info: CLIInfo, directory: Path, model: str | None, schema: dict | None = None) -> list[str]:
    if info.backend == 'codex':
        argv = [*info.argv, 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                '--sandbox', 'read-only', '--color', 'never', '--json',
                '--output-schema', str(directory / 'schema.json'), '-C', str(directory)]
        # These are invocation-local restrictions, not changes to user settings.
        for feature in CODEX_DISABLED_FEATURES:
            argv += ['--disable', feature]
        for setting in ('mcp_servers={}', 'web_search="disabled"', 'project_doc_max_bytes=0',
                        'approval_policy="never"'):
            argv += ['-c', setting]
    else:
        # --bare accepts only ANTHROPIC_API_KEY, which _environment() removes, so
        # subscription logins failed. An empty setting source list skips user
        # hooks, plugins and CLAUDE.md instead. A '*' deny rule would also block
        # the StructuredOutput tool that --json-schema relies on.
        argv = [*info.argv, '--print', '--output-format', 'json',
                '--json-schema', json.dumps(schema or proposal_schema(), ensure_ascii=True, separators=(',', ':')),
                '--tools', '', '--setting-sources', '', '--disable-slash-commands', '--strict-mcp-config',
                '--mcp-config', '{"mcpServers":{}}', '--no-session-persistence']
    if model:
        argv += ['--model', model]
    if info.backend == 'codex':
        argv += ['-']
    return argv


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == 'nt':
        taskkill = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32' / 'taskkill.exe'
        try:
            subprocess.run([str(taskkill), '/PID', str(process.pid), '/T', '/F'], capture_output=True,
                           timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=False)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _run(info: CLIInfo, prompt: str, directory: Path, model: str | None,
         timeout: float, cancel: threading.Event, schema: dict | None = None) -> dict:
    argv = _command(info, directory, model, schema)
    (directory / 'schema.json').write_text(json.dumps(schema or proposal_schema()), encoding='utf-8')
    flags = (getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)) if os.name == 'nt' else 0
    try:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=directory, env=_environment(), creationflags=flags,
                                   start_new_session=os.name != 'nt')
    except OSError:
        raise ProviderError('모델 CLI를 시작하지 못했습니다. 설치 상태를 확인하세요.') from None
    output = bytearray()
    oversized, pipe_error = threading.Event(), threading.Event()

    def read_pipe(pipe, *, keep: bool) -> None:
        total = 0
        try:
            while chunk := pipe.read(65536):
                total += len(chunk)
                if keep:
                    output.extend(chunk[:max(0, MAX_OUTPUT - len(output))])
                if total > MAX_OUTPUT:
                    oversized.set()
        except OSError:
            pipe_error.set()
        finally:
            pipe.close()

    def write_prompt() -> None:
        try:
            process.stdin.write(prompt.encode('utf-8'))
            process.stdin.flush()
        except (BrokenPipeError, OSError):
            pipe_error.set()
        finally:
            try:
                process.stdin.close()
            except OSError:
                pipe_error.set()

    # Pipes are read concurrently so a full stdout/stderr pipe cannot deadlock
    # prompt delivery. Only bounded stdout is retained; stderr is discarded.
    workers = [threading.Thread(target=read_pipe, args=(process.stdout,), kwargs={'keep': True}, daemon=True),
               threading.Thread(target=read_pipe, args=(process.stderr,), kwargs={'keep': False}, daemon=True),
               threading.Thread(target=write_prompt, daemon=True)]
    try:
        for worker in workers:
            worker.start()
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if cancel.wait(.05):
                raise ModelCancelled('요청을 취소했습니다. 이미 처리된 모델 사용량은 남을 수 있습니다.')
            if time.monotonic() >= deadline:
                raise ProviderError('모델 응답 시간이 초과되었습니다. 원문은 변경하지 않았습니다.')
            if oversized.is_set():
                raise ProviderError('모델 CLI 응답이 허용 크기를 넘었습니다.')
        for worker in workers:
            worker.join(timeout=3)
        if cancel.is_set():
            raise ModelCancelled('요청을 취소했습니다.')
        if oversized.is_set():
            raise ProviderError('모델 CLI 응답이 허용 크기를 넘었습니다.')
        if process.returncode:
            raise ProviderError('모델 요청에 실패했습니다. 해당 CLI의 로그인·사용량·지원 모델을 확인하세요.')
        if pipe_error.is_set() or any(worker.is_alive() for worker in workers):
            raise ProviderError('모델 CLI 통신을 완료하지 못했습니다. 원문은 유지합니다.')
        raw = output.decode('utf-8-sig')
        if info.backend == 'claude':
            data = strict_json(raw)
            if not isinstance(data, dict) or data.get('is_error'):
                raise InputError('모델 요청 실패')
            data = data.get('structured_output') or strict_json(data.get('result', ''))
        else:
            # Codex --json emits JSONL; the final agent message contains the
            # schema-constrained object. No result file is requested.
            final_message = None
            completed = False
            for line in raw.splitlines():
                if not line.strip():
                    continue
                event = strict_json(line)
                if not isinstance(event, dict):
                    raise InputError('잘못된 모델 이벤트')
                if event.get('type') in {'error', 'turn.failed'}:
                    raise InputError('모델 요청 실패')
                item = event.get('item')
                if event.get('type') == 'item.completed' and isinstance(item, dict) and item.get('type') == 'agent_message':
                    final_message = item.get('text')
                if event.get('type') == 'turn.completed':
                    completed = True
            if not completed or not isinstance(final_message, str):
                raise InputError('모델의 최종 응답이 없습니다.')
            data = strict_json(final_message)
        if not isinstance(data, dict):
            raise InputError('객체가 아닌 결과')
        return data
    except (InputError, UnicodeError, OSError):
        raise ProviderError('모델 응답 형식이 올바르지 않습니다. 원문은 유지합니다.') from None
    finally:
        _terminate(process)
        for worker in workers:
            if worker.ident is not None:
                worker.join(timeout=3)
        output.clear()


def model_plan(text: str, *, backend: str, allow_model: bool = False, model: str | None = None,
               mode: str = 'personal', terms: tuple[str, ...] = (), voice: str = '', timeout: float = 180,
               cancel: threading.Event | None = None,
               runner: Callable | None = None, persona: str | None = None) -> dict:
    if backend not in BACKENDS:
        raise InputError('Codex 또는 Claude Code를 선택하세요.')
    if allow_model is not True:
        raise InputError('선택한 모델 서비스로 원문을 전송하는 데 동의해야 합니다.')
    if model is not None and (not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,120}', model)):
        raise InputError('모델 이름이 유효하지 않습니다.')
    if type(timeout) not in (int, float) or not 1 <= timeout <= 300:
        raise InputError('모델 제한 시간은 1~300초여야 합니다.')
    task = prepare(text, mode=mode, terms=terms, voice=voice, persona=persona)
    if mode == 'preserve':
        return {'schema_version': '1.0', 'source_sha256': task['source_sha256'], 'edits': []}
    info = cli_info(backend)
    if not info or not info.supported:
        raise ProviderError(('Codex' if backend == 'codex' else 'Claude Code') + ' CLI가 없거나 지원 버전이 아닙니다.')
    task['output_schema'] = proposal_schema()
    task['instruction'] += ('\n오프셋 없이 original/replacement/reason/rule을 작성한다. '
                            '도구, 파일 조회, 브라우저, 외부 검색은 사용하지 않는다. 제공된 글만 편집한다. '
                            '긴 문장을 짧은 표어로 요약하지 않는다. 실제 변경할 최소 구간을 제안한다.')
    prompt = json.dumps(task, ensure_ascii=False, allow_nan=False)
    cancellation = cancel or threading.Event()
    if cancellation.is_set():
        raise ModelCancelled('요청을 취소했습니다.')
    with tempfile.TemporaryDirectory(prefix='clearwrite-model-') as folder:
        proposal = (runner or _run)(info, prompt, Path(folder), model, timeout, cancellation)
    return resolve_proposals(text, proposal)


def model_style(text: str, *, backend: str, candidate: str | None = None,
                allow_model: bool = False, model: str | None = None, timeout: float = 180,
                cancel: threading.Event | None = None, runner: Callable | None = None) -> dict:
    if backend not in BACKENDS:
        raise InputError('Codex 또는 Claude Code를 선택하세요.')
    if allow_model is not True:
        raise InputError('선택한 모델 서비스로 분석할 글을 전송하는 데 동의해야 합니다.')
    if model is not None and (not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,120}', model)):
        raise InputError('모델 이름이 유효하지 않습니다.')
    if type(timeout) not in (int, float) or not 1 <= timeout <= 300:
        raise InputError('모델 제한 시간은 1~300초여야 합니다.')
    identical = candidate == text
    effective_candidate = None if identical else candidate
    task = prepare_style(text, effective_candidate)
    cancellation = cancel or threading.Event()
    if cancellation.is_set():
        raise ModelCancelled('요청을 취소했습니다.')
    info = cli_info(backend)
    if not info or not info.supported:
        raise ProviderError(('Codex' if backend == 'codex' else 'Claude Code') + ' CLI가 없거나 지원 버전이 아닙니다.')
    with tempfile.TemporaryDirectory(prefix='clearwrite-style-') as folder:
        proposal = (runner or _run)(info, json.dumps(task, ensure_ascii=False, allow_nan=False),
                                   Path(folder), model, timeout, cancellation, response_schema())
    if cancellation.is_set():
        raise ModelCancelled('요청을 취소했습니다.')
    assessments = validate_style(proposal, text, effective_candidate)
    if identical:
        assessments['after'] = assessments['before']
    return {**assessments, 'status': 'completed', 'backend': backend, 'model': model or 'cli_default',
            'cli_version': info.version, 'assessed_at_utc': datetime.now(timezone.utc).isoformat(),
            'source_sha256': task['source_sha256'],
            'candidate_sha256': task['source_sha256'] if identical else task['candidate_sha256'],
            'reused_identical_text': identical, 'interpretation': INTERPRETATION,
            'calibrated': False, 'authorship': 'undetermined', 'cli_runs': 1}

"""Desktop lifecycle: automatic ports, one instance, browser launch, clean stop."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.request
import webbrowser

from . import __version__
from .core import InputError
from .providers import NoRedirect, ProviderError
from .ui import Server


def default_state_directory() -> Path:
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'ClearWrite' / 'runtime'
    return Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local' / 'state')) / 'clearwrite'


class InstanceLock:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.file = (directory / 'instance.lock').open('a+b')
        if os.fstat(self.file.fileno()).st_size == 0:
            self.file.write(b'0')
            self.file.flush()
        self.file.seek(0)
        self.acquired = False
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.acquired = True
        except OSError:
            pass

    def close(self) -> None:
        if self.acquired:
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()


def _request(origin: str, path: str, body: dict | None = None, token: str | None = None) -> dict | str:
    if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{4,5}', origin):
        raise InputError('앱 실행 주소가 올바르지 않습니다.')
    headers = {'Origin': origin}
    if token:
        headers['X-ClearWrite-Token'] = token
    data = None if body is None else json.dumps(body).encode()
    if data is not None:
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(origin + path, data=data, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=12) as response:
        raw = response.read(200_000).decode('utf-8')
    if path == '/':
        return raw
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise InputError('앱 응답 형식이 올바르지 않습니다.')
    return value


def existing(directory: Path) -> dict | None:
    path = directory / 'instance.json'
    try:
        if not path.is_file() or path.stat().st_size > 4096:
            return None
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict) or not isinstance(value.get('url'), str):
            return None
        health = _request(value['url'], '/api/health')
        return value if health.get('app') == 'ClearWrite' and health.get('instance_id') == value.get('instance_id') else None
    except (OSError, ValueError, ProviderError):
        return None


def shutdown(directory: Path) -> bool:
    info = existing(directory)
    if not info:
        return False
    page = _request(info['url'], '/')
    match = re.search(r'name="clearwrite-token" content="([A-Za-z0-9_-]+)"', page)
    if not match:
        raise InputError('앱 종료 정보를 확인하지 못했습니다.')
    return _request(info['url'], '/api/shutdown', {}, match.group(1)).get('status') == 'stopping'


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='backslashreplace')
            except (OSError, ValueError):
                pass
    parser = argparse.ArgumentParser(description='ClearWrite desktop editor')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--state-dir', type=Path, default=default_state_directory())
    parser.add_argument('--shutdown', action='store_true')
    args = parser.parse_args(argv)
    directory = args.state_dir.expanduser().absolute()
    lock = None
    log = None
    info = None
    old_stdout, old_stderr = sys.stdout, sys.stderr
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if sys.stdout is None or sys.stderr is None:
            log = (directory / 'startup.log').open('a', encoding='utf-8')
            if sys.stdout is None:
                sys.stdout = log
            if sys.stderr is None:
                sys.stderr = log
        if type(args.port) is not int or not (args.port == 0 or 1024 <= args.port <= 65535):
            raise InputError('포트는 0 또는 1024~65535여야 합니다.')
        if args.shutdown:
            return 0 if shutdown(directory) else 3
        lock = InstanceLock(directory)
        if not lock.acquired:
            info = existing(directory)
            if info:
                if not args.no_open:
                    webbrowser.open(info['url'])
                print(json.dumps({'status': 'already_running', 'url': info['url']}), flush=True)
                return 0
            raise InputError('다른 ClearWrite가 시작 중입니다. 잠시 후 다시 실행하세요.')
        with Server(args.port) as server:
            info = {'pid': os.getpid(), 'url': server.origin, 'instance_id': server.instance_id, 'version': __version__}
            staged = directory / 'instance.tmp'
            staged.write_text(json.dumps(info), encoding='utf-8')
            os.replace(staged, directory / 'instance.json')
            print(json.dumps({'status': 'running', 'url': server.origin, 'version': __version__}), flush=True)
            if not args.no_open:
                webbrowser.open(server.origin)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
        return 0
    except (InputError, OSError, ProviderError, ValueError):
        print('ClearWrite를 시작하지 못했습니다. 실행 중인 앱과 포트, 설치 파일을 확인하세요.', file=sys.stderr, flush=True)
        return 3
    finally:
        if lock:
            if lock.acquired and info:
                metadata = directory / 'instance.json'
                try:
                    if metadata.is_file() and json.loads(metadata.read_text(encoding='utf-8')).get('pid') == os.getpid():
                        metadata.unlink()
                except (OSError, ValueError):
                    pass
            lock.close()
        if log:
            sys.stdout, sys.stderr = old_stdout, old_stderr
            log.close()


if __name__ == '__main__':
    raise SystemExit(main())

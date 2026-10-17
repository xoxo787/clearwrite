"""Opt-in loopback model adapter, using only Python's standard library.

Ollama: fixed IPv4 loopback, no proxy/redirect, no tools or model pulls.
Transport can be injected for offline contract tests. Mocks are not live tests.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable

from .core import InputError, prepare, proposal_schema, resolve_proposals
from .io import strict_json

MAX_RESPONSE = 1_500_000


class ProviderError(RuntimeError):
    """Sanitized provider error. Never include request bodies, keys or server text."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        raise ProviderError("서버 리디렉션을 거부했습니다.")


def request_json(method: str, url: str, headers: dict[str, str], body: Any,
                 timeout: float) -> dict[str, Any]:
    if not 0 < timeout <= 300:
        raise InputError("네트워크 타임아웃이 유효하지 않습니다.")
    # URL is constructed by adapters, never taken from source prose or model output.
    data = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ProviderError("서버 응답이 허용 크기를 넘었습니다.")
        result = strict_json(raw.decode("utf-8"))
        if not isinstance(result, dict):
            raise ProviderError("서버 응답이 JSON 객체가 아닙니다.")
        return result
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"서버가 HTTP {exc.code} 오류를 반환했습니다. 요청 내용은 기록하지 않았습니다.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProviderError("서버에 연결하지 못했거나 응답 시간이 초과되었습니다.") from None
    except (UnicodeError, InputError):
        raise ProviderError("서버가 유효한 UTF-8 JSON을 반환하지 않았습니다.") from None


Transport = Callable[[str, str, dict[str, str], Any, float], dict[str, Any]]


def ollama_plan(text: str, *, model: str, mode: str = "personal", terms: tuple[str, ...] = (),
                voice: str = "", port: int = 11434, timeout: float = 120,
                transport: Transport = request_json) -> dict[str, Any]:
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,120}", model):
        raise InputError("Ollama 모델 이름이 유효하지 않습니다.")
    if "://" in model or any(part in {"..", "."} for part in model.split("/")):
        raise InputError("모델 이름에 상대 경로를 사용할 수 없습니다.")
    if "cloud" in model.lower():
        raise InputError("이 어댑터는 cloud 모델을 허용하지 않습니다. 로컬 모델을 선택하세요.")
    if type(port) is not int or not 1024 <= port <= 65535:
        raise InputError("Ollama 포트는 1024~65535 범위여야 합니다.")
    task = prepare(text, mode=mode, terms=terms, voice=voice)
    instruction = task.pop("instruction")
    task.pop("output_schema")
    schema = proposal_schema()
    instruction += "\n이번 응답은 오프셋 없는 제안 형식을 사용한다. start/end는 쓰지 않는다. original은 원문에 정확히 한 번 나타나는 구간이어야 한다."
    response = transport("POST", f"http://127.0.0.1:{port}/api/chat",
                         {"Content-Type": "application/json"},
                         {"model": model, "stream": False, "format": schema,
                          "messages": [{"role": "system", "content": instruction},
                                       {"role": "user", "content": json.dumps(task, ensure_ascii=False)}],
                          "options": {"temperature": 0}}, timeout)
    message = response.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ProviderError("Ollama 응답에 편집 계획이 없습니다.")
    try:
        plan = strict_json(message["content"])
    except InputError:
        raise ProviderError("모델이 JSON 계획을 반환하지 않았습니다. 원문은 수정하지 않았습니다.") from None
    if not isinstance(plan, dict):
        raise ProviderError("모델이 올바른 편집 계획을 반환하지 않았습니다.")
    return resolve_proposals(text, plan)


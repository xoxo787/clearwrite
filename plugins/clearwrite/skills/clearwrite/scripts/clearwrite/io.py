"""UTF-8 I/O with bounded input, no silent clobber and no secret logging."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from .core import InputError, MAX_CHARS, checked_text

MAX_JSON_BYTES = 2_000_000


def read_text(path: str, *, max_chars: int = MAX_CHARS) -> str:
    if path == "-":
        # TextIO.read(size) bounds decoded characters (also on Windows).
        text = sys.stdin.read(max_chars + 1)
    else:
        p = Path(path)
        if not p.is_file():
            raise InputError(f"입력 파일이 없습니다: {p}")
        if p.stat().st_size > max_chars * 4 + 4:
            raise InputError("입력 파일이 너무 큽니다.")
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            text = f.read(max_chars + 1)
    if len(text) > max_chars:
        raise InputError(f"입력은 {max_chars:,}자 이하여야 합니다.")
    return checked_text(text)


def strict_json(text: str) -> Any:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for k, v in pairs:
            if k in obj:
                raise InputError(f"중복 JSON 키: {k}")
            obj[k] = v
        return obj
    def no_constant(value: str) -> None:
        raise InputError("JSON에는 NaN/Infinity를 사용할 수 없습니다.")
    if len(text.encode("utf-8")) > MAX_JSON_BYTES:
        raise InputError("JSON 응답이 너무 큽니다.")
    try:
        return json.loads(text, object_pairs_hook=no_duplicates, parse_constant=no_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise InputError("올바른 JSON이 아닙니다.") from exc


def read_json(path: str) -> Any:
    p = Path(path)
    if not p.is_file() or p.stat().st_size > MAX_JSON_BYTES:
        raise InputError("JSON 파일이 없거나 너무 큽니다.")
    return strict_json(p.read_text(encoding="utf-8-sig"))


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def ensure_destination(path: str, *, force: bool = False, inputs: tuple[str, ...] = ()) -> Path:
    p = Path(path).expanduser().absolute()
    if p.is_symlink():
        raise InputError("심볼릭 링크 파일을 출력 대상으로 사용할 수 없습니다.")
    if any(x != "-" and p.resolve() == Path(x).expanduser().resolve() for x in inputs):
        raise InputError("입력 파일은 덮어쓰지 않습니다. 다른 출력 경로를 사용하세요.")
    if p.exists() and not force:
        raise InputError(f"출력 파일이 이미 있습니다: {p.name} (--force로 명시적 교체)")
    if not p.parent.is_dir():
        raise InputError("출력 폴더가 없습니다. 먼저 폴더를 만드세요.")
    return p


def write_text(path: str, text: str, *, force: bool = False, inputs: tuple[str, ...] = ()) -> None:
    p = ensure_destination(path, force=force, inputs=inputs)
    # For new files use exclusive creation, preventing check/use races.
    if not force:
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return
    # Atomic replacement does not follow a target symlink introduced by a race.
    fd, temporary = tempfile.mkstemp(prefix=".clearwrite-", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(temporary, p)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

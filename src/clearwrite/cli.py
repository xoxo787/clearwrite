"""ClearWrite CLI. No API key, account, model or installation needed for builtin mode."""
from __future__ import annotations

import argparse
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .core import (InputError, MODES, DEFAULT_MIN_RETENTION, analyze, apply_plan, make_plan, prepare,
                   proposal_schema, resolve_proposals, verify)
from .io import dumps, ensure_destination, read_json, read_text, write_text
from .personas import BUILTIN_PERSONAS, PERSONAS, edit_budget, get_persona, resolve_style
from .styles import KEEP, STYLES, conformance
from .providers import ProviderError, ollama_plan


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clearwrite", description="맑은글: 한국어·영어 최소 윤문 및 문체 분석")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("analyze", "rewrite", "prepare", "plan", "apply", "verify", "detect"):
        c = sub.add_parser(name)
        c.add_argument("input", help="UTF-8 텍스트/Markdown 파일. - 는 표준입력")
        c.add_argument("-o", "--output", help="텍스트 또는 JSON 출력 파일 (명령에 따라 다름)")
        c.add_argument("--force", action="store_true", help="기존 출력만 교체. 입력 파일은 교체 불가")
        c.add_argument("--term", action="append", default=[], help="보호할 고유명사/용어, 여러 번 지정 가능")
        if name in {"rewrite", "plan", "prepare"}:
            c.add_argument("--mode", choices=sorted(MODES), default="personal")
        if name in {"rewrite", "prepare"}:
            c.add_argument("--voice", help="문체 참고 UTF-8 파일, 최대 3,000자")
        if name in {"rewrite", "apply", "verify"}:
            c.add_argument("--min-retention", type=float, default=DEFAULT_MIN_RETENTION,
                           help="정보 압축 방지용 최소 분량 비율(기본 0.85, 0이면 해제). 짧은 글은 완화 적용")
        if name in {"rewrite", "prepare", "apply", "verify"}:
            c.add_argument("--persona", choices=list(PERSONAS), default=None,
                           help="편집자 페르소나: 말투와 개입 강도. 기본 editor(담백한 편집자)")
            c.add_argument("--style", choices=list(STYLES), default=None,
                           help="문법 스타일(종결어미). 비우면 페르소나 기본값: formal 합니다체, friendly 해요체, 나머지 keep")
        if name in {"rewrite", "apply"}:
            c.add_argument("--report", help="전후 점수·수정 내역·보존 검사를 담는 JSON. 원문도 포함됨")
            c.add_argument("--max-change", type=float, default=None, help="비우면 페르소나 기본값(editor 0.35)")
            c.add_argument("--policy", choices=["atomic", "safe-subset"], default=None,
                           help="비우면 페르소나 기본값(editor atomic)")
        if name == "rewrite":
            c.add_argument("--backend", choices=["builtin", "codex", "claude", "ollama"], default="builtin")
            c.add_argument("--allow-model", action="store_true", help="선택한 Codex/Claude 모델 서비스로 원문 전송 동의")
            c.add_argument("--model", help="모델 이름. Codex/Claude에서 비우면 CLI 기본값")
            c.add_argument("--ollama-port", type=int, default=11434)
            c.add_argument("--timeout", type=float, default=120)
        if name == "prepare":
            c.add_argument("--proposals", action="store_true", help="문자 오프셋 대신 유일한 원문 구간으로 제안")
        if name == "apply":
            group = c.add_mutually_exclusive_group(required=True)
            group.add_argument("--plan", help="오프셋 포함 계획 JSON")
            group.add_argument("--proposals", help="오프셋 없는 제안 JSON")
            c.add_argument("--select", help="적용할 제안 번호(1부터). 예: 1,3,4. 비우면 전부")
            c.add_argument("--summary", action="store_true",
                           help="제안별 적용·제외 사유와 (-o 사용 시) 결과 본문을 표준오류에 한 번에 출력")
        if name == "verify":
            c.add_argument("candidate")
            c.add_argument("--max-change", type=float, default=None, help="비우면 페르소나 기본값(editor 0.35)")
        if name == "detect":
            c.add_argument("--provider", choices=["style", "codex", "claude"], default="style")
            c.add_argument("--allow-model", action="store_true", help="선택한 모델로 문체 분석할 글 전송 동의")
            c.add_argument("--candidate", help="함께 분석할 수정본 UTF-8 파일")
            c.add_argument("--model", help="비우면 선택한 CLI 기본 모델")
            c.add_argument("--timeout", type=float, default=90)
    c = sub.add_parser("serve", help="127.0.0.1에서 글 붙여넣기 화면 실행")
    c.add_argument("--port", type=int, default=0, help="0은 사용 가능한 포트 자동 선택")
    c.add_argument("--open", action="store_true", dest="open_browser")
    sub.add_parser("doctor", help="환경 및 가용 기능 확인. 비밀값이나 원문은 출력하지 않음")
    return p


def emit(value: Any, output: str | None, force: bool, inputs: tuple[str, ...]) -> None:
    text = value if isinstance(value, str) else dumps(value)
    if output:
        write_text(output, text, force=force, inputs=inputs)
    else:
        sys.stdout.write(text)
        if text and not text.endswith("\n"):
            sys.stdout.write("\n")


def select_edits(plan: Any, select: str | None) -> tuple[Any, list[int]]:
    """Keep only the chosen 1-based proposal numbers; return the numbers kept, in order."""
    edits = plan.get("edits") if isinstance(plan, dict) else None
    if not isinstance(edits, list):
        return plan, []
    if not select:
        return plan, list(range(1, len(edits) + 1))
    try:
        numbers = [int(x) for x in select.replace(" ", "").split(",") if x]
    except ValueError:
        raise InputError("--select에는 1,3처럼 쉼표로 구분한 번호를 쓰세요.") from None
    if not numbers or len(set(numbers)) != len(numbers) or any(n < 1 or n > len(edits) for n in numbers):
        raise InputError(f"--select 번호는 1~{len(edits)} 사이에서 겹치지 않게 고르세요.")
    numbers.sort()
    return {**plan, "edits": [edits[n - 1] for n in numbers]}, numbers


def summary_text(result: dict[str, Any], numbers: list[int], plan_edits: list[dict[str, Any]],
                 *, max_change: float, include_text: bool) -> str:
    """Compact per-proposal verdicts so a host model needs no extra file reads."""
    def key(e: dict[str, Any]) -> tuple[str, str]:
        return e.get("original", ""), e.get("replacement", "")
    applied = {key(e) for e in result["applied_edits"]}
    rejected = {key(r["edit"]): r["reason"] for r in result["rejected_edits"]}
    check = result["verification"]
    lines = [f'상태: {result["status"]} · 적용 {len(result["applied_edits"])}곳 · 제외 {len(rejected)}곳 · '
             f'변경률 {check["character_change_rate"]:.1%} (한도 {max_change:.0%})']
    for n, e in zip(numbers, plan_edits):
        k = key(e)
        if k in applied:
            verdict = "적용"
        elif k in rejected:
            verdict = f"제외({rejected[k]})"
        else:
            verdict = "보류(문서 검사 실패)"
        lines.append(f'[{n}] {verdict}  "{e.get("original", "")}" → "{e.get("replacement", "")}"  · {e.get("reason", "")}')
    if check["failures"]:
        lines.append("문서 검사 실패: " + ", ".join(check["failures"]))
    lines.append("AI 작성 확률이 아닙니다. 검사 통과는 의미 보존의 증명이 아닙니다.")
    if include_text:
        lines += ["--- 결과 본문 ---", result["text"]]
    return "\n".join(lines)


def doctor() -> dict[str, Any]:
    return {"version": __version__, "python": platform.python_version(), "platform": platform.system(),
            "builtin_ready": sys.version_info >= (3, 10), "runtime_dependencies": [],
            "codex_on_path": bool(shutil.which("codex")), "ollama_on_path": bool(shutil.which("ollama")),
            "claude_on_path": bool(shutil.which("claude")),
            "live_inference_tested_by_doctor": False, "network_requests": 0}


def main(argv: list[str] | None = None) -> int:
    # Windows pipes use a legacy encoding unless stdin is configured too.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="strict" if stream is sys.stdin else "backslashreplace")
            except (OSError, ValueError):
                pass
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            print(dumps(doctor()), end="")
            return 0
        if args.command == "serve":
            from .ui import serve
            serve(port=args.port, open_browser=args.open_browser)
            return 0
        inputs = (args.input,)
        if args.command == "verify":
            inputs += (args.candidate,)
        if args.command == "apply":
            inputs += (args.plan or args.proposals,)
        if getattr(args, "voice", None):
            inputs += (args.voice,)
        if getattr(args, "candidate", None) and args.command == "detect":
            inputs += (args.candidate,)
        outputs = [x for x in (args.output, getattr(args, "report", None)) if x]
        if len({str(Path(x).expanduser().resolve()) for x in outputs}) != len(outputs):
            raise InputError("결과 파일과 검수 파일에는 서로 다른 경로를 사용하세요.")
        for path in outputs:
            ensure_destination(path, force=args.force, inputs=inputs)
        text = read_text(args.input)
        terms = tuple(args.term)
        if len(terms) > 100 or any(not t or len(t) > 500 for t in terms):
            raise InputError("보호 용어는 각 1~500자, 최대 100개여야 합니다.")
        if args.command in {"analyze", "detect"}:
            value = analyze(text, terms=terms)
            if args.command == "detect" and args.provider in {"codex", "claude"}:
                from .model_cli import model_style
                candidate = read_text(args.candidate) if args.candidate else None
                value = model_style(text, backend=args.provider, candidate=candidate,
                                    allow_model=args.allow_model, model=args.model, timeout=args.timeout)
        elif args.command == "plan":
            value = make_plan(text, mode=args.mode, terms=terms)
        elif args.command == "prepare":
            voice = read_text(args.voice, max_chars=3000) if args.voice else ""
            value = prepare(text, mode=args.mode, terms=terms, voice=voice, persona=args.persona, style=args.style)
            if args.proposals:
                value["instruction"] += "\nstart/end 없이 original/replacement/reason/rule만 작성한다. original은 원문에 정확히 한 번만 나오는 구간이어야 한다."
                value["output_schema"] = proposal_schema()
        elif args.command == "verify":
            selected = get_persona(args.persona)
            max_change, _ = edit_budget(selected, resolve_style(selected, args.style), args.max_change)
            value = verify(text, read_text(args.candidate), terms=terms, max_change=max_change,
                           min_retention=args.min_retention)
        else:
            persona = get_persona(args.persona)
            style = resolve_style(persona, args.style)
            max_change, policy = edit_budget(persona, style, args.max_change, args.policy)
            numbers: list[int] = []
            if args.command == "apply":
                plan, numbers = select_edits(read_json(args.plan or args.proposals), args.select)
                if args.proposals:
                    plan = resolve_proposals(text, plan)
                backend = "supplied-plan"
            else:
                backend = args.backend
                if args.mode == "preserve":
                    plan = make_plan(text, mode="preserve", terms=terms)
                elif args.backend in {"codex", "claude"}:
                    from .model_cli import model_plan
                    voice = read_text(args.voice, max_chars=3000) if args.voice else ""
                    plan = model_plan(text, backend=args.backend, allow_model=args.allow_model, model=args.model,
                                      mode=args.mode, terms=terms, voice=voice, timeout=args.timeout,
                                      persona=persona.id, style=style.id)
                elif args.backend == "ollama":
                    if not args.model:
                        raise InputError("--backend ollama에는 --model이 필요합니다. 모델을 자동 설치하지 않습니다.")
                    voice = read_text(args.voice, max_chars=3000) if args.voice else ""
                    plan = ollama_plan(text, model=args.model, mode=args.mode, terms=terms,
                                       voice=voice, port=args.ollama_port, timeout=args.timeout,
                                       persona=persona.id, style=style.id)
                else:
                    if args.voice:
                        raise InputError("builtin 모드는 문체 예시를 해석하지 않습니다. prepare 또는 Ollama를 사용하세요.")
                    if persona.id not in BUILTIN_PERSONAS or style.id != KEEP:
                        raise InputError("builtin 규칙은 페르소나 말투나 문법 스타일을 적용하지 못합니다. "
                                         "proofreader·editor와 --style keep을 쓰거나 모델 백엔드를 선택하세요.")
                    plan = make_plan(text, mode=args.mode, terms=terms)
            result = apply_plan(text, plan, terms=terms, max_change=max_change,
                                policy=policy, min_retention=args.min_retention)
            result["backend"] = backend
            result["persona"] = persona.public()
            result["edit_budget"] = {"max_change": max_change, "policy": policy}
            result["style"] = style.public()
            if style.id != KEEP:
                result["style_conformance"] = {"before": conformance(text, style.id, terms=terms),
                                               "after": conformance(result["text"], style.id, terms=terms)}
            from .comparison import comparison
            result.update(comparison(text, result))
            if args.report:
                write_text(args.report, dumps(result), force=args.force, inputs=inputs)
            emit(result["text"], args.output, args.force, inputs)
            if getattr(args, "summary", False):
                print(summary_text(result, numbers, plan["edits"], max_change=max_change,
                                   include_text=bool(args.output)), file=sys.stderr)
            else:
                print(f'{result["status"]}: 문체 후보 {result["before"]["ai_style_score"]} → {result["after"]["ai_style_score"]} / '
                      f'수정 {len(result["applied_edits"])}곳. AI 작성 확률이 아닙니다.', file=sys.stderr)
            if result["status"] == "blocked":
                return 2
            return 0
        emit(value, args.output, args.force, inputs)
        if args.command == "verify" and not value["passed"]:
            return 2
        return 0
    except (InputError, ProviderError, OSError, UnicodeError) as exc:
        print(f"clearwrite: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("\n중단했습니다.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

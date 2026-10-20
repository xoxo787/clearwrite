"""Grammar styles: a target Korean sentence-ending register, chosen apart from the persona.

Conformance is a heuristic count of sentence endings. It shows which sentences
still miss the target; it is not a grammar checker and never blocks an edit.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .core import InputError, mask_protected, protected_spans

KEEP = "keep"


@dataclass(frozen=True)
class Style:
    id: str
    label: str
    example: str
    guidance: str

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "example": self.example}


STYLES = {s.id: s for s in (
    Style(KEEP, "원문 종결어미 유지", "", ""),
    Style("hamnida", "합니다체", "~합니다, ~입니까?",
          "합쇼체(~합니다, ~입니다, ~합니까?, ~하십시오)로 통일한다."),
    Style("haeyo", "해요체", "~해요, ~예요, ~할까요?",
          "해요체(~해요, ~예요/이에요, ~할 수 있어요, ~할까요?)로 통일한다. 반말이나 유행어는 쓰지 않는다."),
    Style("handa", "한다체", "~한다, ~이다, ~인가?",
          "신문·논문에 쓰는 한다체(~한다, ~이다, ~했다, ~인가?)로 통일한다. 독자를 부르는 높임 표현은 평서로 바꾼다."),
)}

# Ordered: "니다" must win over the plain "다" of 한다체.
ENDINGS = (
    ("hamnida", re.compile(r"(?:니다|니까|십시오|시다)$")),
    ("haeyo", re.compile(r"(?:요|죠)$")),
    ("handa", re.compile(r"(?:다|가|까|냐|라|자)$")),
)
SENTENCE_RE = re.compile(r"[^.!?。！？\n]+[.!?。！？]+")
TRAILING = "\"'”’)」』]>*_ \t"


def get_style(style_id: Any) -> Style:
    if not isinstance(style_id, str) or style_id not in STYLES:
        raise InputError("알 수 없는 문법 스타일입니다.")
    return STYLES[style_id]


def style_instruction(style: Style) -> str:
    if style.id == KEEP:
        return ""
    return (f"문법 스타일: {style.label}. 한국어 문장의 종결어미를 {style.guidance} "
            "이 통일은 모든 문장에 적용할 수 있고, 필자 말투나 종결어미를 유지하라는 다른 지침보다 우선한다. "
            "인용문, 코드, 제목과 목록 항목의 명사형 끝맺음은 바꾸지 않는다. 영어 문장에는 적용하지 않는다. "
            "어미를 바꿀 때 시제, 부정, 가능성, 높임의 대상과 주장 강도는 그대로 둔다.")


def ending_class(sentence: str) -> str | None:
    """Return the register of a sentence ending, or None when it has no Korean ending."""
    stripped = sentence.rstrip(".!?。！？" + TRAILING)
    if not stripped or not re.match(r"[가-힣]", stripped[-1]):
        return None
    for name, pattern in ENDINGS:
        if pattern.search(stripped):
            return name
    return "other"


def conformance(text: str, style_id: str, *, terms: tuple[str, ...] = ()) -> dict[str, Any] | None:
    style = get_style(style_id)
    if style.id == KEEP:
        return None
    # Quotations and code keep their own register, so they are not counted.
    prose = mask_protected(text, protected_spans(text, terms))
    total, matching, misses = 0, 0, []
    for match in SENTENCE_RE.finditer(prose):
        kind = ending_class(match.group(0))
        if kind is None:
            continue
        total += 1
        if kind == style.id:
            matching += 1
        elif len(misses) < 5:
            misses.append(text[match.start():match.end()].strip()[-40:])
    return {"target": style.id, "label": style.label, "sentences": total, "matching": matching,
            "rate": round(matching / total, 4) if total else None, "mismatched_examples": misses,
            "method": "문장 끝 어미 규칙 판정(휴리스틱). 인용·코드·제목은 제외합니다."}

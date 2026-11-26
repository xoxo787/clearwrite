"""Structural pattern diagnosis for Korean prose. Standard library only.

Counts structure-level habits that often make prose read as machine-written: commas
after connective endings, mechanical enumeration, teaser and wrap-up sentences, stock
emotional phrasing and "not merely A but B" framing. The result tells an editing model
which patterns dominate a text so it fixes those first.

These are heuristic counts, not a score to minimise and not an AI-authorship signal.
Human writers use every one of these forms; a pattern matters only when it repeats.
"""
from __future__ import annotations

import re
import statistics
from typing import Any

from .core import mask_protected, protected_spans

# Commas right after a connective ending: "갔고, 먹었으며, 좋았지만, 보니," ...
ENDING_COMMA_RE = re.compile(r"[가-힣](?:고|며|면서|지만|는데|은데|던데|어서|아서|여서|해서|니까|으니|니|면|도|자|듯이|도록|려고|다가)\s*,")
ENUMERATION_RE = re.compile(r"(?:^|\s)(?:첫째|둘째|셋째|넷째|다섯째)\s*[,，]?")
TEASER_RE = re.compile(r"(?:소개(?:합니다|한다|해 드리겠습니다|하겠습니다)|살펴보(?:겠습니다|자|도록 하겠습니다)|알아보(?:겠습니다|자|도록 하겠습니다)"
                       r"|(?:까요|을까|ㄹ까)\s*\?)")
WRAP_UP_RE = re.compile(r"(?:순간이었(?:습니)?다|실감(?:했|하게 되었|이 났)|깨닫(?:게 되었|았)|되새기|소중함|의미를 (?:되새|더하|가지)"
                        r"|가슴(?:이|을|\s?한구석)|마음 한(?:구석|편)|벅차(?:올|오르)|뭉클|무엇보다 중요|라고 할 수 있(?:습니)?다)")
STOCK_RE = re.compile(r"(?:삼삼오오|눈 녹듯|은은하게|생생하게 와닿|온기|활기를 띠|설렘|설레는 마음|발걸음을 옮기|뜨거운 열기|따뜻한 배움터"
                      r"|고스란히|빼곡|한자리에 모여|두 눈을 의심|청천벽력)")
NOT_ONLY_RE = re.compile(r"(?:단순히\s?[^.!?\n]{1,40}?(?:이|가|을|를|것이|데)?\s?(?:아니라|아닌|넘어|그치지 않고)|그저\s?[^.!?\n]{1,30}?(?:이|가)\s?아니었)")

PATTERNS = {
    "ending_comma": ("연결어미 뒤 쉼표", ENDING_COMMA_RE),
    "enumeration": ("첫째·둘째식 기계적 열거", ENUMERATION_RE),
    "teaser": ("예고·수사 의문 문장", TEASER_RE),
    "wrap_up": ("감상·교훈으로 끝맺는 상투 문장", WRAP_UP_RE),
    "stock_phrase": ("상투적인 묘사 표현", STOCK_RE),
    "not_only": ("'단순히 A가 아니라 B' 틀", NOT_ONLY_RE),
}
# Rough per-sentence rates above which a pattern is reported as dominant. Chosen by hand
# from the development texts; deliberately not fitted to any held-out or detector data.
DOMINANT_RATE = {"ending_comma": .25, "enumeration": .0, "teaser": .0, "wrap_up": .12, "stock_phrase": .12, "not_only": .0}
# A pattern seen once is not a habit: questions and contrasts are often deliberate.
MIN_COUNT = {"ending_comma": 2, "enumeration": 2, "teaser": 2, "wrap_up": 2, "stock_phrase": 2, "not_only": 2}
SENTENCE_RE = re.compile(r"[^.!?。！？\n]+[.!?。！？]*")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_RE.findall(text) if len(s.strip()) > 1]


def _cv(values: list[int]) -> float | None:
    if len(values) < 3 or not statistics.mean(values):
        return None
    return round(statistics.pstdev(values) / statistics.mean(values), 3)


def structure_signals(text: str, *, terms: tuple[str, ...] = ()) -> dict[str, Any]:
    prose = mask_protected(text, protected_spans(text, terms))
    sents = _sentences(prose)
    n = max(1, len(sents))
    patterns: dict[str, Any] = {}
    for key, (label, pattern) in PATTERNS.items():
        hits = list(pattern.finditer(prose))
        if key == "enumeration" and len(hits) < 2:
            hits = []  # One "첫째" alone is not a mechanical list.
        sentences_hit = sum(bool(pattern.search(s)) for s in sents) if hits else 0
        patterns[key] = {"label": label, "count": len(hits), "sentence_rate": round(sentences_hit / n, 3),
                         "examples": [text[m.start():m.end()].strip() for m in hits[:3]]}
    dominant = sorted((k for k, v in patterns.items() if v["count"] >= MIN_COUNT[k] and v["sentence_rate"] > DOMINANT_RATE[k]),
                      key=lambda k: -patterns[k]["sentence_rate"])
    paragraphs = [p for p in re.split(r"\n\s*\n", prose) if p.strip()]
    return {
        "patterns": patterns, "dominant": dominant, "sentences": len(sents),
        "uniformity": {"sentence_length_cv": _cv([len(s) for s in sents]),
                       "paragraph_length_cv": _cv([len(p) for p in paragraphs]),
                       "note": "길이 변동은 참고용이다. 문장 길이를 일부러 들쭉날쭉하게 만들지 않는다."},
        "interpretation": "구조 습관의 개수다. 낮출 점수나 AI 작성 판정이 아니다. 반복될 때만 고칠 후보로 본다.",
    }


def diagnosis_instruction(signals: dict[str, Any]) -> str:
    if not signals["dominant"]:
        return "구조 진단: 두드러지게 반복되는 구조 습관을 찾지 못했다. 억지로 고칠 곳을 만들지 않는다."
    parts = []
    for key in signals["dominant"]:
        p = signals["patterns"][key]
        sample = ", ".join(f"'{x}'" for x in p["examples"][:2])
        parts.append(f"{p['label']} {p['count']}회" + (f"(예: {sample})" if sample else ""))
    return ("구조 진단(엔진 집계, 참고용): 이 글에서 반복되는 습관은 " + "; ".join(parts) + ". "
            "이 습관부터 고치되, 원문에 필요한 정보·장면·대화·조건은 그대로 둔다.")

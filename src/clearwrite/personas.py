"""Editor personas: a register (tone and grammar) plus an intervention budget.

A persona decides how boldly a model edits and which register it writes in.
Every persona still passes the same preservation gates; a stronger persona is
never permission to add facts or change claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import InputError

INTENSITIES = {"light": "가볍게", "medium": "보통", "strong": "적극적으로"}
SHARED_LIMITS = ("어떤 페르소나든 사실·수치·주체·인과·부정·가능성·조건, 필자의 관점과 주장 강도는 바꾸지 않는다. "
                 "페르소나는 말투와 개입 정도만 정한다. 인용문 안의 표현은 바꾸지 않는다.")


@dataclass(frozen=True)
class Persona:
    id: str
    label: str
    intensity: str
    changes_voice: bool
    max_change: float
    policy: str
    summary: str
    guidance: str

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "intensity": self.intensity,
                "intensity_label": INTENSITIES[self.intensity], "changes_voice": self.changes_voice,
                "max_change": self.max_change, "policy": self.policy, "summary": self.summary}


# The editor persona keeps the 0.3 budget (35%, atomic) so existing callers are unchanged.
# Stronger personas propose more edits; safe-subset keeps the passing ones instead of
# discarding the whole plan when a single edit fails a gate.
PERSONAS = {p.id: p for p in (
    Persona("proofreader", "꼼꼼한 교정자", "light", False, .15, "atomic",
            "맞춤법·띄어쓰기·조사·이중 피동처럼 틀리거나 겹친 곳만 고칩니다.",
            "개입 강도: 가볍게. 가장 좁은 구간만 고친다. 맞춤법, 띄어쓰기, 조사와 어미 활용 오류, 이중 피동, 명백히 겹친 표현만 고친다. "
            "어순, 낱말 선택, 문장 길이, 종결어미, 문단 구성은 바꾸지 않는다. 고칠지 애매하면 고치지 않는다. "
            "영어는 철자, 문법, 관사, 수 일치와 'in order to' 같은 명백한 군더더기만 고친다."),
    Persona("editor", "담백한 편집자", "medium", False, .35, "atomic",
            "필자의 말투를 지키며 반복·늘어진 연결·상투적 예고를 다듬습니다.",
            "개입 강도: 보통. 필자의 말투와 종결어미를 유지하면서 반복, 늘어진 연결 표현, 상투적 예고와 과장, "
            "명사 나열을 자연스럽게 다듬는다. 문장 구조는 꼭 필요할 때만 바꾼다."),
    Persona("formal", "격식 있는 보고자", "medium", True, .5, "safe-subset",
            "합니다체로 통일하고 구어·감탄·수사 의문을 보고서 문장으로 바꿉니다.",
            "말투 바꾸기: 격식 있는 보고자. 한국어 종결어미를 합쇼체(~합니다, ~입니다)로 일관되게 바꾼다. "
            "구어 표현, 감탄, 독자에게 묻는 수사 의문문은 평서문으로 바꾼다. 실제로 답을 구하는 질문은 유지한다. "
            "주관적인 수식어는 덜어내되 새 근거를 만들지 않는다. "
            "영어는 격식체로 쓴다: 축약형을 풀고, 수사 의문문과 구어 표현을 중립적인 서술로 바꾼다."),
    Persona("columnist", "칼럼니스트", "strong", False, .5, "safe-subset",
            "필자의 관점은 지키되 문장을 과감히 재구성해 리듬과 흐름을 살립니다.",
            "개입 강도: 적극적으로. 필자의 관점, 어조, 종결어미 체계는 유지하되 문장을 과감히 재구성해 읽는 흐름을 살린다. "
            "같은 서술어와 문형의 반복을 바꾸고, 짧은 문장과 긴 문장을 섞어 리듬을 만든다. "
            "내용 없는 도입·예고·결론 문구와 과장은 덜어내거나 바로 옆 문장에 녹인다. "
            "피동과 명사화는 능동·동사 중심으로 바꾼다. 긴 문장은 나눌 수 있고, 이어진 두 문장은 하나로 합칠 수 있지만 논리 순서와 예시는 지킨다. "
            "영어도 같은 원칙으로 능동태, 다양한 문장 길이, 군더더기 도입 삭제를 적용한다."),
    Persona("plain", "쉬운 말 해설가", "strong", False, .5, "safe-subset",
            "긴 문장을 나누고 어려운 낱말을 쉬운 말로 바꿔 처음 읽는 사람도 따라오게 합니다.",
            "개입 강도: 적극적으로, 쉬운 말. 한 문장에 한 가지 생각만 담도록 긴 문장을 나눈다. "
            "어려운 한자어와 외래어는 같은 뜻의 쉬운 말로 바꾼다. 정확성에 필요한 전문용어는 그대로 두고, 원문에 없는 정의를 지어내지 않는다. "
            "부정과 조건 표현은 형태를 바꾸지 않는다. 종결어미 체계는 원문을 따른다. "
            "영어는 Plain Language 원칙으로 짧은 문장, 흔한 낱말, 능동태를 쓴다."),
    Persona("friendly", "다정한 안내자", "strong", True, .5, "safe-subset",
            "해요체로 바꿔 독자에게 말을 건네듯 부드럽게 씁니다.",
            "말투 바꾸기: 다정한 안내자. 한국어 종결어미를 해요체(~해요, ~예요, ~할 수 있어요)로 일관되게 바꾼다. "
            "독자에게 말을 건네듯 쓰되 반말, 유행어, 이모티콘, 새 감탄사는 넣지 않는다. 딱딱한 한자어는 같은 뜻의 쉬운 말로 바꾼다. "
            "영어는 'you'와 축약형을 쓰는 따뜻한 대화체로 쓰되 속어는 쓰지 않는다."),
)}
DEFAULT_PERSONA = "editor"
# Builtin rules cannot produce a register change, so only budget-only personas apply there.
BUILTIN_PERSONAS = frozenset({"proofreader", "editor"})


def get_persona(persona_id: Any = None) -> Persona:
    if persona_id is None:
        return PERSONAS[DEFAULT_PERSONA]
    if not isinstance(persona_id, str) or persona_id not in PERSONAS:
        raise InputError("알 수 없는 페르소나입니다.")
    return PERSONAS[persona_id]


def persona_instruction(persona: Persona) -> str:
    # The persona is an editing policy, not role-play: the base prompt still forbids invented voices.
    parts = [f"편집자 페르소나: {persona.label}. 페르소나는 편집 방식이며 인물 연기가 아니다.", persona.guidance]
    if persona.intensity == "strong":
        parts.append("이 강도에서는 '최소 편집'보다 페르소나 지침을 우선하되, 정보 보존 규칙은 언제나 그보다 우선한다.")
        # Multi-sentence rewrites trip the local compression gate even when only filler is cut.
        parts.append("여러 문장을 한 편집으로 묶어 통째로 다시 쓰지 않는다. 한 편집은 한 문장을 넘지 않게 나누되, "
                     "두 문장을 하나로 합칠 때만 그 두 문장을 한 편집으로 묶는다. "
                     "군더더기 도입·예고 문구는 그 표현만 지우는 짧은 편집으로 따로 제안한다.")
    if persona.changes_voice:
        parts.append("페르소나가 말투를 바꾸도록 정했으므로 이 범위의 종결어미·낱말 변경은 필자 말투 유지 지침보다 우선하고, "
                     "종결어미 통일은 모든 문장에 적용할 수 있다.")
    parts.append(SHARED_LIMITS)
    return " ".join(parts)


def catalog() -> list[dict[str, Any]]:
    return [p.public() for p in PERSONAS.values()]

# 소개글 윤문과 자체 검수 기록

2026-10-18, Codex에 설치된 ClearWrite 스킬 0.3.1을 `publish` 기준으로 실행했습니다. 이 대화의 모델이 [직전 소개글](original.md)을 바탕으로 수정안을 작성했고, 설치된 Python 엔진이 적용 가능 여부를 검사했습니다. [최종 소개글](edited.md)은 README에 그대로 넣었습니다.

## 점수가 뜻하는 것

아래 수치는 **같은 Codex 대화의 모델이 글을 작성·윤문하고 스스로 평가한 참고 점수**입니다. 독립 모델, 외부 AI 탐지기 또는 사람 독자의 평가가 아닙니다. 상세 모델 식별자는 기록하지 않았습니다. 문체 점수는 반복·상투적 표현·획일적 흐름·추상적 부연을 각각 0~25점으로 평가한 합계입니다.

| 문체 항목 | 원문 | 수정본 |
| --- | ---: | ---: |
| 같은 말·구조의 반복 / 25 | 4 | 3 |
| 상투적인 연결·강조 / 25 | 7 | 7 |
| 획일적인 문장 흐름 / 25 | 3 | 3 |
| 구체성 없는 추상적 부연 / 25 | 5 | 4 |
| 합계 / 100 | **19** | **17** |

자가 평가에서 **19점 → 17점으로 2점 낮아졌습니다.** 제품명 등의 반복과 포괄적인 표현이 조금 줄었다고 평가했습니다. 홍보용 도입과 병렬 목록은 유지돼 두 항목은 그대로입니다. 원문과 수정본 모두 AI가 작성한 문장이며, 이 차이를 AI 생성 확률·작성률·탐지 회피 성능이 줄었다는 뜻으로 해석할 수 없습니다. 독자 이해도나 읽기 피로도도 측정하지 않았습니다.

원문·수정본은 같은 기준으로 한 차례씩 점수를 기록했습니다. 낮은 점수를 얻으려고 수정안을 반복 생성하거나, 탐지기를 호출하거나, 기준을 완화하지 않았습니다. [모델 평가와 정확한 인용](model-style-review.json)을 공개합니다. Python 검증기는 인용이 각 글에 실제로 있는지, 해시와 항목·점수 범위가 맞는지 검사하고 합계를 계산했습니다. 이 검증이 주관적인 점수의 정확성을 독립적으로 확인한 것은 아닙니다. 추가 CLI 모델 요청은 없습니다.

## 실제로 적용된 변경

- 적용한 수정: **9곳**
- 실제 수정 비율: **10.37%**
- 삭제·교체된 원문 글자: 101자
- 추가·대체된 글자: 94자
- 원문 944자 / 수정본 937자. Markdown 서식·링크 문자열·공백·줄바꿈을 포함한 Unicode 코드포인트 기준입니다.
- 계산: `(101 + 94) / (944 + 937) × 100 = 10.3668%`

이는 바뀐 글자의 양입니다. AI 작성 비율이나 가독성 향상률이 아닙니다. 로컬 규칙 기반 문체 후보 점수는 별도로 원문 0.0 → 수정본 0.0이며, 위의 모델 자체 평가와는 다른 지표입니다.

첫 수정안에서는 부정 표현과 가능성 표현을 바꾼 두 제안이 `scope_negation_or_modality_changed`로 차단됐고 전체 적용을 보류했습니다. 해당 표현을 유지하도록 **한 번 수정**한 뒤 최종 9곳이 통과했습니다. [첫 차단 기록](first-pass-report.json), [최종 제안](proposals.json), [최종 엔진 보고서](application-report.json)를 함께 공개합니다. 수정본의 문체 점수는 이 보존 검사와 수정이 끝난 뒤 평가했습니다.

숫자·링크와 부정·가능성 표현의 기계적 보존 검사를 통과했고, 공백 제외 분량은 원문의 98.67%입니다. 이 대화에서 주체·인과·예외도 원문과 대조했습니다. 의미 보존의 독립 증명은 아니며, 보고서의 `semantic_equivalence`는 `not_established`로 유지합니다.

| 원문 | 수정본 | 수정 이유 |
| --- | --- | --- |
| 분명 매끄러운데, 읽다 보면 같은 말이 반복됩니다. | 겉으로는 매끄러워도 같은 말이 되풀이되는 글이 있습니다. | 모든 AI 글에 반복이 있다는 인상을 줄이고, 독자가 겪을 수 있는 구체적인 불편으로 표현했습니다. |
| 설명은 긴데 요점은 잘 잡히지 않고, 조금만 고치면 될 것 같은데 어디부터 손대야 할지 막막합니다. | 설명은 길어도 요점은 잘 잡히지 않고, 조금만 손보면 될 것 같은데 어디부터 고쳐야 할지 막막합니다. | 부정 표현인 잘 잡히지 않고를 유지하면서 연결 표현과 손질 동작을 다듬었습니다. |
| 2026년 ACM 학회에 발표된 소규모 탐색 연구에서는, 주의집중과 정보처리에 어려움이 있는 참여자들이 AI 답변의 지나친 길이와 빽빽한 구성을 이용 장벽으로 꼽았습니다. | 2026년 ACM 학회에 발표된 소규모 탐색 연구에서, 주의집중과 정보처리에 어려움을 겪는 참여자들은 AI 답변의 지나친 길이와 빽빽한 구성을 이용 장벽으로 꼽았습니다. | 연구의 시기·규모·대상·관찰 내용을 유지하면서 조사와 주어의 호응을 다듬었습니다. |
| 독자를 고려한 분량과 구성의 중요성을 시사하는 결과입니다. | 답변의 분량과 구성을 독자에게 맞출 필요가 있음을 시사합니다. | 막연한 중요성 표현을 독자에게 맞춘다는 편집 판단으로 연결했습니다. 연구 결과의 해석은 시사한다는 수준으로 유지했습니다. |
| 원문의 뜻과 말투를 살리면서, 사람이 읽기 편하도록 문장을 다듬는 프로그램입니다. | 원문의 뜻과 말투를 살리며, 사람이 읽기 편하도록 문장을 다듬습니다. | 제품을 다시 정의하는 표현을 덜고 실제로 하는 일을 직접 썼습니다. |
| ClearWrite에서는 수정 결과를 원문과 직접 비교할 수 있습니다. | 다듬은 글은 원문과 직접 비교할 수 있습니다. | 바로 앞에 나온 제품명을 반복하지 않고 비교하는 대상을 분명히 했습니다. |
| 마음에 드는 변화인지 직접 살펴보고 판단하세요. | 바뀐 표현이 내 글에 어울리는지 직접 확인하세요. | 막연한 변화 대신 사용자가 확인할 표현과 판단 기준을 구체적으로 썼습니다. |
| 이번 윤문에서 실제로 바뀐 글자의 비율을 보여줍니다. | 윤문 전후의 글자 차이를 계산해 실제 수정 비율을 보여줍니다. | 수정 비율이 무엇을 바탕으로 계산되는지 기능 설명에 담았습니다. |
| 한국어와 영어를 지원하며, 설치하고 로그인한 **Codex CLI 또는 Claude Code**와 연결해 사용할 수 있습니다. | 한국어와 영어를 지원합니다. 설치와 로그인을 마친 **Codex CLI 또는 Claude Code**에 연결해 사용할 수 있습니다. | 지원 언어와 사용 준비 조건을 두 문장으로 나누되 사용할 수 있다는 가능성 표현을 유지했습니다. |

## 연구 인용의 범위

소개글이 인용한 연구는 Jaeyeon Lee, Seo Yeon Lee, Gyuyeon Jung, Morgan G. Ames의 [Too Long to Read? Restructuring LLM Responses for Users with Attention-Related Challenges](https://doi.org/10.1145/3803784.3816862), ACM Creativity & Cognition 2026 포스터 논문입니다. 자기보고한 인지·정보처리 어려움을 기준으로 모집한 참여자 10명의 탐색적 인터뷰이며, 대조군 없는 정적 예제 평가입니다. 모든 AI 글의 읽기 피로도를 입증하거나 ClearWrite의 효과를 검증한 연구로 소개하지 않습니다.

## 기계적 검사 재현

저장소 루트에서 아래를 실행합니다. 예시 출력 폴더가 이미 있으면 다른 새 이름을 고르세요. 파일을 덮어쓰거나 모델을 호출하지 않습니다.

```sh
python -c "from pathlib import Path; Path('.clearwrite-runs/promotion-replay').mkdir(parents=True)"
python plugins/clearwrite/skills/clearwrite/scripts/clearwrite_skill.py apply docs/promotion-review/original.md --proposals docs/promotion-review/proposals.json -o .clearwrite-runs/promotion-replay/edited.md --report .clearwrite-runs/promotion-replay/report.json
```

아래 Python 코드는 저장된 모델 응답의 해시·인용·항목 범위와 합계를 다시 검증합니다. **AI가 같은 점수를 다시 낸다는 재현 검사가 아닙니다.**

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, 'plugins/clearwrite/skills/clearwrite/scripts')
from clearwrite.style import validate_style

root = Path('docs/promotion-review')
review = json.loads((root / 'model-style-review.json').read_text(encoding='utf-8'))
original = (root / 'original.md').read_bytes().decode('utf-8')
edited = (root / 'edited.md').read_bytes().decode('utf-8')
validated = validate_style(review['response'], original, edited)
assert validated == review['validated']
print(validated['before']['score'], validated['after']['score'])
```

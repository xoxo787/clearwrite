# ClearWrite 비교 실험 기록

실행: 2026-10-17T12:14:39.752771+00:00 · Python 3.13.5 · Linux

## 실험에 들어간 자료

웹 원문 8개(역사적 사람 저작물 4, 사람 편집 문서 참고군 4), 새 AI 글 8개, 별도 스트레스 예문 4개. 총 20개.
원문·출처·라이선스·해시는 `data/corpus.jsonl`에, 수정 제안은 `data/editorial_proposals.jsonl`에 보관했다.

비교군은 원문 유지(noop), 기본 규칙(builtin), 이번 대화에서 AI가 작성한 문맥 편집 제안을 엔진으로 적용한 재현군(session_editorial_replay)이다. 마지막 군은 Codex/Ollama 실호출 결과가 아니다.

## 실제 측정값

| 처리 | 언어 | 자료군 | n | 문체 후보 전→후 | 읽기 부담 참고 전→후 | 수정/그대로/차단 |
|---|---|---|---:|---:|---:|---:|
| builtin | ko | human_historical | 2 | 0.0 → 0.0 | 5.07 → 5.07 | 0/2/0 |
| builtin | ko | human_reference | 2 | 3.635 → 0.0 | 4.3 → 2.665 | 1/1/0 |
| builtin | ko | ai_generated | 4 | 10.547 → 2.02 | 4.748 → 0.91 | 3/1/0 |
| builtin | ko | stress_fixture | 2 | 15.0 → 0.0 | 6.75 → 0.0 | 2/0/0 |
| builtin | en | human_historical | 2 | 0.0 → 0.0 | 13.42 → 13.42 | 0/2/0 |
| builtin | en | human_reference | 2 | 0.0 → 0.0 | 20.0 → 20.0 | 0/2/0 |
| builtin | en | ai_generated | 4 | 9.465 → 5.545 | 4.26 → 2.495 | 2/2/0 |
| builtin | en | stress_fixture | 2 | 35.0 → 25.0 | 15.75 → 11.25 | 1/0/1 |
| session_editorial_replay | ko | human_historical | 2 | 0.0 → 0.0 | 5.07 → 5.07 | 0/2/0 |
| session_editorial_replay | ko | human_reference | 2 | 3.635 → 3.635 | 4.3 → 4.3 | 0/2/0 |
| session_editorial_replay | ko | ai_generated | 4 | 10.547 → 0.0 | 4.748 → 0.0 | 3/1/0 |
| session_editorial_replay | en | human_historical | 2 | 0.0 → 0.0 | 13.42 → 13.42 | 0/2/0 |
| session_editorial_replay | en | human_reference | 2 | 0.0 → 0.0 | 20.0 → 20.0 | 0/2/0 |
| session_editorial_replay | en | ai_generated | 4 | 9.465 → 9.465 | 4.26 → 4.26 | 0/2/2 |

## 결과 해석

AI가 생성했어도 문체 후보 점수가 0인 글: ai_ko_automation, ai_en_automation, ai_en_observer. 0점은 사람 작성 인증이 아니다.
기본 규칙은 제한된 연결 표현만 바꾸므로 문맥 편집보다 수정 폭이 작다. 문맥 편집의 내부 점수 하락은 독립 품질 평가가 아니다. 이 실험만으로 인지 피로 감소, 모든 장르의 품질 개선, AI 탐지 회피율을 주장할 수 없다.
보호 검사 통과는 문자·수치·일부 조건이 유지됐다는 뜻이다. 원문 속 주체·인과·암묵적 의미 전체를 검증했다는 뜻은 아니다.

## 외부 탐지기

- ai_ko_venv / before: not_run (external_transmission_not_authorized); fraction_ai=None
- ai_ko_venv / after: not_run (external_transmission_not_authorized); fraction_ai=None
- ai_ko_automation / before: not_run (external_transmission_not_authorized); fraction_ai=None
- ai_ko_automation / after: not_run (external_transmission_not_authorized); fraction_ai=None

수치가 null인 항목은 0점이 아니라 미실측이다. 공식 API 예시 응답을 실험 결과로 사용하지 않았다.

## 재현

```sh
python scripts/benchmark.py --out reports/reproduced
```

외부 전송 동의와 PANGRAM_API_KEY가 있을 때만 `--external --external-limit 2`를 추가한다. 최대 2개 글의 전후 4요청이며 요금이 발생할 수 있다.

## 아직 검증하지 않은 것

실제 독자의 이해도·재독 횟수·피로도, 실시간 Codex/Ollama 생성, Windows/macOS 네이티브 실행, 외부 탐지기의 한국어 정확도는 미검증이다. `blind-review.html`은 수집 양식이며 현재 참여자 수는 0이다.

# Third-party notices / 재사용 내역

ClearWrite의 새 코드와 문서는 MIT로 배포합니다. 아래 저작권과 라이선스도 유지해야 합니다. 벤치마크 원문은 각각의 별도 조건을 따릅니다. 상위 프로젝트·저자·서비스의 보증이나 공식 제휴를 뜻하지 않습니다.

## im-not-ai — epoko77-ai

- Source: https://github.com/epoko77-ai/im-not-ai
- Copyright (c) 2026 epoko77-ai. MIT: `licenses/im-not-ai-MIT.txt`.
- 실제 재사용한 코드: `skills/humanize-korean/references/metrics_v2.py`의 `change_rate`와 대구 보존용 `antithesis_count`를 `src/clearwrite/upstream_compat.py`로 작게 추출·변형했습니다.
- 조회한 파일 blob: `1a967957153163f60ff1d8bdb3c93457108cf7eb`. 조회일: 2026-10-17. 코드 검색에서 확인한 리포지터리 커밋: `b37e0206d31fffd9149bf57168d4d62eb2086bee`.
- 변경점: 광범위한 상위 모듈 의존성과 sys.path 변조를 제거했습니다. 4,000자를 넘는 문자열에서는 SequenceMatcher의 autojunk를 켜 병적인 비교 비용을 줄입니다. 긴 글의 수치는 상위 구현과 다를 수 있습니다. 원문의 30/50% 기준을 그대로 채택하지 않고 기본 중단 예산을 35%로 정했습니다. 모든 수치는 의미 보존의 증명이 아닙니다.
- 한국어 이중 피동·명사형 중첩·번역투 검토 관점을 참고해 좁은 규칙으로 다시 작성했습니다. 규칙의 source 태그는 개념적 계보이며 상위의 전체 85개 패턴을 이식했다는 뜻이 아닙니다.
- 전체 저장소를 클론하거나 상위 CLI를 완전 실행한 것은 아닙니다. 공개 소스의 선택한 파일을 읽고 필요한 기능을 재구성했습니다.

## Humanizer — Siqi Chen / blader

- Source: https://github.com/blader/humanizer
- Copyright (c) 2025 Siqi Chen. MIT: `licenses/humanizer-MIT.txt`.
- 검토 문서: `SKILL.md`, metadata version `3.1.0`, 2026-10-17 조회.
- 장식적 도입·반복 결론·과장·실제 필자 샘플·사실 보존·입력 데이터 경계에 관한 아이디어를 `core.py`와 `skills/clearwrite/references/editorial_rules.md`에 선택적으로 번안했습니다.
- 원문 전체를 복제한 스킬이 아닙니다. 대시·대구를 무조건 없애는 규칙, 탐지 회피를 목표로 하는 최적화는 채택하지 않았습니다. 사람이 쓴 것처럼 보이려고 새로운 경험이나 감정을 만들어 넣지 않습니다.

## 데이터와 서비스

- Python 문서 발췌: PSF License Agreement, `licenses/PSF-2.0.txt` 및 소스 배포판 `data/NOTICE.md` 참고.
- 역사적 문학 원문: 저자, 출처, 원문 연도, 재배포 근거를 소스 배포판 `data/corpus.jsonl`과 `data/NOTICE.md`에 기록했습니다. 인용 원문·전사본은 ClearWrite MIT 라이선스의 적용 대상으로 오해하면 안 됩니다.
- Pangram, Ollama, Codex의 이름은 호환 대상을 식별하기 위한 것입니다. 모델 가중치나 API 키를 포함하지 않습니다. 해당 서비스 조건과 이용 비용은 별도입니다.

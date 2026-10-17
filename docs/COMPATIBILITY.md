# 호환성과 실제 확인 범위

기준일 2026-10-18. 규격에 맞춘 구현, 모의 응답 테스트, 실제 호스트 실행을 구분합니다.

**0.3.1 릴리스 확인:** Windows x64 / Python 3.13.14에서 자동 검사 223개(통과 221, 심볼릭 링크 권한에 따른 생략 2)를 실행했습니다. 새 Windows portable EXE에서 공개 예문 144자로 Codex CLI 0.147.0의 실제 윤문·문체 분석을 각 1회 확인했습니다. 윤문은 수정 없이 반환됐고 문체 점수 34점과 실제 인용 근거를 검증했습니다. 두 요청 모두 임시 폴더에는 고정 스키마만 생성됐습니다. 강제 종료·취소·시간 초과·파이프 포화·새 요청 없는 기록 만료와 종료 경합은 별도 회귀 검사로 확인했습니다. Claude Code는 해당 CLI가 없어 모의 프로세스 계약만 검사했습니다. 이전 0.3.0에서 확인한 브라우저 시나리오는 README에 정리돼 있습니다. CI의 현재 상태는 [GitHub Actions](https://github.com/xoxo787/clearwrite/actions)에서 확인하세요.

| 환경 | 제공 형태 | 실제 확인 범위 | 필요한 것 |
|---|---|---|---|
| Windows x64 | Python 포함 portable EXE | 실행·중복 실행 재사용·종료·브라우저 UI | 모델 작업에는 지원 CLI와 로그인 |
| Windows 소스 / Python 3.10+ | CLI·로컬 웹·wheel | 로컬 3.13.14 검사, 한글/공백 경로·UTF-8·오프라인 설치 | Python, 모델 작업에는 CLI |
| Linux/macOS 소스 | CLI·로컬 웹·wheel | GUI·실모델 네이티브 미검증; CI와 초기 기록은 별도 | Python 3.10+, 모델 작업에는 CLI |
| Codex CLI 편집·분석 | 설치된 CLI로 새 요청 | 0.147.0 실제 윤문·문체 분석 | 지원 옵션과 자체 로그인·사용량 |
| Claude Code 편집·분석 | 설치된 CLI로 새 요청 | 모의 하위 프로세스·스키마·HTTP 규약; 실호출 미검증 | 지원 옵션과 자체 로그인·사용량 |
| 지원되는 ChatGPT/Codex 데스크톱 플러그인 표면 | `plugin.json` + `.codex-plugin/plugin.json` | 유효 JSON·포함 파일·자체 실행 검사 | 설치/활성화, 코드 실행 권한 별도 |
| Codex IDE 확장 | 직접 설치하는 스킬 | 패키지 구조 확인 | 공식 문서상 플러그인 미지원 |
| 코드 실행 없는 ChatGPT 환경 | 포함된 문체 스킬 | 언어 지침은 사용 가능 | Python 검사 미실행을 반드시 알림 |
| Ollama | loopback `/api/chat` + JSON schema | 모의 응답 계약 테스트 | 로컬 모델을 미리 설치, 실제 모델 품질 별도 |

Python 3.10 문법 범위로 작성했으며 실행 의존성은 표준 라이브러리뿐입니다. CI는 Ubuntu/macOS/Windows × Python 3.10–3.13을 구성하며 실행 결과를 네이티브 GUI·로그인된 모델 검증으로 표현하지 않습니다. 최초 0.1.x 환경의 기록은 [이전 검증 기록](../reports/VALIDATION.md)에 있습니다. 새로운 버전 전체를 자동 보증하지 않습니다.

## Codex 경로와 중복

사용자 스킬은 `~/.agents/skills/clearwrite`, 프로젝트 스킬은 `<repo>/.agents/skills/clearwrite`입니다. 새 세션에서 `$clearwrite`를 명시적으로 호출합니다. `agents/openai.yaml`은 암묵적 실행을 끕니다. 기존 AGENTS.md·config.toml·권한 정책·API 키 파일은 변경하지 않습니다.

플러그인은 사용자 기준 `~/.codex/plugins/clearwrite`, 사용자 카탈로그는 `~/.agents/plugins/marketplace.json`입니다. 프로젝트 설치는 `<repo>/plugins/clearwrite`와 `<repo>/.agents/plugins/marketplace.json`입니다. 로컬 source 경로는 카탈로그 파일의 부모가 아니라 사용자 홈/프로젝트 루트를 기준으로 작성됩니다. 등록 후 호스트 UI에서 설치/활성화가 필요합니다.

같은 이름의 스킬과 플러그인을 동시에 설치하지 않는 편이 좋습니다. 설치 경로는 사용 중인 Codex의 실제 홈 환경과 일치해야 합니다. Windows와 WSL은 서로 다른 홈입니다. 이 프로그램은 어느 쪽에 설치된 Codex가 사용자의 주 환경인지 추측하지 않습니다.

## 재배치와 번들

`src/clearwrite`가 유일한 원본입니다. `python scripts/build_bundles.py`가 스킬/플러그인 내부에 같은 Python 파일을 복사합니다. `data/bundle-source-hashes.json`과 테스트로 일치 여부를 확인합니다. 스킬 실행 스크립트는 자신의 위치를 기준으로 패키지를 찾으므로 저장소 원본을 삭제해도 설치된 번들은 독립적으로 작동합니다.

설치기는 기본 dry-run이며 `--apply`에서만 쓰기 작업을 합니다. 기존 다른 버전은 `--replace` 없이는 건드리지 않고, 교체 시 백업합니다. 심볼릭 링크 경로는 보수적으로 거부합니다. 관리자 권한이 필요하지 않은 사용자/프로젝트 폴더를 사용하세요.

## 공식 규격

- https://developers.openai.com/codex/noninteractive
- https://developers.openai.com/codex/skills
- https://developers.openai.com/codex/plugins
- https://developers.openai.com/plugins/build/plugins
- https://docs.ollama.com/api/chat

0.3.0 호환 변경: Pangram provider, --detector, --allow-external 및 벤치마크 --external 옵션을 제거했습니다. 문체 평가는 detect --provider codex|claude --allow-model [--candidate FILE]로 실행합니다. 기존 로컬 분석과 builtin/ollama CLI는 유지합니다.

0.3.1은 공개 CLI 옵션과 저장된 검수 JSON 형식을 유지합니다. 내부 모델 통신은 내용 파일 대신 파이프를 사용하며, 서버의 완료·실패·취소 기록은 완료 시점부터 15분 뒤 유휴 중에도 자동 삭제합니다. 화면의 글과 사용자가 저장한 파일에는 이 기한을 적용하지 않습니다.

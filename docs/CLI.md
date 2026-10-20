# CLI·Codex 스킬·빌드 안내

명령은 저장소 루트에서 실행합니다. Python 3.10 이상이며 런타임은 표준 라이브러리만 사용합니다.

## 파일 처리

```sh
python rewrite.py rewrite input.txt --backend codex --allow-model -o edited.txt --report report.json
python rewrite.py detect input.txt --provider codex --candidate edited.txt --allow-model -o style.json
python rewrite.py analyze input.txt
python rewrite.py doctor
```

Claude Code는 `--backend claude` / `--provider claude`를 사용합니다. `detect`의 `--candidate`를 생략하면 원문만 평가합니다. `--allow-model`은 해당 요청에 글을 전송한다는 명시적 동의입니다. 본인의 설치된 CLI와 로그인이 필요하고 계정 사용량이 소모됩니다.

기본 `rewrite`는 좁은 로컬 규칙 모드입니다. 문맥 윤문에는 모델 백엔드를 명시하세요. 기존 Ollama CLI는 호환 목적으로 남아 있으며 화면의 선택지는 Codex/Claude입니다. 로컬 규칙 점수와 모델 문체 점수는 별개입니다.

| 명령 | 출력 |
| --- | --- |
| `analyze FILE` / `detect FILE` | 로컬 규칙 분석 JSON |
| `rewrite FILE` | 결과 글, `--report`로 비교·수정량·보존 검사 JSON |
| `detect FILE --provider codex --allow-model` | 모델 문체 평가와 인용 이유 JSON |
| `prepare FILE --proposals` | 모델에 줄 오프셋 없는 제안 작업 JSON |
| `plan FILE` | builtin의 위치 포함 편집 계획 |
| `apply FILE --proposals proposals.json` | 외부 제안을 검사한 뒤 적용 |
| `apply FILE --plan plan.json` | 위치 포함 계획 검사·적용 |
| `verify ORIGINAL CANDIDATE` | 분량·숫자·인용·변경량 검사 JSON |
| `serve --port 8765` | 지정한 loopback 포트에서 화면 실행 |
| `doctor` | Python·CLI 탐색 정보; 모델 요청 없음 |

입력 `-`는 표준입력입니다. 출력과 검수 파일은 별도 경로를 사용하며 입력 파일을 덮어쓰지 않습니다. 기존 출력 교체는 `--force`로 지정합니다. 명령마다 허용 옵션이 다르므로 `python rewrite.py COMMAND --help`를 확인하세요.

종료 코드: 0=처리 완료, 2=편집/보존 검사 차단, 3=입력·파일·모델·통신 오류, 130=사용자 중단. 예전 외부 판독 미완료 코드 4와 Pangram 옵션은 현재 경로에서 사용하지 않습니다.

## 편집 기준과 검사

`--mode personal/publish/technical/preserve`, `--persona proofreader/editor/formal/columnist/plain/friendly`, `--term`, `--max-change`, `--policy atomic/safe-subset`을 지원합니다. 일반적인 윤문은 기본 설정을 사용하세요. `--persona`는 개입 강도와 말투를 정하고 변경 한도·적용 방식의 기본값도 바꿉니다. `--max-change`/`--policy`를 직접 지정하면 그 값이 우선합니다. 내장 규칙(`--backend builtin`)은 `proofreader`와 `editor`만 받습니다. `preserve`는 원문을 유지하고 모델 윤문 요청을 하지 않습니다.

기본 변경 예산은 문자 유사도 35%이며 상한은 50%입니다. 공백 제외 100자 이상의 글은 기본 분량 85%, 50~99자는 70% 이상을 보존하도록 검사합니다. 개별 편집의 과도한 축약도 검사합니다. 이는 의미 보존의 증명이 아닙니다. 명시적으로 요약을 요청한 경우에만 `--min-retention 0`을 사용할 수 있습니다. [검사 원리](ARCHITECTURE.md)

## Codex 스킬 설치

```sh
python scripts/install_codex.py --kind skill
python scripts/install_codex.py --kind skill --apply
```

첫 명령으로 변경 계획을 확인합니다. 기본 위치는 `~/.agents/skills/clearwrite`입니다. 설치 후 새 Codex 세션에서 호출합니다.

```text
$clearwrite 이 글을 뜻과 필자의 목소리를 유지하면서 다듬고, 바꾼 이유를 보여 줘.
```

스킬은 현재 호스트 모델을 사용하며 Codex를 다시 실행하지 않습니다. Python 검사를 실행할 수 있는 환경이 필요합니다. 반면 독립 프로그램은 설치된 CLI로 새 요청을 실행합니다.

기존 설치는 자동 교체하지 않습니다. 본인의 대상 경로를 확인한 뒤 `--replace --apply`로 백업·교체할 수 있습니다. 프로젝트 전용 설치는 `--project PATH`를 사용합니다. 스킬과 플러그인을 동시에 설치하면 이름이 중복될 수 있습니다.

플러그인 형태는 `--kind plugin`이며 설치기의 등록 이후 호스트에서 설치·활성화해야 합니다. [호환성과 설치 위치](COMPATIBILITY.md)

## Windows 실행 파일 빌드

Windows의 별도 빌드 가상 환경을 사용합니다. 빌드 도구는 런타임 의존성과 별개입니다.

```powershell
python -m venv .build-env
.build-env\Scripts\python.exe -m pip install -r requirements-build.txt
python scripts/build_bundles.py
.build-env\Scripts\python.exe scripts/build_windows.py --out build-windows
```

출력 폴더는 존재하지 않는 새 경로여야 합니다. `build-windows/dist/ClearWrite` 전체가 배포 단위입니다. 사용자가 설치한 모델 CLI·로그인·개인 글을 포함하지 않습니다. `requirements-build.lock.txt`는 릴리스 빌드 환경의 버전 기록입니다.

## 테스트·재현

```sh
python scripts/build_bundles.py
python -m unittest discover -s tests -v
python scripts/benchmark.py --out reports/reproduced
```

기본 검사는 모델·외부 서비스를 호출하지 않습니다. 벤치마크는 출처가 기록된 공개 예문과 저장된 편집 제안을 재현하며 모델 문체 점수의 정확도를 측정하지 않습니다. 개인 글로 만든 보고서는 공개 저장소에 포함하지 마세요.

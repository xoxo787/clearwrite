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

`--mode personal/publish/technical/preserve`, `--persona proofreader/editor/formal/columnist/plain/friendly`, `--style keep/hamnida/haeyo/handa`, `--term`, `--max-change`, `--policy atomic/safe-subset`을 지원합니다. 일반적인 윤문은 기본 설정을 사용하세요. `--persona`는 개입 강도와 말투를 정하고 변경 한도·적용 방식의 기본값도 바꿉니다. `--max-change`/`--policy`를 직접 지정하면 그 값이 우선합니다. `--style`은 종결어미를 통일하며, 비우면 페르소나 기본값(formal 합니다체, friendly 해요체, 나머지 keep)을 씁니다. 스타일을 바꾸면 변경 한도는 최소 0.35, 적용 방식은 safe-subset이 되고 보고서에 `style_conformance`(전후 일치율)가 남습니다. 내장 규칙(`--backend builtin`)은 `proofreader`·`editor`와 `--style keep`만 받습니다. `preserve`는 원문을 유지하고 모델 윤문 요청을 하지 않습니다.

기본 변경 예산은 문자 유사도 35%이며 상한은 50%입니다. 공백 제외 100자 이상의 글은 기본 분량 85%, 50~99자는 70% 이상을 보존하도록 검사합니다. 개별 편집의 과도한 축약도 검사합니다. 이는 의미 보존의 증명이 아닙니다. 명시적으로 요약을 요청한 경우에만 `--min-retention 0`을 사용할 수 있습니다. [검사 원리](ARCHITECTURE.md)

`numbers_units_or_order_changed`가 나오면 숫자뿐 아니라 `mg/L` 같은 단위, `천/만/억` 같은 배율, 대소문자도 대조하세요. `claim_qualifier_changed`는 일부/전체·근삿값·예외·상관/인과 표지가 달라졌다는 뜻입니다. 정확한 표현을 원문대로 남기고 다른 어색한 부분만 수정할 수 있습니다. 새 검사는 기존 제안 JSON 1.0을 그대로 받지만 이전에 통과한 제안을 차단할 수 있으며, `numbers_before/after`의 수량 토큰은 더 긴 단위를 포함할 수 있습니다.

스킬 작업에서 보호 용어는 `prepare`와 `apply`에 똑같이 전달합니다. 문체 샘플은 `prepare`에서만 읽습니다.

```sh
python rewrite.py prepare input.txt --proposals --term ClearWrite --voice sample.txt -o task.json
python rewrite.py apply input.txt --proposals proposals.json --term ClearWrite -o edited.txt --report report.json
```

## Codex 스킬 설치

```sh
python scripts/install_codex.py --kind skill
python scripts/install_codex.py --kind skill --apply
```

첫 명령으로 변경 계획을 확인합니다. 기본 위치는 `~/.agents/skills/clearwrite`입니다. 설치 후 새 Codex 세션에서 호출합니다.

```text
$clearwrite 이 글을 뜻과 필자의 목소리를 유지하면서 다듬고, 바꾼 이유를 보여 줘.
```

요청에 강도나 말투가 없으면 스킬은 편집 전에 한 번 묻습니다. 강도는 보통(`editor`, 기본)·가볍게(`proofreader`)·적극적으로(`columnist`)·쉽게(`plain`) 중에서, 말투는 원문 유지(`keep`, 기본)·합니다체·해요체·한다체 중에서 고릅니다. "칼럼처럼 한다체로"처럼 요청에 적으면 묻지 않습니다. 질문할 수 없는 비대화형 실행이나 "바로 해줘"라는 요청에서는 `editor` + `keep`으로 진행합니다.

스킬은 현재 호스트 모델을 사용하며 Codex를 다시 실행하지 않습니다. Python 검사를 실행할 수 있는 환경이 필요합니다. 반면 독립 프로그램은 설치된 CLI로 새 요청을 실행합니다.

기존 설치는 자동 교체하지 않습니다. 본인의 대상 경로를 확인한 뒤 `--replace --apply`로 백업·교체할 수 있습니다. 스킬 백업은 같은 이름의 스킬로 다시 읽히지 않도록 `skills/` 밖의 `.clearwrite-backups/`(예: `~/.agents/.clearwrite-backups/`)에 보관합니다. 프로젝트 전용 설치는 `--project PATH`를 사용합니다. 스킬과 플러그인을 동시에 설치하면 이름이 중복될 수 있습니다.

플러그인 형태는 `--kind plugin`이며 설치기의 등록 이후 호스트에서 설치·활성화해야 합니다. [호환성과 설치 위치](COMPATIBILITY.md)

## Claude Code 스킬 설치

```sh
python scripts/install_codex.py --host claude
python scripts/install_codex.py --host claude --apply
```

같은 스킬 번들을 `~/.claude/skills/clearwrite`에 설치합니다. `--project PATH`를 주면 `PATH/.claude/skills/clearwrite`에 설치합니다. 새 Claude Code 세션에서 `/clearwrite`로 호출하거나 윤문을 요청합니다. Claude Code는 스킬 설치만 지원하며 `--kind plugin`은 거부합니다. `settings.json`과 권한 설정은 바꾸지 않습니다. 설치 위치와 파일 구성은 자동 검사로 확인했지만, 실제 Claude Code 세션에서 스킬이 호출되는지는 별도로 확인해야 합니다.

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
python scripts/build_bundles.py --check
python -m unittest discover -s tests -v
python scripts/benchmark.py --out reports/reproduced
```

기본 검사는 모델·외부 서비스를 호출하지 않습니다. 벤치마크는 출처가 기록된 공개 예문과 저장된 편집 제안을 재현하며 모델 문체 점수의 정확도를 측정하지 않습니다. 개인 글로 만든 보고서는 공개 저장소에 포함하지 마세요.

번들 생성은 생성 디렉터리 전체를 삭제하지 않고 파일을 갱신합니다. 동기화 대상에 원본에 없는 파일이 있으면 보존한 채 오류를 내므로 내용을 확인해 별도로 보관한 뒤 다시 실행하세요. `--check`는 파일을 쓰지 않고 원본 코드·스킬/플러그인 코드와 참조 문서·해시의 불일치를 검사합니다.

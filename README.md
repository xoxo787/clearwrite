<div align="center">

<img src="docs/images/clearwrite-banner.svg" alt="ClearWrite · 맑은글 — 고친 곳을 보고, 이유를 읽고, 내 글로 남기세요." width="100%">

**원문 · 수정본 · 수정 이유를 한 화면에서 확인하는 한국어·영어 윤문 도구**

[Windows 베타 다운로드](https://github.com/xoxo787/clearwrite/releases/download/v0.3.0/ClearWrite-0.3.0-Windows-x64.zip) · [사용 설명서](docs/DESKTOP.md) · [English](README.en.md) · [오류 제보](https://github.com/xoxo787/clearwrite/issues)

[![Offline tests](https://github.com/xoxo787/clearwrite/actions/workflows/ci.yml/badge.svg)](https://github.com/xoxo787/clearwrite/actions/workflows/ci.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-285d4c)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-465b70)
![Windows x64 beta](https://img.shields.io/badge/Windows-x64%20beta-8a702e)

</div>

ClearWrite는 글을 다듬은 결과와 **어디를 어떻게, 왜 바꿨는지**를 함께 보여줍니다. 노란 형광펜을 누르면 원문과 수정본, 판단 이유가 같은 위치로 이동합니다. 필자는 필요한 수정을 살펴보고, 자신의 글로 남길 수 있습니다.

> **시작 전 확인**  
> Windows 배포판에는 Python이 포함되어 있습니다. 윤문·AI 문체 분석에는 **본인이 설치하고 로그인한 Codex CLI 또는 Claude Code**가 필요합니다. 요청한 글은 해당 모델 서비스로 전송되며 본인 계정의 사용량이 소모됩니다.

## 한눈에 보기

![ClearWrite의 원문·수정본·수정 이유 비교 화면](docs/images/editor-preview.png)

*프로그램에 포함된 설정 안내문을 ‘예시 체험’으로 연 실제 화면입니다. 저장된 편집안을 적용하며 모델을 호출하지 않습니다. 문체 점수는 사용자가 분석을 실행한 뒤 표시됩니다.*

| 기능 | 화면에서 확인하는 것 |
| --- | --- |
| **형광펜 비교** | 추가·수정은 노란색, 삭제·기존 표현은 분홍색과 취소선 |
| **수정 이유** | 바꾸기 전 표현, 바꾼 표현, 수정한 이유를 연결해서 표시 |
| **같은 위치로 이동** | 구간이나 설명을 누르면 원문·수정본·이유 영역을 함께 이동 |
| **AI 문체 분석** | 선택한 Codex·Claude의 문체 점수와 실제 인용 근거 |
| **실제 수정 비율** | 적용된 글자 차이를 계산하고 삭제·추가 글자 수를 표시 |
| **결과 보관** | 수정본 TXT와 원문·편집 내역·문체 평가를 포함한 JSON 저장 |

## 시작하기

### Windows에서 사용하기

1. [Codex CLI](https://developers.openai.com/codex/cli/) 또는 [Claude Code](https://code.claude.com/docs/en/overview)를 설치하고 본인 계정으로 로그인합니다. 데스크톱 앱 로그인과 CLI 준비는 별개입니다.
2. [Windows x64 ZIP](https://github.com/xoxo787/clearwrite/releases/download/v0.3.0/ClearWrite-0.3.0-Windows-x64.zip)을 받아 **전체 압축을 해제**합니다.
3. `ClearWrite/ClearWrite.exe`를 실행합니다. `_internal` 폴더를 함께 두세요.
4. 먼저 **예시 체험**으로 형광펜과 수정 이유를 확인합니다. 이 버튼은 모델을 호출하지 않습니다.
5. 본인의 글을 넣고 모델을 선택한 뒤, 전송에 동의하고 **윤문하기**를 누릅니다.
6. 문체 평가도 필요하면 전송에 다시 동의하고 **AI 문체 분석**을 누릅니다. 원문과 현재 수정본을 함께 분석하며 글을 다시 윤문하지 않습니다.

내 PC에서만 열리는 브라우저 화면을 사용합니다. 기본 포트는 자동 선택되며, 별도의 웹 서버를 마련할 필요가 없습니다. 글은 자동 저장되지 않으므로 필요한 결과를 저장하고 **앱 종료**로 종료하세요.

**현재는 서명 전 포터블 베타판입니다.** Windows에서 게시자·평판 경고가 나타날 수 있습니다. 보안 기능을 끄는 방식으로 해결하지 마세요. 상세 실행법과 연결 문제 해결은 [사용 설명서](docs/DESKTOP.md)에 있습니다.

### 소스에서 실행하기

Python 3.10 이상이면 기본 실행에 추가 Python 패키지가 필요 없습니다.

```sh
git clone https://github.com/xoxo787/clearwrite.git
cd clearwrite
python rewrite.py
```

macOS/Linux에서는 환경에 따라 `python3`를 사용합니다. 소스 CLI는 여러 운영체제를 대상으로 작성했으며, 실제 확인 범위는 아래 검증 표와 [호환성 문서](docs/COMPATIBILITY.md)를 참고하세요.

## 점수는 이렇게 읽으세요

### AI 문체 점수: 0~100의 참고용 모델 평가

선택한 Codex·Claude가 다음 네 가지를 각각 0~25점으로 평가합니다.

- 같은 말과 구조의 **반복**
- **상투적인 연결·강조**
- **획일적인 문장 흐름**
- 구체성 없는 **추상적 부연**

높은 점수는 이 문체 특징이 더 두드러진다는 뜻입니다. 인용한 문장이 실제 원문·수정본에 있는지, 점수 범위와 입력 해시가 맞는지 검사한 뒤 표시합니다.

**AI 작성 확률이나 AI가 작성한 비율을 측정하는 기능은 아닙니다.** 사람의 글에도 이런 특징이 있고, AI의 글에도 없을 수 있습니다. 평가의 일관성과 저자 판별 정확도는 검증하지 않았으며, 장르·모델·실행에 따라 결과가 달라질 수 있습니다.

Pangram이나 별도 탐지기 API 키는 사용하지 않습니다. 분석 오류·취소·입력 변경 시 이전 점수를 지우고 **미분석**으로 표시합니다.

### 실제 수정 비율: 이번 윤문에서 바뀐 글자의 양

이 수치는 모델에게 물어보지 않고 실제 적용된 편집에서 계산합니다.

```text
(삭제·교체된 원문 글자 + 추가·대체된 글자)
────────────────────────────────────────── × 100
          원문 글자 수 + 수정본 글자 수
```

공백·줄바꿈을 포함한 Unicode 코드포인트 기준입니다. 수정이 없거나 보존 검사에서 차단되어 원문을 유지하면 0%입니다. 글자 수와 계산식은 검수 JSON에도 저장합니다.

## 뜻과 필자의 목소리를 살피는 편집

![원문 보관에서 모델 제안·보존 검사·수정 적용·비교까지의 편집 과정](docs/images/editing-flow.svg)

ClearWrite는 요약보다 **필요한 만큼의 윤문**을 지향합니다. 정확한 원문 위치, 숫자·단위·일부 조건 표현, 인용·코드·보호 용어와 과도한 축약을 검사합니다. 기본 변경 예산과 분량 보존 기준을 넘는 제안은 차단할 수 있습니다.

이 기계적 검사는 모든 의미 변화나 사실 왜곡을 잡아내지는 못합니다. 최종 결과는 원문과 함께 검토하세요. 세부 기준과 알려진 한계는 [구조와 판단 기준](docs/ARCHITECTURE.md)에 공개했습니다.

## 내 계정으로 연결하고, 전송 전에 확인합니다

- Codex·Claude CLI의 기존 로그인을 사용합니다. ClearWrite가 로그인 파일을 읽거나 복사하지 않습니다.
- 현재 채팅의 답을 재사용하지 않고 **별도의 새 요청**을 실행합니다. 윤문과 문체 분석은 각각 사용량을 소모합니다.
- 전송 동의 후에만 모델을 호출합니다. 앱 화면은 로컬에서 열리지만 모델 처리는 OpenAI 또는 Anthropic 서비스에서 이뤄집니다.
- **예시 체험 · 로컬 규칙 분석 · 원문 보존**은 모델을 호출하지 않습니다.
- 모델에는 제공한 글만 처리하도록 요청하며 도구·MCP·플러그인을 제한합니다. 시간·출력 한도와 취소 처리를 둡니다.
- 글과 검수 기록은 사용자가 저장할 때 파일로 남습니다. 검수 JSON에는 원문이 포함됩니다.

전송·저장 범위는 [보안 문서](SECURITY.md)에서 확인할 수 있습니다.

## CLI와 Codex 스킬

```sh
# 로그인된 Codex CLI로 윤문
python rewrite.py rewrite input.txt --backend codex --allow-model -o edited.txt --report report.json

# 원문과 수정본의 문체를 함께 평가
python rewrite.py detect input.txt --provider codex --candidate edited.txt --allow-model -o style.json

# 모델 요청 없이 로컬 규칙으로 편집 후보 분석
python rewrite.py analyze input.txt

# Codex 스킬 설치 계획 확인 → 적용
python scripts/install_codex.py --kind skill
python scripts/install_codex.py --kind skill --apply
```

스킬을 설치한 뒤 새 Codex 세션에서 `$clearwrite`로 호출할 수 있습니다. 스킬은 현재 호스트의 모델을 사용하고, 독립 프로그램은 설치된 CLI로 새 요청을 실행합니다. 두 경로의 차이와 전체 명령은 [CLI·스킬 안내](docs/CLI.md)에 정리했습니다.

## 확인한 범위

| 항목 | 확인 상태 |
| --- | --- |
| Windows x64 포터블 EXE | 실행·중복 실행 재사용·종료 확인 |
| Codex CLI 0.147.0 | 실제 윤문·문체 분석 연결 확인 |
| Claude Code | 모의 프로세스·응답 규약 검사 완료, 실제 호출 미검증 |
| 로컬 자동 검사 | Windows / Python 3.13.14에서 212개 실행, 210개 통과·2개 생략 |
| 브라우저 화면 | 형광펜·수정 이유·점수·다운로드·실패·취소·입력 변경·반응형 검사 |
| Python wheel | 새 가상 환경에서 오프라인 설치·CLI 실행 확인 |
| GitHub Actions | Ubuntu·Windows·macOS / Python 3.10~3.13의 12개 조합 통과 |
| AI 저자 판별 정확도 · 독자 이해도 개선 | 검증하지 않음 |

자동 검사는 실제 모델을 호출하지 않습니다. 모델 연결 검사와 모의 응답 검사를 구분하며, CI의 최신 결과는 상단 배지와 [Actions](https://github.com/xoxo787/clearwrite/actions)에서 확인할 수 있습니다.

## 개발과 기여

```sh
python scripts/build_bundles.py
python -m unittest discover -s tests -v
python scripts/benchmark.py --out reports/reproduced
```

`src/clearwrite`가 원본 코드이고, 스킬·플러그인 내부 복사본은 생성기로 동기화합니다. Python 실행 의존성은 표준 라이브러리뿐입니다. Windows 실행 파일을 직접 빌드하려면 [빌드 안내](docs/CLI.md#windows-실행-파일-빌드)를 참고하세요.

오류를 발견하면 OS·버전·재현 절차와 비식별 예문을 [Issues](https://github.com/xoxo787/clearwrite/issues)에 남겨 주세요. 개인 원문과 API 키는 게시하지 마세요. [기여 안내](CONTRIBUTING.md) · [변경 기록](CHANGELOG.md) · [평가 방법](docs/EVALUATION.md)

## 라이선스와 출처

ClearWrite의 코드와 문서는 [MIT License](LICENSE)로 배포합니다. 재사용한 코드와 번안에는 원래 고지를 유지하며, 비교 자료의 라이선스는 별도입니다.

[재사용·저작권 고지](THIRD_PARTY_NOTICES.md) · [개별 라이선스](licenses/) · [자료 출처](data/NOTICE.md)

<div align="center">

# ClearWrite · 맑은글

**See what changed. Understand why. Keep your voice.**

[Download Windows beta](https://github.com/xoxo787/clearwrite/releases/download/v0.3.0/ClearWrite-0.3.0-Windows-x64.zip) · [한국어](README.md) · [Desktop guide](docs/DESKTOP.md) · [Report an issue](https://github.com/xoxo787/clearwrite/issues)

</div>

ClearWrite is a Korean/English prose editor that connects original text, edited text and explanations. Select a highlight or a reason to navigate all three panes together. Use your installed, logged-in Codex CLI or Claude Code for rewriting and optional style assessment.

![Linked original, edited text and explanations](docs/images/editor-preview.png)

*The screenshot uses the built-in public example. It replays a saved edit plan without a model request. Style scores appear after an explicitly requested analysis.*

## Start on Windows

1. Install and sign in to [Codex CLI](https://developers.openai.com/codex/cli/) or [Claude Code](https://code.claude.com/docs/en/overview). A desktop-app login alone does not set up the CLI.
2. Download the Windows x64 ZIP and extract the **whole folder**.
3. Run `ClearWrite/ClearWrite.exe`, keeping `_internal` beside it. No Python installation is required.
4. Try the built-in example, or enter text, select a model, consent to transmission and click **윤문하기** (Rewrite).
5. To assess style, consent again and click **AI 문체 분석**. It evaluates the source and current accepted output without rewriting them again.

This is an unsigned portable beta. Do not disable OS security protections to run it. Save your result before closing the app: writing is not automatically saved.

## What you can inspect

- Yellow highlights for additions/changes, pink strikethrough for removed/original wording.
- Original wording, replacement and explanation linked to the same edit.
- Model style scores with actual quotation evidence, checked against the input.
- Actual applied-character change rates and counts.
- TXT export and a JSON report containing source, edits, checks and completed assessments.

## What the scores mean

**Model style score:** four uncalibrated 0–25 judgments, totaling 0–100: repetition, formulaic phrasing, uniform flow and unsupported abstraction. This is **not an AI authorship probability, AI-written fraction or proof of who wrote the text**. Genre, model and repeated runs can affect results. Invalid quotes, hashes or scores are rejected. Failed, cancelled or stale assessments are not replaced with zero.

**Actual change rate:** `(removed + added) / (source characters + result characters) * 100`, calculated from applied-edit character diffs, including whitespace and Unicode codepoints. No applied change means 0%. Counts and method are exported.

The legacy local `ai_style_score` is a separate rule-candidate density, not the new model score. Pangram integration was removed in 0.3.0.

## Your account and your text

The interface runs on loopback. Model work is a **new request to the selected CLI's provider**, consuming your own account's usage. Source and accepted output are transmitted only after consent. ClearWrite does not read or copy CLI login files. It restricts tools/MCP/plugins, uses bounded temporary workspaces and supports cancellation. The provider/CLI has its own processing and retention policies.

The example, local rule analysis and preserve mode do not call a model. JSON exports contain the original text. Read [SECURITY.md](SECURITY.md) for scope and limitations.

## Source and CLI

Python 3.10+ with standard-library runtime dependencies:

```sh
git clone https://github.com/xoxo787/clearwrite.git
cd clearwrite
python rewrite.py
python rewrite.py rewrite input.txt --backend codex --allow-model -o edited.txt --report report.json
python rewrite.py detect input.txt --provider codex --candidate edited.txt --allow-model -o style.json
python rewrite.py analyze input.txt
```

Use `--backend claude` or `--provider claude` for Claude Code. The default CLI rewrite path remains a narrow builtin rule editor. It is not an LLM. Legacy Ollama CLI compatibility is retained; browser rewriting uses Codex/Claude. See [CLI and skill setup](docs/CLI.md).

## Verification and development

Windows x64 EXE startup, single-instance reuse and shutdown were tested. Codex CLI 0.147.0 was called for real rewriting and style assessment. Claude Code has offline subprocess/response contract tests but no live call in the release environment. The recorded Windows/Python 3.13.14 suite ran 211 tests: 209 passed, 2 symlink-related skips. Browser QA covered linked navigation, scores/reasons, downloads, failures, cancellation, stale inputs and responsive layouts. A local wheel was installed in a clean environment without network downloads.

These checks do not validate authorship detection, reader cognition or universal semantic preservation. Current CI results are available in [Actions](https://github.com/xoxo787/clearwrite/actions).

```sh
python scripts/build_bundles.py
python -m unittest discover -s tests -v
python scripts/benchmark.py --out reports/reproduced
```

`src/clearwrite` is authoritative; generated bundles must stay synchronized. See [contributing](CONTRIBUTING.md), [architecture](docs/ARCHITECTURE.md), [compatibility](docs/COMPATIBILITY.md) and [changelog](CHANGELOG.md).

## License

Code and documentation are under [MIT](LICENSE). Preserve the original notices for reused code. Corpus materials have their own provenance and licenses: [third-party notices](THIRD_PARTY_NOTICES.md), [licenses](licenses/), [data notice](data/NOTICE.md).

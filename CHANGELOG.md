# Changelog

## Unreleased — 2026-11-04

The skill now asks for editing strength (`editor`, `proofreader`, `columnist`, `plain`; `formal`/`friendly` by name) and Korean sentence ending (`keep`, `hamnida`, `haeyo`, `handa`) before editing when the request names neither, and asks only for the missing one when the request names one. Non-interactive runs and "just do it" requests proceed with `editor` + `keep` and say so. Style-analysis and builtin rule requests are not affected. This changes skill instructions only; CLI defaults, the browser editor and the proposal schema are unchanged. Whether hosts follow the question step has not been tested in live sessions.

Strengthened the editing skill with paragraph-role review, reference resolution, subject–verb proximity, conditional sentence-splitting, terminology consistency and a two-way check for omissions and unsupported additions. Added Korean/English decision examples, including cases best left unchanged, and linked primary writing guidance and simplification-evaluation research. The shared model prompt uses the same review criteria. These changes have not been independently evaluated with readers or live model calls.

Fixed quantity preservation gaps: common scientific units, compound units, Korean magnitudes, full time/count units and unit casing now participate in both patch and final-document checks. Added `claim_qualifier_changed` for changes to limited lexical cues for partial/universal/majority scope, numeric approximation, exceptions and correlation/causation. Safe-subset still retains passing independent edits. These conservative checks can reject valid paraphrases and do not establish semantic equivalence.

Public CLI options and proposal schema 1.0 remain compatible. Quantity arrays can contain more complete tokens (for example `1억5천만원` instead of separate digits), and previously accepted proposals may now be blocked. No stored-data migration is required.

Bundle generation updates files without recursively deleting generated directories, preserves and reports unexpected files in synchronized trees, and supports a read-only `python scripts/build_bundles.py --check` comparison of code, skill references and source hashes.

Added Claude Code skill installation: `python scripts/install_codex.py --host claude [--apply]` installs the same skill bundle into `~/.claude/skills/clearwrite` (or `PATH/.claude/skills/clearwrite` with `--project`). `--host` defaults to `codex`, so existing commands are unchanged; Claude Code plugins are rejected. The skill text no longer assumes Codex as the only host. Skill backups made by `--replace` now go to a `.clearwrite-backups/` folder next to `skills/` instead of inside it, where hosts could load them as a second `clearwrite` skill. Invocation inside a live Claude Code session is not covered by automated tests.

Stabilized Windows HTTP header-rejection tests by sending headers without the deliberately unread body, as the existing oversized-request test already does. They still require immediate 403/415 responses and do not change server authorization or content-type handling.

## 0.4.0 — 2026-10-21

Added editor personas that set register and intervention strength: `proofreader` (light, 15%, atomic), `editor` (default, unchanged 35% atomic), `formal` (합니다체), `columnist`, `plain` and `friendly` (해요체). The last four use a 50% change budget and the safe-subset policy, so one gated edit no longer discards every other passing edit. All personas keep the same preservation gates and forbid new facts. `rewrite`, `prepare`, `apply` and `verify` accept `--persona`; explicit `--max-change`/`--policy` still win. Strong personas are asked for sentence-sized edits, because multi-sentence rewrites tripped the local compression gate even when only filler was cut. Reports record `persona` and `edit_budget`. Builtin rules accept only `proofreader` and `editor`. The editor adds a persona selector and reports edits dropped by safe-subset.

Fixed the Claude Code backend for subscription logins. `--bare` reads only `ANTHROPIC_API_KEY`, which ClearWrite strips, so every Claude request failed with "Not logged in". Isolation now uses `--setting-sources ""` and `--disable-slash-commands`; the `--disallowedTools '*'` rule is removed because it also denied the StructuredOutput tool. Verified with Claude Code 2.1.304: no hooks, skills, tools or MCP servers load, and the user CLAUDE.md is not included.

Added grammar styles, chosen apart from personas: `--style keep|hamnida|haeyo|handa` (합니다체·해요체·한다체) unifies Korean sentence endings. Without `--style`, `formal` keeps 합니다체 and `friendly` keeps 해요체, so their previous behavior is unchanged. A style conversion gets at least a 35% budget and the safe-subset policy. Reports add `style` and `style_conformance` (before/after share of sentences ending in the target register; a rule-based count that skips quotes, code and headings). The editor adds a style selector and shows the rate. 개조식 is not included yet.

The compression gates no longer count information-free filler as lost content. Cutting phrases such as "In conclusion", "it is important to note that", "Let's dive in" or "결론적으로", or using a rule's concise equivalent ("in order to" → "to"), is measured against the filler-free original; compressing the remaining content is still blocked. Reports add `filler_adjusted_length_ratio` beside `visible_length_ratio`. Number, scope, direction and protected-span gates are unchanged.

The scope gate no longer treats the standalone adverb "보다" (보다 효율적으로, "more") as a comparison, which blocked "보다 → 더" and some sentence-ending conversions. The attached particle (전년보다) is still guarded.

Redesigned the editor as a proofreading sheet: cool paper with a blue-pencil accent, settings gathered into one band, Myeongjo serif for the text being edited and the wordmark, blue highlighter marks with pencil underlines, margin-note styling for edit reasons, and one ruled panel instead of three cards for style scores. Only local fonts are referenced, so the CSP is unchanged. Element IDs and editor behavior are unchanged.

Web assets are pinned to LF so bundle hashes match across platforms.

## 0.3.1 — 2026-10-18

Replaced ClearWrite's prompt, response and stderr temporary files with bounded subprocess pipes. Codex responses now come from the final agent message in its documented JSONL stream; Claude's JSON envelope is read from stdout. Only the static response schema is written to the temporary working directory. ClearWrite no longer creates prose-bearing request files even if the parent process exits abruptly. CLI/provider-owned storage and earlier-version leftovers remain outside this guarantee.

Completed, failed and cancelled server jobs expire 15 minutes after completion using a background cleaner, without waiting for another request. Reads also reject expired jobs. Shutdown clears stored records, cancels running work and prevents late results from restoring a cleared record. The editor's current text and files explicitly saved by the user are retained.

Added privacy regressions covering abrupt exits, cancellation, timeouts, malformed/oversized output, simultaneous pipe pressure, idle expiry and shutdown races. Also removed inherited `CODEX_API_KEY` from the model CLI environment. Public command options and saved report formats are unchanged.

## 0.3.0 — 2026-10-17

Removed Pangram integration. Added consent-gated Codex/Claude style assessments with four 0–25 dimensions, exact quotation and input-hash validation, and a separate model-analysis action. Added applied-character change statistics and JSON export. Failed/cancelled/stale assessments clear prior scores while preserving accepted editing output. Existing CLI callers must migrate from Pangram flags to `detect --provider codex|claude --allow-model`.

The public documentation now includes a Windows download path, onboarding, privacy/usage boundaries, an actual public-example screenshot and explicit verification limits.

## 0.2.1 — 2026-10-17

Fixed change selection so original, edited text and explanation panes scroll together. Each pane moves internally instead of scrolling the outer page repeatedly. Added text-neutral anchors at insertion/deletion positions, including inserted spaces and partial deletions. Selecting a change from the original-editing view restores comparison mode. Click, keyboard and previous/next navigation share the same behavior; reduced-motion settings are respected. Editing plans and the preservation engine are unchanged.

## 0.2.0 — 2026-10-17

Added a three-pane browser editor with linked character highlights, original/replacement/reason cards, keyboard navigation, TXT/JSON export, stale-result protection and explicit per-request consent. Browser backends are now installed Codex CLI and Claude Code CLI. The former builtin/Ollama browser selector is removed; CLI compatibility remains. Model requests run in temporary workspaces with tool restrictions, bounded output, cancellation and timeouts. Detection displays actual provider fractions or unmeasured states; failures preserve editing output.

Added an unsigned Windows portable build, automatic port selection, single-instance reuse and clean shutdown. The default serve port is now automatic; specify `--port 8765` to retain the old address. Fixed UTF-8 piped input on Windows. Regenerated versioned skills/plugins without automatically installing them. Preservation engine behavior remains the 0.1.1 baseline.

## 0.1.1 — 2026-10-17

Default editing now preserves explanatory depth instead of compressing paragraphs into short conclusions. Added independent guards for both full-document loss and per-edit overcompression (measured without whitespace), plus a visible retention report and explicit CLI override for genuinely requested summarization. Updated Codex instructions, example rewrite and tests. Internal style scores remain non-independent proxies, not readability or authorship measurements.

## 0.1.0 — 2026-10-17

Initial usable development release: zero-dependency Python CLI and loopback web
editor, Korean/English selective rules, native Codex skill, portable/compatibility
plugin packaging, exact-anchored model proposals and transactional guards,
optional local Ollama and opt-in Pangram async API adapters, provenance-preserving
comparison corpus and replay report, reproducible tests and private installer.

This release does not claim calibrated AI authorship detection, verified reduction
in cognitive fatigue, or production security certification. Live Codex/Ollama and
external detector measurements require an appropriate environment and credentials.

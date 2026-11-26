# Changelog

## Unreleased — 2026-11-04

Naturalness sessions are easier to read: words that differ are highlighted on both sides (so the edited side is not revealed), `--min-diff` drops pairs whose visible texts differ by less than the given share as `tiny_difference`, the start screen says that some pairs are deliberate attention checks, a 'same' (tie) choice is available on key 3, and the default session size is 12. Scoring leaves ties out of the win count, reports them as `ties`, computes the threshold from the remaining pairs, and counts a tie on an attention check as a failure. In the first reader session, near-identical pairs and unannounced attention checks were the main sources of fatigue and confusion.

`naturalness_eval.py build --max-chars N` shows each pair as the same whole-sentence passage around the first change (about N characters) instead of both full texts, and trims attention-check texts the same way. In the first development sessions this cut the median reading per pair from about 1,030 to 375 characters. The excerpt always covers the whole first change on both sides (including text appended at the end), keeps at least one unchanged sentence when one side would otherwise be empty, adds context only while both sides stay within the limit, and does not split sentences inside numbers such as 3.14 or after quoted terminators such as 「안녕.」이라고. Excerpt results describe that passage, not the whole text; pairs whose excerpts match are skipped as `identical_excerpt`.

The skill installer no longer creates and recursively deletes a temporary folder before copying. It copies into a fresh uniquely named folder under `.clearwrite-staging/` next to `skills/` (retrying on a name collision) and then moves it into place, so a failed copy never leaves a partial folder where hosts load skills; if the final move fails (for example across filesystems), the previous install is moved back. A test parses shipped Python and fails on direct `rmtree`/`removedirs` calls or imports of those names; it does not catch every indirect form. Backups and reports are unchanged.

Added the `natural` persona and structural diagnosis. `prepare` now returns `structure`: counts of commas after connective endings, mechanical enumeration, teaser and wrap-up sentences, stock descriptive phrases and "not merely A but B" framing, plus the dominant patterns; for `natural` the diagnosis is also added to the instruction. The counts are editing hints, not a score to minimise or an authorship signal. `natural` (strong, 50%, safe-subset) may merge, split and reorder sentences within a paragraph and delete information-free sentences, so it skips only the per-edit compression check; number, scope, claim, direction, protected-span and document-length checks still run, with a default length floor of 0.75 instead of 0.85. Reports add `gates` (applied length floor and whether per-edit compression ran); `edit_budget` is unchanged. The skill offers `natural` as the third strength option and ships `references/structure_patterns.md`. Thresholds were set by hand on development texts only; the held-out texts were not used. Reader preference for `natural` has not been measured yet.

Added `scripts/naturalness_eval.py` and `docs/NATURALNESS-EVAL.md` for blind pairwise naturalness evaluation by one reader: sessions show two versions of the same text with a single question (which reads more naturally), randomize side and order from a recorded seed, keep the answer key outside the session folder, repeat about 15% of pairs with sides swapped for self-consistency, and add human-versus-degraded attention checks. Scoring reports wins, Wilson intervals and a one-sided binomial test against a threshold fixed before results (for example 31 of 48). Sessions with attention checks below 75% or self-consistency below 70% are invalid. Results are one reader's preference, not authorship, AI probability or detector evasion. No reader results exist yet.

Added a review mode to the skill: requests such as "검토해 줘" or "맞춤법 봐 줘" get a numbered list of engine-checked findings, split into required (spelling, spacing, particles, grammar) and optional (style), and only the numbers the user picks are applied. Unclear requests are treated as review, which never changes the original. `apply` gains `--select N,M` (apply only the chosen 1-based proposals, keeping their original numbers) and `--summary` (per-proposal applied/excluded verdicts with reasons, plus the result text when `-o` is used, on stderr). Without the new flags `apply` output is unchanged. To cut host round trips, the skill now runs `doctor` only after a failure, reads `prepare` output directly instead of a `task.json` file, relies on `--summary` instead of re-reading result files, uses one shell command per call without `cd`/`&&`/variables, and skips `references/` for proofreading. In an analysis of 11 earlier non-interactive runs, about 117 of 123 seconds per run were model turns rather than engine time, and 18 of 41 `apply` calls failed on compound shell commands; the effect of these instructions on live sessions has not been measured yet.

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

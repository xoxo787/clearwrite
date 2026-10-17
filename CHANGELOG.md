# Changelog

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

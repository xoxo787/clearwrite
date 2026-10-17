"""Small adapted excerpt from im-not-ai, not its complete scoring engine.

Original: epoko77-ai/im-not-ai, metrics_v2.py, blob
1a967957153163f60ff1d8bdb3c93457108cf7eb (retrieved 2026-10-17).
Copyright (c) 2026 epoko77-ai. MIT; see licenses/im-not-ai-MIT.txt.
Changes: removed CLI, baseline and markup modes; bounded the expensive exact
character comparison to 4,000 characters. Longer documents use autojunk=True.
This is a similarity complement, NOT an edit-distance or semantic score.
"""
import difflib
import re


def change_rate(before: str, after: str) -> float:
    if not before and not after:
        return 0.0
    matcher = difflib.SequenceMatcher(
        None, before, after, autojunk=max(len(before), len(after)) > 4000
    )
    return 1.0 - matcher.ratio()


def antithesis_count(text: str) -> int:
    # Human writers use these too. Never use this count as proof of authorship.
    return len(re.findall(r"(?:가|이)\s*아니라|이기\s*이전에|되기\s*이전에|이기보다", text))

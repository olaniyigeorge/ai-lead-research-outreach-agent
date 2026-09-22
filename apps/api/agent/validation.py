"""Deterministic, zero-cost gibberish check for a submitted objective.

This runs before anything else -- no model call, not even the cheap Haiku
sanity check in stages/sanity_check.py. Something like "ssssssssss" should
never reach a model at all.
"""

import re

_REPEATED_CHAR_RUN = re.compile(r"(.)\1{4,}")  # same character 5+ times in a row
_WORD_RE = re.compile(r"[A-Za-z']{2,}")


def looks_like_gibberish(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return True

    if _REPEATED_CHAR_RUN.search(normalized.lower()):
        return True

    words = {w.lower() for w in _WORD_RE.findall(normalized)}
    if len(words) < 3:
        return True

    unique_ratio = len(set(normalized.lower())) / len(normalized)
    if unique_ratio < 0.15:
        return True

    return False

"""Name and address similarity for grouping, confidence and eval (FR-4.2, FR-8.2).

Overlap coefficient on normalized words: shared words divided by the size of the shorter side.
Names and addresses often differ by extra words ("Bò Né 3 Ngon - Dương Thị Mười"), so this is
used instead of Jaccard, which would penalize the extra words.
"""

import re

from app.core.text import normalize_text

# FR-3.3: generic words dropped before comparing names (CLAUDE.md: "quán", "tiệm").
GENERIC_WORDS = frozenset({"quan", "tiem"})

_NON_WORD = re.compile(r"[^\w\s]+")


def _tokens(text: str) -> set[str]:
    """Words only: punctuation is dropped so "1," and "1" are the same token."""
    return set(_NON_WORD.sub(" ", normalize_text(text)).split()) - GENERIC_WORDS


def name_overlap(a: str, b: str) -> float:
    """Shared tokens / size of the shorter token set. 0.0 when either side has no tokens."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))

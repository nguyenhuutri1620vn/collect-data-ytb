"""Place confidence (FR-4.3, revised in D26): mention confidence x address factor x count factor.

- mention confidence: mean of the Gemini `confidence` of the place's mentions
- address factor: 1.0 when the mentions' addresses agree (or none is given); 0.7 when two of them
  name different addresses, which suggests the mentions may be different places (D26)
- count factor: 1 - 0.3^n, so one mention gives 0.7, two give 0.91

PUBLISH_THRESHOLD stays at 0.6. The 0.3 and the 0.7 are starting values, to be tuned later.
"""

from collections.abc import Iterable

from app.core.similarity import name_overlap

NO_CONFLICT_FACTOR = 1.0
CONFLICT_FACTOR = 0.7
_MISS_RATE = 0.3


def addresses_conflict(addresses: Iterable[str | None], threshold: float) -> bool:
    """True when two non-empty addresses share too few tokens (name_overlap below threshold)."""
    present = [a for a in addresses if a]
    return any(
        name_overlap(a, b) < threshold for i, a in enumerate(present) for b in present[i + 1 :]
    )


def count_factor(mention_count: int) -> float:
    if mention_count < 1:
        raise ValueError("a place needs at least one mention")
    return 1 - _MISS_RATE**mention_count


def place_confidence(mention_confidences: list[float], *, address_conflict: bool) -> float:
    if not mention_confidences:
        raise ValueError("a place needs at least one mention")
    mean = sum(mention_confidences) / len(mention_confidences)
    factor = CONFLICT_FACTOR if address_conflict else NO_CONFLICT_FACTOR
    return round(mean * factor * count_factor(len(mention_confidences)), 4)

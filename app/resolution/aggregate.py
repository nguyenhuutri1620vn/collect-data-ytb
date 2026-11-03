"""R4 aggregation (FR-4.3): the mentions of one place -> the aggregated fields of `places`.

Pure functions, no I/O. `confidence` is not computed here: its formula is fixed at M3 (FR-4.3).
"""

import re
import statistics
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.core.text import normalize_text

OUTLIER_RATIO = 3  # FR-4.3: drop prices further than 3x away from the median
MAX_SENTENCES = 10  # FR-4.3: highlights and tips per place
_URL_TYPES = frozenset({"website", "facebook", "instagram", "tiktok"})
_NON_DIGIT = re.compile(r"\D+")


@dataclass(frozen=True)
class MentionFacts:
    """What one mention says, as stored on `mentions` (no ORM here)."""

    video_id: str
    confidence: float
    price_min_vnd: int | None = None
    price_max_vnd: int | None = None
    price_unit: str | None = None
    time_slots: tuple[str, ...] = ()
    vibes: tuple[str, ...] = ()
    amenities: tuple[str, ...] = ()
    suitable_for: tuple[str, ...] = ()
    setting: str | None = None
    reservation_required: bool | None = None
    group_size_min: int | None = None
    group_size_max: int | None = None
    visit_duration_min_minutes: int | None = None
    visit_duration_max_minutes: int | None = None
    contacts: tuple[tuple[str, str], ...] = ()  # (type, value)
    highlights: tuple[str, ...] = ()
    tips: tuple[str, ...] = ()
    items: tuple[tuple[str, int | None], ...] = ()  # (name, price_vnd)


def _median(values: Iterable[int]) -> int | None:
    values = list(values)
    return round(statistics.median(values)) if values else None


def _without_outliers(values: list[int]) -> list[int]:
    """Keep values within [median / 3, median * 3]. With median 0 only zeros survive."""
    if not values:
        return []
    mid = statistics.median(values)
    return [v for v in values if mid / OUTLIER_RATIO <= v <= mid * OUTLIER_RATIO]


def _price(values: list[int | None]) -> int | None:
    return _median(_without_outliers([v for v in values if v is not None]))


def _most_common(values: Iterable[Any]) -> Any | None:
    """Most frequent non-null value. A tie gives None."""
    counts = Counter(v for v in values if v is not None).most_common()
    if not counts or (len(counts) > 1 and counts[0][1] == counts[1][1]):
        return None
    return counts[0][0]


def _setting(values: Iterable[str | None]) -> str | None:
    """Like _most_common, but a tie between indoor and outdoor means mixed (FR-4.3)."""
    counts = Counter(v for v in values if v is not None).most_common()
    if (
        len(counts) >= 2
        and counts[0][1] == counts[1][1]
        and {counts[0][0], counts[1][0]}
        == {
            "indoor",
            "outdoor",
        }
    ):
        return "mixed"
    return _most_common(values)


def _tag_fields(
    mentions: list[MentionFacts], attr: str, min_share: float
) -> tuple[list[str], dict[str, int]]:
    """(list, counts): values in at least `min_share` of the mentions that have the field, and
    the per-value mention counts."""
    having = [getattr(m, attr) for m in mentions if getattr(m, attr)]
    counts: Counter[str] = Counter()
    for values in having:
        counts.update(set(values))
    listed = sorted(v for v, n in counts.items() if n / len(having) >= min_share)
    return listed, dict(sorted(counts.items()))


def _contact_key(kind: str, value: str) -> str:
    if kind == "phone":
        return _NON_DIGIT.sub("", value)
    if kind in _URL_TYPES:
        return value.split("?", 1)[0].rstrip("/").strip()
    return value.strip()


def _contacts(mentions: list[MentionFacts]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], int] = {}
    for m in mentions:
        for kind, value in set(m.contacts):
            key = (kind, _contact_key(kind, value))
            merged[key] = merged.get(key, 0) + 1
    return [{"type": k, "value": v, "mentions": n} for (k, v), n in merged.items()]


def _sentences(mentions: list[MentionFacts], attr: str) -> list[dict[str, str]]:
    """Union of sentences, from the most confident mentions first, capped at MAX_SENTENCES."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for m in sorted(mentions, key=lambda m: -m.confidence):
        for text in getattr(m, attr):
            if text not in seen and len(out) < MAX_SENTENCES:
                seen.add(text)
                out.append({"text": text, "video_id": m.video_id})
    return out


def _items(mentions: list[MentionFacts]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    prices: dict[str, list[int]] = {}
    for m in mentions:
        for name, price in m.items:
            key = normalize_text(name)
            entry = grouped.setdefault(key, {"name": name, "mentions": 0})
            entry["mentions"] += 1
            if price is not None:
                prices.setdefault(key, []).append(price)
    return [{**entry, "price_vnd": _median(prices.get(key, []))} for key, entry in grouped.items()]


def aggregate_place(mentions: list[MentionFacts], *, attr_min_share: float = 0.3) -> dict[str, Any]:
    """Columns of `places` derived from its mentions (everything except confidence and status)."""
    if not mentions:
        raise ValueError("a place needs at least one mention")
    ordered = sorted(mentions, key=lambda m: -m.confidence)
    source_video_ids = list(dict.fromkeys(m.video_id for m in ordered))
    time_slots, time_slot_counts = _tag_fields(mentions, "time_slots", attr_min_share)
    vibes, vibe_counts = _tag_fields(mentions, "vibes", attr_min_share)
    amenities, amenity_counts = _tag_fields(mentions, "amenities", attr_min_share)
    suitable_for, suitable_for_counts = _tag_fields(mentions, "suitable_for", attr_min_share)
    return {
        "price_min_vnd": _price([m.price_min_vnd for m in mentions]),
        "price_max_vnd": _price([m.price_max_vnd for m in mentions]),
        "price_unit": _most_common(m.price_unit for m in mentions),
        "time_slots": time_slots,
        "time_slot_counts": time_slot_counts,
        "vibes": vibes,
        "vibe_counts": vibe_counts,
        "amenities": amenities,
        "amenity_counts": amenity_counts,
        "suitable_for": suitable_for,
        "suitable_for_counts": suitable_for_counts,
        "setting": _setting(m.setting for m in mentions),
        "reservation_required": _most_common(m.reservation_required for m in mentions),
        "group_size_min": _median(
            m.group_size_min for m in mentions if m.group_size_min is not None
        ),
        "group_size_max": _median(
            m.group_size_max for m in mentions if m.group_size_max is not None
        ),
        "visit_duration_min_minutes": _median(
            m.visit_duration_min_minutes
            for m in mentions
            if m.visit_duration_min_minutes is not None
        ),
        "visit_duration_max_minutes": _median(
            m.visit_duration_max_minutes
            for m in mentions
            if m.visit_duration_max_minutes is not None
        ),
        "contacts": _contacts(mentions),
        "highlights": _sentences(mentions, "highlights"),
        "tips": _sentences(mentions, "tips"),
        "items": _items(mentions),
        "mention_count": len(mentions),
        "source_video_ids": source_video_ids,
    }

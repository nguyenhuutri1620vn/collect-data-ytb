"""Eval metrics (FR-8.2): pure functions, no I/O.

Places are matched by name similarity; matched pairs are then compared field by field.
Each field is compared as a set of values, so scalar and list fields share one code path.
"""

from dataclasses import dataclass, field

from app.core.similarity import name_overlap
from app.core.text import normalize_text
from app.geo.aliases import resolve_legacy_district
from app.schemas.extraction import ExtractedPlace, VideoExtraction
from app.tags.normalize import to_slug

# Place-level fields compared on matched pairs. "name" is handled by matching, not here.
FIELDS = (
    "category",
    "price",
    "district",
    "setting",
    "time_slots",
    "suitable_for",
    "vibes",
    "amenities",
    "contacts",
)


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    hallucinated: int = 0  # prediction has a value where gold is empty
    gold_empty: int = 0  # gold has no value; denominator of the hallucination rate

    def add(self, other: "Counts") -> None:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn
        self.hallucinated += other.hallucinated
        self.gold_empty += other.gold_empty

    def precision(self) -> float | None:
        return _ratio(self.tp, self.tp + self.fp)

    def recall(self) -> float | None:
        return _ratio(self.tp, self.tp + self.fn)

    def hallucination_rate(self) -> float | None:
        return _ratio(self.hallucinated, self.gold_empty)


@dataclass
class VideoScore:
    relevant_ok: bool
    counts: dict[str, Counts] = field(default_factory=dict)


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def match_places(
    pred: list[ExtractedPlace], gold: list[ExtractedPlace], threshold: float
) -> list[tuple[int, int]]:
    """Greedy one-to-one matching, best similarity first. Returns (pred_index, gold_index)."""
    scored = sorted(
        (
            (name_overlap(p.name, g.name), i, j)
            for i, p in enumerate(pred)
            for j, g in enumerate(gold)
        ),
        key=lambda t: (-t[0], t[1], t[2]),
    )
    used_pred: set[int] = set()
    used_gold: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for score, i, j in scored:
        if score < threshold:
            break
        if i in used_pred or j in used_gold:
            continue
        used_pred.add(i)
        used_gold.add(j)
        pairs.append((i, j))
    return pairs


def field_values(place: ExtractedPlace) -> dict[str, set[str]]:
    """Comparable values per field. Empty set means no value."""
    has_price = place.price_min_vnd is not None or place.price_max_vnd is not None
    legacy = resolve_legacy_district(place.district_raw)
    return {
        "category": {place.category},
        "price": {f"{place.price_min_vnd}-{place.price_max_vnd}"} if has_price else set(),
        "district": {legacy} if legacy else set(),
        "setting": {place.setting} if place.setting else set(),
        "time_slots": set(place.time_slots),
        "suitable_for": set(place.suitable_for),
        "vibes": {to_slug(v) for v in place.vibes} - {""},
        "amenities": {to_slug(a) for a in place.amenities} - {""},
        "contacts": {f"{c.type}:{normalize_text(c.value)}" for c in place.contacts},
    }


def compare_fields(pred: ExtractedPlace, gold: ExtractedPlace) -> dict[str, Counts]:
    p_vals = field_values(pred)
    g_vals = field_values(gold)
    result: dict[str, Counts] = {}
    for name in FIELDS:
        p, g = p_vals[name], g_vals[name]
        result[name] = Counts(
            tp=len(p & g),
            fp=len(p - g),
            fn=len(g - p),
            hallucinated=1 if p and not g else 0,
            gold_empty=1 if not g else 0,
        )
    return result


def score_video(pred: VideoExtraction, gold: VideoExtraction, threshold: float) -> VideoScore:
    pred_places = pred.places if pred.is_relevant else []
    gold_places = gold.places if gold.is_relevant else []
    pairs = match_places(pred_places, gold_places, threshold)

    name = Counts(
        tp=len(pairs),
        fp=len(pred_places) - len(pairs),
        fn=len(gold_places) - len(pairs),
    )
    counts: dict[str, Counts] = {"name": name}
    for i, j in pairs:
        for key, c in compare_fields(pred_places[i], gold_places[j]).items():
            counts.setdefault(key, Counts()).add(c)
    return VideoScore(relevant_ok=pred.is_relevant == gold.is_relevant, counts=counts)


def aggregate(scores: list[VideoScore]) -> dict[str, Counts]:
    total: dict[str, Counts] = {}
    for score in scores:
        for key, c in score.counts.items():
            total.setdefault(key, Counts()).add(c)
    return total

"""R4 stage: mentions -> places (FR-4.1 to FR-4.4, D25, D26).

Derived data: every run recomputes all places from the current analyses, so it can be repeated
after a rule change without calling Gemini (CLAUDE.md, pipeline notes).
"""

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.text import normalize_text
from app.models import Mention, Place, Video
from app.resolution.aggregate import MentionFacts, aggregate_place
from app.resolution.confidence import addresses_conflict, place_confidence
from app.resolution.grouping import group_mentions

logger = logging.getLogger(__name__)


@dataclass
class ResolveReport:
    mentions: int
    places: int
    published: int
    draft: int


def _facts(m: Mention, video_id: str) -> MentionFacts:
    return MentionFacts(
        video_id=video_id,
        confidence=m.confidence or 0.0,
        price_min_vnd=m.price_min_vnd,
        price_max_vnd=m.price_max_vnd,
        price_unit=m.price_unit,
        time_slots=tuple(m.time_slots or ()),
        vibes=tuple(m.vibes or ()),
        amenities=tuple(m.amenities or ()),
        suitable_for=tuple(m.suitable_for or ()),
        setting=m.setting,
        reservation_required=m.reservation_required,
        group_size_min=m.group_size_min,
        group_size_max=m.group_size_max,
        visit_duration_min_minutes=m.visit_duration_min_minutes,
        visit_duration_max_minutes=m.visit_duration_max_minutes,
        contacts=tuple((c["type"], c["value"]) for c in m.contacts or []),
        highlights=tuple(m.highlights or ()),
        tips=tuple(m.tips or ()),
        items=tuple((i["name"], i.get("price_vnd")) for i in m.items or []),
    )


def _most_common(values: list[str]) -> str:
    """Most frequent value; ties go to the value that appears first (highest confidence)."""
    counts = Counter(values)
    best = max(counts.values())
    return next(v for v in values if counts[v] == best)


async def resolve_places(session: AsyncSession, settings: Settings) -> ResolveReport:
    rows = (
        await session.execute(
            select(Mention, Video.video_id)
            .join(Video, Video.current_analysis_fk == Mention.analysis_fk)
            .where(Video.status.in_(("analyzed", "resolved")))
            .order_by(Mention.id)
        )
    ).all()
    mentions = [m for m, _ in rows]
    video_ids = [vid for _, vid in rows]

    # Recompute from scratch: detach mentions, drop old places, then rebuild.
    await session.execute(update(Mention).values(place_fk=None))
    await session.execute(delete(Place))

    groups = group_mentions(
        [(m.name_raw, m.legacy_district) for m in mentions],
        threshold=settings.name_match_threshold,
    )
    published = draft = 0
    for group in groups:
        # Highest-confidence mention first, so the name and tie-breaks come from the best source.
        group.sort(key=lambda i: -(mentions[i].confidence or 0.0))
        members = [mentions[i] for i in group]
        facts = [_facts(mentions[i], video_ids[i]) for i in group]
        fields: dict[str, Any] = aggregate_place(facts)
        confidence = place_confidence(
            [f.confidence for f in facts],
            address_conflict=addresses_conflict(
                [m.address_raw for m in members], settings.name_match_threshold
            ),
        )
        district = members[0].legacy_district
        publish = district is not None and confidence >= settings.publish_threshold
        status = "published" if publish else "draft"
        published += publish
        draft += not publish

        place = Place(
            name=members[0].name_raw,
            name_normalized=normalize_text(members[0].name_raw),
            address_raw=next((m.address_raw for m in members if m.address_raw), None),
            legacy_district=district,
            category=_most_common([m.category for m in members]),
            sub_category=next((m.sub_category for m in members if m.sub_category), None),
            confidence=confidence,
            status=status,
            **fields,
        )
        session.add(place)
        await session.flush()
        for i in group:
            mentions[i].place_fk = place.id
            mentions[i].match_status = "unmatched"

    for vid in set(video_ids):
        await session.execute(
            update(Video)
            .where(Video.video_id == vid, Video.status == "analyzed")
            .values(status="resolved")
        )
    await session.flush()
    report = ResolveReport(len(mentions), len(groups), published, draft)
    logger.info("resolution done", extra={"places": report.places, "mentions": report.mentions})
    return report

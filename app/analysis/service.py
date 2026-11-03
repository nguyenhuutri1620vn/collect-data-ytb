"""R2 Analysis: one video -> Gemini -> validated extraction -> analyses + mentions."""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.gemini import GeminiQuotaExhausted, GeminiResult, VideoAnalyzer
from app.analysis.prompts import PROMPT_VERSION, build_prompt
from app.core.config import Settings
from app.core.quota import QuotaExceeded, add_usage, ensure_quota, quota_day
from app.core.text import normalize_text
from app.geo.aliases import resolve_legacy_district
from app.models import Analysis, Mention, Video
from app.schemas.extraction import SCHEMA_VERSION, ExtractedPlace, VideoExtraction
from app.tags.normalize import TagRegistry

logger = logging.getLogger(__name__)

MAX_SENTENCES = 5  # highlights / tips per mention (FR-2.4)


@dataclass
class AnalysisOutcome:
    status: str
    mention_count: int = 0
    analysis_id: int | None = None


class _InvalidOutput(Exception):
    pass


def _parse(text: str) -> tuple[dict, VideoExtraction]:
    try:
        raw = json.loads(text)
        return raw, VideoExtraction.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise _InvalidOutput(str(exc)) from exc


async def call_gemini(
    session: AsyncSession,
    analyzer: VideoAnalyzer,
    url: str,
    settings: Settings,
    now: datetime,
) -> GeminiResult:
    """One Gemini call behind the quota guard (shared by Analysis and eval)."""
    day = quota_day(now, settings.quota_timezone)
    safety = settings.quota_safety_ratio
    await ensure_quota(
        session, day, "gemini", "video_seconds",
        limit=settings.gemini_daily_video_seconds, safety_ratio=safety,
    )  # fmt: skip
    await ensure_quota(
        session, day, "gemini", "requests",
        limit=settings.gemini_daily_requests, safety_ratio=safety,
    )  # fmt: skip
    try:
        result = await analyzer.analyze(url, build_prompt())
    except GeminiQuotaExhausted as exc:
        raise QuotaExceeded(str(exc)) from exc
    await add_usage(session, day, "gemini", "requests", 1)
    await add_usage(session, day, "gemini", "video_seconds", result.video_seconds or 0)
    return result


async def _build_mention(
    registry: TagRegistry, video: Video, analysis: Analysis, ordinal: int, place: ExtractedPlace
) -> Mention:
    legacy_district = resolve_legacy_district(place.district_raw)
    return Mention(
        video_fk=video.id,
        analysis_fk=analysis.id,
        ordinal=ordinal,
        match_status="pending",
        name_raw=place.name,
        name_normalized=normalize_text(place.name),
        address_raw=place.address_raw,
        district_raw=place.district_raw,
        legacy_district=legacy_district,
        district_source="district_raw" if legacy_district else None,
        category=place.category,
        sub_category=place.sub_category,
        items=[i.model_dump() for i in place.items],
        price_min_vnd=place.price_min_vnd,
        price_max_vnd=place.price_max_vnd,
        price_unit=place.price_unit,
        time_slots=list(dict.fromkeys(place.time_slots)),
        opening_hours_raw=place.opening_hours_raw,
        vibes=await registry.normalize("vibe", place.vibes),
        amenities=await registry.normalize("amenity", place.amenities),
        suitable_for=list(dict.fromkeys(place.suitable_for)),
        group_size_min=place.group_size_min,
        group_size_max=place.group_size_max,
        setting=place.setting,
        visit_duration_min_minutes=place.visit_duration_min_minutes,
        visit_duration_max_minutes=place.visit_duration_max_minutes,
        reservation_required=place.reservation_required,
        contacts=[c.model_dump() for c in place.contacts],
        highlights=place.highlights[:MAX_SENTENCES],
        tips=place.tips[:MAX_SENTENCES],
        evidence=[e.model_dump() for e in place.evidence],
        confidence=place.confidence,
    )


async def analyze_video(
    session: AsyncSession,
    video: Video,
    analyzer: VideoAnalyzer,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> AnalysisOutcome:
    """Analyze one video and advance its status. Does not commit.

    Raises QuotaExceeded when the daily Gemini quota is (nearly) used up; the video is left
    untouched so the stage can resume on the next quota day.
    """
    now = now or datetime.now(UTC)
    log = {"video_id": video.video_id}
    try:
        result = await call_gemini(session, analyzer, video.url, settings, now)
        try:
            raw, extraction = _parse(result.text)
        except _InvalidOutput:
            logger.warning("invalid gemini output, calling again", extra=log)
            result = await call_gemini(session, analyzer, video.url, settings, now)
            raw, extraction = _parse(result.text)  # FR-2.2: one extra call, not a retry
    except QuotaExceeded:
        raise
    except _InvalidOutput as exc:
        video.status = "failed"
        video.error_message = f"output does not match schema v{SCHEMA_VERSION}: {exc}"[:2000]
        logger.error("gemini output invalid twice", extra=log)
        return AnalysisOutcome(status="failed")
    except Exception as exc:
        video.retry_count += 1
        video.error_message = f"{type(exc).__name__}: {exc}"[:2000]
        if video.retry_count >= settings.max_retries:
            video.status = "failed"
        logger.error("analysis failed", extra={**log, "retry_count": video.retry_count})
        return AnalysisOutcome(status=video.status)

    analysis = Analysis(
        video_fk=video.id,
        raw_output=raw,
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        model=result.model,
        media_resolution=result.media_resolution,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        video_seconds=result.video_seconds,
    )
    session.add(analysis)
    await session.flush()

    # FR-2.6: mentions from earlier analyses stay, but no longer belong to any place.
    await session.execute(
        update(Mention)
        .where(Mention.video_fk == video.id, Mention.analysis_fk != analysis.id)
        .values(place_fk=None)
    )

    registry = await TagRegistry.load(session)
    places = extraction.places if extraction.is_relevant else []
    for ordinal, place in enumerate(places):
        session.add(await _build_mention(registry, video, analysis, ordinal, place))

    video.current_analysis_fk = analysis.id
    video.is_relevant = extraction.is_relevant
    video.status = "analyzed" if places else "rejected"
    video.error_message = None
    await session.flush()
    logger.info(
        "video analyzed",
        extra={**log, "status": video.status, "mentions": len(places), "analysis_id": analysis.id},
    )
    return AnalysisOutcome(status=video.status, mention_count=len(places), analysis_id=analysis.id)

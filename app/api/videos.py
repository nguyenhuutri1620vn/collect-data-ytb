from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Analysis, Mention, Video

router = APIRouter()

_MENTION_FIELDS = (
    "ordinal", "match_status", "name_raw", "address_raw", "district_raw", "legacy_district",
    "district_source", "category", "sub_category", "items", "price_min_vnd", "price_max_vnd",
    "price_unit", "time_slots", "opening_hours_raw", "vibes", "amenities", "suitable_for",
    "group_size_min", "group_size_max", "setting", "visit_duration_min_minutes",
    "visit_duration_max_minutes", "reservation_required", "contacts", "highlights", "tips",
    "evidence", "confidence",
)  # fmt: skip


@router.get("/videos/{video_id}")
async def get_video(video_id: str, session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    """Ops view: status, every analysis run (raw output) and the current mentions."""
    video = await session.scalar(select(Video).where(Video.video_id == video_id))
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    analyses = (
        await session.scalars(
            select(Analysis).where(Analysis.video_fk == video.id).order_by(Analysis.id)
        )
    ).all()
    mentions = (
        await session.scalars(
            select(Mention)
            .where(Mention.analysis_fk == video.current_analysis_fk)
            .order_by(Mention.ordinal)
        )
    ).all()
    return {
        "video_id": video.video_id,
        "url": video.url,
        "status": video.status,
        "is_relevant": video.is_relevant,
        "retry_count": video.retry_count,
        "error_message": video.error_message,
        "analyses": [
            {
                "id": a.id,
                "created_at": a.created_at.isoformat(),
                "prompt_version": a.prompt_version,
                "schema_version": a.schema_version,
                "model": a.model,
                "media_resolution": a.media_resolution,
                "tokens_in": a.tokens_in,
                "tokens_out": a.tokens_out,
                "video_seconds": a.video_seconds,
                "raw_output": a.raw_output,
            }
            for a in analyses
        ],
        "mentions": [{f: getattr(m, f) for f in _MENTION_FIELDS} for m in mentions],
    }

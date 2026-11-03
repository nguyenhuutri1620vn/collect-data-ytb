"""Manually push YouTube URLs through Analysis (debug / experiments).

    python -m app.analysis.ingest URL [URL ...] [--reanalyze]

Each call to Gemini consumes real quota.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analysis.gemini import GeminiClient, VideoAnalyzer
from app.analysis.service import AnalysisOutcome, analyze_video
from app.core.config import Settings, get_settings
from app.core.db import create_engine
from app.core.logging import configure_logging
from app.core.quota import QuotaExceeded
from app.models import Mention, Video
from app.sources.youtube import canonical_url, parse_video_id

DONE_STATUSES = {"analyzed", "enriched", "resolved", "rejected"}


async def ingest_youtube(session: AsyncSession, url: str) -> Video:
    """Get or create the video row (idempotent on source + video_id, FR-1.4)."""
    video_id = parse_video_id(url)
    if video_id is None:
        raise ValueError(f"not a YouTube video URL: {url!r}")
    await session.execute(
        insert(Video)
        .values(source="youtube", video_id=video_id, url=canonical_url(video_id))
        .on_conflict_do_nothing(index_elements=["source", "video_id"])
    )
    return await session.scalar(
        select(Video).where(Video.source == "youtube", Video.video_id == video_id)
    )


async def ingest_and_analyze(
    session: AsyncSession,
    url: str,
    analyzer: VideoAnalyzer,
    settings: Settings,
    *,
    reanalyze: bool = False,
    now: datetime | None = None,
) -> tuple[Video, AnalysisOutcome | None]:
    """Analyze unless already done (outcome None).

    A manual run gives failed videos a fresh start.
    """
    video = await ingest_youtube(session, url)
    if video.status in DONE_STATUSES and not reanalyze:
        return video, None
    if video.status == "failed" or reanalyze:
        video.status, video.retry_count = "discovered", 0
    return video, await analyze_video(session, video, analyzer, settings, now=now)


async def _summary(session: AsyncSession, video: Video) -> dict:
    mentions = (
        await session.scalars(
            select(Mention)
            .where(Mention.analysis_fk == video.current_analysis_fk)
            .order_by(Mention.ordinal)
        )
    ).all()
    return {
        "video_id": video.video_id,
        "status": video.status,
        "error": video.error_message,
        "places": [
            {
                "name": m.name_raw,
                "category": m.category,
                "sub_category": m.sub_category,
                "address_raw": m.address_raw,
                "district_raw": m.district_raw,
                "legacy_district": m.legacy_district,
                "price_vnd": [m.price_min_vnd, m.price_max_vnd, m.price_unit],
                "time_slots": m.time_slots,
                "vibes": m.vibes,
                "amenities": m.amenities,
                "suitable_for": m.suitable_for,
                "setting": m.setting,
                "contacts": m.contacts,
                "tips": m.tips,
                "evidence": len(m.evidence),
                "confidence": m.confidence,
            }
            for m in mentions
        ],
    }


async def _run(urls: list[str], reanalyze: bool) -> int:
    settings = get_settings()
    analyzer = GeminiClient.from_settings(settings)
    engine = create_engine(settings.database_url)
    exit_code = 0
    try:
        for url in urls:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                try:
                    video, _ = await ingest_and_analyze(
                        session, url, analyzer, settings, reanalyze=reanalyze
                    )
                except QuotaExceeded as exc:
                    print(json.dumps({"url": url, "stopped": f"quota: {exc}"}, ensure_ascii=False))
                    return 2
                except ValueError as exc:
                    print(json.dumps({"url": url, "error": str(exc)}, ensure_ascii=False))
                    exit_code = 1
                    continue
                await session.commit()
                print(json.dumps(await _summary(session, video), ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()
    return exit_code


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="python -m app.analysis.ingest")
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--reanalyze", action="store_true", help="analyze again (calls Gemini)")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args.urls, args.reanalyze))


if __name__ == "__main__":
    sys.exit(main())

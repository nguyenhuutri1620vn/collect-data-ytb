from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.quota import QuotaExceeded, add_usage, ensure_quota, get_usage, quota_day


def test_quota_day_uses_quota_timezone() -> None:
    # 2026-11-03 03:00 UTC is still 2026-11-02 in Los Angeles.
    now = datetime(2026, 11, 3, 3, 0, tzinfo=UTC)
    assert quota_day(now, "America/Los_Angeles") == date(2026, 11, 2)


async def test_add_usage_accumulates(session: AsyncSession) -> None:
    day = date(2026, 11, 2)
    await add_usage(session, day, "gemini", "video_seconds", 40)
    await add_usage(session, day, "gemini", "video_seconds", 2)

    assert await get_usage(session, day, "gemini", "video_seconds") == 42
    assert await get_usage(session, day, "gemini", "requests") == 0


async def test_ensure_quota_stops_near_limit(session: AsyncSession) -> None:
    day = date(2026, 11, 2)
    await add_usage(session, day, "gemini", "video_seconds", 90)

    await ensure_quota(session, day, "gemini", "video_seconds", limit=101, safety_ratio=0.9)
    with pytest.raises(QuotaExceeded):
        await ensure_quota(session, day, "gemini", "video_seconds", limit=100, safety_ratio=0.9)
    # No configured limit means no check.
    await ensure_quota(session, day, "gemini", "video_seconds", limit=None, safety_ratio=0.9)

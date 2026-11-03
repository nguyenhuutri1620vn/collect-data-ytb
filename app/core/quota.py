"""Daily quota accounting (FR-7.2, FR-7.3). Quota days use QUOTA_TIMEZONE."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QuotaUsage


class QuotaExceeded(Exception):
    pass


def quota_day(now: datetime, tz: str) -> date:
    return now.astimezone(ZoneInfo(tz)).date()


async def get_usage(session: AsyncSession, day: date, service: str, metric: str) -> int:
    value = await session.scalar(
        select(QuotaUsage.value).where(
            QuotaUsage.date == day, QuotaUsage.service == service, QuotaUsage.metric == metric
        )
    )
    return value or 0


async def add_usage(
    session: AsyncSession, day: date, service: str, metric: str, amount: int
) -> None:
    stmt = insert(QuotaUsage).values(date=day, service=service, metric=metric, value=amount)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["date", "service", "metric"],
            set_={"value": QuotaUsage.value + stmt.excluded.value},
        )
    )


async def ensure_quota(
    session: AsyncSession,
    day: date,
    service: str,
    metric: str,
    *,
    limit: int | None,
    safety_ratio: float,
) -> None:
    """Raise QuotaExceeded once usage reaches limit * safety_ratio; no limit means no check."""
    if limit is None:
        return
    used = await get_usage(session, day, service, metric)
    if used >= limit * safety_ratio:
        raise QuotaExceeded(f"{service}.{metric}: {used} of {limit} used on {day}")

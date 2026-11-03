from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.gemini import GeminiQuotaExhausted
from app.analysis.service import analyze_video
from app.core.config import Settings
from app.core.quota import QuotaExceeded, add_usage, get_usage, quota_day
from app.models import Analysis, Mention, Place, Video
from tests.fakes import FakeAnalyzer, gemini_fixture

NOW = datetime(2026, 11, 3, 5, 0, tzinfo=UTC)
TWO_PLACES = gemini_fixture("two_places.json")
NOT_RELEVANT = gemini_fixture("not_relevant.json")


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, database_url="postgresql+asyncpg://unused/x", max_retries=2)


@pytest.fixture
async def video(session: AsyncSession) -> Video:
    v = Video(video_id="abc123xyz00", url="https://www.youtube.com/watch?v=abc123xyz00")
    session.add(v)
    await session.flush()
    return v


async def mentions_of(session: AsyncSession, video: Video) -> list[Mention]:
    stmt = select(Mention).where(Mention.video_fk == video.id).order_by(Mention.id)
    return list((await session.scalars(stmt)).all())


async def test_analyzed_video_stores_analysis_and_mentions(
    session: AsyncSession, video: Video, settings: Settings
) -> None:
    analyzer = FakeAnalyzer(TWO_PLACES)

    outcome = await analyze_video(session, video, analyzer, settings, now=NOW)

    assert outcome.status == "analyzed"
    assert outcome.mention_count == 2
    assert analyzer.calls[0][0] == "https://www.youtube.com/watch?v=abc123xyz00"
    assert video.status == "analyzed"
    assert video.is_relevant is True

    analysis = await session.get(Analysis, video.current_analysis_fk)
    assert analysis.prompt_version == "1"
    assert analysis.schema_version == "1"
    assert analysis.model == "gemini-fake"
    assert analysis.media_resolution == "low"
    assert (analysis.tokens_in, analysis.tokens_out, analysis.video_seconds) == (1000, 200, 45)
    assert analysis.raw_output["places"][0]["vibes"] == ["Bình dân", "check-in"]

    first, second = await mentions_of(session, video)
    assert (first.analysis_fk, first.ordinal, second.ordinal) == (analysis.id, 0, 1)
    assert first.name_raw == "Quán Bánh Tráng Cô Ba"
    assert first.name_normalized == "quan banh trang co ba"
    assert first.match_status == "pending"
    assert (first.legacy_district, first.district_source) == ("Quận 3", "district_raw")
    assert (first.price_min_vnd, first.price_max_vnd, first.price_unit) == (
        20000,
        35000,
        "per_item",
    )
    assert first.vibes == ["binh_dan", "song_ao"]
    assert first.amenities == ["wifi"]
    assert first.items == [{"name": "bánh tráng trộn", "price_vnd": 25000}]
    assert first.contacts == [{"type": "phone", "value": "0901 234 567"}]
    assert first.evidence[0]["timestamp"] == "00:05"
    assert first.confidence == 0.9
    assert second.vibes == ["thu_gian", "lang_man"]
    assert (second.legacy_district, second.price_unit) == ("Bình Thạnh", None)

    day = quota_day(NOW, settings.quota_timezone)
    assert await get_usage(session, day, "gemini", "requests") == 1
    assert await get_usage(session, day, "gemini", "video_seconds") == 45


async def test_unresolved_district_has_no_source(
    session: AsyncSession, video: Video, settings: Settings
) -> None:
    text = TWO_PLACES.replace('"district_raw": "Q.3"', '"district_raw": "gần chợ Bến Thành"')

    await analyze_video(session, video, FakeAnalyzer(text), settings, now=NOW)

    first, _ = await mentions_of(session, video)
    assert (first.district_raw, first.legacy_district, first.district_source) == (
        "gần chợ Bến Thành",
        None,
        None,
    )


async def test_not_relevant_video_is_rejected(
    session: AsyncSession, video: Video, settings: Settings
) -> None:
    outcome = await analyze_video(session, video, FakeAnalyzer(NOT_RELEVANT), settings, now=NOW)

    assert outcome.status == "rejected"
    assert (video.status, video.is_relevant) == ("rejected", False)
    assert video.current_analysis_fk is not None
    assert await mentions_of(session, video) == []


async def test_relevant_without_places_is_rejected(
    session: AsyncSession, video: Video, settings: Settings
) -> None:
    text = NOT_RELEVANT.replace('"is_relevant": false', '"is_relevant": true')

    outcome = await analyze_video(session, video, FakeAnalyzer(text), settings, now=NOW)

    assert outcome.status == "rejected"
    assert video.is_relevant is True


async def test_invalid_output_is_retried_once(
    session: AsyncSession, video: Video, settings: Settings
) -> None:
    analyzer = FakeAnalyzer('{"is_relevant": "maybe"}', TWO_PLACES)

    outcome = await analyze_video(session, video, analyzer, settings, now=NOW)

    assert outcome.status == "analyzed"
    assert len(analyzer.calls) == 2
    assert video.retry_count == 0
    day = quota_day(NOW, settings.quota_timezone)
    assert await get_usage(session, day, "gemini", "requests") == 2


async def test_invalid_output_twice_fails(
    session: AsyncSession, video: Video, settings: Settings
) -> None:
    outcome = await analyze_video(session, video, FakeAnalyzer("not json", "{}"), settings, now=NOW)

    assert outcome.status == "failed"
    assert video.status == "failed"
    assert "schema" in video.error_message
    assert video.current_analysis_fk is None


async def test_call_error_counts_retry_then_fails(
    session: AsyncSession, video: Video, settings: Settings
) -> None:
    first = await analyze_video(
        session, video, FakeAnalyzer(RuntimeError("boom")), settings, now=NOW
    )
    assert (first.status, video.status, video.retry_count) == ("discovered", "discovered", 1)
    assert "boom" in video.error_message

    second = await analyze_video(
        session, video, FakeAnalyzer(RuntimeError("boom")), settings, now=NOW
    )
    assert (second.status, video.status, video.retry_count) == ("failed", "failed", 2)


async def test_daily_quota_exhausted_does_not_count_retry(
    session: AsyncSession, video: Video, settings: Settings
) -> None:
    analyzer = FakeAnalyzer(GeminiQuotaExhausted("per day"))

    with pytest.raises(QuotaExceeded):
        await analyze_video(session, video, analyzer, settings, now=NOW)
    assert (video.status, video.retry_count) == ("discovered", 0)


async def test_quota_guard_blocks_before_call(
    session: AsyncSession, video: Video, settings: Settings
) -> None:
    day = quota_day(NOW, settings.quota_timezone)
    await add_usage(session, day, "gemini", "video_seconds", settings.gemini_daily_video_seconds)
    analyzer = FakeAnalyzer(TWO_PLACES)

    with pytest.raises(QuotaExceeded):
        await analyze_video(session, video, analyzer, settings, now=NOW)
    assert analyzer.calls == []


async def test_reanalysis_detaches_old_mentions_from_places(
    session: AsyncSession, video: Video, settings: Settings
) -> None:
    await analyze_video(session, video, FakeAnalyzer(TWO_PLACES), settings, now=NOW)
    place = Place(name="Cafe Mây", name_normalized="cafe may", category="uong")
    session.add(place)
    await session.flush()
    old = await mentions_of(session, video)
    for m in old:
        m.place_fk = place.id
    await session.flush()
    first_analysis = video.current_analysis_fk

    await analyze_video(session, video, FakeAnalyzer(TWO_PLACES), settings, now=NOW)

    assert video.current_analysis_fk != first_analysis
    all_mentions = await mentions_of(session, video)
    assert len(all_mentions) == 4
    for m in all_mentions:
        await session.refresh(m)
    assert all(m.place_fk is None for m in all_mentions)

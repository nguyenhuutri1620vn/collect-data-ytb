from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.ingest import ingest_and_analyze
from app.core.config import Settings
from app.models import Mention, Place
from app.resolution.stage import resolve_places
from tests.fakes import FakeAnalyzer, gemini_fixture

NOW = datetime(2026, 11, 3, 5, 0, tzinfo=UTC)
URL_A = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
URL_B = "https://www.youtube.com/shorts/aaaaaaaaaaa"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://unused/x",
        admin_token="t",
        max_retries=2,
    )


async def test_resolve_builds_one_place_per_mention_and_publishes_by_confidence(
    session: AsyncSession,
) -> None:
    settings = _settings()
    analyzer = FakeAnalyzer(gemini_fixture("two_places.json"))
    await ingest_and_analyze(session, URL_A, analyzer, settings, now=NOW)

    report = await resolve_places(session, settings)

    assert (report.mentions, report.places) == (2, 2)
    places = {p.name: p for p in (await session.scalars(select(Place))).all()}
    banh_trang = places["Quán Bánh Tráng Cô Ba"]
    cafe = places["Cafe Mây"]
    # one mention at 0.9 with no address conflict -> 0.63, published
    assert (banh_trang.confidence, banh_trang.status) == (0.63, "published")
    assert banh_trang.legacy_district == "Quận 3"
    assert banh_trang.mention_count == 1
    # one mention at 0.7 -> 0.49, stays draft
    assert (cafe.confidence, cafe.status) == (0.49, "draft")
    assert cafe.legacy_district == "Bình Thạnh"

    linked = (await session.scalars(select(Mention).where(Mention.place_fk.is_not(None)))).all()
    assert len(linked) == 2 and {m.match_status for m in linked} == {"unmatched"}


async def test_second_video_with_same_places_merges_them(session: AsyncSession) -> None:
    settings = _settings()
    await ingest_and_analyze(
        session, URL_A, FakeAnalyzer(gemini_fixture("two_places.json")), settings, now=NOW
    )
    await ingest_and_analyze(
        session, URL_B, FakeAnalyzer(gemini_fixture("two_places.json")), settings, now=NOW
    )

    report = await resolve_places(session, settings)

    assert (report.mentions, report.places) == (4, 2)
    places = (await session.scalars(select(Place))).all()
    assert {p.mention_count for p in places} == {2}
    assert sorted(len(p.source_video_ids) for p in places) == [2, 2]
    # two mentions: 0.9 -> 0.9 * 1.0 * 0.91 = 0.819 published; 0.7 -> 0.637 published
    assert sorted(p.confidence for p in places) == [0.637, 0.819]


async def test_resolve_is_repeatable_without_duplicating_places(session: AsyncSession) -> None:
    settings = _settings()
    await ingest_and_analyze(
        session, URL_A, FakeAnalyzer(gemini_fixture("two_places.json")), settings, now=NOW
    )
    await resolve_places(session, settings)
    again = await resolve_places(session, settings)

    assert again.places == 2
    assert len((await session.scalars(select(Place))).all()) == 2

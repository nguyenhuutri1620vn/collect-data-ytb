from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.ingest import ingest_and_analyze
from app.core.config import Settings
from app.resolution.stage import resolve_places
from tests.fakes import FakeAnalyzer, gemini_fixture

NOW = datetime(2026, 11, 3, 5, 0, tzinfo=UTC)
URL = "https://www.youtube.com/shorts/dQw4w9WgXcQ"


async def test_output_views_expose_only_published_places(session: AsyncSession) -> None:
    settings = Settings(
        _env_file=None, database_url="postgresql+asyncpg://unused/x", admin_token="t", max_retries=2
    )
    await ingest_and_analyze(
        session, URL, FakeAnalyzer(gemini_fixture("two_places.json")), settings, now=NOW
    )
    await resolve_places(session, settings)

    names = [r.name for r in await session.execute(text("select name from output.places"))]
    assert names == ["Quán Bánh Tráng Cô Ba"]  # the other place is a draft (confidence 0.49)

    columns = {
        r.column_name
        for r in await session.execute(
            text(
                "select column_name from information_schema.columns "
                "where table_schema = 'output' and table_name = 'places'"
            )
        )
    }
    assert not columns & {"google_place_id", "closed_permanently", "status", "raw_output"}
    assert "maps_url" not in columns


async def test_media_links_carry_evidence_seconds(session: AsyncSession) -> None:
    settings = Settings(
        _env_file=None, database_url="postgresql+asyncpg://unused/x", admin_token="t", max_retries=2
    )
    await ingest_and_analyze(
        session, URL, FakeAnalyzer(gemini_fixture("two_places.json")), settings, now=NOW
    )
    await resolve_places(session, settings)

    links = [
        r.video_url for r in await session.execute(text("select video_url from output.place_media"))
    ]
    # fixture evidence for the published place is at 00:05 -> &t=5
    assert links == ["https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=5"]


async def test_reader_role_can_read_views_but_not_base_tables(session: AsyncSession) -> None:
    async def can(obj: str) -> bool:
        return bool(
            await session.scalar(
                text("select has_table_privilege('output_reader', :obj, 'SELECT')"), {"obj": obj}
            )
        )

    assert await can("output.places")
    assert not await can("public.places")
    assert not await can("public.mentions")
    version = await session.scalar(
        text(
            "select obj_description(oid, 'pg_namespace') from pg_namespace where nspname = 'output'"
        )
    )
    assert version == "OUTPUT_VERSION=1"

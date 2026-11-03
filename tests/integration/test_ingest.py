from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.ingest import ingest_and_analyze, ingest_youtube
from app.core.config import Settings
from app.core.db import get_session
from app.main import create_app
from app.models import Video
from tests.fakes import FakeAnalyzer, gemini_fixture

URL = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
NOW = datetime(2026, 11, 3, 5, 0, tzinfo=UTC)
TOKEN = "test-admin-token"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://unused/x",
        admin_token=TOKEN,
        max_retries=2,
    )


async def test_ingest_is_idempotent(session: AsyncSession) -> None:
    first = await ingest_youtube(session, URL)
    second = await ingest_youtube(session, "https://youtu.be/dQw4w9WgXcQ")

    assert first.id == second.id
    assert first.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert (first.source, first.status) == ("youtube", "discovered")
    count = await session.scalar(select(func.count()).select_from(Video))
    assert count == 1


async def test_ingest_rejects_non_youtube(session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="YouTube"):
        await ingest_youtube(session, "https://www.tiktok.com/@a/video/123")


async def test_ingest_and_analyze_skips_done_video_unless_reanalyze(
    session: AsyncSession, settings: Settings
) -> None:
    analyzer = FakeAnalyzer(gemini_fixture("two_places.json"), gemini_fixture("two_places.json"))

    video, outcome = await ingest_and_analyze(session, URL, analyzer, settings, now=NOW)
    assert outcome is not None and outcome.status == "analyzed"

    _, skipped = await ingest_and_analyze(session, URL, analyzer, settings, now=NOW)
    assert skipped is None
    assert len(analyzer.calls) == 1

    _, again = await ingest_and_analyze(session, URL, analyzer, settings, reanalyze=True, now=NOW)
    assert again is not None and again.status == "analyzed"
    assert len(analyzer.calls) == 2


async def test_failed_video_is_retried_on_manual_ingest(
    session: AsyncSession, settings: Settings
) -> None:
    video = await ingest_youtube(session, URL)
    video.status, video.retry_count = "failed", 2
    analyzer = FakeAnalyzer(gemini_fixture("not_relevant.json"))

    _, outcome = await ingest_and_analyze(session, URL, analyzer, settings, now=NOW)

    assert outcome is not None and outcome.status == "rejected"
    assert video.retry_count == 0


@pytest.fixture
async def api(
    session: AsyncSession, settings: Settings
) -> AsyncIterator[tuple[httpx.AsyncClient, FakeAnalyzer]]:
    app = create_app(settings)
    analyzer = FakeAnalyzer(gemini_fixture("two_places.json"))

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    async with app.router.lifespan_context(app):
        app.state.analyzer = analyzer
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, analyzer


async def test_post_ingest_requires_token(api: tuple[httpx.AsyncClient, FakeAnalyzer]) -> None:
    client, analyzer = api

    missing = await client.post("/ingest/youtube", json={"url": URL})
    wrong = await client.post(
        "/ingest/youtube", json={"url": URL}, headers={"Authorization": "Bearer nope"}
    )

    assert (missing.status_code, wrong.status_code) == (401, 401)
    assert analyzer.calls == []


async def test_post_ingest_analyzes_and_get_video_shows_result(
    api: tuple[httpx.AsyncClient, FakeAnalyzer],
) -> None:
    client, _ = api
    auth = {"Authorization": f"Bearer {TOKEN}"}

    response = await client.post("/ingest/youtube", json={"url": URL}, headers=auth)
    assert response.status_code == 200
    assert response.json() == {"video_id": "dQw4w9WgXcQ", "status": "analyzed", "mention_count": 2}

    detail = await client.get("/videos/dQw4w9WgXcQ")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "analyzed"
    assert len(body["analyses"]) == 1
    assert body["analyses"][0]["prompt_version"] == "1"
    assert body["analyses"][0]["raw_output"]["is_relevant"] is True
    assert [m["name_raw"] for m in body["mentions"]] == ["Quán Bánh Tráng Cô Ba", "Cafe Mây"]
    assert body["mentions"][0]["legacy_district"] == "Quận 3"


async def test_post_ingest_bad_url_is_400(api: tuple[httpx.AsyncClient, FakeAnalyzer]) -> None:
    client, _ = api

    response = await client.post(
        "/ingest/youtube",
        json={"url": "https://example.com/x"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 400


async def test_get_unknown_video_is_404(api: tuple[httpx.AsyncClient, FakeAnalyzer]) -> None:
    client, _ = api

    assert (await client.get("/videos/zzzzzzzzzzz")).status_code == 404

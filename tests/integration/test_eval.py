import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.eval.runner import build_report, format_summary, load_gold, run_eval, write_report
from app.schemas.extraction import VideoExtraction
from tests.fakes import FakeAnalyzer, gemini_fixture

NOW = datetime(2026, 11, 3, 5, 0, tzinfo=UTC)
GOLD_ID = "dQw4w9WgXcQ"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://unused/x",
        gemini_daily_requests=100,
        gemini_daily_video_seconds=10_000_000,
    )


def _factory(session: AsyncSession) -> Callable[[], AsyncIterator[AsyncSession]]:
    """Hands out the test session without closing it (the fixture owns its transaction)."""

    @asynccontextmanager
    async def make() -> AsyncIterator[AsyncSession]:
        yield session

    return make


def _write_gold(gold_dir: Path, video_id: str = GOLD_ID) -> None:
    gold_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(gemini_fixture("two_places.json"))
    data["places"] = data["places"][:1]  # gold has one place, prediction has two
    (gold_dir / f"{video_id}.json").write_text(json.dumps(data, ensure_ascii=False))


def test_load_gold_reads_one_file_per_video(tmp_path: Path) -> None:
    _write_gold(tmp_path)
    items = load_gold(tmp_path)

    assert [i.video_id for i in items] == [GOLD_ID]
    assert items[0].url == f"https://www.youtube.com/watch?v={GOLD_ID}"
    assert isinstance(items[0].label, VideoExtraction)


async def test_run_eval_scores_predictions_and_reports(
    session: AsyncSession, tmp_path: Path
) -> None:
    _write_gold(tmp_path / "gold")
    gold = load_gold(tmp_path / "gold")
    analyzer = FakeAnalyzer(gemini_fixture("two_places.json"))

    run = await run_eval(gold, analyzer, _factory(session), _settings(), threshold=0.8, now=NOW)
    report = build_report(run, _settings(), threshold=0.8, now=NOW)
    path = write_report(report, tmp_path / "reports", NOW)

    assert run.stopped is None and run.errors == []
    assert analyzer.calls[0][0] == f"https://www.youtube.com/watch?v={GOLD_ID}"
    assert report["scored_videos"] == 1
    assert report["metrics"]["name"]["tp"] == 1
    assert report["metrics"]["name"]["fp"] == 1  # the second predicted place has no gold
    assert report["prompt_version"] == "1" and report["schema_version"] == "1"
    assert path.exists()
    assert "precision" in format_summary(report)


async def test_invalid_output_is_counted_not_skipped(session: AsyncSession, tmp_path: Path) -> None:
    _write_gold(tmp_path / "gold")
    run = await run_eval(
        load_gold(tmp_path / "gold"),
        FakeAnalyzer("not json"),
        _factory(session),
        _settings(),
        threshold=0.8,
        now=NOW,
    )

    assert run.invalid_outputs == 1
    assert len(run.scores) == 1
    assert run.scores[0].counts["name"].fn == 1

"""Test doubles for external clients (no real API calls in tests, hard rule 3)."""

import json
from pathlib import Path

from app.analysis.gemini import GeminiResult

GEMINI_FIXTURES = Path(__file__).parent / "fixtures" / "gemini"


def gemini_fixture(name: str) -> str:
    return (GEMINI_FIXTURES / name).read_text()


class FakeAnalyzer:
    """Returns queued texts (or raises queued exceptions) in order."""

    model = "gemini-fake"
    media_resolution = "low"

    def __init__(self, *outcomes: str | Exception, video_seconds: int | None = 45) -> None:
        self.outcomes = list(outcomes)
        self.video_seconds = video_seconds
        self.calls: list[tuple[str, str]] = []

    async def analyze(self, video_url: str, prompt: str) -> GeminiResult:
        self.calls.append((video_url, prompt))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return GeminiResult(
            text=outcome,
            model=self.model,
            media_resolution=self.media_resolution,
            tokens_in=1000,
            tokens_out=200,
            video_seconds=self.video_seconds,
        )


def as_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)

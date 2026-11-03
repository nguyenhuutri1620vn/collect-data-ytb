from types import SimpleNamespace

import pytest
from google.genai import errors, types

from app.analysis.gemini import GeminiClient, GeminiQuotaExhausted, estimate_video_seconds
from app.schemas.extraction import VideoExtraction

URL = "https://www.youtube.com/watch?v=abc123"


def usage(
    audio: int | None = None, video: int | None = None
) -> types.GenerateContentResponseUsageMetadata:
    details = []
    if audio is not None:
        details.append(
            types.ModalityTokenCount(modality=types.MediaModality.AUDIO, token_count=audio)
        )
    if video is not None:
        details.append(
            types.ModalityTokenCount(modality=types.MediaModality.VIDEO, token_count=video)
        )
    return types.GenerateContentResponseUsageMetadata(
        prompt_token_count=1000, candidates_token_count=200, prompt_tokens_details=details
    )


class FakeModels:
    def __init__(self, outcomes: list) -> None:
        self.outcomes = outcomes
        self.calls: list[dict] = []

    async def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def fake_client(outcomes: list) -> tuple[GeminiClient, FakeModels]:
    models = FakeModels(outcomes)
    sdk = SimpleNamespace(aio=SimpleNamespace(models=models))
    client = GeminiClient(
        sdk, model="gemini-test", media_resolution="low", max_retries=2, sleep=lambda _: _noop()
    )
    return client, models


async def _noop() -> None:
    return None


def response(text: str = '{"is_relevant": false, "video_summary": "x", "places": []}') -> object:
    return SimpleNamespace(text=text, usage_metadata=usage(audio=32 * 45))


def api_error(code: int, message: str) -> errors.APIError:
    cls = errors.ClientError if code < 500 else errors.ServerError
    return cls(code, {"error": {"code": code, "message": message, "status": "X"}})


async def test_request_puts_video_before_prompt_with_schema() -> None:
    client, models = fake_client([response()])

    result = await client.analyze(URL, "PROMPT")

    call = models.calls[0]
    parts = call["contents"].parts
    assert parts[0].file_data.file_uri == URL
    assert parts[1].text == "PROMPT"
    config = call["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is VideoExtraction
    assert config.media_resolution == types.MediaResolution.MEDIA_RESOLUTION_LOW
    assert call["model"] == "gemini-test"
    assert result.text.startswith('{"is_relevant"')
    assert (result.tokens_in, result.tokens_out, result.video_seconds) == (1000, 200, 45)
    assert (result.model, result.media_resolution) == ("gemini-test", "low")


async def test_retries_server_error_then_succeeds() -> None:
    client, models = fake_client([api_error(503, "overloaded"), response()])

    await client.analyze(URL, "PROMPT")

    assert len(models.calls) == 2


async def test_gives_up_after_max_retries() -> None:
    client, models = fake_client([api_error(500, "boom")] * 3)

    with pytest.raises(errors.ServerError):
        await client.analyze(URL, "PROMPT")
    assert len(models.calls) == 3


async def test_daily_quota_429_is_not_retried() -> None:
    client, models = fake_client(
        [
            api_error(
                429, "Quota exceeded for metric: generate_content_free_tier_requests, limit per day"
            )
        ]
    )

    with pytest.raises(GeminiQuotaExhausted):
        await client.analyze(URL, "PROMPT")
    assert len(models.calls) == 1


async def test_client_error_is_not_retried() -> None:
    client, models = fake_client([api_error(400, "bad request")])

    with pytest.raises(errors.ClientError):
        await client.analyze(URL, "PROMPT")
    assert len(models.calls) == 1


def test_estimate_video_seconds() -> None:
    assert estimate_video_seconds(usage(audio=32 * 60), "low") == 60
    assert estimate_video_seconds(usage(video=66 * 30), "low") == 30
    assert estimate_video_seconds(usage(video=258 * 10), "default") == 10
    assert estimate_video_seconds(usage(), "low") is None
    assert estimate_video_seconds(None, "low") is None

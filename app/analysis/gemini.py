"""Thin Gemini client: reads a YouTube video by URL (C2) and returns the raw JSON text."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from google import genai
from google.genai import errors, types

from app.core.config import Settings
from app.schemas.extraction import VideoExtraction

logger = logging.getLogger(__name__)

# Token rates used to estimate processed video length (C4 tracks seconds per quota day).
AUDIO_TOKENS_PER_SECOND = 32
FRAME_TOKENS = {"low": 66, "default": 258}  # one frame per second

_MEDIA_RESOLUTION = {
    "low": types.MediaResolution.MEDIA_RESOLUTION_LOW,
    "default": None,
}


class GeminiQuotaExhausted(Exception):
    """429 for an exhausted daily quota: stop the stage, not the record's fault (FR-7.4)."""


@dataclass
class GeminiResult:
    text: str
    model: str
    media_resolution: str
    tokens_in: int | None
    tokens_out: int | None
    video_seconds: int | None


class VideoAnalyzer(Protocol):
    model: str
    media_resolution: str

    async def analyze(self, video_url: str, prompt: str) -> GeminiResult: ...


def estimate_video_seconds(
    usage: types.GenerateContentResponseUsageMetadata | None, media_resolution: str
) -> int | None:
    if usage is None:
        return None
    counts = {d.modality: d.token_count or 0 for d in usage.prompt_tokens_details or []}
    if counts.get(types.MediaModality.AUDIO):
        return round(counts[types.MediaModality.AUDIO] / AUDIO_TOKENS_PER_SECOND)
    if counts.get(types.MediaModality.VIDEO):
        return round(counts[types.MediaModality.VIDEO] / FRAME_TOKENS[media_resolution])
    return None


def _is_daily_quota(exc: errors.APIError) -> bool:
    message = (exc.message or "").lower().replace(" ", "")
    return exc.code == 429 and ("perday" in message or "daily" in message)


def _is_retryable(exc: errors.APIError) -> bool:
    return exc.code == 429 or (exc.code or 0) >= 500


class GeminiClient:
    def __init__(
        self,
        sdk: Any,
        *,
        model: str,
        media_resolution: str,
        max_retries: int,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._sdk = sdk
        self.model = model
        self.media_resolution = media_resolution
        self._max_retries = max_retries
        self._sleep = sleep

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiClient":
        if settings.gemini_api_key is None:
            raise RuntimeError("GEMINI_API_KEY is not set")
        sdk = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
        return cls(
            sdk,
            model=settings.gemini_model,
            media_resolution=settings.gemini_media_resolution,
            max_retries=settings.max_retries,
        )

    async def analyze(self, video_url: str, prompt: str) -> GeminiResult:
        contents = types.Content(
            role="user",
            parts=[
                types.Part(file_data=types.FileData(file_uri=video_url)),
                types.Part(text=prompt),
            ],
        )
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=VideoExtraction,
            media_resolution=_MEDIA_RESOLUTION[self.media_resolution],
            temperature=0,
        )
        attempt = 0
        while True:
            try:
                response = await self._sdk.aio.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
                break
            except errors.APIError as exc:
                if _is_daily_quota(exc):
                    raise GeminiQuotaExhausted(exc.message) from exc
                if not _is_retryable(exc) or attempt >= self._max_retries:
                    raise
                attempt += 1
                logger.warning(
                    "gemini call failed, retrying",
                    extra={"video_url": video_url, "code": exc.code, "attempt": attempt},
                )
                await self._sleep(2**attempt)

        usage = response.usage_metadata
        return GeminiResult(
            text=response.text or "",
            model=self.model,
            media_resolution=self.media_resolution,
            tokens_in=usage.prompt_token_count if usage else None,
            tokens_out=usage.candidates_token_count if usage else None,
            video_seconds=estimate_video_seconds(usage, self.media_resolution),
        )

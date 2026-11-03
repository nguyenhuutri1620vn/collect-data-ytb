"""YouTube URL helpers. Videos are read by Gemini from the URL; never downloaded (C2)."""

import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import httpx

from app.core.config import Settings

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_WATCH_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
_PATH_PREFIXES = ("/shorts/", "/live/", "/embed/")


def parse_video_id(url: str) -> str | None:
    url = url.strip()
    if _VIDEO_ID.match(url):
        return url
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    candidate: str | None = None
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in _WATCH_HOSTS:
        if parsed.path == "/watch":
            candidate = (parse_qs(parsed.query).get("v") or [None])[0]
        else:
            for prefix in _PATH_PREFIXES:
                if parsed.path.startswith(prefix):
                    candidate = parsed.path.removeprefix(prefix).split("/")[0]
    return candidate if candidate and _VIDEO_ID.match(candidate) else None


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


# --- YouTube Data API v3: search for candidates (eval gold set, R1 later) ---

API_BASE = "https://www.googleapis.com/youtube/v3"
SEARCH_UNITS = 100  # search.list
VIDEOS_UNITS = 1  # videos.list, up to 50 ids per call
_VIDEOS_PER_CALL = 50
_ISO_DURATION = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def parse_iso_duration(value: str) -> int | None:
    """ISO 8601 duration from contentDetails (e.g. "PT1M30S") -> seconds."""
    match = _ISO_DURATION.match(value)
    if not match or not any(match.groups()):
        return None
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


class YouTubeClient:
    """Thin Data API client. The key goes in a header so it never appears in logged URLs."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    @classmethod
    def from_settings(cls, settings: Settings) -> "YouTubeClient":
        if settings.youtube_api_key is None:
            raise RuntimeError("YOUTUBE_API_KEY is not set")
        http = httpx.AsyncClient(
            base_url=API_BASE,
            headers={"X-Goog-Api-Key": settings.youtube_api_key.get_secret_value()},
            timeout=20,
        )
        return cls(http)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def search_video_ids(
        self,
        query: str,
        *,
        published_after: datetime,
        max_results: int = 25,
        region: str = "VN",
        language: str = "vi",
    ) -> list[str]:
        response = await self._http.get(
            "/search",
            params={
                "part": "id",
                "type": "video",
                "videoDuration": "short",
                "q": query,
                "regionCode": region,
                "relevanceLanguage": language,
                "publishedAfter": published_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "maxResults": max_results,
            },
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        return [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]

    async def durations(self, video_ids: list[str]) -> dict[str, int]:
        """Seconds per video id. Unknown or unparsable durations are left out."""
        result: dict[str, int] = {}
        for start in range(0, len(video_ids), _VIDEOS_PER_CALL):
            chunk = video_ids[start : start + _VIDEOS_PER_CALL]
            response = await self._http.get(
                "/videos", params={"part": "contentDetails", "id": ",".join(chunk)}
            )
            response.raise_for_status()
            for item in response.json().get("items", []):
                seconds = parse_iso_duration(item.get("contentDetails", {}).get("duration", ""))
                if seconds is not None:
                    result[item["id"]] = seconds
        return result

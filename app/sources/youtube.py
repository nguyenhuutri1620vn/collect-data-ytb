"""YouTube URL helpers. Videos are read by Gemini from the URL; never downloaded (C2)."""

import re
from urllib.parse import parse_qs, urlparse

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

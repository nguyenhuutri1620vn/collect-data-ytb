import pytest

from app.sources.youtube import canonical_url, parse_video_id


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?feature=share&v=dQw4w9WgXcQ&t=10", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("youtube.com/shorts/dQw4w9WgXcQ?feature=share", "dQw4w9WgXcQ"),
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.tiktok.com/@a/video/123", None),
        ("https://www.youtube.com/watch?v=short", None),
        ("https://evil.com/shorts/dQw4w9WgXcQ", None),
        ("", None),
    ],
)
def test_parse_video_id(url: str, expected: str | None) -> None:
    assert parse_video_id(url) == expected


def test_canonical_url() -> None:
    assert canonical_url("dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

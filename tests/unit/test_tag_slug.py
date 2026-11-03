import pytest

from app.tags.normalize import to_slug


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Bình dân", "binh_dan"),
        ("check-in", "check_in"),
        ("yen tinh", "yen_tinh"),
        ("  Sống  ảo!! ", "song_ao"),
        ("lang_man", "lang_man"),
        ("Chỗ đậu xe máy", "cho_dau_xe_may"),
        ("Wi-Fi", "wi_fi"),
        ("", ""),
        ("!!!", ""),
    ],
)
def test_to_slug(raw: str, expected: str) -> None:
    assert to_slug(raw) == expected

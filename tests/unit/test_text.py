import unicodedata

from app.core.text import normalize_text


def test_normalize_text_strips_diacritics_case_and_spaces() -> None:
    assert normalize_text("  Quán  Cà Phê Đường ") == "quan ca phe duong"


def test_normalize_text_nfd_equals_nfc() -> None:
    nfd = unicodedata.normalize("NFD", "Phú Nhuận")
    assert normalize_text(nfd) == normalize_text("Phú Nhuận") == "phu nhuan"

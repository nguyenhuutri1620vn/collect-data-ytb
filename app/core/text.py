import re
import unicodedata

_SPACES = re.compile(r"\s+")


def normalize_text(s: str) -> str:
    """NFC, lowercase, strip Vietnamese diacritics (đ → d), collapse whitespace."""
    s = unicodedata.normalize("NFC", s).lower().replace("đ", "d")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return _SPACES.sub(" ", s).strip()

"""District aliases (FR-5.4). Extend here, never inline elsewhere."""

import re

from app.core.text import normalize_text
from app.geo.districts import LEGACY_DISTRICTS, RURAL_DISTRICTS, SUB_AREA_PARENT

_PUNCT = re.compile(r"[.,\-]")
_SPACES = re.compile(r"\s+")
# "q 1" and "q1" (also "d 1"/"d1") are the same alias.
_PREFIX_NUMBER = re.compile(r"\b([qd]) (\d+)\b")

_SUB_AREA_ALIASES: dict[str, list[str]] = {
    "Quận 2": ["Q2", "District 2", "D2"],
    "Quận 9": ["Q9", "District 9", "D9"],
    "Quận Thủ Đức": ["Thủ Đức", "Q. Thủ Đức"],
}

_ABBREVIATIONS: dict[str, list[str]] = {
    "Bình Thạnh": ["BT"],
    "Gò Vấp": ["GV"],
    "Phú Nhuận": ["PN"],
    "Tân Bình": ["TB"],
}


def alias_key(s: str) -> str:
    key = _SPACES.sub(" ", _PUNCT.sub(" ", normalize_text(s))).strip()
    return _PREFIX_NUMBER.sub(r"\1\2", key)


def _aliases_for(name: str) -> list[str]:
    if name.startswith("Quận "):
        n = name.removeprefix("Quận ")
        aliases = [f"Q{n}", f"District {n}", f"D{n}"]
        if n == "1":
            aliases.append("Quận nhất")
        return aliases
    if name == SUB_AREA_PARENT:
        place = name.removeprefix("TP ")
        aliases = [f"TP. {place}", f"Thành phố {place}"]
        for sub_area, sub_aliases in _SUB_AREA_ALIASES.items():
            aliases += [sub_area, *sub_aliases]
        return aliases
    if name in RURAL_DISTRICTS:
        return [f"Huyện {name}", f"H. {name}"]
    return [f"Quận {name}", f"Q. {name}", *_ABBREVIATIONS.get(name, [])]


# Canonical name -> human-readable aliases (seeded into legacy_districts.aliases).
DISTRICT_ALIAS_LISTS: dict[str, list[str]] = {name: _aliases_for(name) for name in LEGACY_DISTRICTS}

# alias_key(alias) -> canonical name.
DISTRICT_ALIASES: dict[str, str] = {
    alias_key(alias): name
    for name, aliases in DISTRICT_ALIAS_LISTS.items()
    for alias in (name, *aliases)
}

_SUB_AREA_KEYS: dict[str, str] = {
    alias_key(alias): name
    for name, aliases in _SUB_AREA_ALIASES.items()
    for alias in (name, *aliases)
}


def resolve_legacy_district(raw: str | None) -> str | None:
    """Exact alias match only; unknown text gives None instead of a guess (C8)."""
    if raw is None:
        return None
    return DISTRICT_ALIASES.get(alias_key(raw))


def resolve_legacy_sub_area(raw: str | None) -> str | None:
    if raw is None:
        return None
    return _SUB_AREA_KEYS.get(alias_key(raw))

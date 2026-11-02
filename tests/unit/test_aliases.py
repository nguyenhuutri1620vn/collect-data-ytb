import pytest

from app.geo.aliases import (
    DISTRICT_ALIAS_LISTS,
    DISTRICT_ALIASES,
    resolve_legacy_district,
    resolve_legacy_sub_area,
)
from app.geo.districts import LEGACY_DISTRICTS, LEGACY_SUB_AREAS, TARGET_PLACES


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Q1", "Quận 1"),
        ("Q.1", "Quận 1"),
        ("q 1", "Quận 1"),
        ("quận 1", "Quận 1"),
        ("Quận nhất", "Quận 1"),
        ("District 1", "Quận 1"),
        ("Quận 10", "Quận 10"),
        ("q11", "Quận 11"),
        ("Q.12", "Quận 12"),
        ("BT", "Bình Thạnh"),
        ("bình thạnh", "Bình Thạnh"),
        ("Q. Bình Thạnh", "Bình Thạnh"),
        ("Tân Bình", "Tân Bình"),
        ("Bình Tân", "Bình Tân"),
        ("Quận 2", "TP Thủ Đức"),
        ("Q9", "TP Thủ Đức"),
        ("Thủ Đức", "TP Thủ Đức"),
        ("TP. Thủ Đức", "TP Thủ Đức"),
        ("thành phố Thủ Đức", "TP Thủ Đức"),
        ("huyện Củ Chi", "Củ Chi"),
        ("Củ Chi", "Củ Chi"),
        ("H. Nhà Bè", "Nhà Bè"),
    ],
)
def test_resolve_legacy_district(raw: str, expected: str) -> None:
    assert resolve_legacy_district(raw) == expected


@pytest.mark.parametrize("raw", ["Quận 13", "Biên Hòa", "", "   ", None, "quận 1 2"])
def test_resolve_legacy_district_unknown_is_none(raw: str | None) -> None:
    assert resolve_legacy_district(raw) is None


def test_every_district_resolves_itself() -> None:
    for name in LEGACY_DISTRICTS:
        assert resolve_legacy_district(name) == name


def test_alias_values_are_canonical() -> None:
    assert set(DISTRICT_ALIASES.values()) == set(LEGACY_DISTRICTS)
    assert set(DISTRICT_ALIAS_LISTS) == set(LEGACY_DISTRICTS)


def test_district_list_and_targets() -> None:
    assert len(LEGACY_DISTRICTS) == 22
    assert set(TARGET_PLACES) == set(LEGACY_DISTRICTS)
    assert sum(TARGET_PLACES.values()) == 850


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Q2", "Quận 2"),
        ("quận 9", "Quận 9"),
        ("District 9", "Quận 9"),
        ("Thủ Đức", "Quận Thủ Đức"),
        ("Quận Thủ Đức", "Quận Thủ Đức"),
        ("Quận 1", None),
        (None, None),
    ],
)
def test_resolve_legacy_sub_area(raw: str | None, expected: str | None) -> None:
    assert resolve_legacy_sub_area(raw) == expected
    assert expected is None or expected in LEGACY_SUB_AREAS

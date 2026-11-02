import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.aliases import DISTRICT_ALIAS_LISTS
from app.geo.districts import LEGACY_DISTRICTS, LEGACY_SUB_AREAS, SUB_AREA_PARENT
from app.models import LegacyDistrict, LegacySubArea, Tag
from app.tags.seed import SEED_TAGS

SNAKE_CASE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")


async def test_districts_seeded(session: AsyncSession) -> None:
    rows = (await session.scalars(select(LegacyDistrict))).all()

    assert {r.name for r in rows} == set(LEGACY_DISTRICTS)
    assert sum(r.target_places for r in rows) == 850
    for r in rows:
        assert r.aliases == DISTRICT_ALIAS_LISTS[r.name]
        assert r.geom is None


async def test_sub_areas_seeded(session: AsyncSession) -> None:
    rows = (await session.scalars(select(LegacySubArea))).all()

    assert {r.name for r in rows} == set(LEGACY_SUB_AREAS)
    assert all(r.legacy_district == SUB_AREA_PARENT for r in rows)
    assert all(r.geom is None for r in rows)


async def test_tags_seeded_match_seed_file(session: AsyncSession) -> None:
    rows = (await session.scalars(select(Tag))).all()

    assert {(r.kind, r.slug, r.label, tuple(r.aliases)) for r in rows} == {
        (t.kind, t.slug, t.label, t.aliases) for t in SEED_TAGS
    }
    assert sum(r.kind == "vibe" for r in rows) == 12
    assert sum(r.kind == "amenity" for r in rows) == 10
    assert all(r.mention_count == 0 and r.canonical_slug is None for r in rows)


def test_seed_slugs_are_snake_case() -> None:
    for tag in SEED_TAGS:
        assert SNAKE_CASE.match(tag.slug), tag.slug
        for alias in tag.aliases:
            assert SNAKE_CASE.match(alias), alias

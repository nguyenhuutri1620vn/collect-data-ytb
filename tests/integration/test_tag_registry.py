from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tag
from app.tags.normalize import TagRegistry


async def test_normalizes_aliases_and_dedupes(session: AsyncSession) -> None:
    registry = await TagRegistry.load(session)

    result = await registry.normalize("vibe", ["chill", "Thư giãn", "yen tinh", "check-in"])

    # chill / yen_tinh are aliases of thu_gian; label text maps through its slug.
    assert result == ["thu_gian", "song_ao"]


async def test_auto_registers_unseen_tag(session: AsyncSession) -> None:
    registry = await TagRegistry.load(session)

    result = await registry.normalize("amenity", ["Bàn ngoài trời"])

    assert result == ["ban_ngoai_troi"]
    tag = await session.get(Tag, ("amenity", "ban_ngoai_troi"))
    assert tag is not None
    assert tag.label == "Bàn ngoài trời"
    assert tag.canonical_slug is None


async def test_counts_mentions(session: AsyncSession) -> None:
    registry = await TagRegistry.load(session)

    await registry.normalize("vibe", ["lang_man"])
    await registry.normalize("vibe", ["hen ho", "lãng mạn"])

    tag = await session.get(Tag, ("vibe", "lang_man"))
    await session.refresh(tag)
    assert tag.mention_count == 2  # once per normalize() call (one mention), not per raw tag


async def test_follows_canonical_slug(session: AsyncSession) -> None:
    session.add(Tag(kind="vibe", slug="lang_man_2", label="Lãng mạn 2", canonical_slug="lang_man"))
    await session.flush()
    registry = await TagRegistry.load(session)

    assert await registry.normalize("vibe", ["lang man 2"]) == ["lang_man"]


async def test_limits_to_five_and_drops_empty(session: AsyncSession) -> None:
    registry = await TagRegistry.load(session)

    result = await registry.normalize(
        "vibe", ["!!!", "lang_man", "rieng_tu", "giai_tri", "nang_dong", "soi_dong", "song_ao"]
    )

    assert result == ["lang_man", "rieng_tu", "giai_tri", "nang_dong", "soi_dong"]
    count = (await session.scalars(select(Tag).where(Tag.slug == ""))).all()
    assert count == []

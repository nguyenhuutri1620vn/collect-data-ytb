"""Open-tag normalization (FR-9.2): raw tag -> snake_case slug -> alias lookup -> canonical tag.

Unseen tags are registered automatically (no manual review, C3).
"""

import re
from collections.abc import Iterable

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text import normalize_text
from app.models import Tag

MAX_TAGS = 5
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def to_slug(raw: str) -> str:
    return _NON_ALNUM.sub("_", normalize_text(raw)).strip("_")


class TagRegistry:
    """In-memory view of `tags` for one unit of work; writes go through the given session."""

    def __init__(self, session: AsyncSession, keys: dict[tuple[str, str], str]) -> None:
        self._session = session
        self._keys = keys  # (kind, slug of slug/alias/label) -> canonical slug

    @classmethod
    async def load(cls, session: AsyncSession) -> "TagRegistry":
        tags = (await session.scalars(select(Tag))).all()
        keys: dict[tuple[str, str], str] = {}
        for tag in tags:
            canonical = tag.canonical_slug or tag.slug
            for key in (tag.slug, to_slug(tag.label), *(to_slug(a) for a in tag.aliases)):
                keys.setdefault((tag.kind, key), canonical)
        # A tag's own slug always wins over another tag's alias or label.
        for tag in tags:
            keys[(tag.kind, tag.slug)] = tag.canonical_slug or tag.slug
        return cls(session, keys)

    async def normalize(self, kind: str, raw_tags: Iterable[str]) -> list[str]:
        """Canonical slugs for one mention's tags, deduplicated, at most MAX_TAGS."""
        result: list[str] = []
        for raw in raw_tags:
            slug = to_slug(raw)
            if not slug:
                continue
            canonical = self._keys.get((kind, slug))
            if canonical is None:
                canonical = await self._register(kind, slug, raw.strip())
            if canonical not in result:
                result.append(canonical)
            if len(result) == MAX_TAGS:
                break
        if result:
            await self._session.execute(
                update(Tag)
                .where(Tag.kind == kind, Tag.slug.in_(result))
                .values(mention_count=Tag.mention_count + 1)
            )
        return result

    async def _register(self, kind: str, slug: str, label: str) -> str:
        await self._session.execute(
            insert(Tag)
            .values(kind=kind, slug=slug, label=label)
            .on_conflict_do_nothing(index_elements=["kind", "slug"])
        )
        self._keys[(kind, slug)] = slug
        return slug

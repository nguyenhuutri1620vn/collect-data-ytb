from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, in_check, text_array

TAG_KINDS = ("vibe", "amenity")


class Tag(Base):
    """Open tags for vibes and amenities (R9)."""

    __tablename__ = "tags"
    __table_args__ = (CheckConstraint(in_check("kind", TAG_KINDS), name="ck_tags_kind"),)

    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = text_array()
    canonical_slug: Mapped[str | None] = mapped_column(Text)
    mention_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

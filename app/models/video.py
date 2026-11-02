from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, in_check, updated_at

VIDEO_SOURCES = ("youtube",)
VIDEO_STATUSES = ("discovered", "analyzed", "enriched", "resolved", "rejected", "failed")
AVAILABILITIES = ("available", "unavailable")


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        UniqueConstraint("source", "video_id", name="uq_videos_source_video_id"),
        CheckConstraint(in_check("source", VIDEO_SOURCES), name="ck_videos_source"),
        CheckConstraint(in_check("status", VIDEO_STATUSES), name="ck_videos_status"),
        CheckConstraint(in_check("availability", AVAILABILITIES), name="ck_videos_availability"),
        Index("ix_videos_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[str] = mapped_column(Text, server_default=text("'youtube'"), nullable=False)
    video_id: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    channel_id: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[int | None] = mapped_column(Integer)
    availability: Mapped[str] = mapped_column(
        Text, server_default=text("'available'"), nullable=False
    )
    metadata_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default=text("'discovered'"), nullable=False)
    is_relevant: Mapped[bool | None]
    current_analysis_fk: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "analyses.id",
            name="fk_videos_current_analysis_fk",
            use_alter=True,
            ondelete="SET NULL",
        ),
    )
    retry_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    video_fk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    media_resolution: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    video_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_at()

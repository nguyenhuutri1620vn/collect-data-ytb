from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, Text, func
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Channel(Base):
    __tablename__ = "channels"

    channel_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    uploads_playlist_id: Mapped[str | None] = mapped_column(Text)
    videos_seen: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"), nullable=False)
    videos_relevant: Mapped[int] = mapped_column(
        Integer, server_default=sql_text("0"), nullable=False
    )
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    area: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    modifier: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"), nullable=False)
    runs: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"), nullable=False)
    low_yield_streak: Mapped[int] = mapped_column(
        Integer, server_default=sql_text("0"), nullable=False
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KeywordRun(Base):
    __tablename__ = "keyword_runs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    keyword_fk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ran_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    results_count: Mapped[int] = mapped_column(
        Integer, server_default=sql_text("0"), nullable=False
    )
    new_videos_count: Mapped[int] = mapped_column(
        Integer, server_default=sql_text("0"), nullable=False
    )
    quota_units: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"), nullable=False)


class VideoKeyword(Base):
    __tablename__ = "video_keywords"

    video_fk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True
    )
    keyword_fk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("keywords.id", ondelete="CASCADE"), primary_key=True
    )
    keyword_run_fk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("keyword_runs.id", ondelete="CASCADE"), primary_key=True
    )

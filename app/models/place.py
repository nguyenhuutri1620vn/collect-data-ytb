from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    CATEGORIES,
    PRICE_UNITS,
    SETTINGS,
    Base,
    created_at,
    in_check,
    jsonb_list,
    jsonb_object,
    text_array,
    updated_at,
)

MATCH_STATUSES = ("pending", "matched", "unmatched", "ambiguous", "out_of_scope")
DISTRICT_SOURCES = ("coordinates", "district_raw")
PLACE_STATUSES = ("draft", "published", "hidden", "out_of_scope")


class Mention(Base):
    """One video's claim about one place (RAW_REQUIREMENTS §6, FR-2.6)."""

    __tablename__ = "mentions"
    __table_args__ = (
        UniqueConstraint("analysis_fk", "ordinal", name="uq_mentions_analysis_fk_ordinal"),
        CheckConstraint(in_check("match_status", MATCH_STATUSES), name="ck_mentions_match_status"),
        CheckConstraint(
            in_check("district_source", DISTRICT_SOURCES), name="ck_mentions_district_source"
        ),
        CheckConstraint(in_check("category", CATEGORIES), name="ck_mentions_category"),
        CheckConstraint(in_check("setting", SETTINGS), name="ck_mentions_setting"),
        CheckConstraint(in_check("price_unit", PRICE_UNITS), name="ck_mentions_price_unit"),
        Index("ix_mentions_match_status", "match_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    video_fk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_fk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    place_fk: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("places.id", ondelete="SET NULL"), index=True
    )
    match_status: Mapped[str] = mapped_column(
        Text, server_default=text("'pending'"), nullable=False
    )
    match_score: Mapped[float | None] = mapped_column(Float)
    name_raw: Mapped[str] = mapped_column(Text, nullable=False)
    name_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    address_raw: Mapped[str | None] = mapped_column(Text)
    district_raw: Mapped[str | None] = mapped_column(Text)
    legacy_district: Mapped[str | None] = mapped_column(Text, ForeignKey("legacy_districts.name"))
    ward: Mapped[str | None] = mapped_column(Text)
    legacy_sub_area: Mapped[str | None] = mapped_column(Text)
    district_source: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    sub_category: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list] = jsonb_list()
    price_min_vnd: Mapped[int | None] = mapped_column(BigInteger)
    price_max_vnd: Mapped[int | None] = mapped_column(BigInteger)
    price_unit: Mapped[str | None] = mapped_column(Text)
    time_slots: Mapped[list[str]] = text_array()
    opening_hours_raw: Mapped[str | None] = mapped_column(Text)
    vibes: Mapped[list[str]] = text_array()
    amenities: Mapped[list[str]] = text_array()
    suitable_for: Mapped[list[str]] = text_array()
    group_size_min: Mapped[int | None] = mapped_column(Integer)
    group_size_max: Mapped[int | None] = mapped_column(Integer)
    setting: Mapped[str | None] = mapped_column(Text)
    visit_duration_min_minutes: Mapped[int | None] = mapped_column(Integer)
    visit_duration_max_minutes: Mapped[int | None] = mapped_column(Integer)
    reservation_required: Mapped[bool | None] = mapped_column(Boolean)
    contacts: Mapped[list] = jsonb_list()
    highlights: Mapped[list[str]] = text_array()
    tips: Mapped[list[str]] = text_array()
    evidence: Mapped[list] = jsonb_list()
    confidence: Mapped[float | None] = mapped_column(Float)
    retry_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


class Place(Base):
    """Canonical place aggregated from mentions (FR-4.3). Stores no Google content but the id."""

    __tablename__ = "places"
    __table_args__ = (
        CheckConstraint(in_check("status", PLACE_STATUSES), name="ck_places_status"),
        CheckConstraint(in_check("category", CATEGORIES), name="ck_places_category"),
        CheckConstraint(in_check("setting", SETTINGS), name="ck_places_setting"),
        CheckConstraint(in_check("price_unit", PRICE_UNITS), name="ck_places_price_unit"),
        Index("ix_places_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    address_raw: Mapped[str | None] = mapped_column(Text)
    ward: Mapped[str | None] = mapped_column(Text)
    legacy_district: Mapped[str | None] = mapped_column(Text, ForeignKey("legacy_districts.name"))
    legacy_sub_area: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    sub_category: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list] = jsonb_list()
    price_min_vnd: Mapped[int | None] = mapped_column(BigInteger)
    price_max_vnd: Mapped[int | None] = mapped_column(BigInteger)
    price_unit: Mapped[str | None] = mapped_column(Text)
    opening_hours_raw: Mapped[str | None] = mapped_column(Text)
    time_slots: Mapped[list[str]] = text_array()
    time_slot_counts: Mapped[dict] = jsonb_object()
    vibes: Mapped[list[str]] = text_array()
    vibe_counts: Mapped[dict] = jsonb_object()
    amenities: Mapped[list[str]] = text_array()
    amenity_counts: Mapped[dict] = jsonb_object()
    suitable_for: Mapped[list[str]] = text_array()
    suitable_for_counts: Mapped[dict] = jsonb_object()
    group_size_min: Mapped[int | None] = mapped_column(Integer)
    group_size_max: Mapped[int | None] = mapped_column(Integer)
    setting: Mapped[str | None] = mapped_column(Text)
    visit_duration_min_minutes: Mapped[int | None] = mapped_column(Integer)
    visit_duration_max_minutes: Mapped[int | None] = mapped_column(Integer)
    reservation_required: Mapped[bool | None] = mapped_column(Boolean)
    contacts: Mapped[list] = jsonb_list()
    highlights: Mapped[list] = jsonb_list()
    tips: Mapped[list] = jsonb_list()
    mention_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    source_video_ids: Mapped[list[str]] = text_array()
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(Text, server_default=text("'draft'"), nullable=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-02 23:36:06.051519
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "channels",
        sa.Column("channel_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("uploads_playlist_id", sa.Text(), nullable=True),
        sa.Column("videos_seen", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("videos_relevant", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("channel_id"),
    )
    op.create_table(
        "keywords",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("area", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("modifier", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("runs", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("low_yield_streak", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("text"),
    )
    op.create_table(
        "legacy_districts",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "aliases", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("target_places", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_index(
        "ix_legacy_districts_geom",
        "legacy_districts",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_table(
        "quota_usage",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("service", sa.Text(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("value", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("date", "service", "metric"),
    )
    op.create_table(
        "tags",
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column(
            "aliases", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("canonical_slug", sa.Text(), nullable=True),
        sa.Column("mention_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('vibe', 'amenity')", name="ck_tags_kind"),
        sa.PrimaryKeyConstraint("kind", "slug"),
    )
    op.create_table(
        "videos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'youtube'"), nullable=False),
        sa.Column("video_id", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("channel_id", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column("availability", sa.Text(), server_default=sa.text("'available'"), nullable=False),
        sa.Column("metadata_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'discovered'"), nullable=False),
        sa.Column("is_relevant", sa.Boolean(), nullable=True),
        sa.Column("current_analysis_fk", sa.BigInteger(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "availability IN ('available', 'unavailable')", name="ck_videos_availability"
        ),
        sa.CheckConstraint("source IN ('youtube')", name="ck_videos_source"),
        sa.CheckConstraint(
            "status IN ('discovered', 'analyzed', 'enriched', 'resolved', 'rejected', 'failed')",
            name="ck_videos_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "video_id", name="uq_videos_source_video_id"),
    )
    op.create_index("ix_videos_status", "videos", ["status"], unique=False)
    op.create_table(
        "wards",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "legacy_districts",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_index("ix_wards_geom", "wards", ["geom"], unique=False, postgresql_using="gist")
    op.create_table(
        "analyses",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("video_fk", sa.BigInteger(), nullable=False),
        sa.Column("raw_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("media_resolution", sa.Text(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("video_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["video_fk"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analyses_video_fk"), "analyses", ["video_fk"], unique=False)
    # videos <-> analyses reference each other, so this FK is added after both exist.
    op.create_foreign_key(
        "fk_videos_current_analysis_fk",
        "videos",
        "analyses",
        ["current_analysis_fk"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "keyword_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("keyword_fk", sa.BigInteger(), nullable=False),
        sa.Column(
            "ran_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("results_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("new_videos_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("quota_units", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["keyword_fk"], ["keywords.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_keyword_runs_keyword_fk"), "keyword_runs", ["keyword_fk"], unique=False
    )
    op.create_table(
        "legacy_sub_areas",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("legacy_district", sa.Text(), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["legacy_district"],
            ["legacy_districts.name"],
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_index(
        "ix_legacy_sub_areas_geom",
        "legacy_sub_areas",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_table(
        "places",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("google_place_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_normalized", sa.Text(), nullable=False),
        sa.Column("address_raw", sa.Text(), nullable=True),
        sa.Column("ward", sa.Text(), nullable=True),
        sa.Column("legacy_district", sa.Text(), nullable=True),
        sa.Column("legacy_sub_area", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("sub_category", sa.Text(), nullable=True),
        sa.Column(
            "items",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("price_min_vnd", sa.BigInteger(), nullable=True),
        sa.Column("price_max_vnd", sa.BigInteger(), nullable=True),
        sa.Column("price_unit", sa.Text(), nullable=True),
        sa.Column("opening_hours_raw", sa.Text(), nullable=True),
        sa.Column(
            "time_slots",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "time_slot_counts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "vibes", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "vibe_counts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "amenities", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "amenity_counts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "suitable_for",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "suitable_for_counts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("group_size_min", sa.Integer(), nullable=True),
        sa.Column("group_size_max", sa.Integer(), nullable=True),
        sa.Column("setting", sa.Text(), nullable=True),
        sa.Column("visit_duration_min_minutes", sa.Integer(), nullable=True),
        sa.Column("visit_duration_max_minutes", sa.Integer(), nullable=True),
        sa.Column("reservation_required", sa.Boolean(), nullable=True),
        sa.Column(
            "contacts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "highlights",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "tips",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("mention_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "source_video_ids",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "closed_permanently", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('an', 'uong', 'tham_quan', 'vui_choi', 'khac')", name="ck_places_category"
        ),
        sa.CheckConstraint(
            "price_unit IN ('per_item', 'per_person', 'ticket')", name="ck_places_price_unit"
        ),
        sa.CheckConstraint("setting IN ('indoor', 'outdoor', 'mixed')", name="ck_places_setting"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'hidden', 'out_of_scope')", name="ck_places_status"
        ),
        sa.ForeignKeyConstraint(
            ["legacy_district"],
            ["legacy_districts.name"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("google_place_id", name="uq_places_google_place_id"),
    )
    op.create_index("ix_places_status", "places", ["status"], unique=False)
    op.create_table(
        "mentions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("video_fk", sa.BigInteger(), nullable=False),
        sa.Column("analysis_fk", sa.BigInteger(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("place_fk", sa.BigInteger(), nullable=True),
        sa.Column("google_place_id", sa.Text(), nullable=True),
        sa.Column("match_status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("name_raw", sa.Text(), nullable=False),
        sa.Column("name_normalized", sa.Text(), nullable=False),
        sa.Column("address_raw", sa.Text(), nullable=True),
        sa.Column("district_raw", sa.Text(), nullable=True),
        sa.Column("legacy_district", sa.Text(), nullable=True),
        sa.Column("ward", sa.Text(), nullable=True),
        sa.Column("legacy_sub_area", sa.Text(), nullable=True),
        sa.Column("district_source", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("sub_category", sa.Text(), nullable=True),
        sa.Column(
            "items",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("price_min_vnd", sa.BigInteger(), nullable=True),
        sa.Column("price_max_vnd", sa.BigInteger(), nullable=True),
        sa.Column("price_unit", sa.Text(), nullable=True),
        sa.Column(
            "time_slots",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("opening_hours_raw", sa.Text(), nullable=True),
        sa.Column(
            "vibes", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "amenities", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "suitable_for",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("group_size_min", sa.Integer(), nullable=True),
        sa.Column("group_size_max", sa.Integer(), nullable=True),
        sa.Column("setting", sa.Text(), nullable=True),
        sa.Column("visit_duration_min_minutes", sa.Integer(), nullable=True),
        sa.Column("visit_duration_max_minutes", sa.Integer(), nullable=True),
        sa.Column("reservation_required", sa.Boolean(), nullable=True),
        sa.Column(
            "contacts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "highlights",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "tips", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "category IN ('an', 'uong', 'tham_quan', 'vui_choi', 'khac')",
            name="ck_mentions_category",
        ),
        sa.CheckConstraint(
            "district_source IN ('coordinates', 'district_raw')", name="ck_mentions_district_source"
        ),
        sa.CheckConstraint(
            "match_status IN ('pending', 'matched', 'unmatched', 'ambiguous', 'out_of_scope')",
            name="ck_mentions_match_status",
        ),
        sa.CheckConstraint(
            "price_unit IN ('per_item', 'per_person', 'ticket')", name="ck_mentions_price_unit"
        ),
        sa.CheckConstraint("setting IN ('indoor', 'outdoor', 'mixed')", name="ck_mentions_setting"),
        sa.ForeignKeyConstraint(["analysis_fk"], ["analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["legacy_district"],
            ["legacy_districts.name"],
        ),
        sa.ForeignKeyConstraint(["place_fk"], ["places.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["video_fk"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_fk", "ordinal", name="uq_mentions_analysis_fk_ordinal"),
    )
    op.create_index("ix_mentions_match_status", "mentions", ["match_status"], unique=False)
    op.create_index(op.f("ix_mentions_place_fk"), "mentions", ["place_fk"], unique=False)
    op.create_index(op.f("ix_mentions_video_fk"), "mentions", ["video_fk"], unique=False)
    op.create_table(
        "video_keywords",
        sa.Column("video_fk", sa.BigInteger(), nullable=False),
        sa.Column("keyword_fk", sa.BigInteger(), nullable=False),
        sa.Column("keyword_run_fk", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["keyword_fk"], ["keywords.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["keyword_run_fk"], ["keyword_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_fk"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("video_fk", "keyword_fk", "keyword_run_fk"),
    )


def downgrade() -> None:
    # Leaves the postgis extension in place: it is shared and not owned by this schema.
    op.drop_constraint("fk_videos_current_analysis_fk", "videos", type_="foreignkey")
    op.drop_table("video_keywords")
    op.drop_index(op.f("ix_mentions_video_fk"), table_name="mentions")
    op.drop_index(op.f("ix_mentions_place_fk"), table_name="mentions")
    op.drop_index("ix_mentions_match_status", table_name="mentions")
    op.drop_table("mentions")
    op.drop_index("ix_places_status", table_name="places")
    op.drop_table("places")
    op.drop_index(
        "ix_legacy_sub_areas_geom", table_name="legacy_sub_areas", postgresql_using="gist"
    )
    op.drop_table("legacy_sub_areas")
    op.drop_index(op.f("ix_keyword_runs_keyword_fk"), table_name="keyword_runs")
    op.drop_table("keyword_runs")
    op.drop_index(op.f("ix_analyses_video_fk"), table_name="analyses")
    op.drop_table("analyses")
    op.drop_index("ix_wards_geom", table_name="wards", postgresql_using="gist")
    op.drop_table("wards")
    op.drop_index("ix_videos_status", table_name="videos")
    op.drop_table("videos")
    op.drop_table("tags")
    op.drop_table("quota_usage")
    op.drop_index(
        "ix_legacy_districts_geom", table_name="legacy_districts", postgresql_using="gist"
    )
    op.drop_table("legacy_districts")
    op.drop_table("keywords")
    op.drop_table("channels")

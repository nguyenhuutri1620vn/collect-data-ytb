"""Drop Google Places columns (D25) and create the read-only `output` schema (R10).

The output views read base tables with the view owner's rights, so the reader role needs no
privileges on base tables. Creating the login role and its password is done outside code (FR-10.3).
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0003_output_views"
down_revision: str | None = "0002_seed_reference_data"
branch_labels = None
depends_on = None

OUTPUT_VERSION = "1"

PLACE_COLUMNS = """
    p.id, p.name, p.name_normalized, p.address_raw, p.legacy_district, p.legacy_sub_area,
    p.ward, p.category, p.sub_category, p.items, p.price_min_vnd, p.price_max_vnd, p.price_unit,
    p.opening_hours_raw, p.time_slots, p.time_slot_counts, p.vibes, p.vibe_counts,
    p.amenities, p.amenity_counts, p.suitable_for, p.suitable_for_counts, p.group_size_min,
    p.group_size_max, p.setting, p.visit_duration_min_minutes, p.visit_duration_max_minutes,
    p.reservation_required, p.contacts, p.highlights, p.tips, p.mention_count,
    p.source_video_ids, p.confidence, p.updated_at
"""


def upgrade() -> None:
    op.execute("ALTER TABLE places DROP CONSTRAINT IF EXISTS uq_places_google_place_id")
    op.drop_column("places", "google_place_id")
    op.drop_column("places", "closed_permanently")
    op.drop_column("mentions", "google_place_id")

    op.execute("CREATE SCHEMA output")
    op.execute(f"COMMENT ON SCHEMA output IS 'OUTPUT_VERSION={OUTPUT_VERSION}'")

    op.execute(f"""
        CREATE VIEW output.places AS
        SELECT {PLACE_COLUMNS}
        FROM places p
        WHERE p.status = 'published'
    """)

    op.execute("""
        CREATE VIEW output.place_mentions AS
        SELECT m.place_fk AS place_id, v.video_id, m.name_raw, m.address_raw, m.district_raw,
               m.legacy_district, m.price_min_vnd, m.price_max_vnd, m.price_unit, m.time_slots,
               m.vibes, m.amenities, m.suitable_for, m.setting, m.contacts, m.highlights,
               m.tips, m.evidence, m.confidence
        FROM mentions m
        JOIN places p ON p.id = m.place_fk AND p.status = 'published'
        JOIN videos v ON v.id = m.video_fk
    """)

    # One row per (place, video, evidence timestamp). The link carries &t=<seconds>.
    # Titles are not stored (C10), so the view has no title column.
    op.execute("""
        CREATE VIEW output.place_media AS
        SELECT DISTINCT
               m.place_fk AS place_id,
               v.video_id,
               'https://www.youtube.com/watch?v=' || v.video_id
                 || '&t=' || (split_part(e->>'timestamp', ':', 1)::int * 60
                              + split_part(e->>'timestamp', ':', 2)::int) AS video_url,
               'https://i.ytimg.com/vi/' || v.video_id || '/hqdefault.jpg' AS thumbnail_url
        FROM mentions m
        JOIN places p ON p.id = m.place_fk AND p.status = 'published'
        JOIN videos v ON v.id = m.video_fk AND v.availability = 'available'
        CROSS JOIN LATERAL jsonb_array_elements(m.evidence) AS e
        WHERE e->>'timestamp' ~ '^[0-9]{1,3}:[0-5][0-9]$'
    """)

    op.execute("""
        CREATE VIEW output.tags AS
        SELECT kind, slug, label, mention_count
        FROM tags
    """)

    op.execute("""
        CREATE VIEW output.legacy_districts AS
        SELECT ld.name AS legacy_district, sa.name AS legacy_sub_area, ld.target_places
        FROM legacy_districts ld
        LEFT JOIN legacy_sub_areas sa ON sa.legacy_district = ld.name
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'output_reader') THEN
                CREATE ROLE output_reader NOLOGIN;
            END IF;
        END $$
    """)
    op.execute("GRANT USAGE ON SCHEMA output TO output_reader")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA output TO output_reader")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS output CASCADE")
    op.add_column("mentions", sa.Column("google_place_id", sa.Text(), nullable=True))
    op.add_column("places", sa.Column("google_place_id", sa.Text(), nullable=True))
    op.add_column(
        "places",
        sa.Column(
            "closed_permanently", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.create_unique_constraint("uq_places_google_place_id", "places", ["google_place_id"])

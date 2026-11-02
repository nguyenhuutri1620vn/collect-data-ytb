"""seed reference data: legacy districts, sub-areas, suggested tags

Values are copied from app/geo and app/tags at the time of writing so this migration never
changes when the code does. Later alias/tag additions go into new data migrations.

Revision ID: 0002_seed_reference_data
Revises: 0001_initial_schema
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0002_seed_reference_data"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (name, target_places, aliases)
LEGACY_DISTRICTS = [
    ("Quận 1", 50, ["Q1", "District 1", "D1", "Quận nhất"]),
    ("Quận 3", 50, ["Q3", "District 3", "D3"]),
    ("Quận 4", 50, ["Q4", "District 4", "D4"]),
    ("Quận 5", 50, ["Q5", "District 5", "D5"]),
    ("Quận 6", 50, ["Q6", "District 6", "D6"]),
    ("Quận 7", 50, ["Q7", "District 7", "D7"]),
    ("Quận 8", 50, ["Q8", "District 8", "D8"]),
    ("Quận 10", 50, ["Q10", "District 10", "D10"]),
    ("Quận 11", 50, ["Q11", "District 11", "D11"]),
    ("Quận 12", 30, ["Q12", "District 12", "D12"]),
    ("Bình Thạnh", 50, ["Quận Bình Thạnh", "Q. Bình Thạnh", "BT"]),
    ("Gò Vấp", 30, ["Quận Gò Vấp", "Q. Gò Vấp", "GV"]),
    ("Phú Nhuận", 50, ["Quận Phú Nhuận", "Q. Phú Nhuận", "PN"]),
    ("Tân Bình", 50, ["Quận Tân Bình", "Q. Tân Bình", "TB"]),
    ("Tân Phú", 30, ["Quận Tân Phú", "Q. Tân Phú"]),
    ("Bình Tân", 30, ["Quận Bình Tân", "Q. Bình Tân"]),
    (
        "TP Thủ Đức",
        80,
        [
            "TP. Thủ Đức",
            "Thành phố Thủ Đức",
            "Quận 2",
            "Q2",
            "District 2",
            "D2",
            "Quận 9",
            "Q9",
            "District 9",
            "D9",
            "Quận Thủ Đức",
            "Thủ Đức",
            "Q. Thủ Đức",
        ],
    ),
    ("Bình Chánh", 10, ["Huyện Bình Chánh", "H. Bình Chánh"]),
    ("Củ Chi", 10, ["Huyện Củ Chi", "H. Củ Chi"]),
    ("Hóc Môn", 10, ["Huyện Hóc Môn", "H. Hóc Môn"]),
    ("Nhà Bè", 10, ["Huyện Nhà Bè", "H. Nhà Bè"]),
    ("Cần Giờ", 10, ["Huyện Cần Giờ", "H. Cần Giờ"]),
]

SUB_AREA_PARENT = "TP Thủ Đức"
LEGACY_SUB_AREAS = [
    "Quận 2",
    "Quận 9",
    "Quận Thủ Đức",
]

# (kind, slug, label, aliases)
TAGS = [
    ("vibe", "lang_man", "Lãng mạn", ["hen_ho"]),
    ("vibe", "rieng_tu", "Riêng tư", []),
    ("vibe", "giai_tri", "Giải trí", []),
    ("vibe", "nang_dong", "Năng động", []),
    ("vibe", "thu_gian", "Thư giãn", ["chill", "yen_tinh"]),
    ("vibe", "soi_dong", "Sôi động", []),
    ("vibe", "song_ao", "Sống ảo", ["check_in", "chup_anh"]),
    ("vibe", "hoai_niem", "Hoài niệm", ["co_xua"]),
    ("vibe", "sang_trong", "Sang trọng", []),
    ("vibe", "binh_dan", "Bình dân", []),
    ("vibe", "gan_gui_thien_nhien", "Gần gũi thiên nhiên", []),
    ("vibe", "van_hoa_lich_su", "Văn hóa lịch sử", []),
    ("amenity", "wifi", "Wifi", []),
    ("amenity", "may_lanh", "Máy lạnh", []),
    ("amenity", "cho_dau_xe_may", "Chỗ đậu xe máy", []),
    ("amenity", "cho_dau_o_to", "Chỗ đậu ô tô", []),
    ("amenity", "phong_rieng", "Phòng riêng", []),
    ("amenity", "cho_thu_cung", "Cho thú cưng", []),
    ("amenity", "khu_vui_choi_tre_em", "Khu vui chơi trẻ em", []),
    ("amenity", "o_cam_sac", "Ổ cắm sạc", []),
    ("amenity", "nhan_dat_cho", "Nhận đặt chỗ", []),
    ("amenity", "giao_hang", "Giao hàng", []),
]

legacy_districts = sa.table(
    "legacy_districts",
    sa.column("name", sa.Text),
    sa.column("target_places", sa.Integer),
    sa.column("aliases", ARRAY(sa.Text)),
)
legacy_sub_areas = sa.table(
    "legacy_sub_areas", sa.column("name", sa.Text), sa.column("legacy_district", sa.Text)
)
tags = sa.table(
    "tags",
    sa.column("kind", sa.Text),
    sa.column("slug", sa.Text),
    sa.column("label", sa.Text),
    sa.column("aliases", ARRAY(sa.Text)),
)


def upgrade() -> None:
    op.bulk_insert(
        legacy_districts,
        [
            {"name": name, "target_places": target, "aliases": aliases}
            for name, target, aliases in LEGACY_DISTRICTS
        ],
    )
    op.bulk_insert(
        legacy_sub_areas,
        [{"name": name, "legacy_district": SUB_AREA_PARENT} for name in LEGACY_SUB_AREAS],
    )
    op.bulk_insert(
        tags,
        [
            {"kind": kind, "slug": slug, "label": label, "aliases": aliases}
            for kind, slug, label, aliases in TAGS
        ],
    )


def downgrade() -> None:
    op.execute(
        tags.delete().where(
            sa.tuple_(tags.c.kind, tags.c.slug).in_([(k, s) for k, s, _, _ in TAGS])
        )
    )
    op.execute(legacy_sub_areas.delete().where(legacy_sub_areas.c.name.in_(LEGACY_SUB_AREAS)))
    op.execute(
        legacy_districts.delete().where(
            legacy_districts.c.name.in_([name for name, _, _ in LEGACY_DISTRICTS])
        )
    )

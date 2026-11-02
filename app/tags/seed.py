"""Suggested tags and initial aliases (FR-9.3, RAW_REQUIREMENTS §7).

Changes reach the DB through a data migration. Only append new tags at the end: the list is
also fed to the prompt, and reordering it requires a PROMPT_VERSION bump and an eval run.
"""

from typing import NamedTuple


class SeedTag(NamedTuple):
    kind: str
    slug: str
    label: str
    aliases: tuple[str, ...] = ()


SEED_TAGS: tuple[SeedTag, ...] = (
    SeedTag("vibe", "lang_man", "Lãng mạn", ("hen_ho",)),
    SeedTag("vibe", "rieng_tu", "Riêng tư"),
    SeedTag("vibe", "giai_tri", "Giải trí"),
    SeedTag("vibe", "nang_dong", "Năng động"),
    SeedTag("vibe", "thu_gian", "Thư giãn", ("chill", "yen_tinh")),
    SeedTag("vibe", "soi_dong", "Sôi động"),
    SeedTag("vibe", "song_ao", "Sống ảo", ("check_in", "chup_anh")),
    SeedTag("vibe", "hoai_niem", "Hoài niệm", ("co_xua",)),
    SeedTag("vibe", "sang_trong", "Sang trọng"),
    SeedTag("vibe", "binh_dan", "Bình dân"),
    SeedTag("vibe", "gan_gui_thien_nhien", "Gần gũi thiên nhiên"),
    SeedTag("vibe", "van_hoa_lich_su", "Văn hóa lịch sử"),
    SeedTag("amenity", "wifi", "Wifi"),
    SeedTag("amenity", "may_lanh", "Máy lạnh"),
    SeedTag("amenity", "cho_dau_xe_may", "Chỗ đậu xe máy"),
    SeedTag("amenity", "cho_dau_o_to", "Chỗ đậu ô tô"),
    SeedTag("amenity", "phong_rieng", "Phòng riêng"),
    SeedTag("amenity", "cho_thu_cung", "Cho thú cưng"),
    SeedTag("amenity", "khu_vui_choi_tre_em", "Khu vui chơi trẻ em"),
    SeedTag("amenity", "o_cam_sac", "Ổ cắm sạc"),
    SeedTag("amenity", "nhan_dat_cho", "Nhận đặt chỗ"),
    SeedTag("amenity", "giao_hang", "Giao hàng"),
)

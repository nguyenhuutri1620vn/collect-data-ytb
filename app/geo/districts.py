"""Pre-2025 HCMC districts (FR-5.3) and coverage targets (RAW_REQUIREMENTS §9)."""

LEGACY_DISTRICTS: tuple[str, ...] = (
    "Quận 1",
    "Quận 3",
    "Quận 4",
    "Quận 5",
    "Quận 6",
    "Quận 7",
    "Quận 8",
    "Quận 10",
    "Quận 11",
    "Quận 12",
    "Bình Thạnh",
    "Gò Vấp",
    "Phú Nhuận",
    "Tân Bình",
    "Tân Phú",
    "Bình Tân",
    "TP Thủ Đức",
    "Bình Chánh",
    "Củ Chi",
    "Hóc Môn",
    "Nhà Bè",
    "Cần Giờ",
)

# Rural districts (huyện); the rest are urban (quận) or the city of Thủ Đức.
RURAL_DISTRICTS: tuple[str, ...] = ("Bình Chánh", "Củ Chi", "Hóc Môn", "Nhà Bè", "Cần Giờ")

SUB_AREA_PARENT = "TP Thủ Đức"
LEGACY_SUB_AREAS: tuple[str, ...] = ("Quận 2", "Quận 9", "Quận Thủ Đức")

TARGET_PLACES: dict[str, int] = {
    **dict.fromkeys(
        (
            "Quận 1",
            "Quận 3",
            "Quận 4",
            "Quận 5",
            "Quận 6",
            "Quận 7",
            "Quận 8",
            "Quận 10",
            "Quận 11",
            "Bình Thạnh",
            "Phú Nhuận",
            "Tân Bình",
        ),
        50,
    ),
    "TP Thủ Đức": 80,
    **dict.fromkeys(("Quận 12", "Gò Vấp", "Tân Phú", "Bình Tân"), 30),
    **dict.fromkeys(RURAL_DISTRICTS, 10),
}

"""Gemini extraction schema v1 (RAW_REQUIREMENTS §7).

Changing any enum or field here requires bumping SCHEMA_VERSION and asking first (hard rule 6).
`vibes` and `amenities` are open tags (R9), not enums.
"""

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1"

TimeSlot = Literal["sang", "trua", "chieu", "toi", "khuya"]
GroupType = Literal["mot_minh", "cap_doi", "nhom_nho", "nhom_lon", "gia_dinh"]
Category = Literal["an", "uong", "tham_quan", "vui_choi", "khac"]


class Evidence(BaseModel):
    timestamp: str | None  # "MM:SS"; null when source = description
    source: Literal["audio", "onscreen_text", "description", "visual"]
    text: str


class Item(BaseModel):
    name: str
    price_vnd: int | None


class Contact(BaseModel):
    type: Literal["phone", "facebook", "instagram", "tiktok", "zalo", "website", "other"]
    value: str


class ExtractedPlace(BaseModel):
    name: str
    address_raw: str | None
    district_raw: str | None
    category: Category
    sub_category: str | None
    items: list[Item]
    price_min_vnd: int | None
    price_max_vnd: int | None
    price_unit: Literal["per_item", "per_person", "ticket"] | None
    time_slots: list[TimeSlot]
    opening_hours_raw: str | None
    vibes: list[str]
    amenities: list[str]
    suitable_for: list[GroupType]
    group_size_min: int | None
    group_size_max: int | None
    setting: Literal["indoor", "outdoor", "mixed"] | None
    visit_duration_min_minutes: int | None
    visit_duration_max_minutes: int | None
    reservation_required: bool | None
    contacts: list[Contact]
    highlights: list[str]
    tips: list[str]
    evidence: list[Evidence]
    confidence: float = Field(ge=0, le=1)


class VideoExtraction(BaseModel):
    is_relevant: bool
    video_summary: str
    places: list[ExtractedPlace]

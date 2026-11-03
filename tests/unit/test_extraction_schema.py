import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.extraction import SCHEMA_VERSION, VideoExtraction

FIXTURES = Path(__file__).parent.parent / "fixtures" / "gemini"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_parses_two_places() -> None:
    extraction = VideoExtraction.model_validate(load("two_places.json"))

    assert SCHEMA_VERSION == "1"
    assert extraction.is_relevant
    assert [p.name for p in extraction.places] == ["Quán Bánh Tráng Cô Ba", "Cafe Mây"]
    assert extraction.places[0].items[0].price_vnd == 25000
    assert extraction.places[0].contacts[0].type == "phone"
    assert extraction.places[1].price_unit is None


def test_rejects_unknown_category() -> None:
    data = load("two_places.json")
    data["places"][0]["category"] = "an_uong"

    with pytest.raises(ValidationError):
        VideoExtraction.model_validate(data)


def test_rejects_unknown_time_slot() -> None:
    data = load("two_places.json")
    data["places"][0]["time_slots"] = ["buoi_sang"]

    with pytest.raises(ValidationError):
        VideoExtraction.model_validate(data)


def test_rejects_confidence_out_of_range() -> None:
    data = load("two_places.json")
    data["places"][0]["confidence"] = 1.5

    with pytest.raises(ValidationError):
        VideoExtraction.model_validate(data)

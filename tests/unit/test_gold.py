import json
from pathlib import Path

import pytest

from app.eval.gold import file_state, pending_candidates, write_skeleton
from app.eval.runner import load_gold
from tests.fakes import gemini_fixture


def _candidates_file(directory: Path, candidates: list[dict]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "20260101T000000Z_candidates.json").write_text(
        json.dumps({"candidates": candidates}), encoding="utf-8"
    )


def test_skeleton_is_todo_and_refuses_to_load(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    path = write_skeleton(gold, "a" * 11)
    assert file_state(path) == ("todo", None)
    with pytest.raises(ValueError, match="not ready"):
        load_gold(gold)


def test_write_skeleton_never_overwrites_a_label(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / ("a" * 11 + ".json")).write_text(gemini_fixture("two_places.json"), encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_skeleton(gold, "a" * 11)


def test_invalid_and_broken_files_are_reported(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / "x.json").write_text("{not json", encoding="utf-8")
    (gold / "y.json").write_text(json.dumps({"is_relevant": "maybe"}), encoding="utf-8")
    assert file_state(gold / "x.json")[0] == "invalid"
    assert file_state(gold / "y.json")[0] == "invalid"
    with pytest.raises(ValueError, match="x.json"):
        load_gold(gold)


def test_valid_label_loads(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / ("a" * 11 + ".json")).write_text(gemini_fixture("two_places.json"), encoding="utf-8")
    assert file_state(gold / ("a" * 11 + ".json")) == ("ok", None)
    assert [i.video_id for i in load_gold(gold)] == ["a" * 11]


def test_pending_skips_labeled_and_skeleton_videos_and_duplicates(tmp_path: Path) -> None:
    cands = tmp_path / "candidates"
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / ("a" * 11 + ".json")).write_text(gemini_fixture("two_places.json"), encoding="utf-8")
    write_skeleton(gold, "b" * 11)
    _candidates_file(
        cands,
        [
            {"video_id": "a" * 11, "district": "Quận 1"},
            {"video_id": "b" * 11, "district": "Quận 1"},
            {"video_id": "c" * 11, "district": "Quận 3"},
            {"video_id": "c" * 11, "district": "Quận 3"},
        ],
    )
    pending = pending_candidates(cands, gold)
    assert [c["video_id"] for c in pending] == ["c" * 11]

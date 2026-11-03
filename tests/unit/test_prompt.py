from app.analysis.prompts import PROMPT_VERSION, build_prompt
from app.tags.seed import SEED_TAGS


def test_prompt_version() -> None:
    assert PROMPT_VERSION == "1"


def test_prompt_lists_fixed_values_and_suggested_tags() -> None:
    prompt = build_prompt()

    for value in (
        "sang",
        "trua",
        "chieu",
        "toi",
        "khuya",
        "mot_minh",
        "cap_doi",
        "nhom_nho",
        "nhom_lon",
        "gia_dinh",
        "indoor",
        "outdoor",
        "mixed",
    ):
        assert value in prompt
    for tag in SEED_TAGS:
        assert tag.slug in prompt
    # Suggested tags keep seed order (FR-9.3: only append at the end).
    positions = [prompt.index(f"`{t.slug}`") for t in SEED_TAGS if t.kind == "vibe"]
    assert positions == sorted(positions)


def test_prompt_requires_null_for_missing_facts() -> None:
    prompt = build_prompt()

    assert "null" in prompt
    assert "evidence" in prompt
    assert "MM:SS" in prompt

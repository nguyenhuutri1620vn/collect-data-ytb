import pytest

from app.resolution.aggregate import MentionFacts, aggregate_place


def _m(video_id: str, confidence: float = 0.9, **kw) -> MentionFacts:  # noqa: ANN003
    return MentionFacts(video_id=video_id, confidence=confidence, **kw)


def test_price_is_median_after_dropping_values_over_three_times_the_median() -> None:
    mentions = [
        _m("a", price_min_vnd=20000, price_max_vnd=30000),
        _m("b", price_min_vnd=25000, price_max_vnd=35000),
        _m("c", price_min_vnd=30000, price_max_vnd=40000),
        _m("d", price_min_vnd=900000, price_max_vnd=900000),  # typo-like outlier
    ]
    out = aggregate_place(mentions)
    assert out["price_min_vnd"] == 25000
    assert out["price_max_vnd"] == 35000


def test_price_unit_tie_gives_none_and_majority_wins() -> None:
    tie = [_m("a", price_unit="per_item"), _m("b", price_unit="per_person")]
    assert aggregate_place(tie)["price_unit"] is None
    majority = [*tie, _m("c", price_unit="per_item")]
    assert aggregate_place(majority)["price_unit"] == "per_item"


def test_tag_list_keeps_values_in_at_least_min_share_of_mentions_with_the_field() -> None:
    mentions = [
        _m("a", vibes=("chill", "yen_tinh")),
        _m("b", vibes=("chill",)),
        _m("c", vibes=("binh_dan",)),
        _m("d", vibes=()),  # empty field does not count toward the denominator
    ]
    out = aggregate_place(mentions, attr_min_share=0.3)
    # 3 mentions have vibes. chill: 2/3, binh_dan: 1/3 (kept), yen_tinh: 1/3 (kept)
    assert out["vibes"] == ["binh_dan", "chill", "yen_tinh"]
    assert out["vibe_counts"] == {"binh_dan": 1, "chill": 2, "yen_tinh": 1}

    strict = aggregate_place(mentions, attr_min_share=0.5)
    assert strict["vibes"] == ["chill"]


def test_setting_tie_between_indoor_and_outdoor_is_mixed() -> None:
    mixed = [_m("a", setting="indoor"), _m("b", setting="outdoor")]
    assert aggregate_place(mixed)["setting"] == "mixed"


def test_setting_other_tie_is_none() -> None:
    tie = [
        _m("a", setting="indoor"),
        _m("b", setting="indoor"),
        _m("c", setting="mixed"),
        _m("d", setting="mixed"),
    ]
    assert aggregate_place(tie)["setting"] is None


def test_reservation_tie_is_none() -> None:
    tie = [_m("a", reservation_required=True), _m("b", reservation_required=False)]
    assert aggregate_place(tie)["reservation_required"] is None


def test_contacts_are_merged_after_normalization_and_counted() -> None:
    mentions = [
        _m("a", contacts=(("phone", "0901 234 567"),)),
        _m("b", contacts=(("phone", "0901234567"), ("facebook", "https://fb.com/cafemay?ref=x"))),
        _m("c", contacts=(("facebook", "https://fb.com/cafemay"),)),
    ]
    contacts = {
        (c["type"], c["value"]): c["mentions"] for c in aggregate_place(mentions)["contacts"]
    }
    assert contacts == {("phone", "0901234567"): 2, ("facebook", "https://fb.com/cafemay"): 2}


def test_sentences_are_deduplicated_ordered_by_confidence_and_capped_at_ten() -> None:
    low = _m("low", confidence=0.2, tips=("tip x",))
    high = _m("high", confidence=0.9, tips=tuple(f"tip {i}" for i in range(8)) + ("tip x",))
    mid = _m("mid", confidence=0.5, tips=("tip y", "tip 0", "tip z"))
    tips = aggregate_place([low, high, mid])["tips"]

    assert len(tips) == 10
    assert tips[0] == {"text": "tip 0", "video_id": "high"}
    assert {"text": "tip x", "video_id": "high"} in tips  # kept from the higher-confidence mention
    assert all(t["text"] != "tip x" or t["video_id"] == "high" for t in tips)
    assert tips.count({"text": "tip 0", "video_id": "high"}) == 1


def test_items_group_by_normalized_name_with_median_price() -> None:
    mentions = [
        _m("a", items=(("Bánh tráng trộn", 25000),)),
        _m("b", items=(("banh trang tron", 30000), ("Nước mía", None))),
        _m("c", items=(("Bánh Tráng Trộn", 35000),)),
    ]
    items = {i["name"]: i for i in aggregate_place(mentions)["items"]}
    assert items["Bánh tráng trộn"] == {
        "name": "Bánh tráng trộn",
        "mentions": 3,
        "price_vnd": 30000,
    }
    assert items["Nước mía"]["price_vnd"] is None


def test_source_videos_and_mention_count() -> None:
    out = aggregate_place([_m("low", 0.2), _m("high", 0.9), _m("high", 0.8)])
    assert out["mention_count"] == 3
    assert out["source_video_ids"] == ["high", "low"]


def test_a_place_needs_a_mention() -> None:
    with pytest.raises(ValueError):
        aggregate_place([])

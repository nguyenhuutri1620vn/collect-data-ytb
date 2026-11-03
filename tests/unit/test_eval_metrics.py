from app.core.similarity import name_overlap
from app.eval.metrics import aggregate, match_places, score_video
from app.schemas.extraction import VideoExtraction
from tests.fakes import gemini_fixture

THRESHOLD = 0.8


def _fixture() -> VideoExtraction:
    return VideoExtraction.model_validate_json(gemini_fixture("two_places.json"))


def _with_place(extraction: VideoExtraction, index: int, **changes) -> VideoExtraction:
    places = list(extraction.places)
    places[index] = places[index].model_copy(update=changes)
    return extraction.model_copy(update={"places": places})


def test_name_overlap_ignores_generic_words_and_diacritics() -> None:
    assert name_overlap("Quán Bánh Tráng Cô Ba", "Bánh Tráng Cô Ba") == 1.0
    assert name_overlap("Cafe Mây", "Tiệm Cafe May") == 1.0
    assert name_overlap("Cafe Mây", "Phở Bò") == 0.0


def test_match_places_is_one_to_one_and_respects_threshold() -> None:
    pred = _fixture().places
    gold = list(reversed(pred))
    assert sorted(match_places(pred, gold, THRESHOLD)) == [(0, 1), (1, 0)]
    assert match_places(pred, gold, 1.01) == []


def test_perfect_prediction_scores_full_precision_and_recall() -> None:
    extraction = _fixture()
    score = score_video(extraction, extraction, THRESHOLD)
    total = aggregate([score])

    assert score.relevant_ok
    assert total["name"].tp == 2 and total["name"].fp == total["name"].fn == 0
    for key, counts in total.items():
        assert counts.precision() in (1.0, None), key
        assert counts.hallucinated == 0, key


def test_value_in_prediction_where_gold_is_empty_counts_as_hallucination() -> None:
    gold = _fixture()
    # Gold says Cafe Mây has no vibes/price; prediction invents a price.
    pred = _with_place(gold, 1, price_min_vnd=30000, price_max_vnd=40000)
    total = aggregate([score_video(pred, gold, THRESHOLD)])

    # Only the second pair has an empty gold price, and the prediction fills it in.
    assert total["price"].gold_empty == 1
    assert total["price"].hallucinated == 1
    assert total["price"].hallucination_rate() == 1.0


def test_wrong_district_is_false_positive_and_false_negative() -> None:
    gold = _fixture()
    pred = _with_place(gold, 0, district_raw="Quận 10")
    total = aggregate([score_video(pred, gold, THRESHOLD)])

    # Place 0 is wrong; place 1 (Bình Thạnh) still agrees, so one of two matches.
    assert total["district"].tp == 1
    assert total["district"].fp == 1
    assert total["district"].fn == 1
    assert total["district"].precision() == 0.5


def test_tags_are_compared_after_slug_normalization() -> None:
    gold = _fixture()
    # fixture vibes are "Bình dân" / "check-in"; slugs are binh_dan / check_in
    pred = _with_place(gold, 0, vibes=["binh dan", "CHECK-IN"])
    total = aggregate([score_video(pred, gold, THRESHOLD)])

    # Place 0 has 2 vibes and place 1 has 3, all agreeing after normalization.
    assert total["vibes"].tp == 5
    assert total["vibes"].fp == 0


def test_irrelevant_prediction_has_no_places_and_wrong_relevance() -> None:
    gold = _fixture()
    pred = gold.model_copy(update={"is_relevant": False})
    score = score_video(pred, gold, THRESHOLD)

    assert not score.relevant_ok
    assert score.counts["name"].fn == 2
    assert score.counts["name"].tp == 0

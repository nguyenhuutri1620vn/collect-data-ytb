import pytest

from app.resolution.confidence import addresses_conflict, count_factor, place_confidence


def test_count_factor_rewards_repeat_mentions() -> None:
    assert count_factor(1) == pytest.approx(0.7)
    assert count_factor(2) == pytest.approx(0.91)
    with pytest.raises(ValueError):
        count_factor(0)


def test_confidence_worked_examples_from_d26() -> None:
    # no address conflict, one mention at 0.9 -> 0.9 * 1.0 * 0.7 = 0.63, published at 0.6
    assert place_confidence([0.9], address_conflict=False) == 0.63
    # conflicting addresses -> 0.9 * 0.7 * 0.7 = 0.441, not published
    assert place_confidence([0.9], address_conflict=True) == 0.441


def test_addresses_conflict_only_when_two_addresses_disagree() -> None:
    assert not addresses_conflict([None, "12 Đường Số 1"], threshold=0.8)
    assert not addresses_conflict(["12 Đường Số 1", "12 Đường Số 1, Quận 3"], threshold=0.8)
    assert addresses_conflict(["12 Đường Số 1", "99 Lê Lợi"], threshold=0.8)

from app.resolution.grouping import group_mentions


def test_same_name_and_district_join_one_group() -> None:
    mentions = [("Bò Né 3 Ngon", "Quận 12"), ("Bò Né 3 Ngon - Dương Thị Mười", "Quận 12")]
    assert group_mentions(mentions, threshold=0.8) == [[0, 1]]


def test_same_name_in_another_district_stays_apart() -> None:
    mentions = [("Trà Sữa ABC", "Quận 1"), ("Trà Sữa ABC", "Quận 3")]
    assert group_mentions(mentions, threshold=0.8) == [[0], [1]]


def test_mention_without_district_is_never_grouped() -> None:
    mentions = [("Phở Hà Nội", None), ("Phở Hà Nội", None), ("Phở Hà Nội", "Quận 1")]
    assert group_mentions(mentions, threshold=0.8) == [[0], [1], [2]]


def test_chain_does_not_merge_beyond_the_first_name() -> None:
    # A ~ B and B ~ C, but A and C are not similar: C must not join the group of A.
    mentions = [
        ("Quán Cơm Nhà", "Quận 4"),
        ("Cơm Nhà Mẹ", "Quận 4"),
        ("Mẹ Nấu Cơm", "Quận 4"),
    ]
    groups = group_mentions(mentions, threshold=0.6)
    assert [0, 2] not in groups and [0, 1, 2] not in groups

from app.core.similarity import name_overlap


def test_overlap_accepts_longer_google_name() -> None:
    assert name_overlap("Bò Né 3 Ngon", "Bò Né 3 Ngon - Dương Thị Mười") == 1.0
    assert name_overlap("Cafe Mây", "Phở Bò") == 0.0
    assert name_overlap("quán", "Tiệm") == 0.0  # only generic words

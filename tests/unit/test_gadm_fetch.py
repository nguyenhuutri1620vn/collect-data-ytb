import io
import zipfile
from pathlib import Path

import pytest

from app.geo import gadm

URL = gadm.GADM_SOURCES["4.1"]


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes = b"", length: int = 0) -> None:
        super().__init__(body)
        self.headers = {"Content-Length": str(length or len(body))}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def zipped(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_fetch_declined_downloads_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[str] = []

    def fake_urlopen(req, timeout=None):  # noqa: ANN001, ANN202
        calls.append(getattr(req, "method", None) or "GET")
        return FakeResponse(length=1024 * 1024)

    monkeypatch.setattr(gadm.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(SystemExit):
        gadm.fetch("4.1", tmp_path, assume_yes=False, confirm=lambda _: False)

    assert calls == ["HEAD"]
    assert list(tmp_path.iterdir()) == []
    out = capsys.readouterr().out
    assert "gadm41_VNM_2.json.zip" in out
    assert URL in out
    assert "1.0 MB" in out


def test_fetch_extracts_json_safely(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    body = zipped({"../evil/gadm41_VNM_2.json": b'{"type": "FeatureCollection"}'})

    def fake_urlopen(req, timeout=None):  # noqa: ANN001, ANN202
        return FakeResponse(b"" if getattr(req, "method", None) == "HEAD" else body, len(body))

    monkeypatch.setattr(gadm.urllib.request, "urlopen", fake_urlopen)

    path = gadm.fetch("4.1", tmp_path, assume_yes=True)

    assert path == tmp_path / "gadm41_VNM_2.json"
    assert path.read_text() == '{"type": "FeatureCollection"}'
    assert not (tmp_path.parent / "evil").exists()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HồChíMinh", "Hồ Chí Minh"),
        ("Quận1", "Quận 1"),
        ("Quận12", "Quận 12"),
        ("BìnhThạnh", "Bình Thạnh"),
        ("ThủĐức", "Thủ Đức"),
        ("Bình Thạnh", "Bình Thạnh"),
    ],
)
def test_gadm_display_name(raw: str, expected: str) -> None:
    assert gadm.gadm_display_name(raw) == expected

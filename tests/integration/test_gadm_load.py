import json
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.gadm import BoundaryLoadError, LoadReport, load_boundaries

FIXTURES = Path(__file__).parent.parent / "fixtures" / "geo"
PRE2021 = FIXTURES / "districts_pre2021.geojson"
MERGED = FIXTURES / "districts_merged.geojson"
SQUARE_AREA = 0.01 * 0.01


def variant(tmp_path: Path, source: Path, edit) -> Path:  # noqa: ANN001
    data = json.loads(source.read_text())
    edit(data["features"])
    path = tmp_path / source.name
    path.write_text(json.dumps(data, ensure_ascii=False))
    return path


async def scalar(session: AsyncSession, sql: str) -> object:
    return (await session.execute(text(sql))).scalar_one()


async def test_load_pre2021(session: AsyncSession) -> None:
    report = await load_boundaries(session, PRE2021)

    assert report == LoadReport(districts_loaded=22, sub_areas_loaded=3, sub_areas_missing=[])
    assert await scalar(session, "SELECT count(*) FROM legacy_districts WHERE geom IS NULL") == 0
    assert await scalar(
        session,
        "SELECT bool_and(ST_GeometryType(geom) = 'ST_MultiPolygon' AND ST_SRID(geom) = 4326) "
        "FROM legacy_districts",
    )
    area = await scalar(
        session, "SELECT ST_Area(geom) FROM legacy_districts WHERE name = 'TP Thủ Đức'"
    )
    assert area == pytest.approx(3 * SQUARE_AREA, abs=1e-9)
    assert await scalar(session, "SELECT count(*) FROM legacy_sub_areas WHERE geom IS NULL") == 0


async def test_ignores_other_provinces(session: AsyncSession) -> None:
    await load_boundaries(session, PRE2021)

    dong_nai = "ST_MakeEnvelope(107.4, 11.4, 107.41, 11.41, 4326)"
    assert not await scalar(
        session,
        f"SELECT ST_Intersects(geom, {dong_nai}) FROM legacy_districts WHERE name = 'Tân Phú'",
    )


async def test_load_merged_without_sub_areas(session: AsyncSession) -> None:
    report = await load_boundaries(session, MERGED)

    assert report.sub_areas_loaded == 0
    assert report.sub_areas_missing == ["Quận 2", "Quận 9", "Quận Thủ Đức"]
    assert await scalar(session, "SELECT count(*) FROM legacy_sub_areas WHERE geom IS NULL") == 3
    area = await scalar(
        session, "SELECT ST_Area(geom) FROM legacy_districts WHERE name = 'TP Thủ Đức'"
    )
    assert area == pytest.approx(0.05 * 0.05, abs=1e-9)


async def test_load_merged_with_sub_area_file(session: AsyncSession) -> None:
    report = await load_boundaries(session, MERGED, PRE2021)

    assert report.sub_areas_loaded == 3
    assert report.sub_areas_missing == []
    area = await scalar(
        session, "SELECT ST_Area(geom) FROM legacy_districts WHERE name = 'TP Thủ Đức'"
    )
    assert area == pytest.approx(0.05 * 0.05, abs=1e-9)


async def test_sub_area_file_must_be_pre2021(session: AsyncSession) -> None:
    with pytest.raises(BoundaryLoadError, match="pre-2021"):
        await load_boundaries(session, MERGED, MERGED)


async def test_load_twice_is_idempotent(session: AsyncSession) -> None:
    first = await load_boundaries(session, PRE2021)
    second = await load_boundaries(session, PRE2021)

    assert first == second
    area = await scalar(
        session, "SELECT ST_Area(geom) FROM legacy_districts WHERE name = 'TP Thủ Đức'"
    )
    assert area == pytest.approx(3 * SQUARE_AREA, abs=1e-9)


async def test_unmapped_name_raises(session: AsyncSession, tmp_path: Path) -> None:
    def add_unknown(features: list) -> None:
        extra = json.loads(json.dumps(features[0]))
        extra["properties"]["NAME_2"] = "Quận 99"
        features.append(extra)

    with pytest.raises(BoundaryLoadError, match="Quận 99"):
        await load_boundaries(session, variant(tmp_path, PRE2021, add_unknown))


async def test_missing_district_raises(session: AsyncSession, tmp_path: Path) -> None:
    def drop_can_gio(features: list) -> None:
        features[:] = [f for f in features if f["properties"]["NAME_2"] != "Cần Giờ"]

    with pytest.raises(BoundaryLoadError, match="Cần Giờ"):
        await load_boundaries(session, variant(tmp_path, PRE2021, drop_can_gio))


async def test_load_gadm41_spaceless_names(session: AsyncSession, tmp_path: Path) -> None:
    """GADM 4.1 writes names without spaces: "HồChíMinh", "Quận1", "BìnhThạnh"."""

    def squash(features: list) -> None:
        for f in features:
            for key in ("NAME_1", "NAME_2"):
                f["properties"][key] = f["properties"][key].replace(" ", "")

    report = await load_boundaries(session, variant(tmp_path, PRE2021, squash))

    assert report == LoadReport(districts_loaded=22, sub_areas_loaded=3, sub_areas_missing=[])
    dong_nai = "ST_MakeEnvelope(107.4, 11.4, 107.41, 11.41, 4326)"
    assert not await scalar(
        session,
        f"SELECT ST_Intersects(geom, {dong_nai}) FROM legacy_districts WHERE name = 'Tân Phú'",
    )


@pytest.mark.parametrize("dropped", ["Thủ Đức", "Quận 9"])
async def test_partial_pre2021_file_raises(
    session: AsyncSession, tmp_path: Path, dropped: str
) -> None:
    """A file with only some of Quận 2 / Quận 9 / Thủ Đức would load an incomplete TP Thủ Đức."""

    def drop(features: list) -> None:
        features[:] = [f for f in features if f["properties"]["NAME_2"] != dropped]

    with pytest.raises(BoundaryLoadError, match="TP Thủ Đức"):
        await load_boundaries(session, variant(tmp_path, PRE2021, drop))

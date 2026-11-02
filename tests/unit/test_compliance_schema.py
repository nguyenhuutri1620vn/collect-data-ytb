from geoalchemy2 import Geography, Geometry

from app.models import Base

BOUNDARY_GEOM_COLUMNS = {"legacy_districts.geom", "legacy_sub_areas.geom", "wards.geom"}
LOCATION_NAMES = {"lat", "lng", "latitude", "longitude", "location", "coordinates"}


def test_no_location_columns() -> None:
    """C7/D16: place coordinates are never persisted; geometry is only for boundaries."""
    geom_columns = set()
    for table in Base.metadata.tables.values():
        for column in table.columns:
            assert column.name not in LOCATION_NAMES, f"{table.name}.{column.name}"
            if isinstance(column.type, Geometry | Geography):
                geom_columns.add(f"{table.name}.{column.name}")

    assert geom_columns == BOUNDARY_GEOM_COLUMNS

"""GADM boundaries: download (`fetch`) and load into legacy_districts / legacy_sub_areas (`load`).

GADM files are not committed (license forbids redistribution, C11, D23); see data/geo/README.

    python -m app.geo.gadm fetch [--version 4.1] [--dest data/geo/raw] [--yes]
    python -m app.geo.gadm load --districts PATH [--sub-areas PATH]
"""

import argparse
import asyncio
import json
import logging
import shutil
import sys
import unicodedata
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.db import create_engine
from app.core.logging import configure_logging
from app.core.text import normalize_text
from app.geo.aliases import resolve_legacy_district, resolve_legacy_sub_area
from app.geo.districts import LEGACY_DISTRICTS, LEGACY_SUB_AREAS

logger = logging.getLogger(__name__)

# Level 2 (district) boundaries for Vietnam.
GADM_SOURCES: dict[str, str] = {
    "4.1": "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_VNM_2.json.zip",
}
DEFAULT_DEST = Path("data/geo/raw")

_HCM_PROVINCE_NAMES = {"ho chi minh", "thanh pho ho chi minh"}
_PRE2021_MARKERS = {"Quận 2", "Quận 9"}


class BoundaryLoadError(Exception):
    pass


@dataclass
class LoadReport:
    districts_loaded: int
    sub_areas_loaded: int
    sub_areas_missing: list[str] = field(default_factory=list)


def _ask(prompt: str) -> bool:
    return input(prompt).strip().lower() in {"y", "yes"}


def fetch(
    version: str,
    dest_dir: Path,
    *,
    assume_yes: bool,
    confirm: Callable[[str], bool] = _ask,
) -> Path:
    """Download and unzip one GADM file after showing its name, source and size."""
    url = GADM_SOURCES[version]
    filename = url.rsplit("/", 1)[1]
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as resp:
        size = int(resp.headers.get("Content-Length") or 0)
    print(f"File:   {filename}\nSource: {url}\nSize:   {size / 1024 / 1024:.1f} MB")
    if not assume_yes and not confirm("Download? [y/N] "):
        raise SystemExit(1)

    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / filename
    with urllib.request.urlopen(urllib.request.Request(url), timeout=300) as resp:
        with zip_path.open("wb") as out:
            shutil.copyfileobj(resp, out)

    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.namelist():
            if not member.endswith(".json"):
                continue
            # Write by basename only: archive paths are untrusted (no "../" escapes).
            target = dest_dir / Path(member).name
            with archive.open(member) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
            extracted.append(target)
    if not extracted:
        raise BoundaryLoadError(f"no .json file in {filename}")
    print(f"Saved:  {extracted[0]}")
    return extracted[0]


def gadm_display_name(name: str) -> str:
    """Restore spaces GADM 4.1 drops ("BìnhThạnh" -> "Bình Thạnh", "Quận1" -> "Quận 1")."""
    name = unicodedata.normalize("NFC", name)
    out: list[str] = []
    for prev, char in zip(" " + name, name, strict=False):
        if (prev.islower() and char.isupper()) or (prev.isalpha() and char.isdigit()):
            out.append(" ")
        out.append(char)
    return "".join(out)


def _hcm_features(path: Path) -> list[tuple[str, dict]]:
    """(NAME_2, geometry) of every feature in Ho Chi Minh City."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        (gadm_display_name(f["properties"]["NAME_2"]), f["geometry"])
        for f in data["features"]
        if normalize_text(gadm_display_name(f["properties"]["NAME_1"])) in _HCM_PROVINCE_NAMES
    ]


def _sub_area_geometries(features: list[tuple[str, dict]]) -> dict[str, list[dict]] | None:
    """Sub-area geometries if the file predates the 2021 Thủ Đức merger, else None."""
    found: dict[str, list[dict]] = {}
    for name, geometry in features:
        sub_area = resolve_legacy_sub_area(name)
        if sub_area:
            found.setdefault(sub_area, []).append(geometry)
    return found if _PRE2021_MARKERS <= found.keys() else None


async def _set_geom(session: AsyncSession, table: str, name: str, geometries: list[dict]) -> None:
    await session.execute(
        text(
            f"UPDATE {table} SET geom = ("
            "  SELECT ST_Multi(ST_Union(ST_SetSRID(ST_GeomFromGeoJSON(g), 4326)))"
            "  FROM unnest(CAST(:geoms AS text[])) AS g"
            ") WHERE name = :name"
        ),
        {"name": name, "geoms": [json.dumps(g) for g in geometries]},
    )


async def load_boundaries(
    session: AsyncSession, districts_file: Path, sub_areas_file: Path | None = None
) -> LoadReport:
    """Overwrite district and sub-area polygons; idempotent. Does not commit."""
    features = _hcm_features(districts_file)

    districts: dict[str, list[dict]] = {}
    unmapped: list[str] = []
    for name, geometry in features:
        district = resolve_legacy_district(name)
        if district is None:
            unmapped.append(name)
        else:
            districts.setdefault(district, []).append(geometry)
    if unmapped:
        raise BoundaryLoadError(f"unmapped GADM district names: {', '.join(unmapped)}")
    missing = [d for d in LEGACY_DISTRICTS if d not in districts]
    if missing:
        raise BoundaryLoadError(f"districts missing from {districts_file}: {', '.join(missing)}")

    sub_areas = _sub_area_geometries(features)
    if sub_areas is None and sub_areas_file is not None:
        sub_areas = _sub_area_geometries(_hcm_features(sub_areas_file))
        if sub_areas is None:
            raise BoundaryLoadError(f"{sub_areas_file} is not a pre-2021 file (no Quận 2 / Quận 9)")
    sub_areas = sub_areas or {}

    for district, geometries in districts.items():
        await _set_geom(session, "legacy_districts", district, geometries)
    for sub_area, geometries in sub_areas.items():
        await _set_geom(session, "legacy_sub_areas", sub_area, geometries)

    return LoadReport(
        districts_loaded=len(districts),
        sub_areas_loaded=len(sub_areas),
        sub_areas_missing=[s for s in LEGACY_SUB_AREAS if s not in sub_areas],
    )


async def _load_command(districts_file: Path, sub_areas_file: Path | None) -> LoadReport:
    engine = create_engine(get_settings().database_url)
    try:
        async with async_sessionmaker(engine)() as session:
            report = await load_boundaries(session, districts_file, sub_areas_file)
            await session.commit()
        return report
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="python -m app.geo.gadm")
    commands = parser.add_subparsers(dest="command", required=True)

    fetch_cmd = commands.add_parser("fetch", help="download GADM level-2 boundaries")
    fetch_cmd.add_argument("--version", default="4.1", choices=sorted(GADM_SOURCES))
    fetch_cmd.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    fetch_cmd.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    load_cmd = commands.add_parser("load", help="load boundaries into the database")
    load_cmd.add_argument("--districts", type=Path, required=True)
    load_cmd.add_argument("--sub-areas", type=Path)

    args = parser.parse_args(argv)
    if args.command == "fetch":
        fetch(args.version, args.dest, assume_yes=args.yes)
        return 0
    try:
        report = asyncio.run(_load_command(args.districts, args.sub_areas))
    except BoundaryLoadError as exc:
        logger.error("boundary load failed", extra={"error": str(exc)})
        return 1
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, text_array


def boundary() -> Mapped[object | None]:
    # GiST index is declared explicitly per table so migrations and models stay comparable.
    return mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=False))


class LegacyDistrict(Base):
    """Pre-2025 district (quận/huyện cũ); boundaries from GADM (FR-5.3, FR-5.6)."""

    __tablename__ = "legacy_districts"
    __table_args__ = (Index("ix_legacy_districts_geom", "geom", postgresql_using="gist"),)

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    aliases: Mapped[list[str]] = text_array()
    target_places: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    geom: Mapped[object | None] = boundary()


class LegacySubArea(Base):
    """Quận 2 / Quận 9 / Quận Thủ Đức inside TP Thủ Đức (FR-5.3)."""

    __tablename__ = "legacy_sub_areas"
    __table_args__ = (Index("ix_legacy_sub_areas_geom", "geom", postgresql_using="gist"),)

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    legacy_district: Mapped[str] = mapped_column(
        Text, ForeignKey("legacy_districts.name"), nullable=False
    )
    geom: Mapped[object | None] = boundary()


class Ward(Base):
    """Post-2025 commune-level unit. No polygon source yet, so the table stays empty in M1."""

    __tablename__ = "wards"
    __table_args__ = (Index("ix_wards_geom", "geom", postgresql_using="gist"),)

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    legacy_districts: Mapped[list[str]] = text_array()
    geom: Mapped[object | None] = boundary()

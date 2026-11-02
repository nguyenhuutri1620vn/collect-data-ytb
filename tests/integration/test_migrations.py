import asyncio

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models import Base
from tests.conftest import alembic_config

TABLES = {
    "videos",
    "analyses",
    "mentions",
    "places",
    "tags",
    "channels",
    "keywords",
    "keyword_runs",
    "video_keywords",
    "quota_usage",
    "legacy_districts",
    "legacy_sub_areas",
    "wards",
}
POSTGIS_TABLES = {"spatial_ref_sys"}


def public_tables(url: str) -> set[str]:
    """Sync helper (no running event loop): alembic commands run in sync tests too."""

    async def fetch() -> set[str]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                names = await conn.run_sync(lambda c: inspect(c).get_table_names(schema="public"))
            return set(names)
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def test_upgrade_creates_all_tables(migrated_db: str) -> None:
    assert TABLES <= public_tables(migrated_db)


async def test_migration_matches_models(session: AsyncSession) -> None:
    def diff(sync_conn):  # noqa: ANN001, ANN202
        context = MigrationContext.configure(
            sync_conn,
            opts={"include_name": lambda name, type_, _: name not in POSTGIS_TABLES},
        )
        return compare_metadata(context, Base.metadata)

    conn = await session.connection()
    assert await conn.run_sync(diff) == []


def test_downgrade_then_upgrade(migrated_db: str) -> None:
    config = alembic_config(migrated_db)

    command.downgrade(config, "base")
    assert public_tables(migrated_db) == POSTGIS_TABLES | {"alembic_version"}

    command.upgrade(config, "head")
    assert TABLES <= public_tables(migrated_db)


async def test_check_constraint_rejects_bad_status(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.execute(
            text(
                "INSERT INTO videos (source, video_id, url, status) "
                "VALUES ('youtube', 'x1', 'https://youtu.be/x1', 'published')"
            )
        )

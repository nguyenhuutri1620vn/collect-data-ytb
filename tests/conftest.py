import os
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture(scope="session")
def test_db_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or get_settings().test_database_url
    if not url:
        pytest.fail("TEST_DATABASE_URL is not set; see .env.example")
    return url


def make_settings(database_url: str) -> Settings:
    return Settings(_env_file=None, database_url=database_url)


async def app_client(database_url: str) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(make_settings(database_url))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def client(test_db_url: str) -> AsyncIterator[httpx.AsyncClient]:
    async for c in app_client(test_db_url):
        yield c


def alembic_config(database_url: str):  # noqa: ANN201 - alembic Config
    from alembic.config import Config

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture(scope="session")
def migrated_db(test_db_url: str) -> str:
    from alembic import command

    config = alembic_config(test_db_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return test_db_url


@pytest.fixture
async def session(migrated_db: str) -> AsyncIterator[AsyncSession]:
    """Session inside an outer transaction that is rolled back after the test."""
    engine = create_async_engine(migrated_db)
    async with engine.connect() as conn:
        trans = await conn.begin()
        async with AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as s:
            yield s
        await trans.rollback()
    await engine.dispose()

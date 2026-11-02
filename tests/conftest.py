import os
from collections.abc import AsyncIterator

import httpx
import pytest

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

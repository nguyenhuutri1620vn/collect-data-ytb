import time

import httpx

from tests.conftest import app_client

UNREACHABLE_DB = "postgresql+asyncpg://saigon:saigon@127.0.0.1:1/x"


async def test_health_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


async def test_health_db_down() -> None:
    async for client in app_client(UNREACHABLE_DB):
        started = time.monotonic()
        response = await client.get("/health")
        elapsed = time.monotonic() - started

        assert response.status_code == 503
        assert response.json() == {"status": "degraded", "db": "error"}
        assert elapsed < 6

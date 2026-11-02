from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

CONNECT_TIMEOUT_SECONDS = 5


def create_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, connect_args={"timeout": CONNECT_TIMEOUT_SECONDS})


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session

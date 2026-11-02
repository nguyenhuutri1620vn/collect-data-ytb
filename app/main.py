from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api import health
from app.core.config import Settings, get_settings
from app.core.db import create_engine
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine((settings or get_settings()).database_url)
        app.state.engine = engine
        app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            yield
        finally:
            await engine.dispose()

    configure_logging()
    app = FastAPI(title="Saigon Places Collector (ops)", lifespan=lifespan)
    app.include_router(health.router)
    return app


app = create_app()

"""Rebuild places from the current analyses (no Gemini calls).

python -m app.resolution
"""

import asyncio
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.db import create_engine
from app.core.logging import configure_logging
from app.resolution.stage import resolve_places


async def _run() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            report = await resolve_places(session, settings)
            await session.commit()
    finally:
        await engine.dispose()
    print(
        f"mentions {report.mentions} · places {report.places} · "
        f"published {report.published} · draft {report.draft}"
    )
    return 0


def main() -> int:
    configure_logging()
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())

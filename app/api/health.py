import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    try:
        async with request.app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        # Log only the error type: the message may contain the connection URL.
        logger.error("health check failed", extra={"error_type": type(exc).__name__})
        return JSONResponse({"status": "degraded", "db": "error"}, status_code=503)
    return JSONResponse({"status": "ok", "db": "ok"})

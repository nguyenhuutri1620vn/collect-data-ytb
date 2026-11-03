from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.gemini import VideoAnalyzer
from app.analysis.ingest import ingest_and_analyze
from app.api.deps import get_analyzer, get_settings_dep, require_admin
from app.core.config import Settings
from app.core.db import get_session
from app.core.quota import QuotaExceeded

router = APIRouter(dependencies=[Depends(require_admin)])


class IngestRequest(BaseModel):
    url: str
    reanalyze: bool = False


class IngestResponse(BaseModel):
    video_id: str
    status: str
    mention_count: int


@router.post("/ingest/youtube")
async def ingest_youtube(
    body: IngestRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    analyzer: Annotated[VideoAnalyzer, Depends(get_analyzer)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> IngestResponse:
    """Push one YouTube URL through Analysis synchronously (calls Gemini: real quota)."""
    try:
        video, outcome = await ingest_and_analyze(
            session, body.url, analyzer, settings, reanalyze=body.reanalyze
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except QuotaExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    await session.commit()
    return IngestResponse(
        video_id=video.video_id,
        status=video.status,
        mention_count=outcome.mention_count if outcome else 0,
    )

import secrets

from fastapi import Header, HTTPException, Request

from app.analysis.gemini import GeminiClient, VideoAnalyzer
from app.core.config import Settings


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def require_admin(request: Request, authorization: str | None = Header(default=None)) -> None:
    token = request.app.state.settings.admin_token
    expected = f"Bearer {token.get_secret_value()}" if token else None
    if expected is None or not secrets.compare_digest(authorization or "", expected):
        raise HTTPException(status_code=401, detail="invalid or missing admin token")


def get_analyzer(request: Request) -> VideoAnalyzer:
    state = request.app.state
    if getattr(state, "analyzer", None) is None:
        state.analyzer = GeminiClient.from_settings(state.settings)
    return state.analyzer

import pytest
from pydantic import ValidationError

from app.core.config import Settings

DB_URL = "postgresql+asyncpg://u:p@h:1/d"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "NAME_MATCH_THRESHOLD", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_settings_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("NAME_MATCH_THRESHOLD", "0.75")

    settings = Settings(_env_file=None)

    assert settings.database_url == DB_URL
    assert settings.name_match_threshold == 0.75
    assert settings.attr_min_share == 0.3
    assert settings.youtube_data_ttl_days == 30
    assert settings.quota_timezone == "America/Los_Angeles"
    assert settings.gemini_api_key is None


def test_settings_requires_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_secret_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("GEMINI_API_KEY", "abc123")

    settings = Settings(_env_file=None)

    assert "abc123" not in repr(settings)
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "abc123"


def test_empty_optional_values_are_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("GEMINI_DAILY_REQUESTS", "")

    settings = Settings(_env_file=None)

    assert settings.gemini_daily_requests is None

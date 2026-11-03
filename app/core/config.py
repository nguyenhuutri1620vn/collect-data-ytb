from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (RAW_REQUIREMENTS §11)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
    )

    database_url: str
    test_database_url: str | None = None

    youtube_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_media_resolution: Literal["low", "default"] = "low"
    google_places_api_key: SecretStr | None = None
    admin_token: SecretStr | None = None

    timezone: str = "Asia/Ho_Chi_Minh"
    quota_timezone: str = "America/Los_Angeles"

    max_video_seconds: int = 300
    published_after_months: int = 18
    name_match_threshold: float = 0.8
    publish_threshold: float = 0.6
    attr_min_share: float = 0.3
    places_top_n: int = 5
    places_recheck_days: int = 30
    youtube_data_ttl_days: int = 30
    quota_safety_ratio: float = 0.9

    gemini_daily_video_seconds: int = 28800
    gemini_daily_requests: int | None = None
    youtube_daily_units: int = 10000
    places_daily_requests: int | None = None

    good_channel_ratio: float = 0.5
    min_channel_videos: int = 5
    keyword_low_yield_runs: int = 3
    worker_concurrency: int = 1
    max_retries: int = 3

    gemini_price_input_per_1m_usd: float = 0
    gemini_price_output_per_1m_usd: float = 0
    places_text_search_price_per_1k_usd: float | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

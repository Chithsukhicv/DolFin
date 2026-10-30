
"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Firebase
    firebase_credentials_path: str = "./firebase-adminsdk.json"

    # Gemini
    #
    # Model names are a moving target and a wrong one fails as an opaque
    # model-not-found at request time, not at startup. Check the official
    # deprecations documentation before a demo.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"

    # LLM gateway budget and timeouts.
    llm_requests_per_minute: int = 5
    llm_timeout_interactive_seconds: float = 20.0
    llm_timeout_deferred_seconds: float = 45.0

    @field_validator("llm_requests_per_minute")
    @classmethod
    def _budget_range(cls, v: int) -> int:
        if not 1 <= v <= 1000:
            raise ValueError(
                "llm_requests_per_minute must be between 1 and 1000 "
                f"(got {v}). Set LLM_REQUESTS_PER_MINUTE in .env."
            )
        return v

    # Portfolio
    starting_cash: float = 100_000.0

    # Price cache
    price_db_path: str = "./data/prices.db"
    price_refresh_interval_minutes: int = 15

    # Market Movement Predictor
    #
    # Model artifacts are written here (resolved relative to project_root).
    # The directory is .gitignore-covered so trained files never enter version
    # control — see .gitignore for the matching pattern.
    market_ml_model_dir: str = "./data/models"

    # Return thresholds that define UP / DOWN vs SIDEWAYS for each horizon.
    market_ml_return_threshold_1d: float = 0.01
    market_ml_return_threshold_3d: float = 0.015
    market_ml_return_threshold_5d: float = 0.02
    market_ml_return_threshold_10d: float = 0.025

    # Model staleness
    market_ml_staleness_days: int = 7

    # Minimum number of complete feature-vector rows.
    market_ml_min_history_bars: int = 60

    # Corpus C — live market news (GNews API)
    #
    # GNews free tier: 100 requests/day. At the default 4-hour interval
    # the app makes 6 requests/day. Set to "" to disable GNews and fall
    # back to the Google News RSS feed.
    gnews_api_key: str = ""

    # How often to refresh live news.
    news_fetch_interval_hours: int = 4

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            o.strip()
            for o in self.cors_origins.split(",")
            if o.strip()
        ]

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent


@lru_cache
def get_settings() -> Settings:
    return Settings()

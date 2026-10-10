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
    # model-not-found at request time, not at startup. Both previous defaults have
    # since been shut down: gemini-1.5-flash was retired, and text-embedding-004
    # was deprecated in January 2026. Check
    # https://ai.google.dev/gemini-api/docs/deprecations before a demo, and
    # override via .env rather than editing here.
    gemini_api_key: str = ""
    # Chosen by measurement against a real free-tier key, not from the docs.
    # Three traps, all learned the hard way:
    #   - Older Flash models return "no longer available to new users" (404) even
    #     though they still appear in list_models().
    #   - The "-latest" aliases resolve to models with no free quota, so they 429
    #     immediately. Pin a version on the free tier.
    #   - gemini-3.6-flash reasons before answering and took ~24s on a coach-sized
    #     prompt. gemini-3.5-flash returned a complete answer to the same prompt in
    #     5.8s. On a path where a learner is waiting, that difference decides
    #     whether the feature is usable at all.
    gemini_model: str = "gemini-3.5-flash"
    # Must carry the "models/" prefix. GenerativeModel() adds it for you;
    # embed_content() raises ValueError without it, which the gateway would swallow
    # as "embeddings unavailable" and silently fall back to lexical ranking.
    gemini_embedding_model: str = "models/gemini-embedding-001"

    # LLM gateway budget and timeouts.
    #
    # 5/min is the actual free-tier ceiling, reported by the API itself as
    # GenerateRequestsPerMinutePerProjectPerModel-FreeTier. Setting this higher
    # does not buy more capacity; it just means we spend the budget on calls
    # Google rejects instead of degrading to our own fallback. Raise it only
    # alongside a paid plan.
    llm_requests_per_minute: int = 5
    # Interactive paths have a learner waiting; deferred analyses do not.
    # Measured round trip on a coach-sized prompt is ~5.8s, so 20s is roughly 3x
    # headroom for a slow day without leaving anyone staring at a spinner.
    llm_timeout_interactive_seconds: float = 20.0
    llm_timeout_deferred_seconds: float = 45.0

    @field_validator("llm_requests_per_minute")
    @classmethod
    def _budget_range(cls, v: int) -> int:
        # Fail loudly at startup rather than behaving oddly at request time.
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
    # model artifacts are written here (resolved relative to project_root).
    # The directory is .gitignore-covered so trained files never enter version
    # control — see .gitignore for the matching pattern.
    market_ml_model_dir: str = "./data/models"

    # Return thresholds that define UP / DOWN vs SIDEWAYS for each horizon.
    # A 1-day move of ±1 % counts as directional; longer windows use wider bands
    # because prices have more room to drift without a genuine trend forming.
    market_ml_return_threshold_1d: float = 0.01    # ±1.0 % for 1-day horizon
    market_ml_return_threshold_3d: float = 0.015   # ±1.5 % for 3-day horizon
    market_ml_return_threshold_5d: float = 0.02    # ±2.0 % for 5-day horizon
    market_ml_return_threshold_10d: float = 0.025  # ±2.5 % for 10-day horizon

    # A model artifact older than this many days is flagged as stale in the
    # HorizonForecast response. Stale probabilities are still returned; the
    # client decides whether to surface the warning.
    market_ml_staleness_days: int = 7

    # Minimum number of complete feature-vector rows (after NaN drop) required
    # for the predictor to return probabilities. Below this the response carries
    # model_status="insufficient_history" instead of guessing.
    market_ml_min_history_bars: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent


@lru_cache
def get_settings() -> Settings:
    return Settings()

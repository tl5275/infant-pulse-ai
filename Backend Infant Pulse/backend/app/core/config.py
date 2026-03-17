from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SQLITE_PATH = (Path(__file__).resolve().parents[3] / "runtime" / "infant_pulse.db").as_posix()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="INFANT_PULSE_",
    )

    app_name: str = "Infant Pulse Backend"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/infant_pulse",
        validation_alias=AliasChoices("DATABASE_URL", "INFANT_PULSE_DATABASE_URL"),
    )
    sqlite_fallback_url: str = f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH}"
    ingest_queue_size: int = 10_000
    recent_vitals_limit: int = 100
    initial_baby_count: int = Field(default=5, ge=1, le=10)
    enable_db_seed: bool = True
    enable_background_worker: bool = True
    cors_origins: list[str] = ["*"]
    simulator_api_url: str = "http://127.0.0.1:8000"
    simulator_interval_seconds: float = 1.0
    simulator_baby_count: int = Field(default=5, ge=1, le=10)
    simulator_anomaly_probability: float = Field(default=0.08, ge=0.0, le=1.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()

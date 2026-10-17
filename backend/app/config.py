"""Application settings, read from environment variables (and the repo-root .env for local runs)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT_ENV, extra="ignore")

    database_url: str = "postgresql+psycopg://rental:rental@localhost:5432/rental_desk"
    # Comma-separated list of allowed browser origins.
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    @property
    def sqlalchemy_url(self) -> str:
        """Render and Heroku-style hosts hand out `postgres://` / `postgresql://` URLs.

        SQLAlchemy needs to be told to use the psycopg 3 driver.
        """
        for prefix in ("postgres://", "postgresql://"):
            if self.database_url.startswith(prefix):
                return "postgresql+psycopg://" + self.database_url[len(prefix) :]
        return self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

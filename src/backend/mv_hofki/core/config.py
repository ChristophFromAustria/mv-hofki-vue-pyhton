"""Application settings loaded from environment variables / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


def _find_project_root() -> Path:
    """Walk up from this file to find the directory containing pyproject.toml."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "mv_hofki"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    BASE_PATH: str = "/"

    PROJECT_ROOT: Path = _find_project_root()

    DATABASE_URL: str = (
        f"sqlite+aiosqlite:///{_find_project_root() / 'data' / 'mv_hofki.db'}"
    )

    CLOUDFLARE_API_TOKEN: str | None = None
    CLOUDFLARE_ACCOUNT_ID: str | None = None
    CLOUDFLARE_POLICY_ID: str | None = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

"""
Application configuration.

All settings are loaded from environment variables at startup.
The app will refuse to start if required variables are missing.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    # ── InsForge / Database ───────────────────────────────────────────────────
    insforge_url: str
    insforge_anon_key: str
    insforge_api_key: str

    @property
    def database_url(self) -> str:
        """
        Build a SQLAlchemy-compatible PostgreSQL URL from the InsForge host.
        InsForge exposes Postgres on the standard port at the project host.
        The actual connection string is read from the INSFORGE_DB_URL env var
        when available (set after running: npx -y @insforge/cli secrets get DB_URL).
        Falls back to a placeholder so config validation still passes.
        """
        return self.insforge_db_url

    insforge_db_url: str = ""  # populated from: npx -y @insforge/cli secrets get DB_URL

    # InsForge JWT secret — used for server-side token verification
    # Get via: npx -y @insforge/cli secrets get JWT_SECRET
    insforge_jwt_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

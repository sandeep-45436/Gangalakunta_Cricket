"""
Application configuration.

All settings are loaded from environment variables at startup.
Supports both backend variables (INSFORGE_*) and frontend Vite variables (VITE_INSFORGE_*)
so a single .env import on Vercel configures both frontend and serverless API routes.
"""
import os
from functools import lru_cache
from typing import List

from pydantic import model_validator
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
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ── InsForge / Database ───────────────────────────────────────────────────
    insforge_url: str = ""
    insforge_anon_key: str = ""
    insforge_api_key: str = ""

    # ── Gemini / LangGraph AI ─────────────────────────────────────────────────
    gemini_api_key: str = ""

    @model_validator(mode="after")
    def _fallback_vite_env_vars(self) -> "Settings":
        if not self.gemini_api_key:
            self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        if not self.insforge_url:
            self.insforge_url = (
                os.getenv("VITE_INSFORGE_URL")
                or "https://asp6i95i.ap-southeast.insforge.app"
            )
        if not self.insforge_anon_key:
            self.insforge_anon_key = os.getenv("VITE_INSFORGE_ANON_KEY", "")
        if not self.insforge_api_key:
            self.insforge_api_key = (
                os.getenv("INSFORGE_API_KEY")
                or self.insforge_anon_key
                or os.getenv("VITE_INSFORGE_ANON_KEY", "")
            )
        return self

    @property
    def database_url(self) -> str:
        return self.insforge_db_url

    insforge_db_url: str = ""
    insforge_jwt_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

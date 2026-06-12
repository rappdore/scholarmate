"""
Application settings — the single source of truth for every filesystem path
and URL the backend uses.

Values can be overridden with SCHOLARMATE_-prefixed environment variables or
a .env file (e.g. SCHOLARMATE_DB_PATH=/somewhere/else.db). Service
constructors must receive these values from the service registry instead of
hardcoding their own defaults.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SCHOLARMATE_",
        env_file=".env",
        extra="ignore",
    )

    db_path: str = "data/reading_progress.db"
    pdf_dir: str = "pdfs"
    epub_dir: str = "epubs"
    thumbnails_dir: str = "thumbnails"
    # Public base URL of this backend, used when rewriting relative resource
    # URLs (e.g. EPUB images) into absolute ones the frontend can fetch.
    base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()

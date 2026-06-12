"""Tests for the application settings module (audit A-3)."""

from app.settings import Settings, get_settings


class TestDefaults:
    def test_default_values(self):
        settings = Settings(_env_file=None)
        assert settings.db_path == "data/reading_progress.db"
        assert settings.pdf_dir == "pdfs"
        assert settings.epub_dir == "epubs"
        assert settings.thumbnails_dir == "thumbnails"
        assert settings.base_url == "http://localhost:8000"


class TestEnvOverrides:
    def test_env_prefix_override(self, monkeypatch):
        monkeypatch.setenv("SCHOLARMATE_DB_PATH", "/tmp/other.db")
        monkeypatch.setenv("SCHOLARMATE_PDF_DIR", "/tmp/books")
        settings = Settings(_env_file=None)
        assert settings.db_path == "/tmp/other.db"
        assert settings.pdf_dir == "/tmp/books"

    def test_unprefixed_env_is_ignored(self, monkeypatch):
        monkeypatch.setenv("DB_PATH", "/tmp/should-be-ignored.db")
        settings = Settings(_env_file=None)
        assert settings.db_path == "data/reading_progress.db"


class TestGetSettings:
    def test_cached_singleton(self):
        assert get_settings() is get_settings()

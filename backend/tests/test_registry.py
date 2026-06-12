"""
Tests for the lifespan-scoped service registry (audit A-3).

The registry must construct every shared service exactly once from Settings,
wire cross-service collaborators to the same instances (B-3), and support
init/reset for test isolation.
"""

import pytest

from app.services.registry import (
    build_registry,
    get_pdf_service,
    get_registry,
    init_services,
    reset_services,
)
from app.settings import Settings


@pytest.fixture
def tmp_settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        db_path=str(tmp_path / "test.db"),
        pdf_dir=str(tmp_path / "pdfs"),
        epub_dir=str(tmp_path / "epubs"),
        thumbnails_dir=str(tmp_path / "thumbnails"),
    )


@pytest.fixture
def registry(tmp_settings):
    return build_registry(tmp_settings)


class TestBuildRegistry:
    def test_services_share_the_configured_db_path(self, registry, tmp_settings):
        assert registry.db_service.db_path == tmp_settings.db_path
        assert registry.documents_repository.db_path == tmp_settings.db_path
        assert registry.llm_config_service.db_path == tmp_settings.db_path
        assert registry.ollama_service.db_path == tmp_settings.db_path
        assert registry.dual_chat_service.db_path == tmp_settings.db_path

    def test_directories_come_from_settings(self, registry, tmp_settings):
        assert str(registry.pdf_service.pdf_dir) == tmp_settings.pdf_dir
        assert str(registry.epub_service.epub_dir) == tmp_settings.epub_dir
        assert str(registry.pdf_service.thumbnails_dir) == tmp_settings.thumbnails_dir
        assert str(registry.epub_service.thumbnails_dir) == tmp_settings.thumbnails_dir

    def test_dual_chat_gets_the_shared_pdf_service(self, registry):
        # B-3: no second PDFService (and second in-memory cache) for dual chat
        assert registry.dual_chat_service.pdf_service is registry.pdf_service

    def test_chat_context_gets_the_shared_content_processor(self, registry):
        assert (
            registry.epub_chat_context_service.content_processor
            is registry.epub_service.content_processor
        )

    def test_ollama_gets_the_shared_request_tracker(self, registry):
        # Cancellations registered via routers must be visible to streams
        assert (
            registry.ollama_service._request_tracking
            is registry.request_tracking_service
        )


class TestLifecycle:
    def test_init_get_reset(self, tmp_settings):
        try:
            initialized = init_services(tmp_settings)
            assert get_registry() is initialized
            assert get_pdf_service() is initialized.pdf_service

            reinitialized = init_services(tmp_settings)
            assert reinitialized is not initialized
            assert get_registry() is reinitialized
        finally:
            reset_services()

    def test_get_registry_is_stable_between_calls(self, tmp_settings):
        try:
            init_services(tmp_settings)
            assert get_registry() is get_registry()
        finally:
            reset_services()

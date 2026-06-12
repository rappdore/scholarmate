"""
Lifespan-scoped service registry.

All shared service singletons are constructed here, in one place, from the
application Settings — replacing the previous pattern of module-level
instances built at import time (which ran DDL and filesystem cache scans on
import, and let several routers construct their own copies of the same
service with drifting in-memory caches; see audit findings A-3 and B-3).

Lifecycle:
- ``main.py``'s FastAPI lifespan calls :func:`init_services` at startup so
  construction (schema init, cache build, thumbnail generation) happens
  exactly once, fail-fast, when the app starts — not when a module happens
  to be imported.
- Routers declare dependencies with ``Depends(get_pdf_service)`` etc.; the
  ``get_*`` accessors all resolve against the one initialized registry
  (lazily initializing it from default Settings if the app is driven
  without a lifespan, e.g. in some tests).
- Tests can call ``init_services(Settings(db_path=...))`` /
  :func:`reset_services` for an isolated registry, or override individual
  dependencies via ``app.dependency_overrides``.
"""

import logging
from dataclasses import dataclass

from app.settings import Settings, get_settings

from .database_service import DatabaseService
from .documents_repository import DocumentsRepository
from .dual_chat_service import DualChatService
from .epub.epub_chat_context_service import EPUBChatContextService
from .epub_service import EPUBService
from .llm_config_service import LLMConfigService
from .ollama_service import OllamaService
from .pdf_service import PDFService
from .progress_service import ProgressService
from .request_tracking_service import RequestTrackingService
from .tts_service import TTSService

logger = logging.getLogger(__name__)


@dataclass
class ServiceRegistry:
    settings: Settings
    db_service: DatabaseService
    documents_repository: DocumentsRepository
    progress_service: ProgressService
    pdf_service: PDFService
    epub_service: EPUBService
    epub_chat_context_service: EPUBChatContextService
    llm_config_service: LLMConfigService
    request_tracking_service: RequestTrackingService
    ollama_service: OllamaService
    dual_chat_service: DualChatService
    tts_service: TTSService


def build_registry(settings: Settings) -> ServiceRegistry:
    """Construct every shared service exactly once from the given settings."""
    logger.info(
        "Building service registry (db=%s, pdfs=%s, epubs=%s)",
        settings.db_path,
        settings.pdf_dir,
        settings.epub_dir,
    )
    pdf_service = PDFService(
        pdf_dir=settings.pdf_dir,
        db_path=settings.db_path,
        thumbnails_dir=settings.thumbnails_dir,
    )
    epub_service = EPUBService(
        epub_dir=settings.epub_dir,
        base_url=settings.base_url,
        db_path=settings.db_path,
        thumbnails_dir=settings.thumbnails_dir,
    )
    request_tracking_service = RequestTrackingService()
    return ServiceRegistry(
        settings=settings,
        db_service=DatabaseService(settings.db_path),
        documents_repository=DocumentsRepository(settings.db_path),
        progress_service=ProgressService(settings.db_path),
        pdf_service=pdf_service,
        epub_service=epub_service,
        epub_chat_context_service=EPUBChatContextService(
            epub_service.content_processor
        ),
        llm_config_service=LLMConfigService(settings.db_path),
        request_tracking_service=request_tracking_service,
        ollama_service=OllamaService(settings.db_path, request_tracking_service),
        dual_chat_service=DualChatService(settings.db_path, pdf_service),
        tts_service=TTSService(),
    )


_registry: ServiceRegistry | None = None


def init_services(settings: Settings | None = None) -> ServiceRegistry:
    """(Re)initialize the registry; called from the FastAPI lifespan."""
    global _registry
    _registry = build_registry(settings or get_settings())
    return _registry


def reset_services() -> None:
    """Drop the registry (test isolation)."""
    global _registry
    _registry = None


def get_registry() -> ServiceRegistry:
    if _registry is None:
        init_services()
    assert _registry is not None
    return _registry


# FastAPI dependency accessors — use as Depends(get_pdf_service) etc.


def get_db_service() -> DatabaseService:
    return get_registry().db_service


def get_documents_repository() -> DocumentsRepository:
    return get_registry().documents_repository


def get_progress_service() -> ProgressService:
    return get_registry().progress_service


def get_pdf_service() -> PDFService:
    return get_registry().pdf_service


def get_epub_service() -> EPUBService:
    return get_registry().epub_service


def get_epub_chat_context_service() -> EPUBChatContextService:
    return get_registry().epub_chat_context_service


def get_llm_config_service() -> LLMConfigService:
    return get_registry().llm_config_service


def get_request_tracking_service() -> RequestTrackingService:
    return get_registry().request_tracking_service


def get_ollama_service() -> OllamaService:
    return get_registry().ollama_service


def get_dual_chat_service() -> DualChatService:
    return get_registry().dual_chat_service


def get_tts_service() -> TTSService:
    return get_registry().tts_service

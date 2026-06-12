"""
Router-level regression tests for the audit fixes:

- B-12/B-3: DELETE /pdf/{id} and DELETE /epub/{id} must remove the registry
  row, delete reading sessions, and evict the entry from the shared
  in-memory cache (previously all three were left stale).
- B-15b: PUT /pdf/{id}/status returns 400 for an invalid status instead of
  falling through to a 500 (mirrors the EPUB endpoint).
- B-1: notes 404s are not swallowed into 500s.
- B-3/A-3: every consumer resolves the same shared service instances through
  app.services.registry.

The route handlers now receive their collaborators via FastAPI Depends, so
these tests simply call them with explicit keyword arguments — no
monkeypatching of module globals.
"""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

import app.routers.epub as epub_router
import app.routers.notes as notes_router
import app.routers.pdf as pdf_router
from app.models.pdf_responses import DatabaseDeletionResults
from app.services.epub_documents_service import EPUBDocumentsService
from app.services.pdf_documents_service import PDFDocumentsService
from app.services.registry import (
    get_dual_chat_service,
    get_epub_service,
    get_pdf_service,
    get_registry,
)


@pytest.fixture
def pdf_docs(tmp_path):
    return PDFDocumentsService(str(tmp_path / "pdf.db"))


@pytest.fixture
def epub_docs(tmp_path):
    return EPUBDocumentsService(str(tmp_path / "epub.db"))


class TestSharedServiceInstances:
    """B-3/A-3: every consumer must resolve THE shared service instance."""

    def test_pdf_service_is_shared(self):
        registry = get_registry()
        assert get_pdf_service() is registry.pdf_service
        assert get_dual_chat_service().pdf_service is registry.pdf_service

    def test_epub_service_is_shared(self):
        registry = get_registry()
        assert get_epub_service() is registry.epub_service
        assert (
            registry.epub_chat_context_service.content_processor
            is registry.epub_service.content_processor
        )


class TestPdfDeletePath:
    """B-12: PDF deletion must clean up registry, sessions, and cache."""

    def _run_delete(self, pdf_docs):
        pdf_id = pdf_docs.create_or_update(filename="gone.pdf", num_pages=3)

        fake_pdf_service = Mock()
        fake_db = Mock()
        fake_db.delete_all_book_data.return_value = DatabaseDeletionResults(
            reading_progress=True, notes=True, highlights=True
        )

        response = pdf_router.delete_book_by_id(
            pdf_id,
            pdf_documents_service=pdf_docs,
            pdf_service=fake_pdf_service,
            db_service=fake_db,
        )
        return pdf_id, fake_pdf_service, fake_db, response

    def test_registry_row_deleted(self, pdf_docs):
        pdf_id, _, _, response = self._run_delete(pdf_docs)
        assert response.success is True
        assert pdf_docs.get_by_id(pdf_id) is None
        assert pdf_docs.get_by_filename("gone.pdf") is None

    def test_reading_sessions_deleted(self, pdf_docs):
        pdf_id, _, fake_db, _ = self._run_delete(pdf_docs)
        fake_db.reading_statistics.delete_sessions_by_pdf_id.assert_called_once_with(
            pdf_id
        )

    def test_cache_entry_evicted(self, pdf_docs):
        _, fake_pdf_service, _, _ = self._run_delete(pdf_docs)
        fake_pdf_service.cache.remove.assert_called_once_with("gone.pdf")

    def test_unknown_id_is_404(self, pdf_docs):
        with pytest.raises(HTTPException) as exc_info:
            pdf_router.delete_book_by_id(
                99999,
                pdf_documents_service=pdf_docs,
                pdf_service=Mock(),
                db_service=Mock(),
            )
        assert exc_info.value.status_code == 404


class TestEpubDeletePath:
    """B-12: EPUB deletion must clean up registry, sessions, and cache."""

    def _run_delete(self, epub_docs):
        epub_id = epub_docs.create_or_update(filename="gone.epub", chapters=3)

        fake_epub_service = Mock()
        fake_db = Mock()
        fake_db.delete_all_epub_data.return_value = {
            "epub_progress": True,
            "epub_chat_notes": True,
            "epub_highlights": True,
        }
        fake_db.epub_reading_statistics.delete_sessions_by_epub_id.return_value = True

        response = epub_router.delete_epub_book_by_id(
            epub_id,
            db_service=fake_db,
            epub_service=fake_epub_service,
            epub_documents_service=epub_docs,
        )
        return epub_id, fake_epub_service, fake_db, response

    def test_registry_row_deleted(self, epub_docs):
        epub_id, _, _, response = self._run_delete(epub_docs)
        assert response["success"] is True
        assert response["deletion_details"]["epub_document"] is True
        assert epub_docs.get_by_id(epub_id) is None
        assert epub_docs.get_by_filename("gone.epub") is None

    def test_reading_sessions_deleted(self, epub_docs):
        epub_id, _, fake_db, response = self._run_delete(epub_docs)
        fake_db.epub_reading_statistics.delete_sessions_by_epub_id.assert_called_once_with(
            epub_id
        )
        assert response["deletion_details"]["epub_reading_sessions"] is True

    def test_cache_entry_evicted(self, epub_docs):
        _, fake_epub_service, _, _ = self._run_delete(epub_docs)
        fake_epub_service.cache.remove.assert_called_once_with("gone.epub")

    def test_unknown_id_is_404(self, epub_docs):
        with pytest.raises(HTTPException) as exc_info:
            epub_router.delete_epub_book_by_id(
                99999,
                db_service=Mock(),
                epub_service=Mock(),
                epub_documents_service=epub_docs,
            )
        assert exc_info.value.status_code == 404


class TestPdfStatusValidation:
    """B-15b: invalid status must be a 400, mirroring the EPUB endpoint."""

    def test_invalid_status_returns_400(self, pdf_docs):
        pdf_id = pdf_docs.create_or_update(filename="status.pdf", num_pages=1)

        request = pdf_router.BookStatusRequest(status="bogus")
        with pytest.raises(HTTPException) as exc_info:
            pdf_router.update_book_status_by_id(
                pdf_id,
                request,
                pdf_documents_service=pdf_docs,
                db_service=Mock(),
            )
        assert exc_info.value.status_code == 400

    def test_valid_status_accepted(self, pdf_docs):
        pdf_id = pdf_docs.create_or_update(filename="status.pdf", num_pages=1)
        fake_db = Mock()
        fake_db.update_book_status.return_value = True

        request = pdf_router.BookStatusRequest(status="reading")
        response = pdf_router.update_book_status_by_id(
            pdf_id,
            request,
            pdf_documents_service=pdf_docs,
            db_service=fake_db,
        )
        assert response.success is True


class TestNotes404NotSwallowed:
    """B-1: HTTPException(404) must not be converted into a 500."""

    def test_get_note_missing_is_404(self):
        fake_db = Mock()
        fake_db.get_chat_note_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            notes_router.get_chat_note_by_id(12345, db_service=fake_db)
        assert exc_info.value.status_code == 404

    def test_delete_note_missing_is_404(self):
        fake_db = Mock()
        fake_db.delete_chat_note.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            notes_router.delete_chat_note(12345, db_service=fake_db)
        assert exc_info.value.status_code == 404

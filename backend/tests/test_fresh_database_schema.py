"""
Regression tests for fresh-database schema creation (audit C-1).

Historically the schema was defined twice (in the DatabaseService facade and
in each specialized service) and the copies drifted: a fresh database was
created without the reading_progress status columns, so every PDF status
operation failed silently on a clean install. These tests construct every
schema-owning service against a brand-new database file and verify that the
resulting schema is complete and that the previously-broken operations work.
"""

import sqlite3

import pytest

from app.models.documents import (
    BookStatus,
    EpubDocumentUpsert,
    EpubPosition,
    PdfDocumentUpsert,
)
from app.services.documents_repository import DocumentsRepository
from app.services.highlights_service import HighlightsService
from app.services.llm_config_service import LLMConfigService
from app.services.notes_service import NotesService
from app.services.progress_service import ProgressService
from app.services.sessions_service import SessionsService


@pytest.fixture
def db_path(tmp_path):
    """Path to a database file that does not exist yet."""
    return str(tmp_path / "fresh.db")


@pytest.fixture
def repo(db_path):
    return DocumentsRepository(db_path)


class Services:
    """The schema-owning services, constructed exactly like at app startup
    (see services.registry.build_registry)."""

    def __init__(self, db_path: str):
        self.progress = ProgressService(db_path)
        self.notes = NotesService(db_path)
        self.highlights = HighlightsService(db_path)
        self.sessions = SessionsService(db_path)
        self.llm_config = LLMConfigService(db_path)


@pytest.fixture
def db_service(db_path, repo):
    """Every schema-owning service constructed against a fresh DB."""
    return Services(db_path)


def _tables(db_path: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {row[0] for row in rows}


def _columns(db_path: str, table: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


class TestFreshSchemaIsComplete:
    def test_all_tables_created(self, db_service, db_path):
        expected = {
            "document_progress",
            "document_notes",
            "document_sessions",
            "document_highlights_pdf",
            "document_highlights_epub",
            "documents",
            "llm_configurations",
        }
        missing = expected - _tables(db_path)
        assert not missing, f"Tables missing on a fresh database: {missing}"

    def test_document_progress_has_status_and_position_columns(
        self, db_service, db_path
    ):
        # The original C-1 bug: status columns were referenced by every status
        # operation but absent from the fresh-database DDL.
        columns = _columns(db_path, "document_progress")
        assert {
            "document_id",
            "status",
            "status_updated_at",
            "manually_set",
            "last_page",
            "total_pages",
            "current_nav_id",
            "nav_metadata",
            "progress_percentage",
        } <= columns

    def test_id_columns_present_everywhere(self, db_service, db_path):
        assert "document_id" in _columns(db_path, "document_notes")
        assert "document_id" in _columns(db_path, "document_highlights_pdf")
        assert "document_id" in _columns(db_path, "document_highlights_epub")

    def test_llm_config_table_complete_with_trigger(self, db_service, db_path):
        assert "always_starts_with_thinking" in _columns(db_path, "llm_configurations")
        with sqlite3.connect(db_path) as conn:
            triggers = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                )
            }
        assert "enforce_single_active_llm" in triggers


class TestFreshDatabaseOperations:
    """Exercise the operations that silently failed on a fresh DB before the fix."""

    def test_pdf_progress_and_status_roundtrip(self, db_service, repo):
        doc_id = repo.upsert(PdfDocumentUpsert(filename="book.pdf", num_pages=100))
        assert db_service.progress.save_pdf_progress(doc_id, 5, 100) is True

        progress = db_service.progress.get_progress(doc_id)
        assert progress is not None
        assert progress.position.last_page == 5
        assert progress.status == BookStatus.NEW

        assert db_service.progress.update_status(doc_id, BookStatus.READING) is True
        progress = db_service.progress.get_progress(doc_id)
        assert progress is not None
        assert progress.status == BookStatus.READING
        assert progress.manually_set is True

    def test_status_on_previously_unseen_book(self, db_service, repo):
        # update_status must be able to create the row from scratch
        doc_id = repo.upsert(PdfDocumentUpsert(filename="unseen.pdf", num_pages=1))
        assert db_service.progress.update_status(doc_id, BookStatus.FINISHED) is True
        progress = db_service.progress.get_progress(doc_id)
        assert progress is not None
        assert progress.status == BookStatus.FINISHED

    def test_epub_progress_roundtrip(self, db_service, repo):
        doc_id = repo.upsert(EpubDocumentUpsert(filename="book.epub", chapters=3))
        assert (
            db_service.progress.save_epub_progress(
                doc_id,
                EpubPosition(
                    current_nav_id="section_1",
                    chapter_id="chapter_1",
                    chapter_title="Chapter One",
                ),
            )
            is True
        )
        progress = db_service.progress.get_progress(doc_id)
        assert progress is not None
        assert progress.position.current_nav_id == "section_1"
        assert progress.status == BookStatus.NEW

    def test_status_counts_on_fresh_db(self, db_service):
        counts = db_service.progress.get_status_counts()
        assert counts.get("all", 0) == 0

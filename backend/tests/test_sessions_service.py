"""
Unit tests for the unified SessionsService (A-1).

Ports the behavioral guarantees of the former PDF/EPUB statistics twins:
offset-only pagination works (B-7 regression), upsert is keyed by
session_id, untracked documents raise ValueError, finished books are
silently skipped, and deletion only touches the targeted document.
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
from app.services.progress_service import ProgressService
from app.services.sessions_service import SessionsService


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "sessions.db")


@pytest.fixture
def repo(db_path):
    return DocumentsRepository(db_path)


@pytest.fixture
def service(db_path, repo):
    return SessionsService(db_path=db_path)


def _tracked_pdf(
    db_path, repo: DocumentsRepository, filename="book.pdf", status="reading"
) -> int:
    doc_id = repo.upsert(PdfDocumentUpsert(filename=filename, num_pages=100))
    progress = ProgressService(db_path)
    progress.save_pdf_progress(doc_id, 1, 100)
    if status != "new":
        progress.update_status(doc_id, BookStatus(status), manual=True)
    return doc_id


def _tracked_epub(
    db_path, repo: DocumentsRepository, filename="book.epub", status="reading"
) -> int:
    doc_id = repo.upsert(EpubDocumentUpsert(filename=filename, chapters=3))
    progress = ProgressService(db_path)
    progress.save_epub_progress(
        doc_id, EpubPosition(current_nav_id="s1"), progress_percentage=10.0
    )
    if status not in ("new", "reading"):
        progress.update_status(doc_id, BookStatus(status), manual=True)
    return doc_id


def _insert_sessions(db_path: str, document_id: int, count: int):
    """Insert sessions directly with deterministic timestamps."""
    with sqlite3.connect(db_path) as conn:
        for i in range(count):
            conn.execute(
                """
                INSERT INTO document_sessions
                    (session_id, document_id, session_start, last_updated,
                     units_read, time_spent_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"sess-{document_id}-{i}",
                    document_id,
                    f"2026-01-01 10:0{i}:00",
                    f"2026-01-01 10:0{i}:00",
                    (i + 1) * 100,
                    60.0,
                ),
            )
        conn.commit()


class TestPagination:
    def test_offset_only_returns_rows(self, service, db_path):
        # B-7 regression: "OFFSET without LIMIT" used to be a swallowed
        # SQLite syntax error returning [].
        _insert_sessions(db_path, document_id=1, count=3)

        page = service.get_sessions(1, offset=1)

        assert page.total_sessions == 3
        assert len(page.sessions) == 2
        assert page.sessions[0].session_id == "sess-1-1"
        assert page.sessions[1].session_id == "sess-1-0"

    def test_limit_only(self, service, db_path):
        _insert_sessions(db_path, document_id=1, count=3)
        page = service.get_sessions(1, limit=2)
        assert len(page.sessions) == 2
        assert page.sessions[0].session_id == "sess-1-2"

    def test_limit_and_offset(self, service, db_path):
        _insert_sessions(db_path, document_id=1, count=3)
        page = service.get_sessions(1, limit=1, offset=1)
        assert len(page.sessions) == 1
        assert page.sessions[0].session_id == "sess-1-1"

    def test_timestamps_are_iso(self, service, db_path):
        _insert_sessions(db_path, document_id=1, count=1)
        page = service.get_sessions(1)
        assert page.sessions[0].session_start == "2026-01-01T10:00:00Z"


class TestUpsertSession:
    def test_insert_then_update_same_session(self, service, db_path, repo):
        doc_id = _tracked_pdf(db_path, repo)

        assert service.upsert_session("sess-a", doc_id, 3, 6.0) is True
        assert service.upsert_session("sess-a", doc_id, 7, 21.0) is True

        page = service.get_sessions(doc_id)
        assert page.total_sessions == 1
        assert page.sessions[0].units_read == 7
        assert page.sessions[0].time_spent_seconds == 21.0

    def test_epub_sessions_share_the_same_table(self, service, db_path, repo):
        pdf_id = _tracked_pdf(db_path, repo)
        epub_id = _tracked_epub(db_path, repo)
        service.upsert_session("sess-pdf", pdf_id, 5, 10.0)
        service.upsert_session("sess-epub", epub_id, 1200, 300.0)
        assert service.get_sessions(pdf_id).total_sessions == 1
        assert service.get_sessions(epub_id).total_sessions == 1

    def test_unknown_document_raises_value_error(self, service):
        with pytest.raises(ValueError):
            service.upsert_session("sess-a", 999, 3, 2.0)

    def test_finished_book_skips_update(self, service, db_path, repo):
        doc_id = _tracked_epub(db_path, repo, status="finished")
        assert service.upsert_session("sess-b", doc_id, 100, 30.0) is True
        assert service.get_sessions(doc_id).total_sessions == 0


class TestDeleteSessions:
    def test_deletes_only_matching_sessions(self, service, db_path):
        _insert_sessions(db_path, document_id=1, count=2)
        _insert_sessions(db_path, document_id=2, count=1)

        assert service.delete_sessions_for_document(1) is True

        assert service.get_sessions(1).total_sessions == 0
        assert service.get_sessions(2).total_sessions == 1

    def test_returns_false_when_nothing_to_delete(self, service):
        assert service.delete_sessions_for_document(123) is False

"""
Regression tests for ReadingStatisticsService (audit B-7) and the new
delete_sessions_by_pdf_id used by book-deletion cleanup.

B-7: offset-only pagination used to emit ``OFFSET`` without ``LIMIT`` — a
SQLite syntax error silently swallowed into an empty result. The query now
emits ``LIMIT -1 OFFSET ?``.
"""

import sqlite3

import pytest

from app.models.documents import PdfDocumentUpsert
from app.services.documents_repository import DocumentsRepository
from app.services.reading_statistics_service import ReadingStatisticsService


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "stats.db")


@pytest.fixture
def service(db_path):
    return ReadingStatisticsService(db_path=db_path)


def _insert_sessions(db_path: str, pdf_id: int, count: int):
    """Insert sessions directly with deterministic timestamps."""
    with sqlite3.connect(db_path) as conn:
        for i in range(count):
            conn.execute(
                """
                INSERT INTO reading_sessions
                    (session_id, pdf_id, session_start, last_updated, pages_read, average_time_per_page)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"sess-{pdf_id}-{i}",
                    pdf_id,
                    f"2026-01-01 10:0{i}:00",
                    f"2026-01-01 10:0{i}:00",
                    i + 1,
                    2.5,
                ),
            )
        conn.commit()


class TestPagination:
    def test_offset_only_returns_rows(self, service, db_path):
        # B-7: this used to return [] because "OFFSET without LIMIT" is a
        # SQLite syntax error swallowed by the except block.
        _insert_sessions(db_path, pdf_id=1, count=3)

        result = service.get_sessions_by_pdf_id(1, offset=1)

        assert result["total_sessions"] == 3
        assert len(result["sessions"]) == 2
        # Ordered by session_start DESC, so offset=1 skips the newest
        assert result["sessions"][0]["session_id"] == "sess-1-1"
        assert result["sessions"][1]["session_id"] == "sess-1-0"

    def test_limit_only(self, service, db_path):
        _insert_sessions(db_path, pdf_id=1, count=3)
        result = service.get_sessions_by_pdf_id(1, limit=2)
        assert len(result["sessions"]) == 2
        assert result["sessions"][0]["session_id"] == "sess-1-2"

    def test_limit_and_offset(self, service, db_path):
        _insert_sessions(db_path, pdf_id=1, count=3)
        result = service.get_sessions_by_pdf_id(1, limit=1, offset=1)
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["session_id"] == "sess-1-1"

    def test_no_pagination(self, service, db_path):
        _insert_sessions(db_path, pdf_id=1, count=3)
        result = service.get_sessions_by_pdf_id(1)
        assert result["total_sessions"] == 3
        assert len(result["sessions"]) == 3


class TestUpsertSession:
    def test_insert_then_update_same_session(self, service, db_path):
        # Make the tracked-PDF precondition pass with a real registry row
        repo = DocumentsRepository(db_path)
        doc_id = repo.upsert(PdfDocumentUpsert(filename="book.pdf", num_pages=100))
        assert service.progress_service.save_pdf_progress(doc_id, 1, 100) is True

        assert service.upsert_session("sess-a", doc_id, 3, 2.0) is True
        assert service.upsert_session("sess-a", doc_id, 7, 3.0) is True

        result = service.get_sessions_by_pdf_id(doc_id)
        assert result["total_sessions"] == 1
        assert result["sessions"][0]["pages_read"] == 7
        assert result["sessions"][0]["average_time_per_page"] == 3.0

    def test_unknown_pdf_raises_value_error(self, service):
        with pytest.raises(ValueError):
            service.upsert_session("sess-a", 999, 3, 2.0)


class TestDeleteSessionsByPdfId:
    def test_deletes_only_matching_sessions(self, service, db_path):
        _insert_sessions(db_path, pdf_id=1, count=2)
        _insert_sessions(db_path, pdf_id=2, count=1)

        assert service.delete_sessions_by_pdf_id(1) is True

        assert service.get_sessions_by_pdf_id(1)["total_sessions"] == 0
        assert service.get_sessions_by_pdf_id(2)["total_sessions"] == 1

    def test_returns_false_when_nothing_to_delete(self, service):
        assert service.delete_sessions_by_pdf_id(123) is False

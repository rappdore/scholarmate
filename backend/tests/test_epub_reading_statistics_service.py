"""
Regression tests for EPUBReadingStatisticsService (audit B-7 and B-15).

B-7: offset-only pagination used to emit ``OFFSET`` without ``LIMIT`` — a
SQLite syntax error silently swallowed into an empty result. The query now
emits ``LIMIT -1 OFFSET ?``.

B-15: upsert_session used to open an extra connection and run a SELECT
purely to log insert-vs-update; that extra query was removed.
"""

import sqlite3

import pytest

from app.models.documents import BookStatus, EpubDocumentUpsert, EpubPosition
from app.services.documents_repository import DocumentsRepository
from app.services.epub_reading_statistics_service import EPUBReadingStatisticsService
from app.services.progress_service import ProgressService


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "epub_stats.db")


@pytest.fixture
def service(db_path):
    return EPUBReadingStatisticsService(db_path=db_path)


def _insert_progress(db_path: str, epub_id: int, status: str = "reading") -> int:
    """Register a tracked EPUB with progress; returns its document id."""
    repo = DocumentsRepository(db_path)
    doc_id = repo.upsert(
        EpubDocumentUpsert(filename=f"book-{epub_id}.epub", chapters=3)
    )
    progress = ProgressService(db_path)
    progress.save_epub_progress(
        doc_id, EpubPosition(current_nav_id="s1"), progress_percentage=10.0
    )
    if status != "reading":
        progress.update_status(doc_id, BookStatus(status), manual=True)
    return doc_id


def _insert_sessions(db_path: str, epub_id: int, count: int):
    """Insert sessions directly with deterministic timestamps."""
    with sqlite3.connect(db_path) as conn:
        for i in range(count):
            conn.execute(
                """
                INSERT INTO epub_reading_sessions
                    (session_id, epub_id, session_start, last_updated, words_read, time_spent_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"sess-{epub_id}-{i}",
                    epub_id,
                    f"2026-01-01 10:0{i}:00",
                    f"2026-01-01 10:0{i}:00",
                    (i + 1) * 100,
                    60.0,
                ),
            )
        conn.commit()


class TestPagination:
    def test_offset_only_returns_rows(self, service, db_path):
        # B-7: this used to return [] because "OFFSET without LIMIT" is a
        # SQLite syntax error swallowed by the except block.
        _insert_sessions(db_path, epub_id=1, count=3)

        result = service.get_sessions_by_epub_id(1, offset=1)

        assert result["total_sessions"] == 3
        assert len(result["sessions"]) == 2
        assert result["sessions"][0]["session_id"] == "sess-1-1"
        assert result["sessions"][1]["session_id"] == "sess-1-0"

    def test_limit_only(self, service, db_path):
        _insert_sessions(db_path, epub_id=1, count=3)
        result = service.get_sessions_by_epub_id(1, limit=2)
        assert len(result["sessions"]) == 2
        assert result["sessions"][0]["session_id"] == "sess-1-2"

    def test_limit_and_offset(self, service, db_path):
        _insert_sessions(db_path, epub_id=1, count=3)
        result = service.get_sessions_by_epub_id(1, limit=1, offset=1)
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["session_id"] == "sess-1-1"


class TestUpsertSession:
    def test_insert_then_update_same_session(self, service, db_path):
        doc_id = _insert_progress(db_path, epub_id=1)

        assert service.upsert_session("sess-a", doc_id, 100, 30.0) is True
        assert service.upsert_session("sess-a", doc_id, 250, 75.0) is True

        result = service.get_sessions_by_epub_id(doc_id)
        assert result["total_sessions"] == 1
        assert result["sessions"][0]["words_read"] == 250
        assert result["sessions"][0]["time_spent_seconds"] == 75.0

    def test_upsert_uses_exactly_one_own_connection(self, service, db_path):
        # B-15: a SELECT just for logging was removed. The progress lookup
        # now lives in ProgressService, so this service opens exactly one
        # connection: the upsert itself.
        doc_id = _insert_progress(db_path, epub_id=1)

        original = service.get_connection
        calls = []

        def counting_get_connection():
            calls.append(1)
            return original()

        service.get_connection = counting_get_connection
        assert service.upsert_session("sess-a", doc_id, 100, 30.0) is True
        assert len(calls) == 1

    def test_unknown_epub_raises_value_error(self, service):
        with pytest.raises(ValueError):
            service.upsert_session("sess-a", 999, 100, 30.0)

    def test_finished_book_skips_update(self, service, db_path):
        doc_id = _insert_progress(db_path, epub_id=2, status="finished")
        assert service.upsert_session("sess-b", doc_id, 100, 30.0) is True
        assert service.get_sessions_by_epub_id(doc_id)["total_sessions"] == 0


class TestDeleteSessionsByEpubId:
    def test_deletes_only_matching_sessions(self, service, db_path):
        _insert_sessions(db_path, epub_id=1, count=2)
        _insert_sessions(db_path, epub_id=2, count=1)

        assert service.delete_sessions_by_epub_id(1) is True
        assert service.get_sessions_by_epub_id(1)["total_sessions"] == 0
        assert service.get_sessions_by_epub_id(2)["total_sessions"] == 1

    def test_returns_false_when_nothing_to_delete(self, service):
        assert service.delete_sessions_by_epub_id(123) is False

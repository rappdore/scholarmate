"""
Regression tests for ReadingProgressService (audit B-6 and B-8).

B-6: UPDATE statements used to do ``SET pdf_id = ?`` with a possibly-None
lookup result, erasing a previously-correct pdf_id. Now COALESCE keeps the
existing id when the lookup fails.

B-8: save_progress/update_book_status used SELECT-then-INSERT-or-UPDATE,
racing under concurrency. They are now single-statement upserts that
preserve the original field semantics.
"""

import sqlite3
import threading

import pytest

from app.services.reading_progress_service import ReadingProgressService


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "progress.db")


@pytest.fixture
def service(db_path):
    return ReadingProgressService(db_path=db_path)


def _read_row(db_path: str, pdf_filename: str) -> sqlite3.Row | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM reading_progress WHERE pdf_filename = ?", (pdf_filename,)
        ).fetchone()


class TestPdfIdCoalesce:
    """B-6: a failed pdf_id lookup must never null an existing id."""

    def test_save_progress_keeps_existing_id_when_lookup_returns_none(
        self, service, db_path
    ):
        service._get_pdf_id = lambda filename: 42
        assert service.save_progress("book.pdf", 1, 100) is True
        assert _read_row(db_path, "book.pdf")["pdf_id"] == 42

        # Lookup now fails (returns None) — id must survive
        service._get_pdf_id = lambda filename: None
        assert service.save_progress("book.pdf", 2, 100) is True
        row = _read_row(db_path, "book.pdf")
        assert row["pdf_id"] == 42
        assert row["last_page"] == 2

    def test_save_progress_sets_id_when_lookup_succeeds(self, service, db_path):
        service._get_pdf_id = lambda filename: None
        assert service.save_progress("book.pdf", 1, 100) is True
        assert _read_row(db_path, "book.pdf")["pdf_id"] is None

        service._get_pdf_id = lambda filename: 7
        assert service.save_progress("book.pdf", 2, 100) is True
        assert _read_row(db_path, "book.pdf")["pdf_id"] == 7

    def test_update_book_status_keeps_existing_id_when_lookup_returns_none(
        self, service, db_path
    ):
        service._get_pdf_id = lambda filename: 42
        assert service.save_progress("book.pdf", 1, 100) is True

        service._get_pdf_id = lambda filename: None
        assert service.update_book_status("book.pdf", "reading") is True
        assert _read_row(db_path, "book.pdf")["pdf_id"] == 42


class TestSaveProgressUpsert:
    """B-8: single-statement upsert semantics."""

    def test_two_saves_same_key_both_succeed(self, service, db_path):
        assert service.save_progress("book.pdf", 1, 100) is True
        assert service.save_progress("book.pdf", 5, 100) is True

        row = _read_row(db_path, "book.pdf")
        assert row["last_page"] == 5
        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM reading_progress").fetchone()[0]
        assert count == 1

    def test_concurrent_saves_same_key_both_succeed(self, service):
        barrier = threading.Barrier(2)
        results = []

        def worker(page: int):
            barrier.wait()
            results.append(service.save_progress("book.pdf", page, 100))

        threads = [threading.Thread(target=worker, args=(p,)) for p in (3, 4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results == [True, True]
        progress = service.get_progress("book.pdf")
        assert progress is not None
        assert progress.last_page in (3, 4)

    def test_save_progress_does_not_clobber_status_fields(self, service):
        assert service.update_book_status("book.pdf", "finished", manual=True) is True

        assert service.save_progress("book.pdf", 10, 100) is True

        progress = service.get_progress("book.pdf")
        assert progress.status.value == "finished"
        assert progress.manually_set is True
        assert progress.last_page == 10

    def test_new_record_gets_default_status(self, service):
        assert service.save_progress("fresh.pdf", 1, 50) is True
        progress = service.get_progress("fresh.pdf")
        assert progress.status.value == "new"
        assert progress.manually_set is False


class TestUpdateBookStatusUpsert:
    """B-8: update_book_status creates-with-defaults or updates status only."""

    def test_creates_row_with_defaults_when_missing(self, service):
        assert service.update_book_status("unseen.pdf", "reading") is True

        progress = service.get_progress("unseen.pdf")
        assert progress is not None
        assert progress.status.value == "reading"
        assert progress.manually_set is True
        assert progress.last_page == 0
        assert progress.total_pages == 0

    def test_updates_status_without_touching_progress(self, service):
        assert service.save_progress("book.pdf", 33, 100) is True
        assert service.update_book_status("book.pdf", "finished") is True

        progress = service.get_progress("book.pdf")
        assert progress.status.value == "finished"
        assert progress.last_page == 33
        assert progress.total_pages == 100

    def test_invalid_status_rejected(self, service):
        assert service.update_book_status("book.pdf", "archived") is False
        assert service.get_progress("book.pdf") is None

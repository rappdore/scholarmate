"""
Regression tests for EPUBProgressService (audit B-6, B-8 and B-15 drift).

B-6: UPDATEs used to do ``SET epub_id = ?`` with a possibly-None lookup
result; COALESCE now keeps the existing id.

B-8: save_progress/update_book_status are now single-statement upserts.
Preserved semantics: nav_metadata is never erased once set, status fields
are auto-derived from progress only when not manually set.

B-15: get_status_counts now includes an "all" total like the PDF twin and
tolerates unexpected status values instead of raising KeyError.
"""

import sqlite3
import threading

import pytest

from app.services.epub_progress_service import EPUBProgressService


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "epub_progress.db")


@pytest.fixture
def service(db_path):
    return EPUBProgressService(db_path=db_path)


def _read_row(db_path: str, epub_filename: str) -> sqlite3.Row | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM epub_reading_progress WHERE epub_filename = ?",
            (epub_filename,),
        ).fetchone()


class TestEpubIdCoalesce:
    """B-6: a failed epub_id lookup must never null an existing id."""

    def test_save_progress_keeps_existing_id_when_lookup_returns_none(
        self, service, db_path
    ):
        service._get_epub_id = lambda filename: 42
        assert service.save_progress("book.epub", "section_1") is True
        assert _read_row(db_path, "book.epub")["epub_id"] == 42

        service._get_epub_id = lambda filename: None
        assert service.save_progress("book.epub", "section_2") is True
        row = _read_row(db_path, "book.epub")
        assert row["epub_id"] == 42
        assert row["current_nav_id"] == "section_2"

    def test_update_book_status_keeps_existing_id_when_lookup_returns_none(
        self, service, db_path
    ):
        service._get_epub_id = lambda filename: 42
        assert service.save_progress("book.epub", "section_1") is True

        service._get_epub_id = lambda filename: None
        assert service.update_book_status("book.epub", "reading") is True
        assert _read_row(db_path, "book.epub")["epub_id"] == 42


class TestSaveProgressUpsert:
    """B-8: single-statement upsert semantics."""

    def test_two_saves_same_key_both_succeed(self, service, db_path):
        assert service.save_progress("book.epub", "s1", progress_percentage=10.0)
        assert service.save_progress("book.epub", "s2", progress_percentage=20.0)

        row = _read_row(db_path, "book.epub")
        assert row["current_nav_id"] == "s2"
        with sqlite3.connect(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM epub_reading_progress"
            ).fetchone()[0]
        assert count == 1

    def test_concurrent_saves_same_key_both_succeed(self, service):
        barrier = threading.Barrier(2)
        results = []

        def worker(nav_id: str):
            barrier.wait()
            results.append(service.save_progress("book.epub", nav_id))

        threads = [threading.Thread(target=worker, args=(s,)) for s in ("s1", "s2")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results == [True, True]
        progress = service.get_progress("book.epub")
        assert progress is not None
        assert progress["current_nav_id"] in ("s1", "s2")

    def test_nav_metadata_preserved_when_new_value_is_null(self, service):
        metadata = {"all_sections": [{"id": "s1"}, {"id": "s2"}], "word_counts": 99}
        assert service.save_progress("book.epub", "s1", nav_metadata=metadata)

        # A later save without nav_metadata must not erase it
        assert service.save_progress("book.epub", "s2", nav_metadata=None)
        progress = service.get_progress("book.epub")
        assert progress["nav_metadata"] == metadata

    def test_existing_nav_metadata_wins_over_new_value(self, service):
        # Preserved pre-existing behavior: once set, nav_metadata (word
        # counts) is kept even if a save supplies a new value.
        original = {"word_counts": 99}
        assert service.save_progress("book.epub", "s1", nav_metadata=original)
        assert service.save_progress("book.epub", "s2", nav_metadata={"other": 1})
        assert service.get_progress("book.epub")["nav_metadata"] == original

    def test_status_auto_updates_with_progress_when_not_manual(self, service):
        assert service.save_progress("book.epub", "s1", progress_percentage=0.0)
        assert service.get_progress("book.epub")["status"] == "new"

        assert service.save_progress("book.epub", "s2", progress_percentage=50.0)
        assert service.get_progress("book.epub")["status"] == "reading"

        assert service.save_progress("book.epub", "s3", progress_percentage=96.0)
        assert service.get_progress("book.epub")["status"] == "finished"

    def test_manually_set_status_not_clobbered_by_save(self, service):
        assert service.save_progress("book.epub", "s1", progress_percentage=10.0)
        assert service.update_book_status("book.epub", "finished", manual=True)

        assert service.save_progress("book.epub", "s2", progress_percentage=20.0)
        progress = service.get_progress("book.epub")
        assert progress["status"] == "finished"
        assert progress["manually_set"] is True
        assert progress["current_nav_id"] == "s2"


class TestUpdateBookStatusUpsert:
    """B-8: update_book_status creates-with-defaults or updates status only."""

    def test_creates_row_when_missing(self, service):
        assert service.update_book_status("unseen.epub", "reading") is True
        progress = service.get_progress("unseen.epub")
        assert progress is not None
        assert progress["status"] == "reading"
        assert progress["manually_set"] is True
        assert progress["current_nav_id"] == "start"

    def test_updates_status_without_touching_progress(self, service):
        assert service.save_progress(
            "book.epub", "s5", scroll_position=120, progress_percentage=42.0
        )
        assert service.update_book_status("book.epub", "finished") is True

        progress = service.get_progress("book.epub")
        assert progress["status"] == "finished"
        assert progress["current_nav_id"] == "s5"
        assert progress["scroll_position"] == 120
        assert progress["progress_percentage"] == 42.0

    def test_invalid_status_rejected(self, service):
        assert service.update_book_status("book.epub", "archived") is False
        assert service.get_progress("book.epub") is None


class TestGetStatusCounts:
    """B-15: 'all' total present; unknown statuses tolerated."""

    def test_counts_include_all_total(self, service):
        assert service.save_progress("a.epub", "s1", progress_percentage=0.0)
        assert service.save_progress("b.epub", "s1", progress_percentage=10.0)
        assert service.update_book_status("c.epub", "finished")

        counts = service.get_status_counts()
        assert counts == {"new": 1, "reading": 1, "finished": 1, "all": 3}

    def test_empty_database_includes_all(self, service):
        assert service.get_status_counts() == {
            "new": 0,
            "reading": 0,
            "finished": 0,
            "all": 0,
        }

    def test_unknown_status_does_not_raise(self, service):
        # The table CHECK constraint normally prevents unknown statuses, but
        # the code must not KeyError if one ever appears (drift, manual edits).
        service.execute_query = lambda *args, **kwargs: [
            ("archived", 2),
            ("reading", 1),
        ]
        counts = service.get_status_counts()
        assert counts == {"new": 0, "reading": 1, "finished": 0, "all": 1}

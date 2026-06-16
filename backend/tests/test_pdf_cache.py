"""
Unit tests for PDFCache covering the audit fixes:

- B-4: _build_cache builds into a local dict and swaps it in atomically, so
  the live cache is never observed empty/partial during a rebuild.
- B-12: remove() evicts a single entry from the in-memory cache after a
  book is deleted.
- B-5 (regression guard): database rows with NULL metadata columns still
  produce a valid cache entry with fallback values.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.models.documents import PdfDocumentUpsert
from app.services.documents_repository import DocumentsRepository
from app.services.pdf_cache import PDFCache


@pytest.fixture
def temp_dirs():
    """Create temporary directories for PDFs, thumbnails and the database."""
    with (
        tempfile.TemporaryDirectory() as pdf_dir,
        tempfile.TemporaryDirectory() as thumb_dir,
        tempfile.TemporaryDirectory() as data_dir,
    ):
        yield {
            "pdf_dir": Path(pdf_dir),
            "thumb_dir": Path(thumb_dir),
            "db_path": str(Path(data_dir) / "test.db"),
        }


@pytest.fixture
def mock_pdf_service(temp_dirs):
    """Mock PDFService whose thumbnail generation returns an existing file."""
    thumb_path = temp_dirs["thumb_dir"] / "thumb.png"
    thumb_path.write_bytes(b"png")
    service = Mock()
    service.generate_thumbnail = Mock(return_value=thumb_path)
    return service


def _mock_pdf_reader(*args, **kwargs):
    reader = Mock()
    reader.pages = [Mock()]
    reader.metadata = {}
    return reader


def _build_cache(temp_dirs, mock_pdf_service) -> PDFCache:
    with patch("app.services.pdf_cache.PdfReader", side_effect=_mock_pdf_reader):
        return PDFCache(
            pdf_dir=temp_dirs["pdf_dir"],
            thumbnails_dir=temp_dirs["thumb_dir"],
            pdf_service=mock_pdf_service,
            db_path=temp_dirs["db_path"],
        )


class TestRemove:
    def test_remove_evicts_entry(self, temp_dirs, mock_pdf_service):
        (temp_dirs["pdf_dir"] / "book.pdf").write_bytes(b"%PDF-1.4")
        cache = _build_cache(temp_dirs, mock_pdf_service)
        assert "book.pdf" in cache._cache

        assert cache.remove("book.pdf") is True

        assert "book.pdf" not in cache._cache
        assert cache.get_all_pdfs() == []
        assert cache.get_cache_info()["pdf_count"] == 0
        with pytest.raises(FileNotFoundError):
            cache.get_pdf_info("book.pdf")

    def test_remove_missing_entry_returns_false(self, temp_dirs, mock_pdf_service):
        cache = _build_cache(temp_dirs, mock_pdf_service)
        assert cache.remove("nope.pdf") is False


class TestAtomicRebuild:
    def test_refresh_swaps_cache_dict_instead_of_clearing(
        self, temp_dirs, mock_pdf_service
    ):
        (temp_dirs["pdf_dir"] / "book.pdf").write_bytes(b"%PDF-1.4")
        cache = _build_cache(temp_dirs, mock_pdf_service)

        old_cache = cache._cache
        assert "book.pdf" in old_cache

        with patch("app.services.pdf_cache.PdfReader", side_effect=_mock_pdf_reader):
            cache.refresh()

        # The rebuild must swap in a new dict; the dict concurrent readers
        # hold a reference to is never cleared or mutated mid-rebuild.
        assert cache._cache is not old_cache
        assert "book.pdf" in old_cache
        assert "book.pdf" in cache._cache

    def test_old_entries_visible_while_rebuild_in_progress(
        self, temp_dirs, mock_pdf_service
    ):
        (temp_dirs["pdf_dir"] / "book.pdf").write_bytes(b"%PDF-1.4")
        cache = _build_cache(temp_dirs, mock_pdf_service)

        observed = {}
        real_glob = type(temp_dirs["pdf_dir"]).glob

        def spying_glob(self, pattern):
            # Snapshot what a concurrent reader would see at the start of
            # the rebuild: the full old cache, not an emptied one.
            observed["mid_rebuild_keys"] = set(cache._cache.keys())
            return real_glob(self, pattern)

        with (
            patch("app.services.pdf_cache.PdfReader", side_effect=_mock_pdf_reader),
            patch.object(type(temp_dirs["pdf_dir"]), "glob", spying_glob),
        ):
            cache.refresh()

        assert observed["mid_rebuild_keys"] == {"book.pdf"}

    def test_refresh_forces_thumbnail_regeneration(self, temp_dirs, mock_pdf_service):
        (temp_dirs["pdf_dir"] / "book.pdf").write_bytes(b"%PDF-1.4")
        thumb = temp_dirs["thumb_dir"] / "book_thumb.png"
        thumb.write_bytes(b"old png")
        mock_pdf_service.generate_thumbnail.return_value = thumb

        docs = DocumentsRepository(temp_dirs["db_path"])
        docs.upsert(
            PdfDocumentUpsert(
                filename="book.pdf",
                num_pages=1,
                thumbnail_path=str(thumb),
            )
        )

        cache = _build_cache(temp_dirs, mock_pdf_service)
        mock_pdf_service.generate_thumbnail.assert_not_called()

        cache.refresh()

        mock_pdf_service.generate_thumbnail.assert_called_with("book.pdf", force=True)

    def test_refresh_can_skip_forced_thumbnail_regeneration(
        self, temp_dirs, mock_pdf_service
    ):
        (temp_dirs["pdf_dir"] / "book.pdf").write_bytes(b"%PDF-1.4")
        thumb = temp_dirs["thumb_dir"] / "book_thumb.png"
        thumb.write_bytes(b"old png")

        docs = DocumentsRepository(temp_dirs["db_path"])
        docs.upsert(
            PdfDocumentUpsert(
                filename="book.pdf",
                num_pages=1,
                thumbnail_path=str(thumb),
            )
        )

        cache = _build_cache(temp_dirs, mock_pdf_service)
        mock_pdf_service.generate_thumbnail.reset_mock()

        cache.refresh(force_thumbnails=False)

        mock_pdf_service.generate_thumbnail.assert_not_called()


class TestNullDatabaseFields:
    def test_db_record_with_null_fields_builds_entry(self, temp_dirs, mock_pdf_service):
        (temp_dirs["pdf_dir"] / "untitled.pdf").write_bytes(b"%PDF-1.4")

        # Pre-seed a registry row where nullable columns are NULL
        docs = DocumentsRepository(temp_dirs["db_path"])
        docs.upsert(PdfDocumentUpsert(filename="untitled.pdf", num_pages=7))

        cache = _build_cache(temp_dirs, mock_pdf_service)

        info = cache._cache["untitled.pdf"]
        assert info.title == "untitled"
        assert info.author == "Unknown"
        assert info.num_pages == 7
        assert info.file_size == 0
        assert info.modified_date == ""
        assert info.created_date == ""

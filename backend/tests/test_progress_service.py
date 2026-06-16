"""
Unit tests for the unified ProgressService (A-1).

Ports the behavioral guarantees of the former PDF/EPUB progress-service
twins: concurrent upserts succeed, PDF saves never clobber status fields,
EPUB saves auto-derive status unless manually set, nav_metadata is never
erased by an incoming None, and status counts include the "all" total.
"""

import threading

import pytest

from app.models.documents import (
    BookStatus,
    DocumentType,
    EpubDocumentUpsert,
    EpubPosition,
    PdfDocumentUpsert,
    PdfPosition,
)
from app.services.documents_repository import DocumentsRepository
from app.services.progress_service import ProgressService


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def repo(db_path):
    return DocumentsRepository(db_path)


@pytest.fixture
def service(db_path, repo):
    return ProgressService(db_path)


@pytest.fixture
def pdf_id(repo):
    return repo.upsert(PdfDocumentUpsert(filename="book.pdf", num_pages=100))


@pytest.fixture
def epub_id(repo):
    return repo.upsert(EpubDocumentUpsert(filename="book.epub", chapters=10))


class TestPdfProgress:
    def test_save_and_get_roundtrip(self, service, pdf_id):
        assert service.save_pdf_progress(pdf_id, 5, 100) is True
        progress = service.get_progress(pdf_id)
        assert progress is not None
        assert progress.doc_type == DocumentType.PDF
        assert progress.filename == "book.pdf"
        assert isinstance(progress.position, PdfPosition)
        assert progress.position.last_page == 5
        assert progress.position.total_pages == 100
        assert progress.progress_percentage == pytest.approx(5.0)
        assert progress.status == BookStatus.NEW

    def test_save_does_not_clobber_status_fields(self, service, pdf_id):
        service.save_pdf_progress(pdf_id, 5, 100)
        assert service.update_status(pdf_id, BookStatus.READING) is True
        service.save_pdf_progress(pdf_id, 50, 100)
        progress = service.get_progress(pdf_id)
        assert progress.status == BookStatus.READING
        assert progress.manually_set is True
        assert progress.position.last_page == 50

    def test_concurrent_saves_same_key_both_succeed(self, service, pdf_id):
        results = []

        def save(page):
            results.append(service.save_pdf_progress(pdf_id, page, 100))

        threads = [threading.Thread(target=save, args=(p,)) for p in (1, 2, 3, 4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(results)


class TestEpubProgress:
    def test_save_and_get_roundtrip(self, service, epub_id):
        assert (
            service.save_epub_progress(
                epub_id,
                EpubPosition(
                    current_nav_id="section_2_1",
                    chapter_id="chapter_2",
                    chapter_title="Chapter Two",
                    scroll_position=120,
                    total_sections=40,
                ),
                progress_percentage=12.5,
            )
            is True
        )
        progress = service.get_progress(epub_id)
        assert progress.doc_type == DocumentType.EPUB
        assert isinstance(progress.position, EpubPosition)
        assert progress.position.current_nav_id == "section_2_1"
        assert progress.position.chapter_title == "Chapter Two"
        assert progress.progress_percentage == 12.5

    def test_epub_cfi_roundtrip_preserve_and_clear(self, service, epub_id):
        cfi = "epubcfi(/4/2[preface]!/4/2/8:42)"
        assert (
            service.save_epub_progress(
                epub_id,
                EpubPosition(current_nav_id="section_1", epub_cfi=cfi),
            )
            is True
        )
        progress = service.get_progress(epub_id)
        assert progress is not None
        assert isinstance(progress.position, EpubPosition)
        assert progress.position.epub_cfi == cfi

        assert (
            service.save_epub_progress(
                epub_id,
                EpubPosition(current_nav_id="section_2", scroll_position=80),
                update_epub_cfi=False,
            )
            is True
        )
        progress = service.get_progress(epub_id)
        assert progress is not None
        assert isinstance(progress.position, EpubPosition)
        assert progress.position.current_nav_id == "section_2"
        assert progress.position.scroll_position == 80
        assert progress.position.epub_cfi == cfi

        assert (
            service.save_epub_progress(
                epub_id,
                EpubPosition(current_nav_id="section_2", epub_cfi=None),
                update_epub_cfi=True,
            )
            is True
        )
        progress = service.get_progress(epub_id)
        assert progress is not None
        assert isinstance(progress.position, EpubPosition)
        assert progress.position.epub_cfi is None

    def test_status_auto_updates_with_progress(self, service, epub_id):
        service.save_epub_progress(epub_id, EpubPosition(), progress_percentage=0.0)
        assert service.get_progress(epub_id).status == BookStatus.NEW

        service.save_epub_progress(epub_id, EpubPosition(), progress_percentage=50.0)
        assert service.get_progress(epub_id).status == BookStatus.READING

        service.save_epub_progress(epub_id, EpubPosition(), progress_percentage=96.0)
        assert service.get_progress(epub_id).status == BookStatus.FINISHED

    def test_manually_set_status_not_clobbered_by_save(self, service, epub_id):
        service.save_epub_progress(epub_id, EpubPosition(), progress_percentage=10.0)
        service.update_status(epub_id, BookStatus.FINISHED, manual=True)
        service.save_epub_progress(epub_id, EpubPosition(), progress_percentage=20.0)
        progress = service.get_progress(epub_id)
        assert progress.status == BookStatus.FINISHED
        assert progress.manually_set is True

    def test_nav_metadata_preserved_when_new_value_is_none(self, service, epub_id):
        service.save_epub_progress(
            epub_id,
            EpubPosition(),
            nav_metadata={"all_sections": [{"id": "s1"}], "words": 1000},
        )
        service.save_epub_progress(epub_id, EpubPosition(), nav_metadata=None)
        progress = service.get_progress(epub_id)
        assert progress.nav_metadata == {"all_sections": [{"id": "s1"}], "words": 1000}

    def test_incoming_nav_metadata_replaces_existing(self, service, epub_id):
        # Deliberate change from the old twin (which kept the FIRST value
        # forever, so the word-count extraction flow could never persist its
        # update): a non-NULL incoming value wins; only None is ignored.
        service.save_epub_progress(epub_id, EpubPosition(), nav_metadata={"v": 1})
        service.save_epub_progress(epub_id, EpubPosition(), nav_metadata={"v": 2})
        assert service.get_progress(epub_id).nav_metadata == {"v": 2}


class TestStatus:
    def test_update_creates_row_when_missing(self, service, pdf_id):
        assert service.update_status(pdf_id, BookStatus.FINISHED) is True
        progress = service.get_progress(pdf_id)
        assert progress.status == BookStatus.FINISHED
        assert progress.position.last_page == 0

    def test_update_does_not_touch_position(self, service, epub_id):
        service.save_epub_progress(
            epub_id, EpubPosition(current_nav_id="s9"), progress_percentage=42.0
        )
        service.update_status(epub_id, BookStatus.FINISHED)
        progress = service.get_progress(epub_id)
        assert progress.position.current_nav_id == "s9"
        assert progress.progress_percentage == 42.0

    def test_get_books_by_status_filters_by_type_and_status(
        self, service, pdf_id, epub_id
    ):
        service.update_status(pdf_id, BookStatus.READING)
        service.update_status(epub_id, BookStatus.READING)
        both = service.get_books_by_status(BookStatus.READING)
        assert {p.document_id for p in both} == {pdf_id, epub_id}
        pdf_only = service.get_books_by_status(BookStatus.READING, DocumentType.PDF)
        assert [p.document_id for p in pdf_only] == [pdf_id]
        assert service.get_books_by_status(BookStatus.FINISHED) == []


class TestStatusCounts:
    def test_counts_include_all_total_and_split_by_type(self, service, pdf_id, epub_id):
        service.update_status(pdf_id, BookStatus.READING)
        service.update_status(epub_id, BookStatus.FINISHED)
        counts = service.get_status_counts()
        assert counts == {"new": 0, "reading": 1, "finished": 1, "all": 2}
        pdf_counts = service.get_status_counts(DocumentType.PDF)
        assert pdf_counts == {"new": 0, "reading": 1, "finished": 0, "all": 1}

    def test_empty_database_includes_all(self, service):
        assert service.get_status_counts() == {
            "all": 0,
            "new": 0,
            "reading": 0,
            "finished": 0,
        }


class TestGetAllAndDelete:
    def test_get_all_progress_by_type(self, service, pdf_id, epub_id):
        service.save_pdf_progress(pdf_id, 3, 10)
        service.save_epub_progress(epub_id, EpubPosition(), progress_percentage=1.0)
        assert len(service.get_all_progress()) == 2
        assert [p.document_id for p in service.get_all_progress(DocumentType.PDF)] == [
            pdf_id
        ]

    def test_delete_progress(self, service, pdf_id):
        service.save_pdf_progress(pdf_id, 3, 10)
        assert service.delete_progress(pdf_id) is True
        assert service.get_progress(pdf_id) is None
        assert service.delete_progress(pdf_id) is False

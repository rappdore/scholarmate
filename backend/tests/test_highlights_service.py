"""
Unit tests for the unified HighlightsService (A-1).

One service, two anchor-specific tables: PDF highlights anchor by
page/offsets/bounding-boxes, EPUB highlights by XPath ranges.
"""

import pytest

from app.models.documents import (
    EpubDocumentUpsert,
    PdfDocumentUpsert,
    PdfHighlightRecord,
)
from app.models.epub_highlights import EPUBHighlightCreate
from app.services.documents_repository import DocumentsRepository
from app.services.highlights_service import HighlightsService


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def repo(db_path):
    return DocumentsRepository(db_path)


@pytest.fixture
def service(db_path, repo):
    return HighlightsService(db_path)


@pytest.fixture
def pdf_id(repo):
    return repo.upsert(PdfDocumentUpsert(filename="book.pdf", num_pages=100))


@pytest.fixture
def epub_id(repo):
    return repo.upsert(EpubDocumentUpsert(filename="book.epub", chapters=10))


def _save_pdf(service, pdf_id, page=1, text="highlighted text", color="#ffff00"):
    return service.save_pdf_highlight(
        document_id=pdf_id,
        page_number=page,
        selected_text=text,
        start_offset=0,
        end_offset=len(text),
        color=color,
        coordinates=[{"x": 1.0, "y": 2.0, "width": 10.0, "height": 5.0}],
    )


def _epub_create(epub_id, nav_id="s1", chapter_id="c1", color="yellow"):
    return EPUBHighlightCreate(
        epub_id=epub_id,
        nav_id=nav_id,
        chapter_id=chapter_id,
        start_xpath="/html/body/p[1]/text()[1]",
        start_offset=0,
        end_xpath="/html/body/p[1]/text()[1]",
        end_offset=10,
        highlight_text="some text",
        color=color,
    )


class TestPdfHighlights:
    def test_save_and_get_roundtrip(self, service, pdf_id):
        highlight_id = _save_pdf(service, pdf_id, page=3)
        assert highlight_id is not None

        record = service.get_pdf_highlight_by_id(highlight_id)
        assert isinstance(record, PdfHighlightRecord)
        assert record.filename == "book.pdf"
        assert record.page_number == 3
        assert record.coordinates == [
            {"x": 1.0, "y": 2.0, "width": 10.0, "height": 5.0}
        ]

    def test_filter_by_page(self, service, pdf_id):
        _save_pdf(service, pdf_id, page=1)
        _save_pdf(service, pdf_id, page=2)
        _save_pdf(service, pdf_id, page=2)
        assert len(service.get_pdf_highlights(pdf_id)) == 3
        assert len(service.get_pdf_highlights(pdf_id, page_number=2)) == 2

    def test_update_color_and_delete(self, service, pdf_id):
        highlight_id = _save_pdf(service, pdf_id)
        assert service.update_pdf_highlight_color(highlight_id, "#ff0000") is True
        assert service.get_pdf_highlight_by_id(highlight_id).color == "#ff0000"
        assert service.delete_pdf_highlight(highlight_id) is True
        assert service.get_pdf_highlight_by_id(highlight_id) is None
        assert service.delete_pdf_highlight(highlight_id) is False

    def test_summary_truncates_long_text(self, service, pdf_id):
        _save_pdf(service, pdf_id, text="x" * 80)
        summary = service.get_pdf_highlights_summary()
        assert summary["book.pdf"].highlights_count == 1
        assert summary["book.pdf"].latest_highlight_text == "x" * 50 + "..."


class TestEpubHighlights:
    def test_save_and_get_roundtrip(self, service, epub_id):
        highlight_id = service.save_epub_highlight(_epub_create(epub_id))
        assert highlight_id is not None

        record = service.get_epub_highlight_by_id(highlight_id)
        assert record.epub_id == epub_id
        assert record.nav_id == "s1"
        assert record.start_xpath == "/html/body/p[1]/text()[1]"
        assert record.color == "yellow"

    def test_filter_by_section_and_chapter(self, service, epub_id):
        service.save_epub_highlight(_epub_create(epub_id, nav_id="s1", chapter_id="c1"))
        service.save_epub_highlight(_epub_create(epub_id, nav_id="s2", chapter_id="c1"))
        service.save_epub_highlight(_epub_create(epub_id, nav_id="s3", chapter_id="c2"))
        assert len(service.get_epub_highlights(epub_id)) == 3
        assert len(service.get_epub_highlights(epub_id, nav_id="s1")) == 1
        assert len(service.get_epub_highlights(epub_id, chapter_id="c1")) == 2

    def test_update_color_and_delete(self, service, epub_id):
        highlight_id = service.save_epub_highlight(_epub_create(epub_id))
        assert service.update_epub_highlight_color(highlight_id, "blue") is True
        assert service.get_epub_highlight_by_id(highlight_id).color == "blue"
        assert service.delete_epub_highlight(highlight_id) is True
        assert service.get_epub_highlight_by_id(highlight_id) is None

    def test_summary_keyed_by_document_id(self, service, epub_id):
        service.save_epub_highlight(_epub_create(epub_id))
        service.save_epub_highlight(_epub_create(epub_id, nav_id="s2"))
        summary = service.get_epub_highlights_summary()
        assert summary[epub_id].highlights_count == 2


class TestSeparateIdSpaces:
    def test_pdf_and_epub_highlight_ids_are_independent(self, service, pdf_id, epub_id):
        pdf_highlight = _save_pdf(service, pdf_id)
        epub_highlight = service.save_epub_highlight(_epub_create(epub_id))
        # Both start at 1 in their own tables — deleting one must not
        # affect the other even with equal ids.
        assert pdf_highlight == epub_highlight == 1
        assert service.delete_pdf_highlight(pdf_highlight) is True
        assert service.get_epub_highlight_by_id(epub_highlight) is not None


class TestDeleteForDocument:
    def test_deletes_both_formats_and_only_target(self, service, pdf_id, epub_id):
        _save_pdf(service, pdf_id)
        service.save_epub_highlight(_epub_create(epub_id))
        assert service.delete_highlights_for_document(pdf_id) is True
        assert service.get_pdf_highlights(pdf_id) == []
        assert len(service.get_epub_highlights(epub_id)) == 1
        assert service.delete_highlights_for_document(epub_id) is True
        assert service.get_epub_highlights(epub_id) == []

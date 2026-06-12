"""
Unit tests for the unified NotesService (A-1).
"""

import pytest

from app.models.documents import (
    DocumentType,
    EpubDocumentUpsert,
    EpubNoteAnchor,
    PdfDocumentUpsert,
    PdfNoteAnchor,
)
from app.services.documents_repository import DocumentsRepository
from app.services.notes_service import NotesService


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def repo(db_path):
    return DocumentsRepository(db_path)


@pytest.fixture
def service(db_path, repo):
    return NotesService(db_path)


@pytest.fixture
def pdf_id(repo):
    return repo.upsert(PdfDocumentUpsert(filename="book.pdf", num_pages=100))


@pytest.fixture
def epub_id(repo):
    return repo.upsert(EpubDocumentUpsert(filename="book.epub", chapters=10))


class TestPdfNotes:
    def test_save_and_get_roundtrip(self, service, pdf_id):
        note_id = service.save_note(
            pdf_id, PdfNoteAnchor(page_number=7), "Title", "Content"
        )
        assert note_id is not None

        notes = service.get_pdf_notes(pdf_id)
        assert len(notes) == 1
        note = notes[0]
        assert note.doc_type == DocumentType.PDF
        assert note.filename == "book.pdf"
        assert isinstance(note.anchor, PdfNoteAnchor)
        assert note.anchor.page_number == 7
        assert note.title == "Title"
        assert note.chat_content == "Content"

    def test_filter_by_page(self, service, pdf_id):
        service.save_note(pdf_id, PdfNoteAnchor(page_number=1), "a", "x")
        service.save_note(pdf_id, PdfNoteAnchor(page_number=2), "b", "y")
        service.save_note(pdf_id, PdfNoteAnchor(page_number=2), "c", "z")
        assert len(service.get_pdf_notes(pdf_id, page_number=2)) == 2
        assert len(service.get_pdf_notes(pdf_id, page_number=3)) == 0


class TestEpubNotes:
    def test_save_and_get_roundtrip(self, service, epub_id):
        note_id = service.save_note(
            epub_id,
            EpubNoteAnchor(
                nav_id="section_2_1",
                chapter_id="chapter_2",
                chapter_title="Chapter Two",
                scroll_position=42,
                context_sections=["s1", "s2"],
            ),
            "Title",
            "Content",
        )
        assert note_id is not None

        notes = service.get_epub_notes(epub_id)
        note = notes[0]
        assert note.doc_type == DocumentType.EPUB
        assert isinstance(note.anchor, EpubNoteAnchor)
        assert note.anchor.nav_id == "section_2_1"
        assert note.anchor.chapter_title == "Chapter Two"
        assert note.anchor.context_sections == ["s1", "s2"]
        assert note.anchor.scroll_position == 42

    def test_filter_by_nav_and_chapter(self, service, epub_id):
        service.save_note(
            epub_id, EpubNoteAnchor(nav_id="s1", chapter_id="c1"), "a", "x"
        )
        service.save_note(
            epub_id, EpubNoteAnchor(nav_id="s2", chapter_id="c1"), "b", "y"
        )
        service.save_note(
            epub_id, EpubNoteAnchor(nav_id="s3", chapter_id="c2"), "c", "z"
        )
        assert len(service.get_epub_notes(epub_id, nav_id="s1")) == 1
        assert len(service.get_epub_notes(epub_id, chapter_id="c1")) == 2
        assert len(service.get_epub_notes(epub_id)) == 3


class TestSharedTable:
    def test_pdf_and_epub_notes_do_not_leak_across(self, service, pdf_id, epub_id):
        service.save_note(pdf_id, PdfNoteAnchor(page_number=1), "p", "x")
        service.save_note(epub_id, EpubNoteAnchor(nav_id="s1"), "e", "y")
        assert len(service.get_pdf_notes(pdf_id)) == 1
        assert len(service.get_epub_notes(epub_id)) == 1

    def test_get_note_by_id_returns_correct_anchor_type(self, service, pdf_id, epub_id):
        pdf_note = service.save_note(pdf_id, PdfNoteAnchor(page_number=1), "p", "x")
        epub_note = service.save_note(epub_id, EpubNoteAnchor(nav_id="s1"), "e", "y")
        assert isinstance(service.get_note_by_id(pdf_note).anchor, PdfNoteAnchor)
        assert isinstance(service.get_note_by_id(epub_note).anchor, EpubNoteAnchor)
        assert service.get_note_by_id(99999) is None


class TestDeletion:
    def test_delete_note(self, service, pdf_id):
        note_id = service.save_note(pdf_id, PdfNoteAnchor(page_number=1), "t", "c")
        assert service.delete_note(note_id) is True
        assert service.get_note_by_id(note_id) is None
        assert service.delete_note(note_id) is False

    def test_delete_notes_for_document(self, service, pdf_id, epub_id):
        service.save_note(pdf_id, PdfNoteAnchor(page_number=1), "a", "x")
        service.save_note(pdf_id, PdfNoteAnchor(page_number=2), "b", "y")
        service.save_note(epub_id, EpubNoteAnchor(nav_id="s1"), "c", "z")
        assert service.delete_notes_for_document(pdf_id) is True
        assert service.get_pdf_notes(pdf_id) == []
        # Other documents untouched
        assert len(service.get_epub_notes(epub_id)) == 1
        # True even when nothing existed (legacy semantics)
        assert service.delete_notes_for_document(pdf_id) is True


class TestSummary:
    def test_summary_keyed_by_filename_with_latest_title(
        self, service, repo, pdf_id, epub_id
    ):
        other_pdf = repo.upsert(PdfDocumentUpsert(filename="other.pdf", num_pages=5))
        service.save_note(pdf_id, PdfNoteAnchor(page_number=1), "first", "x")
        service.save_note(pdf_id, PdfNoteAnchor(page_number=2), "latest", "y")
        service.save_note(other_pdf, PdfNoteAnchor(page_number=1), "only", "z")
        service.save_note(epub_id, EpubNoteAnchor(nav_id="s1"), "epub-note", "w")

        summary = service.get_notes_summary(DocumentType.PDF)
        assert set(summary) == {"book.pdf", "other.pdf"}
        assert summary["book.pdf"].notes_count == 2
        assert summary["book.pdf"].latest_note_title == "latest"
        assert summary["other.pdf"].notes_count == 1

        epub_summary = service.get_notes_summary(DocumentType.EPUB)
        assert set(epub_summary) == {"book.epub"}

    def test_empty_summary(self, service):
        assert service.get_notes_summary(DocumentType.PDF) == {}

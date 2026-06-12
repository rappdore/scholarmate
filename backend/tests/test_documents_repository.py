"""
Unit tests for DocumentsRepository — the unified documents registry (A-1).
"""

import sqlite3

import pytest

from app.models.documents import (
    DocumentType,
    EpubDocumentUpsert,
    PdfDocumentUpsert,
)
from app.services.documents_repository import DocumentsRepository


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def repo(temp_db):
    return DocumentsRepository(db_path=temp_db)


def make_pdf(filename="book.pdf", **overrides) -> PdfDocumentUpsert:
    defaults = dict(
        filename=filename,
        num_pages=100,
        title="A PDF",
        author="Author",
        subject="Subject",
        creator="Creator",
        producer="Producer",
        file_size=1234,
        file_path=f"/pdfs/{filename}",
        thumbnail_path=f"/thumbs/{filename}.png",
        created_date="2026-01-01T00:00:00",
        modified_date="2026-01-02T00:00:00",
        metadata={"k": "v"},
    )
    defaults.update(overrides)
    return PdfDocumentUpsert(**defaults)


def make_epub(filename="book.epub", **overrides) -> EpubDocumentUpsert:
    defaults = dict(
        filename=filename,
        chapters=12,
        title="An EPUB",
        author="Author",
        subject="Subject",
        publisher="Publisher",
        language="en",
        file_size=4321,
        file_path=f"/epubs/{filename}",
        thumbnail_path=f"/thumbs/{filename}.png",
        created_date="2026-01-01T00:00:00",
        modified_date="2026-01-02T00:00:00",
    )
    defaults.update(overrides)
    return EpubDocumentUpsert(**defaults)


class TestSchema:
    def test_fresh_db_has_documents_table(self, repo, temp_db):
        conn = sqlite3.connect(temp_db)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            conn.close()
        assert "documents" in tables

    def test_doc_type_check_constraint(self, repo, temp_db):
        conn = sqlite3.connect(temp_db)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO documents (doc_type, filename) VALUES ('djvu', 'x')"
                )
        finally:
            conn.close()


class TestUpsert:
    def test_insert_pdf_returns_id(self, repo):
        doc_id = repo.upsert(make_pdf())
        assert isinstance(doc_id, int)
        record = repo.get_by_id(doc_id)
        assert record is not None
        assert record.doc_type == DocumentType.PDF
        assert record.num_pages == 100
        assert record.chapters is None
        assert record.publisher is None
        assert record.metadata_json == '{"k": "v"}'

    def test_insert_epub_returns_id(self, repo):
        doc_id = repo.upsert(make_epub())
        record = repo.get_by_id(doc_id)
        assert record is not None
        assert record.doc_type == DocumentType.EPUB
        assert record.chapters == 12
        assert record.publisher == "Publisher"
        assert record.num_pages is None
        assert record.creator is None

    def test_upsert_is_idempotent_keeps_id(self, repo):
        first = repo.upsert(make_pdf())
        second = repo.upsert(make_pdf(title="Updated"))
        assert first == second
        record = repo.get_by_id(first)
        assert record.title == "Updated"

    def test_pdf_and_epub_get_distinct_ids(self, repo):
        pdf_id = repo.upsert(make_pdf())
        epub_id = repo.upsert(make_epub())
        assert pdf_id != epub_id


class TestLookups:
    def test_get_by_filename(self, repo):
        repo.upsert(make_pdf("x.pdf"))
        record = repo.get_by_filename("x.pdf")
        assert record is not None
        assert record.filename == "x.pdf"
        assert repo.get_by_filename("missing.pdf") is None

    def test_get_by_id_missing(self, repo):
        assert repo.get_by_id(999) is None

    def test_get_by_id_with_type_filter(self, repo):
        pdf_id = repo.upsert(make_pdf())
        epub_id = repo.upsert(make_epub())
        assert repo.get_by_id(pdf_id, DocumentType.PDF) is not None
        assert repo.get_by_id(pdf_id, DocumentType.EPUB) is None
        assert repo.get_by_id(epub_id, DocumentType.EPUB) is not None
        assert repo.get_by_id(epub_id, DocumentType.PDF) is None


class TestListAndDelete:
    def test_list_all_and_by_type(self, repo):
        repo.upsert(make_pdf("a.pdf"))
        repo.upsert(make_pdf("b.pdf"))
        repo.upsert(make_epub("c.epub"))
        assert len(repo.list_all()) == 3
        assert len(repo.list_all(DocumentType.PDF)) == 2
        assert len(repo.list_all(DocumentType.EPUB)) == 1

    def test_delete_by_filename(self, repo):
        repo.upsert(make_pdf("a.pdf"))
        assert repo.delete_by_filename("a.pdf") is True
        assert repo.get_by_filename("a.pdf") is None
        assert repo.delete_by_filename("a.pdf") is False

    def test_update_last_accessed(self, repo, temp_db):
        doc_id = repo.upsert(make_pdf())
        conn = sqlite3.connect(temp_db)
        try:
            conn.execute(
                "UPDATE documents SET last_accessed = '2000-01-01 00:00:00' WHERE id = ?",
                (doc_id,),
            )
            conn.commit()
        finally:
            conn.close()
        repo.update_last_accessed(doc_id)
        record = repo.get_by_id(doc_id)
        assert record.last_accessed != "2000-01-01 00:00:00"


class TestEdgeCases:
    def test_minimal_record_with_null_optionals(self, repo):
        doc_id = repo.upsert(EpubDocumentUpsert(filename="bare.epub"))
        record = repo.get_by_id(doc_id)
        assert record.title is None
        assert record.author is None
        assert record.chapters == 0
        assert record.file_size is None

    def test_unicode_in_text_fields(self, repo):
        doc_id = repo.upsert(
            make_pdf("книга.pdf", title="日本語のタイトル", author="Müller, José")
        )
        record = repo.get_by_id(doc_id)
        assert record.title == "日本語のタイトル"
        assert record.author == "Müller, José"
        assert repo.get_by_filename("книга.pdf") is not None


class TestPersistence:
    def test_data_persists_across_instances(self, temp_db):
        repo1 = DocumentsRepository(db_path=temp_db)
        doc_id = repo1.upsert(make_epub())
        repo2 = DocumentsRepository(db_path=temp_db)
        record = repo2.get_by_id(doc_id)
        assert record is not None
        assert record.title == "An EPUB"

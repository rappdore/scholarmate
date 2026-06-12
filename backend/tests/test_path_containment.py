"""
Regression tests for path-traversal containment in file access (audit C-2).

get_pdf_path / get_epub_path historically joined request-supplied filenames
onto the books directory with no containment check, so "../" segments (and,
for EPUBs, URL-encoded forms that survive decoding) could escape it. The
fix resolves the joined path and requires it to stay inside the directory.

The services are instantiated without __init__ (which builds caches and
touches the database); the path methods only need the directory attributes.
"""

import pytest

from app.services.epub_service import EPUBService
from app.services.pdf_service import PDFService


@pytest.fixture
def pdf_service(tmp_path):
    books = tmp_path / "pdfs"
    books.mkdir()
    (books / "real.pdf").write_bytes(b"%PDF-1.4")
    # A PDF outside the books dir that traversal would otherwise reach
    (tmp_path / "secret.pdf").write_bytes(b"%PDF-1.4")

    service = PDFService.__new__(PDFService)
    service.pdf_dir = books
    return service


@pytest.fixture
def epub_service(tmp_path):
    books = tmp_path / "epubs"
    books.mkdir()
    (books / "real.epub").write_bytes(b"PK")
    (tmp_path / "secret.epub").write_bytes(b"PK")

    service = EPUBService.__new__(EPUBService)
    service.epub_dir = books
    return service


class TestPdfPathContainment:
    def test_normal_filename_resolves(self, pdf_service):
        path = pdf_service.get_pdf_path("real.pdf")
        assert path.name == "real.pdf"

    def test_traversal_is_rejected(self, pdf_service):
        with pytest.raises(FileNotFoundError):
            pdf_service.get_pdf_path("../secret.pdf")

    def test_deep_traversal_is_rejected(self, pdf_service):
        with pytest.raises(FileNotFoundError):
            pdf_service.get_pdf_path("../../../../etc/passwd.pdf")

    def test_non_pdf_suffix_is_rejected(self, pdf_service, tmp_path):
        (tmp_path / "pdfs" / "notes.txt").write_text("x")
        with pytest.raises(ValueError):
            pdf_service.get_pdf_path("notes.txt")


class TestEpubPathContainment:
    def test_normal_filename_resolves(self, epub_service):
        path = epub_service.get_epub_path("real.epub")
        assert path.name == "real.epub"

    def test_traversal_is_rejected(self, epub_service):
        with pytest.raises(FileNotFoundError):
            epub_service.get_epub_path("../secret.epub")

    def test_url_encoded_traversal_is_rejected(self, epub_service):
        # get_epub_path URL-decodes first, so an encoded "../" must not escape
        with pytest.raises(FileNotFoundError):
            epub_service.get_epub_path("..%2Fsecret.epub")

    def test_url_encoded_normal_filename_still_works(self, epub_service, tmp_path):
        (tmp_path / "epubs" / "my book.epub").write_bytes(b"PK")
        path = epub_service.get_epub_path("my%20book.epub")
        assert path.name == "my book.epub"

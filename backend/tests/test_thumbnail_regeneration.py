import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.services.epub.epub_image_service import EPUBImageService
from app.services.pdf_service import PDFService


def _make_thumbnail_newer_than_source(source_path: Path, thumbnail_path: Path) -> None:
    source_path.write_bytes(b"source")
    thumbnail_path.write_bytes(b"old thumbnail")
    os.utime(source_path, (1, 1))
    os.utime(thumbnail_path, (2, 2))


def test_pdf_thumbnail_force_bypasses_newer_existing_thumbnail():
    with (
        tempfile.TemporaryDirectory() as pdf_dir,
        tempfile.TemporaryDirectory() as thumb_dir,
        tempfile.TemporaryDirectory() as data_dir,
    ):
        pdf_path = Path(pdf_dir) / "book.pdf"
        thumb_path = Path(thumb_dir) / "book_thumb.png"
        _make_thumbnail_newer_than_source(pdf_path, thumb_path)
        service = PDFService(
            pdf_dir=pdf_dir,
            thumbnails_dir=thumb_dir,
            db_path=str(Path(data_dir) / "test.db"),
        )

        with patch("app.services.pdf_service.fitz.open") as fitz_open:
            assert service.generate_thumbnail("book.pdf") == thumb_path
            fitz_open.assert_not_called()

        with patch(
            "app.services.pdf_service.fitz.open", side_effect=Exception("render")
        ) as fitz_open:
            assert service.generate_thumbnail("book.pdf", force=True) == thumb_path
            fitz_open.assert_called_once()


def test_epub_thumbnail_force_bypasses_newer_existing_thumbnail():
    with (
        tempfile.TemporaryDirectory() as epub_dir,
        tempfile.TemporaryDirectory() as thumb_dir,
    ):
        epub_path = Path(epub_dir) / "book.epub"
        thumb_path = Path(thumb_dir) / "book_thumb_200x280.png"
        _make_thumbnail_newer_than_source(epub_path, thumb_path)
        service = EPUBImageService(thumbnails_dir=thumb_dir)

        with patch("app.services.epub.epub_image_service.epub.read_epub") as read_epub:
            assert service.generate_thumbnail(epub_path) == thumb_path
            read_epub.assert_not_called()

        with patch(
            "app.services.epub.epub_image_service.epub.read_epub",
            side_effect=Exception("render"),
        ) as read_epub:
            assert service.generate_thumbnail(epub_path, force=True) == thumb_path
            read_epub.assert_called_once()

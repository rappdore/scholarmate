import io
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
from PyPDF2 import PdfReader

from app.models.pdf_metadata import PDFBasicMetadata, PDFExtendedMetadata

from .pdf_cache import PDFCache


class PDFService:
    def __init__(
        self, pdf_dir: str = "pdfs", db_path: str = "data/reading_progress.db"
    ) -> None:
        self.pdf_dir = Path(pdf_dir)
        self.thumbnails_dir = Path("thumbnails")
        if not self.pdf_dir.exists():
            self.pdf_dir.mkdir(exist_ok=True)
        if not self.thumbnails_dir.exists():
            self.thumbnails_dir.mkdir(exist_ok=True)

        # Initialize cache with database backing (Phase 1a)
        self.cache = PDFCache(self.pdf_dir, self.thumbnails_dir, self, db_path)

    def list_pdfs(self) -> list[PDFBasicMetadata]:
        """
        List all PDF files in the pdfs directory with metadata (from cache)
        """
        return self.cache.get_all_pdfs()

    def get_pdf_info(self, filename: str) -> PDFExtendedMetadata:
        """
        Get detailed information about a specific PDF (with lazy-loaded extended metadata)
        """
        return self.cache.get_pdf_info(filename)

    def get_pdf_path(self, filename: str) -> Path:
        """
        Get the full path to a PDF file
        """
        file_path = self.pdf_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"PDF {filename} not found")

        if not file_path.suffix.lower() == ".pdf":
            raise ValueError(f"{filename} is not a PDF file")

        return file_path

    def extract_page_text(self, filename: str, page_num: int) -> str:
        """
        Extract text from a specific page of the PDF
        """
        file_path = self.get_pdf_path(filename)

        try:
            with pdfplumber.open(file_path) as pdf:
                if page_num < 1 or page_num > len(pdf.pages):
                    raise ValueError(
                        f"Page {page_num} is out of range. PDF has {len(pdf.pages)} pages."
                    )

                # pdfplumber uses 0-based indexing
                page = pdf.pages[page_num - 1]
                text = page.extract_text()

                return text or ""

        except Exception as e:
            # Fallback to PyPDF2 if pdfplumber fails
            try:
                with open(file_path, "rb") as file:
                    reader = PdfReader(file)
                    if page_num < 1 or page_num > len(reader.pages):
                        raise ValueError(
                            f"Page {page_num} is out of range. PDF has {len(reader.pages)} pages."
                        )

                    page = reader.pages[page_num - 1]
                    text = page.extract_text()

                    return text or ""
            except Exception as fallback_error:
                raise Exception(
                    f"Failed to extract text with both pdfplumber and PyPDF2: {str(e)}, {str(fallback_error)}"
                )

    def generate_thumbnail(
        self, filename: str, width: int = 200, height: int = 280
    ) -> Path:
        """
        Generate a thumbnail image of the first page of the PDF
        Returns the path to the generated thumbnail
        """
        file_path = self.get_pdf_path(filename)

        # Create thumbnail filename
        thumbnail_filename = f"{file_path.stem}_thumb.png"
        thumbnail_path = self.thumbnails_dir / thumbnail_filename

        # Check if thumbnail already exists and is newer than the PDF
        if thumbnail_path.exists():
            pdf_mtime = file_path.stat().st_mtime
            thumb_mtime = thumbnail_path.stat().st_mtime
            if thumb_mtime > pdf_mtime:
                return thumbnail_path

        try:
            # Open PDF with PyMuPDF
            doc = fitz.open(str(file_path))

            # Get first page
            page = doc[0]

            # Create a matrix for scaling to desired size
            # Get page dimensions
            rect = page.rect
            scale_x = width / rect.width
            scale_y = height / rect.height
            scale = min(scale_x, scale_y)  # Maintain aspect ratio

            mat = fitz.Matrix(scale, scale)

            # Render page to pixmap
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))

            # Create a white background image with exact dimensions
            final_image = Image.new("RGB", (width, height), "white")

            # Center the PDF page on the white background
            x_offset = (width - image.width) // 2
            y_offset = (height - image.height) // 2
            final_image.paste(image, (x_offset, y_offset))

            # Save thumbnail
            final_image.save(thumbnail_path, "PNG", optimize=True)

            doc.close()

            return thumbnail_path

        except Exception:
            # If thumbnail generation fails, create a placeholder
            placeholder = Image.new("RGB", (width, height), "#f1f5f9")

            # You could add some text or icon here
            final_image = placeholder
            final_image.save(thumbnail_path, "PNG")

            return thumbnail_path

    def get_thumbnail_path(self, filename: str) -> Path:
        """
        Get the path to a PDF thumbnail from cache (pre-generated)
        """
        thumbnail_path_str = self.cache.get_thumbnail_path(filename)
        if thumbnail_path_str:
            return Path(thumbnail_path_str)
        else:
            # Fallback: generate if not in cache (shouldn't happen normally)
            return self.generate_thumbnail(filename)

    def refresh_cache(self) -> dict[str, object]:
        """
        Refresh the PDF cache by rebuilding from filesystem
        """
        self.cache.refresh()
        return self.cache.get_cache_info()

    def get_cache_info(self) -> dict[str, object]:
        """
        Get metadata about the PDF cache
        """
        return self.cache.get_cache_info()

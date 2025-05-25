from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import io
import base64

import pdfplumber
from PyPDF2 import PdfReader
from PIL import Image
import fitz  # PyMuPDF


class PDFService:
    def __init__(self, pdf_dir: str = "pdfs"):
        self.pdf_dir = Path(pdf_dir)
        self.thumbnails_dir = Path("thumbnails")
        if not self.pdf_dir.exists():
            self.pdf_dir.mkdir(exist_ok=True)
        if not self.thumbnails_dir.exists():
            self.thumbnails_dir.mkdir(exist_ok=True)

    def list_pdfs(self) -> List[Dict[str, Any]]:
        """
        List all PDF files in the pdfs directory with metadata
        """
        pdfs = []

        for file_path in self.pdf_dir.glob("*.pdf"):
            try:
                # Get file stats
                stat = file_path.stat()

                # Get basic PDF info
                with open(file_path, "rb") as file:
                    reader = PdfReader(file)
                    num_pages = len(reader.pages)

                    # Try to get metadata
                    metadata = reader.metadata or {}
                    title = metadata.get("/Title", file_path.stem)
                    author = metadata.get("/Author", "Unknown")

                pdf_info = {
                    "filename": file_path.name,
                    "title": str(title) if title else file_path.stem,
                    "author": str(author) if author else "Unknown",
                    "num_pages": num_pages,
                    "file_size": stat.st_size,
                    "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                }

                pdfs.append(pdf_info)

            except Exception as e:
                # If we can't read a PDF, still include it but with limited info
                stat = file_path.stat()
                pdf_info = {
                    "filename": file_path.name,
                    "title": file_path.stem,
                    "author": "Unknown",
                    "num_pages": 0,
                    "file_size": stat.st_size,
                    "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "error": f"Could not read PDF: {str(e)}",
                }
                pdfs.append(pdf_info)

        # Sort by modified date (newest first)
        pdfs.sort(key=lambda x: x["modified_date"], reverse=True)

        return pdfs

    def get_pdf_info(self, filename: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific PDF
        """
        file_path = self.pdf_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"PDF {filename} not found")

        if not file_path.suffix.lower() == ".pdf":
            raise ValueError(f"{filename} is not a PDF file")

        stat = file_path.stat()

        with open(file_path, "rb") as file:
            reader = PdfReader(file)
            num_pages = len(reader.pages)

            # Get metadata
            metadata = reader.metadata or {}

            pdf_info = {
                "filename": file_path.name,
                "title": str(metadata.get("/Title", file_path.stem)),
                "author": str(metadata.get("/Author", "Unknown")),
                "subject": str(metadata.get("/Subject", "")),
                "creator": str(metadata.get("/Creator", "")),
                "producer": str(metadata.get("/Producer", "")),
                "creation_date": str(metadata.get("/CreationDate", "")),
                "modification_date": str(metadata.get("/ModDate", "")),
                "num_pages": num_pages,
                "file_size": stat.st_size,
                "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            }

            return pdf_info

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

    def generate_thumbnail(self, filename: str, width: int = 200, height: int = 280) -> Path:
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
            final_image = Image.new('RGB', (width, height), 'white')
            
            # Center the PDF page on the white background
            x_offset = (width - image.width) // 2
            y_offset = (height - image.height) // 2
            final_image.paste(image, (x_offset, y_offset))
            
            # Save thumbnail
            final_image.save(thumbnail_path, "PNG", optimize=True)
            
            doc.close()
            
            return thumbnail_path
            
        except Exception as e:
            # If thumbnail generation fails, create a placeholder
            placeholder = Image.new('RGB', (width, height), '#f1f5f9')
            
            # You could add some text or icon here
            final_image = placeholder
            final_image.save(thumbnail_path, "PNG")
            
            return thumbnail_path

    def get_thumbnail_path(self, filename: str) -> Path:
        """
        Get the path to a PDF thumbnail, generating it if it doesn't exist
        """
        return self.generate_thumbnail(filename)

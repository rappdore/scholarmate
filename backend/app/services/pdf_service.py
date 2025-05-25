from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pdfplumber
from PyPDF2 import PdfReader


class PDFService:
    def __init__(self, pdf_dir: str = "pdfs"):
        self.pdf_dir = Path(pdf_dir)
        if not self.pdf_dir.exists():
            self.pdf_dir.mkdir(exist_ok=True)

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

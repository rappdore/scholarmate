"""
Unified document models (A-1/A-2).

One ``documents`` table replaces the former ``pdf_documents`` and
``epub_documents`` registries. A document is identified by its integer id
(primary key) and globally-unique filename; ``doc_type`` discriminates the
format. Format-specific metadata lives in nullable columns typed here.
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel


class DocumentType(str, Enum):
    PDF = "pdf"
    EPUB = "epub"


class BookStatus(str, Enum):
    """Valid book status values"""

    NEW = "new"
    READING = "reading"
    FINISHED = "finished"


class DocumentRecord(BaseModel):
    """A row of the ``documents`` table."""

    id: int
    doc_type: DocumentType
    filename: str
    title: str | None = None
    author: str | None = None
    subject: str | None = None

    # PDF-specific (None for EPUBs)
    num_pages: int | None = None
    creator: str | None = None
    producer: str | None = None

    # EPUB-specific (None for PDFs)
    chapters: int | None = None
    publisher: str | None = None
    language: str | None = None

    # File information
    file_size: int | None = None
    file_path: str | None = None
    thumbnail_path: str | None = None

    # Timestamps (SQLite returns these as strings)
    created_date: str | None = None  # ISO format from filesystem
    modified_date: str | None = None  # ISO format from filesystem
    added_at: str | None = None
    last_accessed: str | None = None

    metadata_json: str | None = None


class PdfDocumentUpsert(BaseModel):
    """Input for creating/updating a PDF document record."""

    doc_type: Literal[DocumentType.PDF] = DocumentType.PDF
    filename: str
    num_pages: int
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    creator: str | None = None
    producer: str | None = None
    file_size: int | None = None
    file_path: str | None = None
    thumbnail_path: str | None = None
    created_date: str | None = None
    modified_date: str | None = None
    metadata: dict | None = None


class EpubDocumentUpsert(BaseModel):
    """Input for creating/updating an EPUB document record."""

    doc_type: Literal[DocumentType.EPUB] = DocumentType.EPUB
    filename: str
    chapters: int = 0
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    publisher: str | None = None
    language: str | None = None
    file_size: int | None = None
    file_path: str | None = None
    thumbnail_path: str | None = None
    created_date: str | None = None
    modified_date: str | None = None
    metadata: dict | None = None


DocumentUpsert = PdfDocumentUpsert | EpubDocumentUpsert


class PdfPosition(BaseModel):
    """Reading position inside a PDF: a page number."""

    kind: Literal["pdf"] = "pdf"
    last_page: int = 0
    total_pages: int | None = None


class EpubPosition(BaseModel):
    """Reading position inside an EPUB: a navigation section + scroll offset."""

    kind: Literal["epub"] = "epub"
    current_nav_id: str = "start"
    chapter_id: str | None = None
    chapter_title: str | None = None
    scroll_position: int = 0
    total_sections: int | None = None


DocumentPosition = PdfPosition | EpubPosition


class DocumentProgress(BaseModel):
    """A row of the unified ``document_progress`` table (joined with documents
    for filename/doc_type)."""

    document_id: int
    doc_type: DocumentType
    filename: str
    position: PdfPosition | EpubPosition
    progress_percentage: float = 0.0
    # EPUB-only navigation/word-count metadata; bulky and preserved across
    # saves (an incoming None never erases a stored value).
    nav_metadata: dict[str, Any] | None = None
    last_updated: str | None = None
    status: BookStatus = BookStatus.NEW
    status_updated_at: str | None = None
    manually_set: bool = False

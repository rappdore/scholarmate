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
    epub_cfi: str | None = None


DocumentPosition = PdfPosition | EpubPosition


class PdfHighlightRecord(BaseModel):
    """A row of ``document_highlights_pdf`` (joined with documents for the
    filename). PDF highlights anchor by page + character offsets + rendered
    bounding boxes."""

    id: int
    document_id: int
    filename: str
    page_number: int
    selected_text: str
    start_offset: int
    end_offset: int
    color: str
    coordinates: list[dict[str, Any]]
    created_at: str
    updated_at: str


class HighlightsSummary(BaseModel):
    """Per-document highlight statistics for list views."""

    highlights_count: int
    latest_highlight_date: str | None = None
    latest_highlight_text: str | None = None


class ReadingSessionRecord(BaseModel):
    """A row of the unified ``document_sessions`` table.

    ``units_read`` counts pages for PDFs and words for EPUBs — the
    format-specific *semantics* live in the consumers, storage is shared.
    Timestamps are ISO-8601 with a UTC indicator.
    """

    session_id: str
    document_id: int
    session_start: str
    last_updated: str
    units_read: int
    time_spent_seconds: float


class SessionsPage(BaseModel):
    """A (possibly paginated) listing of one document's reading sessions."""

    document_id: int
    total_sessions: int
    sessions: list[ReadingSessionRecord]


class PdfNoteAnchor(BaseModel):
    """Where a note attaches in a PDF: a page."""

    kind: Literal["pdf"] = "pdf"
    page_number: int


class EpubNoteAnchor(BaseModel):
    """Where a note attaches in an EPUB: a navigation section + context."""

    kind: Literal["epub"] = "epub"
    nav_id: str
    chapter_id: str | None = None
    chapter_title: str | None = None
    scroll_position: int = 0
    context_sections: list[str] | None = None


NoteAnchor = PdfNoteAnchor | EpubNoteAnchor


class NoteRecord(BaseModel):
    """A row of the unified ``document_notes`` table (joined with documents
    for filename/doc_type)."""

    id: int
    document_id: int
    doc_type: DocumentType
    filename: str
    anchor: PdfNoteAnchor | EpubNoteAnchor
    title: str | None = None
    chat_content: str
    created_at: str
    updated_at: str


class NotesSummary(BaseModel):
    """Per-document note statistics for list views."""

    notes_count: int
    latest_note_date: str | None = None
    latest_note_title: str | None = None


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

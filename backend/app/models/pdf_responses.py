from enum import Enum

from pydantic import BaseModel, computed_field

from .pdf_metadata import PDFBasicMetadata, PDFExtendedMetadata

# ============================================
# Enums
# ============================================


class BookStatus(str, Enum):
    """Valid book status values"""

    NEW = "new"
    READING = "reading"
    FINISHED = "finished"


# ============================================
# Database Record Models
# ============================================


class PDFDocumentRecord(BaseModel):
    """PDF document record from pdf_documents table"""

    id: int
    filename: str
    title: str | None = None
    author: str | None = None
    num_pages: int
    subject: str | None = None
    creator: str | None = None
    producer: str | None = None
    file_size: int | None = None
    file_path: str | None = None
    thumbnail_path: str | None = None
    created_date: str | None = None  # ISO format from filesystem
    modified_date: str | None = None  # ISO format from filesystem
    added_at: str  # SQLite returns as string
    last_accessed: str  # SQLite returns as string
    metadata_json: str | None = None


class ReadingProgress(BaseModel):
    """Reading progress for a PDF"""

    pdf_filename: str
    last_page: int
    total_pages: int | None = None
    last_updated: str  # SQLite returns timestamps as strings
    status: BookStatus = BookStatus.NEW
    status_updated_at: str | None = None  # SQLite timestamp string
    manually_set: bool = False

    @computed_field  # type: ignore[misc]
    @property
    def progress_percentage(self) -> int:
        """Calculate progress percentage"""
        if self.total_pages and self.total_pages > 0:
            return round((self.last_page / self.total_pages) * 100)
        return 0


class ReadingProgressWithId(ReadingProgress):
    """Reading progress with PDF ID added for API responses"""

    pdf_id: int


class NotesInfo(BaseModel):
    """Summary of notes for a PDF"""

    notes_count: int
    latest_note_date: str | None = None  # SQLite timestamp string
    latest_note_title: str | None = None


class HighlightsInfo(BaseModel):
    """Summary of highlights for a PDF"""

    highlights_count: int


class ChatNote(BaseModel):
    """A chat note linked to a PDF page"""

    id: int
    pdf_filename: str
    page_number: int
    title: str
    chat_content: str
    created_at: str  # SQLite timestamp string
    updated_at: str  # SQLite timestamp string


class Highlight(BaseModel):
    """A text highlight with coordinates"""

    id: int
    pdf_filename: str
    page_number: int
    selected_text: str
    start_offset: int
    end_offset: int
    color: str
    coordinates: list[dict[str, float]]  # List of bounding boxes
    created_at: str  # SQLite timestamp string
    updated_at: str  # SQLite timestamp string


# ============================================
# API Response Models (Existing)
# ============================================


class PDFListItem(PDFBasicMetadata):
    """
    PDF item in list view with database IDs.

    Extends basic metadata with database identifiers for API responses.
    Used in GET /api/pdf/list endpoint.
    """

    id: int
    pdf_id: int


class PDFDetailResponse(PDFExtendedMetadata):
    """
    Detailed PDF response with all metadata and database IDs.

    Includes both basic and extended metadata plus database identifiers.
    Used in GET /api/pdf/{pdf_id}/info endpoint.
    """

    id: int
    pdf_id: int


# ============================================
# API Response Models (New)
# ============================================


class PageTextResponse(BaseModel):
    """Response for extracting text from a page"""

    pdf_id: int
    filename: str
    page_number: int
    text: str


class ProgressSaveResponse(BaseModel):
    """Response after saving reading progress"""

    success: bool
    message: str
    pdf_id: int
    last_page: int


class StatusUpdateResponse(BaseModel):
    """Response after updating book status"""

    success: bool
    message: str
    pdf_id: int
    filename: str
    status: BookStatus
    manually_set: bool


class DatabaseDeletionResults(BaseModel):
    """Results from deleting database records only"""

    reading_progress: bool
    notes: bool
    highlights: bool


class DeletionResults(DatabaseDeletionResults):
    """Complete results from deleting book data (files + database)"""

    pdf_file: bool
    thumbnail: bool


class BookDeletionResponse(BaseModel):
    """Response after deleting a book"""

    success: bool
    message: str
    pdf_id: int
    filename: str
    deletion_details: DeletionResults


class PDFListItemEnriched(BaseModel):
    """PDF item in list with all enrichments (progress, notes, highlights)"""

    # Core fields from PDFBasicMetadata
    filename: str
    type: str = "pdf"
    title: str | None = None
    author: str | None = None
    num_pages: int
    file_size: int | None = None
    modified_date: str | None = None
    created_date: str | None = None
    thumbnail_path: str | None = None
    error: str | None = None

    # Database IDs
    id: int
    pdf_id: int

    # Enrichments
    reading_progress: ReadingProgress | None = None
    notes_info: NotesInfo | None = None
    highlights_info: HighlightsInfo | None = None


class AllReadingProgressResponse(BaseModel):
    """Response for getting all reading progress"""

    progress: dict[str, ReadingProgress]  # filename -> progress


class StatusCountsResponse(BaseModel):
    """Count of books by status"""

    new: int = 0
    reading: int = 0
    finished: int = 0
    all: int = 0


class CacheRefreshResponse(BaseModel):
    """Response after refreshing PDF cache"""

    success: bool
    cache_built_at: str
    pdf_count: int
    message: str

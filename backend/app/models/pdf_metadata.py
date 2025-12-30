from pydantic import BaseModel


class PDFBasicMetadata(BaseModel):
    """
    Basic PDF metadata loaded on cache initialization.

    This metadata is always available for all PDFs in the cache.

    Design Note - Date Fields as Strings:
    Date fields (modified_date, created_date, creation_date, modification_date) are
    stored as ISO format strings rather than datetime objects for the following reasons:
    1. Database compatibility - SQLite stores them as TEXT in ISO format
    2. API compatibility - Frontend expects ISO string format in JSON responses
    3. Backward compatibility - Existing code and API contracts use strings
    4. Simplicity - No need for datetime serialization/deserialization at API boundaries

    If migrating to datetime objects in the future, use Pydantic's model_serializer
    to ensure API responses remain ISO strings.
    """

    filename: str
    type: str = "pdf"
    title: str
    author: str
    num_pages: int
    file_size: int
    modified_date: str  # ISO format timestamp from filesystem
    created_date: str  # ISO format timestamp from filesystem
    thumbnail_path: str
    error: str | None = None


class PDFExtendedMetadata(PDFBasicMetadata):
    """
    Extended PDF metadata with lazy-loaded fields.

    These fields are only populated when get_pdf_info() is called,
    as they require reading the PDF file's internal metadata.
    """

    subject: str = ""
    creator: str = ""
    producer: str = ""
    creation_date: str = ""  # PDF internal creation date
    modification_date: str = ""  # PDF internal modification date

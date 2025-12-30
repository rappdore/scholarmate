from pydantic import BaseModel


class EPUBBasicMetadata(BaseModel):
    """
    Basic EPUB metadata loaded on cache initialization.

    This metadata is always available for all EPUBs in the cache.

    Design Note - Date Fields as Strings:
    Date fields (modified_date, created_date) are stored as ISO format strings
    rather than datetime objects for the following reasons:
    1. Database compatibility - SQLite stores them as TEXT in ISO format
    2. API compatibility - Frontend expects ISO string format in JSON responses
    3. Backward compatibility - Existing code and API contracts use strings
    4. Simplicity - No need for datetime serialization/deserialization at API boundaries

    If migrating to datetime objects in the future, use Pydantic's model_serializer
    to ensure API responses remain ISO strings.
    """

    filename: str
    type: str = "epub"
    title: str
    author: str
    chapters: int
    file_size: int
    modified_date: str  # ISO format timestamp from filesystem
    created_date: str  # ISO format timestamp from filesystem
    thumbnail_path: str
    error: str | None = None


class EPUBExtendedMetadata(EPUBBasicMetadata):
    """
    Extended EPUB metadata with lazy-loaded fields.

    These fields are only populated when get_epub_info() is called,
    as they require reading the EPUB file's internal metadata.
    """

    subject: str = ""  # Categories/tags (multiple values joined with ", ")
    publisher: str = ""
    language: str = ""

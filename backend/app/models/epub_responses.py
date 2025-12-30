from typing import Any

from .epub_metadata import EPUBBasicMetadata, EPUBExtendedMetadata


class EPUBListItem(EPUBBasicMetadata):
    """
    EPUB item in list view with database ID and enrichment data.

    Extends basic metadata with database identifier and reading progress.
    """

    id: int
    reading_progress: dict[str, Any] | None = None
    notes_info: dict[str, Any] | None = None
    highlights_info: dict[str, Any] | None = None


class EPUBDetailResponse(EPUBExtendedMetadata):
    """
    Detailed EPUB response with all metadata and database ID.

    Includes both basic and extended metadata plus database identifier.
    """

    id: int

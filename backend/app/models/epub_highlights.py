"""
EPUB Highlight Type Models

Pydantic models for EPUB highlights with proper typing.
Uses XPath + offset pairs for both start and end boundaries.
"""

from pydantic import BaseModel


class EPUBHighlight(BaseModel):
    """An EPUB text highlight with XPath boundaries"""

    id: int
    epub_id: int
    nav_id: str
    chapter_id: str | None = None

    # Start boundary
    start_xpath: str
    start_offset: int

    # End boundary
    end_xpath: str
    end_offset: int

    # Content
    highlight_text: str
    color: str

    created_at: str  # SQLite timestamp string


class EPUBHighlightCreate(BaseModel):
    """Request model for creating a highlight"""

    epub_id: int
    nav_id: str
    chapter_id: str | None = None
    start_xpath: str
    start_offset: int
    end_xpath: str
    end_offset: int
    highlight_text: str
    color: str = "yellow"

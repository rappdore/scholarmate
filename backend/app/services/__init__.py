"""
Services Package

This package contains database services for managing reading progress,
chat notes, and highlights. It provides both specialized services for each
domain and a unified facade service for backward compatibility.
"""

from .base_database_service import BaseDatabaseService
from .chat_notes_service import ChatNotesService
from .database_service import DatabaseService
from .epub_highlights_service import EPUBHighlightService
from .highlights_service import HighlightsService
from .progress_service import ProgressService

__all__ = [
    "DatabaseService",
    "ProgressService",
    "ChatNotesService",
    "HighlightsService",
    "BaseDatabaseService",
    "EPUBHighlightService",
]

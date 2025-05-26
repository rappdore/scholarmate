"""
Services Package

This package contains database services for managing PDF reading progress,
chat notes, and highlights. It provides both specialized services for each
domain and a unified facade service for backward compatibility.
"""

from .base_database_service import BaseDatabaseService
from .chat_notes_service import ChatNotesService
from .database_service import DatabaseService, db_service
from .highlights_service import HighlightsService
from .reading_progress_service import ReadingProgressService

__all__ = [
    "DatabaseService",
    "db_service",
    "ReadingProgressService",
    "ChatNotesService",
    "HighlightsService",
    "BaseDatabaseService",
]

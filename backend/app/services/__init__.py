"""
Services Package

This package contains database services for managing reading progress,
chat notes, and highlights. It provides both specialized services for each
domain and a unified facade service for backward compatibility.
"""

from .base_database_service import BaseDatabaseService
from .database_service import DatabaseService
from .highlights_service import HighlightsService
from .notes_service import NotesService
from .progress_service import ProgressService

__all__ = [
    "DatabaseService",
    "ProgressService",
    "NotesService",
    "HighlightsService",
    "BaseDatabaseService",
]

"""
Services Package

Database-backed domain services. Each service owns its tables and creates
its complete schema on construction; the registry wires them together.
"""

from .base_database_service import BaseDatabaseService
from .highlights_service import HighlightsService
from .notes_service import NotesService
from .progress_service import ProgressService
from .sessions_service import SessionsService

__all__ = [
    "ProgressService",
    "NotesService",
    "HighlightsService",
    "SessionsService",
    "BaseDatabaseService",
]

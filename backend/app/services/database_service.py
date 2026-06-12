"""
Database Service Module

This module provides a comprehensive database service for managing reading progress
and chat notes for PDF documents. It acts as a facade that coordinates specialized
services for different data domains while maintaining backward compatibility.

The service manages three main entities:
1. Reading Progress - tracks the last page read and total pages for each PDF
2. Chat Notes - stores conversation notes associated with specific PDF pages
3. Highlights - stores text highlights with coordinates and metadata
"""

import logging
import os
from typing import TYPE_CHECKING

from .highlights_service import HighlightsService
from .notes_service import NotesService
from .progress_service import ProgressService

if TYPE_CHECKING:
    from app.models.pdf_responses import DatabaseDeletionResults

# Configure logger for this module
logger = logging.getLogger(__name__)


class DatabaseService:
    """
    A facade service class for managing PDF/EPUB reading progress, chat notes, and highlights using SQLite.

    This class coordinates specialized services for different data domains while maintaining
    the same public API for backward compatibility. It delegates operations to:
    - ProgressService: unified reading progress/status tracking (used here for deletion)
    - NotesService: unified chat notes for both formats (used here for deletion)
    - HighlightsService: for text highlights with coordinates

    The database is automatically initialized with the required schema on first use.
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the database service and its specialized services.

        Args:
            db_path (str): Path to the SQLite database file. Defaults to "data/reading_progress.db"
                          The directory will be created if it doesn't exist.
        """
        self.db_path = db_path
        self._ensure_data_dir()

        # Initialize specialized services. Each service owns its tables and
        # creates its complete schema on construction; there is deliberately
        # no schema definition in this facade.
        self.progress = ProgressService(db_path)
        self.notes = NotesService(db_path)
        self.highlights = HighlightsService(db_path)

    def _ensure_data_dir(self):
        """
        Ensure the data directory exists for the database file.

        Creates the directory structure if it doesn't exist. This prevents
        database connection errors when the data directory is missing.
        """
        data_dir = os.path.dirname(self.db_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def delete_all_book_data(
        self, pdf_filename: str, document_id: int
    ) -> "DatabaseDeletionResults":
        """
        Delete all database data for a specific book.

        Args:
            pdf_filename (str): Name of the PDF file to delete all data for
            document_id (int): The document's registry id (keys the progress table)

        Returns:
            DatabaseDeletionResults: Results indicating success/failure for each data type
        """
        from app.models.pdf_responses import DatabaseDeletionResults

        # Delete reading progress
        reading_progress_deleted = self.progress.delete_progress(document_id)

        # Delete notes
        notes_deleted = self.notes.delete_notes_for_document(document_id)

        # Delete highlights
        highlights_deleted = self.highlights.delete_highlights_for_document(document_id)

        return DatabaseDeletionResults(
            reading_progress=reading_progress_deleted,
            notes=notes_deleted,
            highlights=highlights_deleted,
        )

    def delete_all_epub_data(
        self, epub_filename: str, document_id: int
    ) -> dict[str, bool]:
        """
        Delete all database data for a specific EPUB book.

        Args:
            epub_filename (str): Name of the EPUB file to delete all data for
            document_id (int): The document's registry id (keys progress + highlights)

        Returns:
            dict[str, bool]: Dictionary indicating success/failure for each data type
        """
        results = {}

        # Delete EPUB reading progress
        results["epub_progress"] = self.progress.delete_progress(document_id)

        # Delete EPUB chat notes
        results["epub_chat_notes"] = self.notes.delete_notes_for_document(document_id)

        # Delete EPUB highlights (keyed by the document id)
        results["epub_highlights"] = self.highlights.delete_highlights_for_document(
            document_id
        )

        return results

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
import sqlite3
from typing import Any, Dict, List, Optional

from .chat_notes_service import ChatNotesService
from .highlights_service import HighlightsService
from .reading_progress_service import ReadingProgressService

# Configure logger for this module
logger = logging.getLogger(__name__)


class DatabaseService:
    """
    A facade service class for managing PDF reading progress, chat notes, and highlights using SQLite.

    This class coordinates specialized services for different data domains while maintaining
    the same public API for backward compatibility. It delegates operations to:
    - ReadingProgressService: for PDF reading progress tracking
    - ChatNotesService: for conversation notes linked to PDF pages
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

        # Initialize specialized services
        self.reading_progress = ReadingProgressService(db_path)
        self.chat_notes = ChatNotesService(db_path)
        self.highlights = HighlightsService(db_path)

        # For backward compatibility, also initialize the legacy database
        self._ensure_data_dir()
        self._init_database()

    def _ensure_data_dir(self):
        """
        Ensure the data directory exists for the database file.

        Creates the directory structure if it doesn't exist. This prevents
        database connection errors when the data directory is missing.
        """
        data_dir = os.path.dirname(self.db_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def _init_database(self):
        """
        Initialize the database with required tables and indexes.

        Creates three main tables:
        1. reading_progress: Stores the last page read for each PDF
        2. chat_notes: Stores conversation notes linked to specific PDF pages
        3. highlights: Stores text highlights with coordinates and metadata

        Also creates indexes for optimal query performance.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Create reading progress table
            # Stores the current reading position for each PDF document
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reading_progress (
                    pdf_filename TEXT PRIMARY KEY,        -- Unique identifier for each PDF
                    last_page INTEGER NOT NULL,           -- Last page the user was reading
                    total_pages INTEGER,                   -- Total number of pages in the PDF
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- When this record was last modified
                )
            """)

            # Create chat notes table
            # Stores conversation notes that users create while reading PDFs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, -- Unique identifier for each note
                    pdf_filename TEXT NOT NULL,           -- Which PDF this note belongs to
                    page_number INTEGER NOT NULL,         -- Which page this note is associated with
                    title TEXT,                           -- Optional title for the note
                    chat_content TEXT NOT NULL,           -- The actual conversation/note content
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When the note was created
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- When the note was last modified
                )
            """)

            # Create highlights table
            # Stores text highlights with coordinates and visual properties
            conn.execute("""
                CREATE TABLE IF NOT EXISTS highlights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, -- Unique identifier for each highlight
                    pdf_filename TEXT NOT NULL,           -- Which PDF this highlight belongs to
                    page_number INTEGER NOT NULL,         -- Which page this highlight is on
                    selected_text TEXT NOT NULL,          -- The actual highlighted text content
                    start_offset INTEGER NOT NULL,        -- Character position where highlight starts
                    end_offset INTEGER NOT NULL,          -- Character position where highlight ends
                    color TEXT NOT NULL DEFAULT '#ffff00', -- Highlight color in hex format
                    coordinates TEXT NOT NULL,            -- JSON string with bounding box data array
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When the highlight was created
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- When the highlight was last modified
                )
            """)

            # Create index for faster lookups of notes by PDF and page
            # This significantly improves query performance when retrieving notes for a specific page
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_notes_pdf_page
                ON chat_notes(pdf_filename, page_number)
            """)

            # Create indexes for faster lookups of highlights by PDF and page
            # These indexes significantly improve query performance for highlight retrieval
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_highlights_pdf_page
                ON highlights(pdf_filename, page_number)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_highlights_pdf
                ON highlights(pdf_filename)
            """)

            conn.commit()

    def save_reading_progress(
        self, pdf_filename: str, last_page: int, total_pages: int
    ) -> bool:
        """
        Save or update reading progress for a PDF document.

        Uses INSERT OR REPLACE to either create a new record or update an existing one.
        This ensures that each PDF has only one progress record.

        Args:
            pdf_filename (str): Name of the PDF file (used as unique identifier)
            last_page (int): The page number the user was last reading
            total_pages (int): Total number of pages in the PDF document

        Returns:
            bool: True if the operation was successful, False otherwise
        """
        return self.reading_progress.save_progress(pdf_filename, last_page, total_pages)

    def get_reading_progress(self, pdf_filename: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve reading progress for a specific PDF document.

        Args:
            pdf_filename (str): Name of the PDF file to get progress for

        Returns:
            Optional[Dict[str, Any]]: Dictionary containing progress information:
                - pdf_filename: Name of the PDF file
                - last_page: Last page that was being read
                - total_pages: Total pages in the document
                - last_updated: Timestamp of last update
            Returns None if no progress is found for the PDF.
        """
        return self.reading_progress.get_progress(pdf_filename)

    def get_all_reading_progress(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve reading progress for all PDF documents.

        Returns a dictionary where keys are PDF filenames and values contain
        the progress information. Results are ordered by last_updated timestamp
        in descending order (most recently read first).

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping PDF filenames to their progress info:
                {
                    "filename.pdf": {
                        "last_page": int,
                        "total_pages": int,
                        "last_updated": str
                    }
                }
        """
        return self.reading_progress.get_all_progress()

    def save_chat_note(
        self, pdf_filename: str, page_number: int, title: str, chat_content: str
    ) -> Optional[int]:
        """
        Save a chat conversation as a note linked to a specific PDF page.

        This method stores conversation notes that users create while reading PDFs.
        Each note is associated with a specific page and can have an optional title.

        Args:
            pdf_filename (str): Name of the PDF file this note belongs to
            page_number (int): Page number this note is associated with
            title (str): Title for the note (can be empty)
            chat_content (str): The actual conversation or note content

        Returns:
            Optional[int]: The ID of the newly created note, or None if creation failed
        """
        return self.chat_notes.save_note(pdf_filename, page_number, title, chat_content)

    def get_chat_notes_for_pdf(
        self, pdf_filename: str, page_number: Optional[int] = None
    ) -> list[Dict[str, Any]]:
        """
        Retrieve chat notes for a PDF document, optionally filtered by page number.

        This method can return either:
        1. All notes for a PDF (when page_number is None)
        2. Notes for a specific page (when page_number is provided)

        Args:
            pdf_filename (str): Name of the PDF file to get notes for
            page_number (Optional[int]): Specific page number to filter by, or None for all pages

        Returns:
            list[Dict[str, Any]]: List of note dictionaries, each containing:
                - id: Unique note identifier
                - pdf_filename: PDF file name
                - page_number: Associated page number
                - title: Note title
                - chat_content: Note content
                - created_at: Creation timestamp
                - updated_at: Last update timestamp
        """
        return self.chat_notes.get_notes_for_pdf(pdf_filename, page_number)

    def get_chat_note_by_id(self, note_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific chat note by its unique ID.

        This method is useful for getting the full details of a specific note
        when you have its ID (e.g., for editing or viewing a particular note).

        Args:
            note_id (int): Unique identifier of the note to retrieve

        Returns:
            Optional[Dict[str, Any]]: Note dictionary with all fields, or None if not found
        """
        return self.chat_notes.get_note_by_id(note_id)

    def delete_chat_note(self, note_id: int) -> bool:
        """
        Delete a specific chat note by its ID.

        This permanently removes a note from the database. The operation
        cannot be undone, so it should be used with caution.

        Args:
            note_id (int): Unique identifier of the note to delete

        Returns:
            bool: True if a note was deleted, False if no note was found or deletion failed
        """
        return self.chat_notes.delete_note(note_id)

    def get_notes_count_by_pdf(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary statistics about notes for all PDF documents.

        This method provides an overview of note activity across all PDFs,
        including the total number of notes and information about the most recent note.
        This is useful for dashboard views or summary displays.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping PDF filenames to their note statistics:
                {
                    "filename.pdf": {
                        "notes_count": int,           # Total number of notes for this PDF
                        "latest_note_date": str,      # Timestamp of the most recent note
                        "latest_note_title": str      # Title of the most recent note
                    }
                }
        """
        return self.chat_notes.get_notes_count_by_pdf()

    # ========================================
    # HIGHLIGHT METHODS
    # ========================================

    def save_highlight(
        self,
        pdf_filename: str,
        page_number: int,
        selected_text: str,
        start_offset: int,
        end_offset: int,
        color: str,
        coordinates: List[Dict[str, Any]],
    ) -> Optional[int]:
        """
        Save a text highlight with coordinates and metadata.

        This method stores highlights that users create while reading PDFs.
        Each highlight contains the selected text, position offsets, visual properties,
        and coordinate data for accurate rendering.

        Args:
            pdf_filename (str): Name of the PDF file this highlight belongs to
            page_number (int): Page number this highlight is on
            selected_text (str): The actual text content that was highlighted
            start_offset (int): Character position where highlight starts
            end_offset (int): Character position where highlight ends
            color (str): Highlight color in hex format (e.g., '#ffff00')
            coordinates (List[Dict[str, Any]]): List of coordinate dictionaries with bounding box data

        Returns:
            Optional[int]: The ID of the newly created highlight, or None if creation failed
        """
        return self.highlights.save_highlight(
            pdf_filename,
            page_number,
            selected_text,
            start_offset,
            end_offset,
            color,
            coordinates,
        )

    def get_highlights_for_pdf(
        self, pdf_filename: str, page_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve highlights for a PDF document, optionally filtered by page number.

        This method can return either:
        1. All highlights for a PDF (when page_number is None)
        2. Highlights for a specific page (when page_number is provided)

        Args:
            pdf_filename (str): Name of the PDF file to get highlights for
            page_number (Optional[int]): Specific page number to filter by, or None for all pages

        Returns:
            List[Dict[str, Any]]: List of highlight dictionaries, each containing:
                - id: Unique highlight identifier
                - pdf_filename: PDF file name
                - page_number: Associated page number
                - selected_text: Highlighted text content
                - start_offset: Character start position
                - end_offset: Character end position
                - color: Highlight color in hex format
                - coordinates: Parsed coordinate data (as Python objects)
                - created_at: Creation timestamp
                - updated_at: Last update timestamp
        """
        return self.highlights.get_highlights_for_pdf(pdf_filename, page_number)

    def get_highlight_by_id(self, highlight_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific highlight by its unique ID.

        This method is useful for getting the full details of a specific highlight
        when you have its ID (e.g., for editing or viewing a particular highlight).

        Args:
            highlight_id (int): Unique identifier of the highlight to retrieve

        Returns:
            Optional[Dict[str, Any]]: Highlight dictionary with all fields, or None if not found
        """
        return self.highlights.get_highlight_by_id(highlight_id)

    def delete_highlight(self, highlight_id: int) -> bool:
        """
        Delete a specific highlight by its ID.

        This permanently removes a highlight from the database. The operation
        cannot be undone, so it should be used with caution.

        Args:
            highlight_id (int): Unique identifier of the highlight to delete

        Returns:
            bool: True if a highlight was deleted, False if no highlight was found or deletion failed
        """
        return self.highlights.delete_highlight(highlight_id)

    def update_highlight_color(self, highlight_id: int, color: str) -> bool:
        """
        Update the color of a specific highlight.

        This method allows users to change the color of an existing highlight
        without affecting other properties.

        Args:
            highlight_id (int): Unique identifier of the highlight to update
            color (str): New highlight color in hex format (e.g., '#ff0000')

        Returns:
            bool: True if the highlight was updated, False if no highlight was found or update failed
        """
        return self.highlights.update_color(highlight_id, color)

    def get_highlights_count_by_pdf(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary statistics about highlights for all PDF documents.

        This method provides an overview of highlight activity across all PDFs,
        including the total number of highlights and information about the most recent highlight.
        This is useful for dashboard views or summary displays.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping PDF filenames to their highlight statistics:
                {
                    "filename.pdf": {
                        "highlights_count": int,           # Total number of highlights for this PDF
                        "latest_highlight_date": str,      # Timestamp of the most recent highlight
                        "latest_highlight_text": str       # Preview of the most recent highlight text
                    }
                }
        """
        return self.highlights.get_highlights_count_by_pdf()


# Global instance
# This creates a singleton instance of the DatabaseService that can be imported
# and used throughout the application. This ensures all parts of the app use
# the same database connection and configuration.
db_service = DatabaseService()

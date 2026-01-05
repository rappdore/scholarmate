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
from typing import TYPE_CHECKING, Any

from ..models.epub_highlights import EPUBHighlight, EPUBHighlightCreate
from .chat_notes_service import ChatNotesService
from .epub_chat_notes_service import EPUBChatNotesService
from .epub_highlights_service import EPUBHighlightService
from .epub_progress_service import EPUBProgressService
from .epub_reading_statistics_service import EPUBReadingStatisticsService
from .highlights_service import HighlightsService
from .reading_progress_service import ReadingProgressService
from .reading_statistics_service import ReadingStatisticsService

if TYPE_CHECKING:
    from app.models.pdf_responses import DatabaseDeletionResults, ReadingProgress

# Configure logger for this module
logger = logging.getLogger(__name__)


class DatabaseService:
    """
    A facade service class for managing PDF/EPUB reading progress, chat notes, and highlights using SQLite.

    This class coordinates specialized services for different data domains while maintaining
    the same public API for backward compatibility. It delegates operations to:
    - ReadingProgressService: for PDF reading progress tracking
    - EPUBProgressService: for EPUB reading progress tracking
    - ChatNotesService: for conversation notes linked to PDF pages
    - EPUBChatNotesService: for conversation notes linked to EPUB navigation sections
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

        # For backward compatibility, also initialize the legacy database
        self._ensure_data_dir()
        self._init_database()

        # Initialize specialized services
        self.reading_progress = ReadingProgressService(db_path)
        self.epub_progress = EPUBProgressService(db_path)
        self.chat_notes = ChatNotesService(db_path)
        self.epub_chat_notes = EPUBChatNotesService(db_path)
        self.highlights = HighlightsService(db_path)
        self.epub_highlights = EPUBHighlightService(db_path)
        self.reading_statistics = ReadingStatisticsService(db_path)
        self.epub_reading_statistics = EPUBReadingStatisticsService(db_path)

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

            conn.execute("""
                CREATE TABLE IF NOT EXISTS epub_reading_progress (
                    epub_filename TEXT PRIMARY KEY,           -- Unique identifier for each EPUB
                    current_nav_id TEXT NOT NULL,             -- Current finest navigation section
                    chapter_id TEXT,                          -- Chapter-level ID for display
                    chapter_title TEXT,                       -- Chapter title for UI display
                    scroll_position INTEGER DEFAULT 0,       -- Scroll position within current section
                    total_sections INTEGER,                   -- Total navigation sections in book
                    progress_percentage REAL DEFAULT 0.0,    -- Overall book progress (0.0-100.0)
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- Book Status Management (same as PDF system)
                    status TEXT DEFAULT 'new' CHECK (status IN ('new', 'reading', 'finished')),
                    status_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    manually_set BOOLEAN DEFAULT FALSE,      -- Whether status was manually set by user

                    -- EPUB-specific metadata for progress calculation
                    nav_metadata TEXT                         -- JSON metadata about navigation structure
                )
            """)

            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_progress_status
                ON epub_reading_progress(status)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_progress_updated
                ON epub_reading_progress(status, status_updated_at)
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

            # Create pdf_documents table (Phase 1a: PDF Cache Database Backing)
            # Stores persistent metadata for PDF documents to support database-backed caching
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pdf_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL UNIQUE,

                    -- Basic metadata (loaded on cache initialization)
                    title TEXT,
                    author TEXT,
                    num_pages INTEGER NOT NULL,

                    -- Extended metadata (lazy-loaded on first request)
                    subject TEXT,
                    creator TEXT,
                    producer TEXT,

                    -- File information
                    file_size INTEGER,
                    file_path TEXT,
                    thumbnail_path TEXT,

                    -- Timestamps
                    created_date TEXT,          -- ISO format datetime from filesystem
                    modified_date TEXT,         -- ISO format datetime from filesystem
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- Extensibility
                    metadata_json TEXT          -- Full PDF metadata as JSON for future use
                )
            """)

            # Create indexes for pdf_documents table
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pdf_documents_filename
                ON pdf_documents(filename)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pdf_documents_accessed
                ON pdf_documents(last_accessed)
            """)

            # Create epub_documents table (Phase 1b: EPUB Cache Database Backing)
            # Stores persistent metadata for EPUB documents to support database-backed caching
            conn.execute("""
                CREATE TABLE IF NOT EXISTS epub_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL UNIQUE,

                    -- Basic metadata (loaded on cache initialization)
                    title TEXT,
                    author TEXT,
                    chapters INTEGER NOT NULL DEFAULT 0,

                    -- Extended metadata (lazy-loaded on first request)
                    subject TEXT,
                    publisher TEXT,
                    language TEXT,

                    -- File information
                    file_size INTEGER,
                    file_path TEXT,
                    thumbnail_path TEXT,

                    -- Timestamps
                    created_date TEXT,          -- ISO format datetime from filesystem
                    modified_date TEXT,         -- ISO format datetime from filesystem
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- Extensibility
                    metadata_json TEXT          -- Full EPUB metadata as JSON for future use
                )
            """)

            # Create indexes for epub_documents table
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_documents_filename
                ON epub_documents(filename)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_documents_accessed
                ON epub_documents(last_accessed)
            """)

            # Create LLM configurations table
            # Stores multiple LLM endpoint configurations with one active at a time
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_configurations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,                -- User-friendly name
                    description TEXT,                         -- Optional description
                    base_url TEXT NOT NULL,                   -- API endpoint URL
                    api_key TEXT NOT NULL,                    -- Authentication key
                    model_name TEXT NOT NULL,                 -- Model identifier
                    is_active BOOLEAN DEFAULT FALSE,          -- Active configuration flag
                    always_starts_with_thinking BOOLEAN NOT NULL DEFAULT 0,  -- Whether model always starts with thinking block
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for quick lookup of active configuration
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_config_active
                ON llm_configurations(is_active) WHERE is_active = TRUE
            """)

            # Create trigger to ensure only one active LLM configuration
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS enforce_single_active_llm
                BEFORE UPDATE ON llm_configurations
                FOR EACH ROW
                WHEN NEW.is_active = 1
                BEGIN
                    UPDATE llm_configurations SET is_active = 0 WHERE id != NEW.id;
                END
            """)

            # Add always_starts_with_thinking column if it doesn't exist (backward compatible)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(llm_configurations)")
            columns = [column[1] for column in cursor.fetchall()]
            if "always_starts_with_thinking" not in columns:
                logger.info(
                    "Adding always_starts_with_thinking column to llm_configurations table..."
                )
                conn.execute(
                    "ALTER TABLE llm_configurations ADD COLUMN always_starts_with_thinking BOOLEAN NOT NULL DEFAULT 0"
                )
                logger.info("always_starts_with_thinking column added successfully")

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

    def get_reading_progress(self, pdf_filename: str) -> "ReadingProgress | None":
        """
        Retrieve reading progress for a specific PDF document.

        Args:
            pdf_filename (str): Name of the PDF file to get progress for

        Returns:
            ReadingProgress | None: Progress information or None if not found
        """
        return self.reading_progress.get_progress(pdf_filename)

    def get_all_reading_progress(self) -> dict[str, "ReadingProgress"]:
        """
        Retrieve reading progress for all PDFs.

        Returns:
            dict[str, ReadingProgress]: Dictionary mapping PDF filenames to their progress info
        """
        return self.reading_progress.get_all_progress()

    # ========================================
    # EPUB PROGRESS METHODS (separate from PDF)
    # ========================================

    def save_epub_progress(
        self,
        epub_filename: str,
        current_nav_id: str,
        chapter_id: str = None,
        chapter_title: str = None,
        scroll_position: int = 0,
        total_sections: int = None,
        progress_percentage: float = 0.0,
        nav_metadata: dict[str, Any] = None,
    ) -> bool:
        """
        Save or update reading progress for an EPUB document.

        Args:
            epub_filename (str): Name of the EPUB file (used as unique identifier)
            current_nav_id (str): Current finest navigation section ID
            chapter_id (str): Chapter-level ID for display purposes
            chapter_title (str): Chapter title for UI display
            scroll_position (int): Scroll position within current section
            total_sections (int): Total number of navigation sections in book
            progress_percentage (float): Overall book progress (0.0-100.0)
            nav_metadata (dict[str, Any]): Navigation metadata for progress calculation

        Returns:
            bool: True if the operation was successful, False otherwise
        """
        return self.epub_progress.save_progress(
            epub_filename,
            current_nav_id,
            chapter_id,
            chapter_title,
            scroll_position,
            total_sections,
            progress_percentage,
            nav_metadata,
        )

    def get_epub_progress(self, epub_filename: str) -> dict[str, Any] | None:
        """
        Retrieve reading progress for a specific EPUB document.

        Args:
            epub_filename (str): Name of the EPUB file to get progress for

        Returns:
            dict[str, Any] | None: Dictionary containing progress information:
                - epub_filename: Name of the EPUB file
                - current_nav_id: Current navigation section ID
                - chapter_id: Chapter-level ID for display
                - chapter_title: Chapter title
                - scroll_position: Scroll position within section
                - total_sections: Total navigation sections
                - progress_percentage: Overall progress (0.0-100.0)
                - last_updated: Timestamp of last update
                - status: Reading status (new/reading/finished)
                - nav_metadata: Navigation structure metadata
            Returns None if no progress is found for the EPUB.
        """
        return self.epub_progress.get_progress(epub_filename)

    def get_all_epub_progress(self) -> dict[str, dict[str, Any]]:
        """
        Retrieve reading progress for all EPUB documents.

        Returns:
            dict[str, dict[str, Any]]: Dictionary mapping EPUB filenames to their progress info
        """
        return self.epub_progress.get_all_progress()

    def update_epub_book_status(
        self, epub_filename: str, status: str, manual: bool = True
    ) -> bool:
        """
        Update the reading status of an EPUB book.

        Args:
            epub_filename (str): Name of the EPUB file to update status for
            status (str): New status ('new', 'reading', 'finished')
            manual (bool): Whether this status was manually set by the user

        Returns:
            bool: True if the operation was successful, False otherwise
        """
        return self.epub_progress.update_book_status(epub_filename, status, manual)

    def get_epub_books_by_status(
        self, status: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get all EPUB books filtered by status.

        Args:
            status (str | None): Filter by specific status ('new', 'reading', 'finished').
                                   If None, returns all books.

        Returns:
            list[dict[str, Any]]: List of EPUB books with their progress and status information
        """
        return self.epub_progress.get_books_by_status(status)

    def get_epub_status_counts(self) -> dict[str, int]:
        """
        Get count of EPUB books for each status.

        Returns:
            dict[str, int]: Dictionary with status counts
        """
        return self.epub_progress.get_status_counts()

    def delete_epub_progress(self, epub_filename: str) -> bool:
        """
        Delete reading progress record for a specific EPUB.

        Args:
            epub_filename (str): Name of the EPUB file to delete progress for

        Returns:
            bool: True if the record was deleted successfully, False otherwise
        """
        return self.epub_progress.delete_progress(epub_filename)

    def calculate_epub_progress_percentage(
        self, current_nav_id: str, nav_metadata: dict[str, Any] = None
    ) -> float:
        """
        Calculate overall progress percentage for an EPUB based on current navigation position.

        Args:
            current_nav_id (str): Current navigation section ID
            nav_metadata (dict[str, Any]): Navigation structure metadata

        Returns:
            float: Progress percentage (0.0-100.0)
        """
        return self.epub_progress.calculate_progress_percentage(
            current_nav_id, nav_metadata
        )

    def get_epub_chapter_progress_info(
        self, epub_filename: str, chapter_id: str = None
    ) -> dict[str, Any]:
        """
        Get detailed progress information for a specific EPUB chapter or current chapter.

        Args:
            epub_filename (str): Name of the EPUB file
            chapter_id (str): Specific chapter ID, or None for current chapter

        Returns:
            dict[str, Any]: Chapter progress information
        """
        return self.epub_progress.get_chapter_progress_info(epub_filename, chapter_id)

    # ========================================
    # CHAT NOTES METHODS
    # ========================================

    def save_chat_note(
        self, pdf_filename: str, page_number: int, title: str, chat_content: str
    ) -> int | None:
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
            int | None: The ID of the newly created note, or None if creation failed
        """
        return self.chat_notes.save_note(pdf_filename, page_number, title, chat_content)

    def get_chat_notes_for_pdf(
        self, pdf_filename: str, page_number: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve chat notes for a PDF document, optionally filtered by page number.

        This method can return either:
        1. All notes for a PDF (when page_number is None)
        2. Notes for a specific page (when page_number is provided)

        Args:
            pdf_filename (str): Name of the PDF file to get notes for
            page_number (int | None): Specific page number to filter by, or None for all pages

        Returns:
            list[dict[str, Any]]: List of note dictionaries, each containing:
                - id: Unique note identifier
                - pdf_filename: PDF file name
                - page_number: Associated page number
                - title: Note title
                - chat_content: Note content
                - created_at: Creation timestamp
                - updated_at: Last update timestamp
        """
        return self.chat_notes.get_notes_for_pdf(pdf_filename, page_number)

    def get_chat_note_by_id(self, note_id: int) -> dict[str, Any] | None:
        """
        Retrieve a specific chat note by its unique ID.

        This method is useful for getting the full details of a specific note
        when you have its ID (e.g., for editing or viewing a particular note).

        Args:
            note_id (int): Unique identifier of the note to retrieve

        Returns:
            dict[str, Any] | None: Note dictionary with all fields, or None if not found
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

    def get_notes_count_by_pdf(self) -> dict[str, dict[str, Any]]:
        """
        Get summary statistics about notes for all PDF documents.

        This method provides an overview of note activity across all PDFs,
        including the total number of notes and information about the most recent note.
        This is useful for dashboard views or summary displays.

        Returns:
            dict[str, dict[str, Any]]: Dictionary mapping PDF filenames to their note statistics:
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
    # EPUB CHAT NOTES METHODS
    # ========================================

    def save_epub_chat_note(
        self,
        epub_filename: str,
        nav_id: str,
        chapter_id: str,
        chapter_title: str,
        title: str,
        chat_content: str,
        context_sections: list[str] = None,
        scroll_position: int = 0,
    ) -> int | None:
        """
        Save an EPUB chat conversation as a note linked to a navigation section.

        Args:
            epub_filename (str): Name of the EPUB file this note belongs to
            nav_id (str): Precise navigation section identifier
            chapter_id (str): Chapter identifier for grouping/display
            chapter_title (str): Human-readable chapter title
            title (str): Title for the note (can be empty)
            chat_content (str): The actual conversation or note content
            context_sections (list[str]): List of section IDs that provided context
            scroll_position (int): Scroll position within the section

        Returns:
            int | None: The ID of the newly created note, or None if creation failed
        """
        return self.epub_chat_notes.save_note(
            epub_filename,
            nav_id,
            chapter_id,
            chapter_title,
            title,
            chat_content,
            context_sections,
            scroll_position,
        )

    def get_epub_chat_notes(
        self,
        epub_filename: str,
        nav_id: str | None = None,
        chapter_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve chat notes for an EPUB document, with fine-grained or chapter-level filtering.

        Args:
            epub_filename (str): Name of the EPUB file to get notes for
            nav_id (str | None): Specific navigation section to filter by
            chapter_id (str | None): Specific chapter to filter by

        Returns:
            list[dict[str, Any]]: List of note dictionaries with navigation context
        """
        return self.epub_chat_notes.get_notes_for_epub(
            epub_filename, nav_id, chapter_id
        )

    def get_epub_chat_notes_by_chapter(
        self, epub_filename: str
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get EPUB chat notes grouped by chapter for UI display.

        Args:
            epub_filename (str): Name of the EPUB file to get notes for

        Returns:
            dict[str, list[dict[str, Any]]]: Dictionary mapping chapter IDs to their notes
        """
        return self.epub_chat_notes.get_notes_grouped_by_chapter(epub_filename)

    def get_epub_chat_note_by_id(self, note_id: int) -> dict[str, Any] | None:
        """
        Retrieve a specific EPUB chat note by its unique ID.

        Args:
            note_id (int): Unique identifier of the note to retrieve

        Returns:
            dict[str, Any] | None: Note dictionary with all fields, or None if not found
        """
        return self.epub_chat_notes.get_note_by_id(note_id)

    def delete_epub_chat_note(self, note_id: int) -> bool:
        """
        Delete a specific EPUB chat note by its ID.

        Args:
            note_id (int): Unique identifier of the note to delete

        Returns:
            bool: True if a note was deleted, False if no note was found or deletion failed
        """
        return self.epub_chat_notes.delete_note(note_id)

    def get_epub_notes_count_by_epub(self) -> dict[str, dict[str, Any]]:
        """
        Get summary statistics about notes for all EPUB documents.

        Returns:
            dict[str, dict[str, Any]]: Dictionary mapping EPUB filenames to their note statistics
        """
        return self.epub_chat_notes.get_notes_count_by_epub()

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
        coordinates: list[dict[str, Any]],
    ) -> int | None:
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
            coordinates (list[dict[str, Any]]): List of coordinate dictionaries with bounding box data

        Returns:
            int | None: The ID of the newly created highlight, or None if creation failed
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
        self, pdf_filename: str, page_number: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve highlights for a PDF document, optionally filtered by page number.

        This method can return either:
        1. All highlights for a PDF (when page_number is None)
        2. Highlights for a specific page (when page_number is provided)

        Args:
            pdf_filename (str): Name of the PDF file to get highlights for
            page_number (int | None): Specific page number to filter by, or None for all pages

        Returns:
            list[dict[str, Any]]: List of highlight dictionaries, each containing:
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

    def get_highlight_by_id(self, highlight_id: int) -> dict[str, Any] | None:
        """
        Retrieve a specific highlight by its unique ID.

        This method is useful for getting the full details of a specific highlight
        when you have its ID (e.g., for editing or viewing a particular highlight).

        Args:
            highlight_id (int): Unique identifier of the highlight to retrieve

        Returns:
            dict[str, Any] | None: Highlight dictionary with all fields, or None if not found
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

    def get_highlights_count_by_pdf(self) -> dict[str, dict[str, Any]]:
        """
        Get summary statistics about highlights for all PDF documents.

        This method provides an overview of highlight activity across all PDFs,
        including the total number of highlights and information about the most recent highlight.
        This is useful for dashboard views or summary displays.

        Returns:
            dict[str, dict[str, Any]]: Dictionary mapping PDF filenames to their highlight statistics:
                {
                    "filename.pdf": {
                        "highlights_count": int,           # Total number of highlights for this PDF
                        "latest_highlight_date": str,      # Timestamp of the most recent highlight
                        "latest_highlight_text": str       # Preview of the most recent highlight text
                    }
                }
        """
        return self.highlights.get_highlights_count_by_pdf()

    # Status management methods (delegated to reading progress service)

    def update_book_status(
        self, pdf_filename: str, status: str, manual: bool = True
    ) -> bool:
        """
        Update the reading status of a book.

        Args:
            pdf_filename (str): Name of the PDF file to update status for
            status (str): New status ('new', 'reading', 'finished')
            manual (bool): Whether this status was manually set by the user

        Returns:
            bool: True if the operation was successful, False otherwise
        """
        return self.reading_progress.update_book_status(pdf_filename, status, manual)

    def get_books_by_status(self, status: str | None = None) -> list["ReadingProgress"]:
        """
        Get all books filtered by status.

        Args:
            status (str | None): Filter by specific status ('new', 'reading', 'finished').
                                   If None, returns all books.

        Returns:
            list[ReadingProgress]: List of books with their progress and status information
        """
        return self.reading_progress.get_books_by_status(status)

    def get_status_counts(self) -> dict[str, int]:
        """
        Get count of books for each status.

        Returns:
            dict[str, int]: Dictionary with status counts
        """
        return self.reading_progress.get_status_counts()

    def delete_reading_progress(self, pdf_filename: str) -> bool:
        """
        Delete reading progress record for a specific PDF.

        Args:
            pdf_filename (str): Name of the PDF file to delete progress for

        Returns:
            bool: True if the record was deleted successfully, False otherwise
        """
        return self.reading_progress.delete_progress(pdf_filename)

    def delete_all_book_data(self, pdf_filename: str) -> "DatabaseDeletionResults":
        """
        Delete all database data for a specific book.

        Args:
            pdf_filename (str): Name of the PDF file to delete all data for

        Returns:
            DatabaseDeletionResults: Results indicating success/failure for each data type
        """
        from app.models.pdf_responses import DatabaseDeletionResults

        # Delete reading progress
        reading_progress_deleted = self.delete_reading_progress(pdf_filename)

        # Delete notes
        notes_deleted = False
        try:
            with self.chat_notes.get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM chat_notes WHERE pdf_filename = ?", (pdf_filename,)
                )
                conn.commit()
                notes_deleted = (
                    cursor.rowcount >= 0
                )  # Consider successful even if no rows were deleted
        except Exception as e:
            logger.error(f"Error deleting notes for {pdf_filename}: {e}")

        # Delete highlights
        highlights_deleted = False
        try:
            with self.highlights.get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM highlights WHERE pdf_filename = ?", (pdf_filename,)
                )
                conn.commit()
                highlights_deleted = (
                    cursor.rowcount >= 0
                )  # Consider successful even if no rows were deleted
        except Exception as e:
            logger.error(f"Error deleting highlights for {pdf_filename}: {e}")

        return DatabaseDeletionResults(
            reading_progress=reading_progress_deleted,
            notes=notes_deleted,
            highlights=highlights_deleted,
        )

    def delete_all_epub_data(self, epub_filename: str) -> dict[str, bool]:
        """
        Delete all database data for a specific EPUB book.

        Args:
            epub_filename (str): Name of the EPUB file to delete all data for

        Returns:
            dict[str, bool]: Dictionary indicating success/failure for each data type
        """
        results = {}

        # Delete EPUB reading progress
        results["epub_progress"] = self.delete_epub_progress(epub_filename)

        # Delete EPUB chat notes
        try:
            with self.epub_chat_notes.get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM epub_chat_notes WHERE epub_filename = ?",
                    (epub_filename,),
                )
                conn.commit()
                results["epub_chat_notes"] = (
                    cursor.rowcount >= 0
                )  # Consider successful even if no rows were deleted
        except Exception as e:
            logger.error(f"Error deleting EPUB chat notes for {epub_filename}: {e}")
            results["epub_chat_notes"] = False

        # Delete EPUB highlights - need to look up epub_id first
        try:
            from .epub_documents_service import EPUBDocumentsService

            epub_docs_service = EPUBDocumentsService(self.db_path)
            epub_doc = epub_docs_service.get_by_filename(epub_filename)
            if epub_doc:
                epub_id = epub_doc.get("id")
                if epub_id:
                    results["epub_highlights"] = self.delete_epub_highlights_for_epub(
                        epub_id
                    )
                else:
                    results["epub_highlights"] = True  # No ID, nothing to delete
            else:
                results["epub_highlights"] = True  # Doc not found, nothing to delete
        except Exception as e:
            logger.error(f"Error deleting EPUB highlights for {epub_filename}: {e}")
            results["epub_highlights"] = False

        return results

    # ------------------------------------------------------------------
    # EPUB Highlight Delegation Methods
    # ------------------------------------------------------------------

    def save_epub_highlight(self, data: EPUBHighlightCreate) -> int | None:
        """Create a highlight for an EPUB section."""
        return self.epub_highlights.save_highlight(data)

    def get_epub_all_highlights(self, epub_id: int) -> list[EPUBHighlight]:
        """Return all highlights for an EPUB document."""
        return self.epub_highlights.get_all_highlights(epub_id)

    def get_epub_section_highlights(
        self, epub_id: int, nav_id: str
    ) -> list[EPUBHighlight]:
        """Return highlights for a specific nav_id section."""
        return self.epub_highlights.get_highlights_for_section(epub_id, nav_id)

    def get_epub_chapter_highlights(
        self, epub_id: int, chapter_id: str
    ) -> list[EPUBHighlight]:
        """Return all highlights within a chapter."""
        return self.epub_highlights.get_highlights_for_chapter(epub_id, chapter_id)

    def get_epub_highlight_by_id(self, highlight_id: int) -> EPUBHighlight | None:
        return self.epub_highlights.get_highlight_by_id(highlight_id)

    def delete_epub_highlight(self, highlight_id: int) -> bool:
        return self.epub_highlights.delete_highlight(highlight_id)

    def update_epub_highlight_color(self, highlight_id: int, color: str) -> bool:
        return self.epub_highlights.update_color(highlight_id, color)

    def get_epub_highlights_count_by_epub(self) -> dict[int, dict[str, int]]:
        """Return highlight count statistics for all EPUB documents."""
        return self.epub_highlights.get_highlights_count_by_epub()

    def delete_epub_highlights_for_epub(self, epub_id: int) -> bool:
        """Delete all highlights for an EPUB document."""
        return self.epub_highlights.delete_highlights_for_epub(epub_id)


# Global instance
# This creates a singleton instance of the DatabaseService that can be imported
# and used throughout the application. This ensures all parts of the app use
# the same database connection and configuration.
db_service = DatabaseService()

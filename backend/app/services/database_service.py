"""
Database Service Module

This module provides a comprehensive database service for managing reading progress
and chat notes for PDF documents. It uses SQLite as the backend database and provides
methods for CRUD operations on reading progress and chat notes.

The service manages two main entities:
1. Reading Progress - tracks the last page read and total pages for each PDF
2. Chat Notes - stores conversation notes associated with specific PDF pages
"""

import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

# Configure logger for this module
logger = logging.getLogger(__name__)


class DatabaseService:
    """
    A service class for managing PDF reading progress and chat notes using SQLite.
    
    This class provides a complete database abstraction layer for storing and retrieving:
    - Reading progress for PDF documents (last page read, total pages)
    - Chat notes associated with specific PDF pages
    
    The database is automatically initialized with the required schema on first use.
    """
    
    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the database service.
        
        Args:
            db_path (str): Path to the SQLite database file. Defaults to "data/reading_progress.db"
                          The directory will be created if it doesn't exist.
        """
        self.db_path = db_path
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
        
        Creates two main tables:
        1. reading_progress: Stores the last page read for each PDF
        2. chat_notes: Stores conversation notes linked to specific PDF pages
        
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

            # Create index for faster lookups of notes by PDF and page
            # This significantly improves query performance when retrieving notes for a specific page
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_notes_pdf_page
                ON chat_notes(pdf_filename, page_number)
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
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO reading_progress
                    (pdf_filename, last_page, total_pages, last_updated)
                    VALUES (?, ?, ?, ?)
                """,
                    (pdf_filename, last_page, total_pages, datetime.now()),
                )
                conn.commit()
                logger.info(
                    f"Saved reading progress for {pdf_filename}: page {last_page}"
                )
                return True
        except Exception as e:
            logger.error(f"Error saving reading progress: {e}")
            return False

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
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Use Row factory to get dictionary-like access to columns
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT pdf_filename, last_page, total_pages, last_updated
                    FROM reading_progress
                    WHERE pdf_filename = ?
                """,
                    (pdf_filename,),
                )
                row = cursor.fetchone()

                if row:
                    return {
                        "pdf_filename": row["pdf_filename"],
                        "last_page": row["last_page"],
                        "total_pages": row["total_pages"],
                        "last_updated": row["last_updated"],
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting reading progress: {e}")
            return None

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
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT pdf_filename, last_page, total_pages, last_updated
                    FROM reading_progress
                    ORDER BY last_updated DESC
                """)

                progress = {}
                for row in cursor.fetchall():
                    progress[row["pdf_filename"]] = {
                        "last_page": row["last_page"],
                        "total_pages": row["total_pages"],
                        "last_updated": row["last_updated"],
                    }
                return progress
        except Exception as e:
            logger.error(f"Error getting all reading progress: {e}")
            return {}

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
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO chat_notes (pdf_filename, page_number, title, chat_content, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        pdf_filename,
                        page_number,
                        title,
                        chat_content,
                        datetime.now(),
                        datetime.now(),
                    ),
                )
                conn.commit()
                note_id = cursor.lastrowid
                logger.info(f"Saved chat note for {pdf_filename}, page {page_number}")
                return note_id
        except Exception as e:
            logger.error(f"Error saving chat note: {e}")
            return None

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
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                if page_number is not None:
                    # Get notes for a specific page, ordered by creation time (newest first)
                    cursor = conn.execute(
                        """
                        SELECT id, pdf_filename, page_number, title, chat_content, created_at, updated_at
                        FROM chat_notes
                        WHERE pdf_filename = ? AND page_number = ?
                        ORDER BY created_at DESC
                    """,
                        (pdf_filename, page_number),
                    )
                else:
                    # Get all notes for the PDF, ordered by page number then creation time
                    cursor = conn.execute(
                        """
                        SELECT id, pdf_filename, page_number, title, chat_content, created_at, updated_at
                        FROM chat_notes
                        WHERE pdf_filename = ?
                        ORDER BY page_number, created_at DESC
                    """,
                        (pdf_filename,),
                    )

                notes = []
                for row in cursor.fetchall():
                    notes.append(
                        {
                            "id": row["id"],
                            "pdf_filename": row["pdf_filename"],
                            "page_number": row["page_number"],
                            "title": row["title"],
                            "chat_content": row["chat_content"],
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                        }
                    )
                return notes
        except Exception as e:
            logger.error(f"Error getting chat notes: {e}")
            return []

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
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT id, pdf_filename, page_number, title, chat_content, created_at, updated_at
                    FROM chat_notes
                    WHERE id = ?
                """,
                    (note_id,),
                )
                row = cursor.fetchone()

                if row:
                    return {
                        "id": row["id"],
                        "pdf_filename": row["pdf_filename"],
                        "page_number": row["page_number"],
                        "title": row["title"],
                        "chat_content": row["chat_content"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting chat note: {e}")
            return None

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
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM chat_notes WHERE id = ?", (note_id,))
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Deleted chat note {note_id}")
                return deleted
        except Exception as e:
            logger.error(f"Error deleting chat note: {e}")
            return False

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
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # First query: Get count and latest note date for each PDF
                # This is more efficient than trying to get everything in one complex query
                cursor = conn.execute("""
                    SELECT
                        pdf_filename,
                        COUNT(*) as notes_count,
                        MAX(created_at) as latest_note_date
                    FROM chat_notes
                    GROUP BY pdf_filename
                """)

                notes_info = {}
                for row in cursor.fetchall():
                    # Second query: Get the title of the latest note
                    # We do this separately to avoid complex SQL and ensure accuracy
                    title_cursor = conn.execute(
                        """
                        SELECT title
                        FROM chat_notes
                        WHERE pdf_filename = ? AND created_at = ?
                        LIMIT 1
                    """,
                        (row["pdf_filename"], row["latest_note_date"]),
                    )

                    title_row = title_cursor.fetchone()
                    latest_title = title_row["title"] if title_row else "Untitled Note"

                    notes_info[row["pdf_filename"]] = {
                        "notes_count": row["notes_count"],
                        "latest_note_date": row["latest_note_date"],
                        "latest_note_title": latest_title,
                    }

                logger.info(
                    f"Found notes for {len(notes_info)} PDFs: {list(notes_info.keys())}"
                )
                return notes_info
        except Exception as e:
            logger.error(f"Error getting notes count: {e}")
            return {}


# Global instance
# This creates a singleton instance of the DatabaseService that can be imported
# and used throughout the application. This ensures all parts of the app use
# the same database connection and configuration.
db_service = DatabaseService()

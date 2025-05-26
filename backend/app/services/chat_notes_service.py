"""
Chat Notes Service Module

This module provides specialized database operations for managing chat notes
associated with specific PDF pages. It handles storing conversation notes
that users create while reading PDFs.
"""

import logging
from typing import Any, Dict, List, Optional

from .base_database_service import BaseDatabaseService

# Configure logger for this module
logger = logging.getLogger(__name__)


class ChatNotesService(BaseDatabaseService):
    """
    Service class for managing chat notes using SQLite.

    This class provides database operations for storing and retrieving:
    - Chat notes associated with specific PDF pages
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the chat notes service.

        Args:
            db_path (str): Path to the SQLite database file
        """
        super().__init__(db_path)
        self._init_table()

    def _init_table(self):
        """
        Initialize the chat notes table and indexes.
        """
        with self.get_connection() as conn:
            # Create chat notes table
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

            # Create index for faster lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_notes_pdf_page
                ON chat_notes(pdf_filename, page_number)
            """)
            conn.commit()

    def save_note(
        self, pdf_filename: str, page_number: int, title: str, chat_content: str
    ) -> Optional[int]:
        """
        Save a chat conversation as a note linked to a specific PDF page.

        Args:
            pdf_filename (str): Name of the PDF file this note belongs to
            page_number (int): Page number this note is associated with
            title (str): Title for the note (can be empty)
            chat_content (str): The actual conversation or note content

        Returns:
            Optional[int]: The ID of the newly created note, or None if creation failed
        """
        try:
            query = """
                INSERT INTO chat_notes (pdf_filename, page_number, title, chat_content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            params = (
                pdf_filename,
                page_number,
                title,
                chat_content,
                self.get_current_timestamp(),
                self.get_current_timestamp(),
            )

            note_id = self.execute_insert(query, params)
            if note_id:
                logger.info(f"Saved chat note for {pdf_filename}, page {page_number}")
            return note_id
        except Exception as e:
            logger.error(f"Error saving chat note: {e}")
            return None

    def get_notes_for_pdf(
        self, pdf_filename: str, page_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chat notes for a PDF document, optionally filtered by page number.

        Args:
            pdf_filename (str): Name of the PDF file to get notes for
            page_number (Optional[int]): Specific page number to filter by, or None for all pages

        Returns:
            List[Dict[str, Any]]: List of note dictionaries
        """
        try:
            if page_number is not None:
                query = """
                    SELECT id, pdf_filename, page_number, title, chat_content, created_at, updated_at
                    FROM chat_notes
                    WHERE pdf_filename = ? AND page_number = ?
                    ORDER BY created_at DESC
                """
                params = (pdf_filename, page_number)
            else:
                query = """
                    SELECT id, pdf_filename, page_number, title, chat_content, created_at, updated_at
                    FROM chat_notes
                    WHERE pdf_filename = ?
                    ORDER BY page_number, created_at DESC
                """
                params = (pdf_filename,)

            rows = self.execute_query(query, params, fetch_all=True)

            notes = []
            if rows:
                for row in rows:
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

    def get_note_by_id(self, note_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific chat note by its unique ID.

        Args:
            note_id (int): Unique identifier of the note to retrieve

        Returns:
            Optional[Dict[str, Any]]: Note dictionary with all fields, or None if not found
        """
        try:
            query = """
                SELECT id, pdf_filename, page_number, title, chat_content, created_at, updated_at
                FROM chat_notes
                WHERE id = ?
            """
            row = self.execute_query(query, (note_id,), fetch_one=True)

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

    def delete_note(self, note_id: int) -> bool:
        """
        Delete a specific chat note by its ID.

        Args:
            note_id (int): Unique identifier of the note to delete

        Returns:
            bool: True if a note was deleted, False if no note was found or deletion failed
        """
        try:
            query = "DELETE FROM chat_notes WHERE id = ?"
            deleted = self.execute_update_delete(query, (note_id,))
            if deleted:
                logger.info(f"Deleted chat note {note_id}")
            return deleted
        except Exception as e:
            logger.error(f"Error deleting chat note: {e}")
            return False

    def get_notes_count_by_pdf(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary statistics about notes for all PDF documents.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping PDF filenames to their note statistics
        """
        try:
            # First query: Get count and latest note date for each PDF
            query = """
                SELECT
                    pdf_filename,
                    COUNT(*) as notes_count,
                    MAX(created_at) as latest_note_date
                FROM chat_notes
                GROUP BY pdf_filename
            """
            rows = self.execute_query(query, fetch_all=True)

            notes_info = {}
            if rows:
                for row in rows:
                    # Second query: Get the title of the latest note
                    title_query = """
                        SELECT title
                        FROM chat_notes
                        WHERE pdf_filename = ? AND created_at = ?
                        LIMIT 1
                    """
                    title_row = self.execute_query(
                        title_query,
                        (row["pdf_filename"], row["latest_note_date"]),
                        fetch_one=True,
                    )

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

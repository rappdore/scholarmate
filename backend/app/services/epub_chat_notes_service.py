"""
EPUB Chat Notes Service Module

This module provides specialized database operations for managing chat notes
associated with specific EPUB navigation sections. It handles storing conversation notes
that users create while reading EPUBs with precise navigation context.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .base_database_service import BaseDatabaseService

# Configure logger for this module
logger = logging.getLogger(__name__)


class EPUBChatNotesService(BaseDatabaseService):
    """
    Service class for managing EPUB chat notes using SQLite.
    Completely separate from PDF ChatNotesService.

    This class provides database operations for storing and retrieving:
    - Chat notes associated with specific EPUB navigation sections
    - Chapter-level grouping and retrieval for UI display
    - Navigation context tracking for precise positioning
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the EPUB chat notes service.

        Args:
            db_path (str): Path to the SQLite database file
        """
        super().__init__(db_path)
        self._init_table()

    def _init_table(self):
        """
        Initialize the EPUB chat notes table and indexes.
        """
        with self.get_connection() as conn:
            # Create EPUB chat notes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS epub_chat_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,     -- Unique identifier for each note
                    epub_filename TEXT NOT NULL,              -- Which EPUB this note belongs to
                    nav_id TEXT NOT NULL,                     -- Precise section identifier (e.g., 'section_2_1_3')
                    chapter_id TEXT,                          -- Chapter identifier for grouping/display (e.g., 'chapter_2')
                    chapter_title TEXT,                       -- Human-readable chapter title for UI display
                    title TEXT,                               -- Optional user-defined title for the note
                    chat_content TEXT NOT NULL,               -- The actual conversation/note content
                    context_sections TEXT,                    -- JSON array of sections that provided context
                    scroll_position INTEGER DEFAULT 0,        -- Scroll position within the section when note was created
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for fast lookups by EPUB and navigation
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_chat_notes_epub_nav
                ON epub_chat_notes(epub_filename, nav_id)
            """)

            # Create index for chapter-level grouping
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_chat_notes_epub_chapter
                ON epub_chat_notes(epub_filename, chapter_id)
            """)

            conn.commit()

    def save_note(
        self,
        epub_filename: str,
        nav_id: str,
        chapter_id: str,
        chapter_title: str,
        title: str,
        chat_content: str,
        context_sections: List[str] = None,
        scroll_position: int = 0,
    ) -> Optional[int]:
        """
        Save an EPUB chat conversation as a note linked to a navigation section.

        Args:
            epub_filename (str): Name of the EPUB file this note belongs to
            nav_id (str): Precise navigation section identifier
            chapter_id (str): Chapter identifier for grouping/display
            chapter_title (str): Human-readable chapter title
            title (str): Title for the note (can be empty)
            chat_content (str): The actual conversation or note content
            context_sections (List[str]): List of section IDs that provided context
            scroll_position (int): Scroll position within the section

        Returns:
            Optional[int]: The ID of the newly created note, or None if creation failed
        """
        try:
            # Convert context sections to JSON string
            context_json = json.dumps(context_sections) if context_sections else None

            query = """
                INSERT INTO epub_chat_notes (
                    epub_filename, nav_id, chapter_id, chapter_title, title,
                    chat_content, context_sections, scroll_position, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                epub_filename,
                nav_id,
                chapter_id,
                chapter_title,
                title,
                chat_content,
                context_json,
                scroll_position,
                self.get_current_timestamp(),
                self.get_current_timestamp(),
            )

            note_id = self.execute_insert(query, params)
            if note_id:
                logger.info(
                    f"Saved EPUB chat note for {epub_filename}, nav_id {nav_id}"
                )
            return note_id
        except Exception as e:
            logger.error(f"Error saving EPUB chat note: {e}")
            return None

    def get_notes_for_epub(
        self,
        epub_filename: str,
        nav_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chat notes for an EPUB document, with fine-grained or chapter-level filtering.

        Args:
            epub_filename (str): Name of the EPUB file to get notes for
            nav_id (Optional[str]): Specific navigation section to filter by
            chapter_id (Optional[str]): Specific chapter to filter by

        Returns:
            List[Dict[str, Any]]: List of note dictionaries
        """
        try:
            if nav_id is not None:
                # Get notes for specific navigation section
                query = """
                    SELECT id, epub_filename, nav_id, chapter_id, chapter_title, title,
                           chat_content, context_sections, scroll_position, created_at, updated_at
                    FROM epub_chat_notes
                    WHERE epub_filename = ? AND nav_id = ?
                    ORDER BY created_at DESC
                """
                params = (epub_filename, nav_id)
            elif chapter_id is not None:
                # Get notes for specific chapter
                query = """
                    SELECT id, epub_filename, nav_id, chapter_id, chapter_title, title,
                           chat_content, context_sections, scroll_position, created_at, updated_at
                    FROM epub_chat_notes
                    WHERE epub_filename = ? AND chapter_id = ?
                    ORDER BY created_at DESC
                """
                params = (epub_filename, chapter_id)
            else:
                # Get all notes for EPUB
                query = """
                    SELECT id, epub_filename, nav_id, chapter_id, chapter_title, title,
                           chat_content, context_sections, scroll_position, created_at, updated_at
                    FROM epub_chat_notes
                    WHERE epub_filename = ?
                    ORDER BY chapter_id, created_at DESC
                """
                params = (epub_filename,)

            rows = self.execute_query(query, params, fetch_all=True)

            notes = []
            if rows:
                for row in rows:
                    # Parse context sections JSON
                    context_sections = None
                    if row["context_sections"]:
                        try:
                            context_sections = json.loads(row["context_sections"])
                        except json.JSONDecodeError:
                            context_sections = []

                    notes.append(
                        {
                            "id": row["id"],
                            "epub_filename": row["epub_filename"],
                            "nav_id": row["nav_id"],
                            "chapter_id": row["chapter_id"],
                            "chapter_title": row["chapter_title"],
                            "title": row["title"],
                            "chat_content": row["chat_content"],
                            "context_sections": context_sections,
                            "scroll_position": row["scroll_position"],
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                        }
                    )
            return notes
        except Exception as e:
            logger.error(f"Error getting EPUB chat notes: {e}")
            return []

    def get_notes_grouped_by_chapter(
        self, epub_filename: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get notes grouped by chapter for UI display.

        Args:
            epub_filename (str): Name of the EPUB file to get notes for

        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary mapping chapter IDs to their notes
        """
        try:
            notes = self.get_notes_for_epub(epub_filename)
            grouped_notes = {}

            for note in notes:
                chapter_key = note["chapter_id"] or "unknown"
                if chapter_key not in grouped_notes:
                    grouped_notes[chapter_key] = []
                grouped_notes[chapter_key].append(note)

            return grouped_notes
        except Exception as e:
            logger.error(f"Error grouping EPUB chat notes by chapter: {e}")
            return {}

    def get_note_by_id(self, note_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific EPUB chat note by its unique ID.

        Args:
            note_id (int): Unique identifier of the note to retrieve

        Returns:
            Optional[Dict[str, Any]]: Note dictionary with all fields, or None if not found
        """
        try:
            query = """
                SELECT id, epub_filename, nav_id, chapter_id, chapter_title, title,
                       chat_content, context_sections, scroll_position, created_at, updated_at
                FROM epub_chat_notes
                WHERE id = ?
            """
            row = self.execute_query(query, (note_id,), fetch_one=True)

            if row:
                # Parse context sections JSON
                context_sections = None
                if row["context_sections"]:
                    try:
                        context_sections = json.loads(row["context_sections"])
                    except json.JSONDecodeError:
                        context_sections = []

                return {
                    "id": row["id"],
                    "epub_filename": row["epub_filename"],
                    "nav_id": row["nav_id"],
                    "chapter_id": row["chapter_id"],
                    "chapter_title": row["chapter_title"],
                    "title": row["title"],
                    "chat_content": row["chat_content"],
                    "context_sections": context_sections,
                    "scroll_position": row["scroll_position"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            return None
        except Exception as e:
            logger.error(f"Error getting EPUB chat note: {e}")
            return None

    def delete_note(self, note_id: int) -> bool:
        """
        Delete a specific EPUB chat note by its ID.

        Args:
            note_id (int): Unique identifier of the note to delete

        Returns:
            bool: True if a note was deleted, False if no note was found or deletion failed
        """
        try:
            query = "DELETE FROM epub_chat_notes WHERE id = ?"
            deleted = self.execute_update_delete(query, (note_id,))
            if deleted:
                logger.info(f"Deleted EPUB chat note {note_id}")
            return deleted
        except Exception as e:
            logger.error(f"Error deleting EPUB chat note: {e}")
            return False

    def get_notes_count_by_epub(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary statistics about notes for all EPUB documents.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping EPUB filenames to their note statistics
        """
        try:
            # First query: Get count and latest note date for each EPUB
            query = """
                SELECT
                    epub_filename,
                    COUNT(*) as notes_count,
                    MAX(created_at) as latest_note_date
                FROM epub_chat_notes
                GROUP BY epub_filename
            """
            rows = self.execute_query(query, fetch_all=True)

            notes_info = {}
            if rows:
                for row in rows:
                    # Second query: Get the title of the latest note
                    title_query = """
                        SELECT title
                        FROM epub_chat_notes
                        WHERE epub_filename = ? AND created_at = ?
                        LIMIT 1
                    """
                    title_row = self.execute_query(
                        title_query,
                        (row["epub_filename"], row["latest_note_date"]),
                        fetch_one=True,
                    )

                    latest_title = title_row["title"] if title_row else "Untitled Note"

                    notes_info[row["epub_filename"]] = {
                        "notes_count": row["notes_count"],
                        "latest_note_date": row["latest_note_date"],
                        "latest_note_title": latest_title,
                    }

            logger.info(
                f"Found EPUB notes for {len(notes_info)} EPUBs: {list(notes_info.keys())}"
            )
            return notes_info
        except Exception as e:
            logger.error(f"Error getting EPUB notes count: {e}")
            return {}

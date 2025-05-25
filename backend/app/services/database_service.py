import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, db_path: str = "data/reading_progress.db"):
        self.db_path = db_path
        self._ensure_data_dir()
        self._init_database()

    def _ensure_data_dir(self):
        """Ensure the data directory exists"""
        data_dir = os.path.dirname(self.db_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def _init_database(self):
        """Initialize database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reading_progress (
                    pdf_filename TEXT PRIMARY KEY,
                    last_page INTEGER NOT NULL,
                    total_pages INTEGER,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pdf_filename TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    title TEXT,
                    chat_content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for faster lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_notes_pdf_page
                ON chat_notes(pdf_filename, page_number)
            """)

            conn.commit()

    def save_reading_progress(
        self, pdf_filename: str, last_page: int, total_pages: int
    ) -> bool:
        """Save or update reading progress for a PDF"""
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
        """Get reading progress for a PDF"""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
        """Get reading progress for all PDFs"""
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
        """Save a chat conversation as a note"""
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
        """Get chat notes for a PDF, optionally filtered by page"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                if page_number is not None:
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
        """Get a specific chat note by ID"""
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
        """Delete a chat note"""
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
        """Get notes count and latest note info for all PDFs"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                # Simplified query - get count and latest note separately
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
                    # Get the latest note title in a separate query
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
db_service = DatabaseService()

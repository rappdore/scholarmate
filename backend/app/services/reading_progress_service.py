"""
Reading Progress Service Module

This module provides specialized database operations for managing PDF reading progress.
It handles tracking the last page read and total pages for each PDF document.
"""

import logging
from typing import Any, Dict, Optional

from .base_database_service import BaseDatabaseService

# Configure logger for this module
logger = logging.getLogger(__name__)


class ReadingProgressService(BaseDatabaseService):
    """
    Service class for managing PDF reading progress using SQLite.

    This class provides database operations for storing and retrieving:
    - Reading progress for PDF documents (last page read, total pages)
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the reading progress service.

        Args:
            db_path (str): Path to the SQLite database file
        """
        super().__init__(db_path)
        self._init_table()

    def _init_table(self):
        """
        Initialize the reading progress table and indexes.
        """
        with self.get_connection() as conn:
            # Create reading progress table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reading_progress (
                    pdf_filename TEXT PRIMARY KEY,        -- Unique identifier for each PDF
                    last_page INTEGER NOT NULL,           -- Last page the user was reading
                    total_pages INTEGER,                   -- Total number of pages in the PDF
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- When this record was last modified
                )
            """)
            conn.commit()

    def save_progress(
        self, pdf_filename: str, last_page: int, total_pages: int
    ) -> bool:
        """
        Save or update reading progress for a PDF document.

        Args:
            pdf_filename (str): Name of the PDF file (used as unique identifier)
            last_page (int): The page number the user was last reading
            total_pages (int): Total number of pages in the PDF document

        Returns:
            bool: True if the operation was successful, False otherwise
        """
        try:
            query = """
                INSERT OR REPLACE INTO reading_progress
                (pdf_filename, last_page, total_pages, last_updated)
                VALUES (?, ?, ?, ?)
            """
            params = (
                pdf_filename,
                last_page,
                total_pages,
                self.get_current_timestamp(),
            )

            result = self.execute_insert(query, params)
            if result is not None:
                logger.info(
                    f"Saved reading progress for {pdf_filename}: page {last_page}"
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error saving reading progress: {e}")
            return False

    def get_progress(self, pdf_filename: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve reading progress for a specific PDF document.

        Args:
            pdf_filename (str): Name of the PDF file to get progress for

        Returns:
            Optional[Dict[str, Any]]: Dictionary containing progress information or None
        """
        try:
            query = """
                SELECT pdf_filename, last_page, total_pages, last_updated
                FROM reading_progress
                WHERE pdf_filename = ?
            """
            row = self.execute_query(query, (pdf_filename,), fetch_one=True)

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

    def get_all_progress(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve reading progress for all PDF documents.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping PDF filenames to their progress info
        """
        try:
            query = """
                SELECT pdf_filename, last_page, total_pages, last_updated
                FROM reading_progress
                ORDER BY last_updated DESC
            """
            rows = self.execute_query(query, fetch_all=True)

            progress = {}
            if rows:
                for row in rows:
                    progress[row["pdf_filename"]] = {
                        "last_page": row["last_page"],
                        "total_pages": row["total_pages"],
                        "last_updated": row["last_updated"],
                    }
            return progress
        except Exception as e:
            logger.error(f"Error getting all reading progress: {e}")
            return {}

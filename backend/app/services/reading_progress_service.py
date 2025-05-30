"""
Reading Progress Service Module

This module provides specialized database operations for managing PDF reading progress.
It handles tracking the last page read and total pages for each PDF document.
"""

import logging
from typing import Any, Dict, List, Optional

from .base_database_service import BaseDatabaseService

# Configure logger for this module
logger = logging.getLogger(__name__)


class ReadingProgressService(BaseDatabaseService):
    """
    Service class for managing PDF reading progress using SQLite.

    This class provides database operations for storing and retrieving:
    - Reading progress for PDF documents (last page read, total pages)
    - Book status tracking (new, reading, finished)
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
                SELECT pdf_filename, last_page, total_pages, last_updated,
                       status, status_updated_at, manually_set
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
                    "status": row.get("status", "new"),
                    "status_updated_at": row.get("status_updated_at"),
                    "manually_set": bool(row.get("manually_set", False)),
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
                SELECT pdf_filename, last_page, total_pages, last_updated,
                       status, status_updated_at, manually_set
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
                        "status": row.get("status", "new"),
                        "status_updated_at": row.get("status_updated_at"),
                        "manually_set": bool(row.get("manually_set", False)),
                    }
            return progress
        except Exception as e:
            logger.error(f"Error getting all reading progress: {e}")
            return {}

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
        try:
            # Validate status
            valid_statuses = ["new", "reading", "finished"]
            if status not in valid_statuses:
                logger.error(
                    f"Invalid status '{status}'. Must be one of: {valid_statuses}"
                )
                return False

            # Check if record exists, create if not
            existing = self.get_progress(pdf_filename)
            if not existing:
                # Create a new record with default values if it doesn't exist
                query = """
                    INSERT INTO reading_progress
                    (pdf_filename, last_page, total_pages, last_updated, status, status_updated_at, manually_set)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    pdf_filename,
                    0,  # Default last_page
                    0,  # Default total_pages (will be updated when PDF is opened)
                    self.get_current_timestamp(),
                    status,
                    self.get_current_timestamp(),
                    manual,
                )
                result = self.execute_insert(query, params)
            else:
                # Update existing record
                query = """
                    UPDATE reading_progress
                    SET status = ?,
                        status_updated_at = ?,
                        manually_set = ?
                    WHERE pdf_filename = ?
                """
                params = (status, self.get_current_timestamp(), manual, pdf_filename)
                result = self.execute_update_delete(query, params)

            if result:
                logger.info(
                    f"Updated status for {pdf_filename} to '{status}' (manual: {manual})"
                )
                return True
            return False

        except Exception as e:
            logger.error(f"Error updating book status: {e}")
            return False

    def get_books_by_status(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all books filtered by status.

        Args:
            status (Optional[str]): Filter by specific status ('new', 'reading', 'finished').
                                   If None, returns all books.

        Returns:
            List[Dict[str, Any]]: List of books with their progress and status information
        """
        try:
            if status is None:
                # Return all books
                query = """
                    SELECT pdf_filename, last_page, total_pages, last_updated,
                           status, status_updated_at, manually_set
                    FROM reading_progress
                    ORDER BY status_updated_at DESC, last_updated DESC
                """
                params = ()
            else:
                # Validate status
                valid_statuses = ["new", "reading", "finished"]
                if status not in valid_statuses:
                    logger.error(
                        f"Invalid status '{status}'. Must be one of: {valid_statuses}"
                    )
                    return []

                # Filter by status
                query = """
                    SELECT pdf_filename, last_page, total_pages, last_updated,
                           status, status_updated_at, manually_set
                    FROM reading_progress
                    WHERE status = ?
                    ORDER BY status_updated_at DESC, last_updated DESC
                """
                params = (status,)

            rows = self.execute_query(query, params, fetch_all=True)

            books = []
            if rows:
                for row in rows:
                    # Calculate progress percentage
                    progress_percentage = 0
                    if row["total_pages"] and row["total_pages"] > 0:
                        progress_percentage = round(
                            (row["last_page"] / row["total_pages"]) * 100, 1
                        )

                    book_data = {
                        "pdf_filename": row["pdf_filename"],
                        "last_page": row["last_page"],
                        "total_pages": row["total_pages"],
                        "progress_percentage": progress_percentage,
                        "last_updated": row["last_updated"],
                        "status": row.get("status", "new"),
                        "status_updated_at": row.get("status_updated_at"),
                        "manually_set": bool(row.get("manually_set", False)),
                    }
                    books.append(book_data)

            logger.info(
                f"Retrieved {len(books)} books"
                + (f" with status '{status}'" if status else "")
            )
            return books

        except Exception as e:
            logger.error(f"Error getting books by status: {e}")
            return []

    def get_status_counts(self) -> Dict[str, int]:
        """
        Get count of books for each status.

        Returns:
            Dict[str, int]: Dictionary with status counts
        """
        try:
            query = """
                SELECT status, COUNT(*) as count
                FROM reading_progress
                GROUP BY status
            """
            rows = self.execute_query(query, fetch_all=True)

            # Initialize with all statuses
            counts = {"new": 0, "reading": 0, "finished": 0}

            if rows:
                for row in rows:
                    status = row.get("status", "new")
                    if status in counts:
                        counts[status] = row["count"]

            # Calculate total
            counts["all"] = sum(counts.values())

            return counts

        except Exception as e:
            logger.error(f"Error getting status counts: {e}")
            return {"all": 0, "new": 0, "reading": 0, "finished": 0}

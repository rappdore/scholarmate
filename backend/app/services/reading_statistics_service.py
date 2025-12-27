"""
Reading Statistics Service Module

This module provides specialized database operations for managing reading session statistics.
It handles tracking session data including pages read and average reading time per page.
"""

import logging
from typing import Optional

from .base_database_service import BaseDatabaseService
from .pdf_documents_service import PDFDocumentsService
from .reading_progress_service import ReadingProgressService

# Configure logger for this module
logger = logging.getLogger(__name__)


class ReadingStatisticsService(BaseDatabaseService):
    """
    Service class for managing reading session statistics using SQLite.

    This class provides database operations for storing and updating reading sessions:
    - Session creation and updates (via upsert)
    - Tracking pages read per session
    - Tracking average time per page
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the reading statistics service.

        Args:
            db_path (str): Path to the SQLite database file
        """
        super().__init__(db_path)
        self._init_table()
        self.progress_service = ReadingProgressService(db_path)
        # Phase 3a: Initialize PDF documents service for pdf_id lookups
        self._pdf_docs_service = PDFDocumentsService(db_path)

    def _init_table(self):
        """
        Initialize the reading_sessions table and indexes.

        Creates the table if it doesn't exist and sets up indexes for efficient queries.
        Uses CREATE IF NOT EXISTS for idempotency.
        """
        with self.get_connection() as conn:
            # Create reading sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reading_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    pdf_filename TEXT NOT NULL,
                    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    pages_read INTEGER DEFAULT 0,
                    average_time_per_page REAL DEFAULT 0.0
                )
            """)

            # Create indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reading_sessions_session_id
                ON reading_sessions(session_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reading_sessions_pdf_filename
                ON reading_sessions(pdf_filename)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reading_sessions_date
                ON reading_sessions(session_start)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reading_sessions_last_updated
                ON reading_sessions(last_updated)
            """)

            # Phase 3a: Add pdf_id column if it doesn't exist (backward compatible migration)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(reading_sessions)")
            columns = [column[1] for column in cursor.fetchall()]

            if "pdf_id" not in columns:
                logger.info("Adding pdf_id column to reading_sessions table...")
                conn.execute("ALTER TABLE reading_sessions ADD COLUMN pdf_id INTEGER")
                logger.info("pdf_id column added successfully")

            # Create index on pdf_id if it doesn't exist
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reading_sessions_pdf_id
                ON reading_sessions(pdf_id)
            """)

            # =============================================================================
            # ONE-TIME BACKFILL: Populate pdf_id for existing reading_sessions rows
            #
            # Unlike reading_progress which gets updated on access, reading_sessions only
            # receives INSERTs, so existing rows would never get their pdf_id populated.
            # This backfill runs once on startup and updates all rows where pdf_id IS NULL.
            #
            # TODO: This backfill can be removed after all environments have been updated
            #       and no NULL pdf_id values remain. Safe to remove after ~March 2026.
            # =============================================================================
            cursor.execute("""
                UPDATE reading_sessions
                SET pdf_id = (
                    SELECT id FROM pdf_documents
                    WHERE pdf_documents.filename = reading_sessions.pdf_filename
                )
                WHERE pdf_id IS NULL
                AND EXISTS (
                    SELECT 1 FROM pdf_documents
                    WHERE pdf_documents.filename = reading_sessions.pdf_filename
                )
            """)
            backfilled = cursor.rowcount
            if backfilled > 0:
                logger.info(
                    f"Backfilled pdf_id for {backfilled} existing reading_sessions rows"
                )

            conn.commit()

    def _get_pdf_id(self, pdf_filename: str) -> Optional[int]:
        """
        Get the pdf_id for a given PDF filename.

        Phase 3a: Helper method for looking up pdf_id from pdf_documents table.

        Args:
            pdf_filename (str): Name of the PDF file

        Returns:
            Optional[int]: The pdf_id if found, None otherwise
        """
        try:
            pdf_doc = self._pdf_docs_service.get_by_filename(pdf_filename)
            if pdf_doc:
                return pdf_doc.get("id")
            return None
        except Exception as e:
            logger.warning(f"Could not look up pdf_id for {pdf_filename}: {e}")
            return None

    def upsert_session(
        self,
        session_id: str,
        pdf_filename: str,
        pages_read: int,
        average_time_per_page: float,
    ) -> bool:
        """
        Insert or update a reading session.

        If the session_id doesn't exist, creates a new session record.
        If the session_id already exists, updates the existing record.

        Args:
            session_id (str): Unique session identifier (UUID from frontend)
            pdf_filename (str): Name of the PDF file being read
            pages_read (int): Total number of pages read in this session
            average_time_per_page (float): Average time per page in seconds

        Returns:
            bool: True if the operation was successful, False otherwise

        Raises:
            ValueError: If the PDF doesn't exist in reading_progress table
        """
        try:
            # Check if the PDF exists in reading_progress table
            progress = self.progress_service.get_progress(pdf_filename)
            if not progress:
                raise ValueError(
                    f"PDF '{pdf_filename}' does not exist in reading_progress table. "
                    "Statistics updates are only allowed for tracked PDFs."
                )

            # Check if the book status is "finished"
            if progress.get("status") == "finished":
                logger.info(
                    f"Skipping statistics update for finished book: {pdf_filename} "
                    f"(session: {session_id})"
                )
                return True

            # Phase 3a: Look up pdf_id for auto-population
            pdf_id = self._get_pdf_id(pdf_filename)

            query = """
                INSERT INTO reading_sessions
                    (session_id, pdf_filename, pdf_id, pages_read, average_time_per_page, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    pdf_filename = excluded.pdf_filename,
                    pdf_id = excluded.pdf_id,
                    pages_read = excluded.pages_read,
                    average_time_per_page = excluded.average_time_per_page,
                    last_updated = excluded.last_updated
            """

            params = (
                session_id,
                pdf_filename,
                pdf_id,
                pages_read,
                average_time_per_page,
                self.get_current_timestamp(),
            )

            with self.get_connection() as conn:
                conn.execute(query, params)
                conn.commit()
                logger.info(
                    f"Upserted session {session_id} for {pdf_filename} (pdf_id={pdf_id}): "
                    f"{pages_read} pages, {average_time_per_page:.2f}s avg"
                )
                return True

        except ValueError:
            # Re-raise ValueError for PDF not existing
            raise
        except Exception as e:
            logger.error(f"Error upserting session {session_id}: {e}")
            return False

    def get_sessions_by_pdf(
        self, pdf_filename: str, limit: int = None, offset: int = None
    ) -> dict:
        """
        Get all reading sessions for a specific PDF.

        Args:
            pdf_filename (str): Name of the PDF file
            limit (int, optional): Maximum number of sessions to return
            offset (int, optional): Number of sessions to skip (for pagination)

        Returns:
            dict: Dictionary containing:
                - pdf_filename (str): The PDF filename
                - total_sessions (int): Total number of sessions for this PDF
                - sessions (list): List of session dictionaries, each containing:
                    - session_id (str)
                    - pdf_id (int or None): The PDF document ID (Phase 3a)
                    - session_start (str): ISO timestamp
                    - last_updated (str): ISO timestamp
                    - pages_read (int)
                    - average_time_per_page (float)
        """
        try:
            with self.get_connection() as conn:
                # Get total count
                count_query = """
                    SELECT COUNT(*) as total_sessions
                    FROM reading_sessions
                    WHERE pdf_filename = ?
                """
                count_result = conn.execute(count_query, (pdf_filename,)).fetchone()
                total_sessions = count_result[0] if count_result else 0

                # Get sessions (ordered by most recent first)
                # Phase 3a: Include pdf_id in query
                sessions_query = """
                    SELECT session_id, pdf_id, session_start, last_updated, pages_read, average_time_per_page
                    FROM reading_sessions
                    WHERE pdf_filename = ?
                    ORDER BY session_start DESC
                """

                params = [pdf_filename]

                # Add limit/offset if provided
                if limit is not None:
                    sessions_query += " LIMIT ?"
                    params.append(limit)

                if offset is not None:
                    sessions_query += " OFFSET ?"
                    params.append(offset)

                sessions_result = conn.execute(sessions_query, params).fetchall()

                # Convert to list of dictionaries with ISO 8601 formatted timestamps
                # Phase 3a: Include pdf_id in response
                sessions = [
                    {
                        "session_id": row[0],
                        "pdf_id": row[1],
                        "session_start": self.format_timestamp_iso(row[2]),
                        "last_updated": self.format_timestamp_iso(row[3]),
                        "pages_read": row[4],
                        "average_time_per_page": row[5],
                    }
                    for row in sessions_result
                ]

                logger.info(
                    f"Retrieved {len(sessions)} sessions for {pdf_filename} "
                    f"(total: {total_sessions})"
                )

                return {
                    "pdf_filename": pdf_filename,
                    "total_sessions": total_sessions,
                    "sessions": sessions,
                }

        except Exception as e:
            logger.error(f"Error retrieving sessions for {pdf_filename}: {e}")
            return {
                "pdf_filename": pdf_filename,
                "total_sessions": 0,
                "sessions": [],
            }

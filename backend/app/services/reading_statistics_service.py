"""
Reading Statistics Service Module

This module provides specialized database operations for managing reading session statistics.
It handles tracking session data including pages read and average reading time per page.
"""

import logging

from .base_database_service import BaseDatabaseService

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

            conn.commit()

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
        """
        try:
            query = """
                INSERT INTO reading_sessions
                    (session_id, pdf_filename, pages_read, average_time_per_page, last_updated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    pdf_filename = excluded.pdf_filename,
                    pages_read = excluded.pages_read,
                    average_time_per_page = excluded.average_time_per_page,
                    last_updated = excluded.last_updated
            """

            params = (
                session_id,
                pdf_filename,
                pages_read,
                average_time_per_page,
                self.get_current_timestamp(),
            )

            with self.get_connection() as conn:
                conn.execute(query, params)
                conn.commit()
                logger.info(
                    f"Upserted session {session_id} for {pdf_filename}: "
                    f"{pages_read} pages, {average_time_per_page:.2f}s avg"
                )
                return True

        except Exception as e:
            logger.error(f"Error upserting session {session_id}: {e}")
            return False

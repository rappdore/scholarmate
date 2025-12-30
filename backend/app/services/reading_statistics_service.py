"""
Reading Statistics Service Module

This module provides specialized database operations for managing reading session statistics.
It handles tracking session data including pages read and average reading time per page.
"""

import logging

from .base_database_service import BaseDatabaseService
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
                    pdf_id INTEGER NOT NULL,
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
                CREATE INDEX IF NOT EXISTS idx_reading_sessions_pdf_id
                ON reading_sessions(pdf_id)
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
        pdf_id: int,
        pages_read: int,
        average_time_per_page: float,
    ) -> bool:
        """
        Insert or update a reading session.

        Args:
            session_id (str): Unique session identifier (UUID from frontend)
            pdf_id (int): ID of the PDF document being read
            pages_read (int): Total number of pages read in this session
            average_time_per_page (float): Average time per page in seconds

        Returns:
            bool: True if the operation was successful, False otherwise

        Raises:
            ValueError: If the PDF doesn't exist in reading_progress table
        """
        try:
            # Check if the PDF exists in reading_progress table
            progress = self.progress_service.get_progress_by_pdf_id(pdf_id)
            if not progress:
                raise ValueError(
                    f"PDF with id={pdf_id} does not exist in reading_progress table. "
                    "Statistics updates are only allowed for tracked PDFs."
                )

            # Check if the book status is "finished"
            if progress.status == "finished":
                logger.info(
                    f"Skipping statistics update for finished book: pdf_id={pdf_id} "
                    f"(session: {session_id})"
                )
                return True

            query = """
                INSERT INTO reading_sessions
                    (session_id, pdf_id, pages_read, average_time_per_page, last_updated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    pdf_id = excluded.pdf_id,
                    pages_read = excluded.pages_read,
                    average_time_per_page = excluded.average_time_per_page,
                    last_updated = excluded.last_updated
            """

            params = (
                session_id,
                pdf_id,
                pages_read,
                average_time_per_page,
                self.get_current_timestamp(),
            )

            with self.get_connection() as conn:
                conn.execute(query, params)
                conn.commit()
                logger.info(
                    f"Upserted session {session_id} for pdf_id={pdf_id}: "
                    f"{pages_read} pages, {average_time_per_page:.2f}s avg"
                )
                return True

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error upserting session {session_id}: {e}")
            return False

    def get_sessions_by_pdf_id(
        self, pdf_id: int, limit: int = None, offset: int = None
    ) -> dict:
        """
        Get all reading sessions for a specific PDF by ID.

        Args:
            pdf_id (int): ID of the PDF document
            limit (int, optional): Maximum number of sessions to return
            offset (int, optional): Number of sessions to skip (for pagination)

        Returns:
            dict: Dictionary containing:
                - pdf_id (int): The PDF document ID
                - total_sessions (int): Total number of sessions for this PDF
                - sessions (list): List of session dictionaries
        """
        try:
            with self.get_connection() as conn:
                # Get total count
                count_query = """
                    SELECT COUNT(*) as total_sessions
                    FROM reading_sessions
                    WHERE pdf_id = ?
                """
                count_result = conn.execute(count_query, (pdf_id,)).fetchone()
                total_sessions = count_result[0] if count_result else 0

                # Get sessions (ordered by most recent first)
                sessions_query = """
                    SELECT session_id, session_start, last_updated, pages_read, average_time_per_page
                    FROM reading_sessions
                    WHERE pdf_id = ?
                    ORDER BY session_start DESC
                """

                params = [pdf_id]

                if limit is not None:
                    sessions_query += " LIMIT ?"
                    params.append(limit)

                if offset is not None:
                    sessions_query += " OFFSET ?"
                    params.append(offset)

                sessions_result = conn.execute(sessions_query, params).fetchall()

                sessions = [
                    {
                        "session_id": row[0],
                        "session_start": self.format_timestamp_iso(row[1]),
                        "last_updated": self.format_timestamp_iso(row[2]),
                        "pages_read": row[3],
                        "average_time_per_page": row[4],
                    }
                    for row in sessions_result
                ]

                logger.info(
                    f"Retrieved {len(sessions)} sessions for pdf_id={pdf_id} "
                    f"(total: {total_sessions})"
                )

                return {
                    "pdf_id": pdf_id,
                    "total_sessions": total_sessions,
                    "sessions": sessions,
                }

        except Exception as e:
            logger.error(f"Error retrieving sessions for pdf_id={pdf_id}: {e}")
            return {
                "pdf_id": pdf_id,
                "total_sessions": 0,
                "sessions": [],
            }

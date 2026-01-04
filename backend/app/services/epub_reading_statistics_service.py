"""
EPUB Reading Statistics Service Module

This module provides specialized database operations for managing EPUB reading session statistics.
It handles tracking session data including words read and time spent per session.
"""

import logging

from .base_database_service import BaseDatabaseService
from .epub_progress_service import EPUBProgressService

logger = logging.getLogger(__name__)


class EPUBReadingStatisticsService(BaseDatabaseService):
    """
    Service class for managing EPUB reading session statistics using SQLite.

    This class provides database operations for storing and updating reading sessions:
    - Session creation and updates (via upsert)
    - Tracking words read per session
    - Tracking time spent per session
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the EPUB reading statistics service.

        Args:
            db_path (str): Path to the SQLite database file
        """
        super().__init__(db_path)
        self._init_table()
        self.progress_service = EPUBProgressService(db_path)

    def _init_table(self):
        """
        Initialize the epub_reading_sessions table and indexes.

        Creates the table if it doesn't exist and sets up indexes for efficient queries.
        Uses CREATE IF NOT EXISTS for idempotency.
        """
        with self.get_connection() as conn:
            # Create EPUB reading sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS epub_reading_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    epub_id INTEGER NOT NULL,
                    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    words_read INTEGER DEFAULT 0,
                    time_spent_seconds REAL DEFAULT 0.0
                )
            """)

            # Create indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_sessions_session_id
                ON epub_reading_sessions(session_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_sessions_epub_id
                ON epub_reading_sessions(epub_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_sessions_date
                ON epub_reading_sessions(session_start)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_sessions_last_updated
                ON epub_reading_sessions(last_updated)
            """)

            conn.commit()

    def upsert_session(
        self,
        session_id: str,
        epub_id: int,
        words_read: int,
        time_spent_seconds: float,
    ) -> bool:
        """
        Insert or update a reading session.

        Args:
            session_id (str): Unique session identifier (UUID from frontend)
            epub_id (int): ID of the EPUB document being read
            words_read (int): Total number of words read in this session
            time_spent_seconds (float): Time spent reading in seconds

        Returns:
            bool: True if the operation was successful, False otherwise

        Raises:
            ValueError: If the EPUB doesn't exist in epub_reading_progress table
        """
        logger.info(
            f"[SESSION_UPDATE] Received: session_id={session_id[:8]}..., "
            f"epub_id={epub_id}, words_read={words_read}, "
            f"time_spent_seconds={time_spent_seconds:.2f}"
        )

        try:
            # Check if the EPUB exists and get its status
            progress = self._get_progress_by_epub_id(epub_id)
            if not progress:
                logger.error(f"[SESSION_UPDATE] EPUB not found: epub_id={epub_id}")
                raise ValueError(
                    f"EPUB with id={epub_id} does not exist in epub_reading_progress table. "
                    "Statistics updates are only allowed for tracked EPUBs."
                )

            logger.info(
                f"[SESSION_UPDATE] EPUB status: {progress.get('status')}, "
                f"filename: {progress.get('epub_filename')}"
            )

            # Check if the book status is "finished"
            if progress.get("status") == "finished":
                logger.info(
                    f"[SESSION_UPDATE] Skipping - book is finished: epub_id={epub_id}"
                )
                return True

            # Check if session already exists to log insert vs update
            with self.get_connection() as conn:
                existing = conn.execute(
                    "SELECT words_read, time_spent_seconds FROM epub_reading_sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()

                if existing:
                    logger.info(
                        f"[SESSION_UPDATE] Updating existing session: "
                        f"old_words={existing[0]}, new_words={words_read}, "
                        f"old_time={existing[1]:.2f}s, new_time={time_spent_seconds:.2f}s"
                    )
                else:
                    logger.info(
                        f"[SESSION_UPDATE] Creating new session: "
                        f"words={words_read}, time={time_spent_seconds:.2f}s"
                    )

            query = """
                INSERT INTO epub_reading_sessions
                    (session_id, epub_id, words_read, time_spent_seconds, last_updated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    epub_id = excluded.epub_id,
                    words_read = excluded.words_read,
                    time_spent_seconds = excluded.time_spent_seconds,
                    last_updated = excluded.last_updated
            """

            params = (
                session_id,
                epub_id,
                words_read,
                time_spent_seconds,
                self.get_current_timestamp(),
            )

            with self.get_connection() as conn:
                conn.execute(query, params)
                conn.commit()
                logger.info(
                    f"[SESSION_UPDATE] Success: session_id={session_id[:8]}..., "
                    f"epub_id={epub_id}, words={words_read}, time={time_spent_seconds:.2f}s"
                )
                return True

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"[SESSION_UPDATE] Error: session_id={session_id[:8]}..., "
                f"epub_id={epub_id}, error={e}"
            )
            return False

    def _get_progress_by_epub_id(self, epub_id: int) -> dict | None:
        """
        Get EPUB progress record by epub_id.

        Args:
            epub_id (int): ID of the EPUB document

        Returns:
            dict | None: Progress record or None if not found
        """
        try:
            query = """
                SELECT epub_filename, status, manually_set
                FROM epub_reading_progress
                WHERE epub_id = ?
            """
            with self.get_connection() as conn:
                row = conn.execute(query, (epub_id,)).fetchone()
                if row:
                    return {
                        "epub_filename": row[0],
                        "status": row[1],
                        "manually_set": bool(row[2]) if row[2] is not None else False,
                    }
            return None
        except Exception as e:
            logger.error(f"Error getting EPUB progress by id {epub_id}: {e}")
            return None

    def get_sessions_by_epub_id(
        self, epub_id: int, limit: int | None = None, offset: int | None = None
    ) -> dict:
        """
        Get all reading sessions for a specific EPUB by ID.

        Args:
            epub_id (int): ID of the EPUB document
            limit (int, optional): Maximum number of sessions to return
            offset (int, optional): Number of sessions to skip (for pagination)

        Returns:
            dict: Dictionary containing:
                - epub_id (int): The EPUB document ID
                - total_sessions (int): Total number of sessions for this EPUB
                - sessions (list): List of session dictionaries
        """
        try:
            with self.get_connection() as conn:
                # Get total count
                count_query = """
                    SELECT COUNT(*) as total_sessions
                    FROM epub_reading_sessions
                    WHERE epub_id = ?
                """
                count_result = conn.execute(count_query, (epub_id,)).fetchone()
                total_sessions = count_result[0] if count_result else 0

                # Get sessions (ordered by most recent first)
                sessions_query = """
                    SELECT session_id, session_start, last_updated, words_read, time_spent_seconds
                    FROM epub_reading_sessions
                    WHERE epub_id = ?
                    ORDER BY session_start DESC
                """

                params: list = [epub_id]

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
                        "words_read": row[3],
                        "time_spent_seconds": row[4],
                    }
                    for row in sessions_result
                ]

                logger.info(
                    f"Retrieved {len(sessions)} sessions for epub_id={epub_id} "
                    f"(total: {total_sessions})"
                )

                return {
                    "epub_id": epub_id,
                    "total_sessions": total_sessions,
                    "sessions": sessions,
                }

        except Exception as e:
            logger.error(f"Error retrieving sessions for epub_id={epub_id}: {e}")
            return {
                "epub_id": epub_id,
                "total_sessions": 0,
                "sessions": [],
            }

    def delete_sessions_by_epub_id(self, epub_id: int) -> bool:
        """
        Delete all reading sessions for a specific EPUB.

        Args:
            epub_id (int): ID of the EPUB document

        Returns:
            bool: True if sessions were deleted, False otherwise
        """
        try:
            query = "DELETE FROM epub_reading_sessions WHERE epub_id = ?"
            result = self.execute_update_delete(query, (epub_id,))
            if result:
                logger.info(f"Deleted all sessions for epub_id={epub_id}")
            return result
        except Exception as e:
            logger.error(f"Error deleting sessions for epub_id={epub_id}: {e}")
            return False

"""
Sessions Service - unified reading-session storage (A-1).

One ``document_sessions`` table keyed by document_id replaces the former
``reading_sessions`` (PDF) and ``epub_reading_sessions`` twins. Both stored
only counters — no document positions — so storage unifies cleanly:
``units_read`` is pages for PDFs and words for EPUBs, and the PDF wire
field ``average_time_per_page`` is derived (time_spent_seconds /
units_read) instead of stored.
"""

import logging

from app.models.documents import BookStatus, ReadingSessionRecord, SessionsPage

from .base_database_service import BaseDatabaseService
from .progress_service import ProgressService

logger = logging.getLogger(__name__)


class SessionsService(BaseDatabaseService):
    """Reading-session tracking for every document format."""

    def __init__(self, db_path: str = "data/reading_progress.db"):
        super().__init__(db_path)
        self._init_table()
        self.progress_service = ProgressService(db_path)

    def _init_table(self):
        """
        The CREATE TABLE statement is the single source of truth for this
        table's schema; a fresh database gets the complete schema from it.
        """
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    document_id INTEGER NOT NULL,
                    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    units_read INTEGER DEFAULT 0,       -- pages (pdf) / words (epub)
                    time_spent_seconds REAL DEFAULT 0.0
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_sessions_document_id
                ON document_sessions(document_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_sessions_start
                ON document_sessions(session_start)
            """)

            conn.commit()

    def upsert_session(
        self,
        session_id: str,
        document_id: int,
        units_read: int,
        time_spent_seconds: float,
    ) -> bool:
        """
        Insert or update a reading session.

        Raises:
            ValueError: If the document has no progress record (statistics
                updates are only allowed for tracked documents).
        """
        try:
            progress = self.progress_service.get_progress(document_id)
            if not progress:
                raise ValueError(
                    f"Document with id={document_id} does not exist in the "
                    "progress table. Statistics updates are only allowed for "
                    "tracked documents."
                )

            if progress.status == BookStatus.FINISHED:
                logger.info(
                    "Skipping statistics update for finished book: "
                    "document_id=%s (session: %s)",
                    document_id,
                    session_id,
                )
                return True

            query = """
                INSERT INTO document_sessions
                    (session_id, document_id, units_read, time_spent_seconds, last_updated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    document_id = excluded.document_id,
                    units_read = excluded.units_read,
                    time_spent_seconds = excluded.time_spent_seconds,
                    last_updated = excluded.last_updated
            """
            params = (
                session_id,
                document_id,
                units_read,
                time_spent_seconds,
                self.get_current_timestamp(),
            )

            with self.get_connection() as conn:
                conn.execute(query, params)
                conn.commit()
                logger.info(
                    "Upserted session %s for document_id=%s: %s units, %.2fs",
                    session_id,
                    document_id,
                    units_read,
                    time_spent_seconds,
                )
                return True

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error upserting session {session_id}: {e}")
            return False

    def get_sessions(
        self,
        document_id: int,
        limit: int | None = None,
        offset: int | None = None,
    ) -> SessionsPage:
        """Sessions for a document, newest first, optionally paginated."""
        try:
            with self.get_connection() as conn:
                count_row = conn.execute(
                    "SELECT COUNT(*) FROM document_sessions WHERE document_id = ?",
                    (document_id,),
                ).fetchone()
                total_sessions = count_row[0] if count_row else 0

                query = """
                    SELECT session_id, session_start, last_updated,
                           units_read, time_spent_seconds
                    FROM document_sessions
                    WHERE document_id = ?
                    ORDER BY session_start DESC
                """
                params: list = [document_id]

                if limit is not None:
                    query += " LIMIT ?"
                    params.append(limit)
                elif offset is not None:
                    # SQLite requires LIMIT before OFFSET; LIMIT -1 = no limit
                    query += " LIMIT -1"
                if offset is not None:
                    query += " OFFSET ?"
                    params.append(offset)

                rows = conn.execute(query, params).fetchall()

            sessions = [
                ReadingSessionRecord(
                    session_id=row[0],
                    document_id=document_id,
                    session_start=self.format_timestamp_iso(row[1]),
                    last_updated=self.format_timestamp_iso(row[2]),
                    units_read=row[3] or 0,
                    time_spent_seconds=row[4] or 0.0,
                )
                for row in rows
            ]
            return SessionsPage(
                document_id=document_id,
                total_sessions=total_sessions,
                sessions=sessions,
            )
        except Exception as e:
            logger.error(
                f"Error retrieving sessions for document_id={document_id}: {e}"
            )
            return SessionsPage(document_id=document_id, total_sessions=0, sessions=[])

    def delete_sessions_for_document(self, document_id: int) -> bool:
        """Delete all sessions for a document. True if any were deleted."""
        try:
            result = self.execute_update_delete(
                "DELETE FROM document_sessions WHERE document_id = ?", (document_id,)
            )
            if result:
                logger.info(f"Deleted all sessions for document_id={document_id}")
            return result
        except Exception as e:
            logger.error(f"Error deleting sessions for document_id={document_id}: {e}")
            return False

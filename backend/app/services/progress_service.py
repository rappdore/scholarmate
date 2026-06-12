"""
Progress Service - unified reading progress and status tracking (A-1).

One ``document_progress`` table keyed by document_id replaces the former
``reading_progress`` (PDF, filename-keyed) and ``epub_reading_progress``
twins. Format-specific position fields live in nullable columns; reads JOIN
the documents registry so every returned record carries its filename and
doc_type and parses into a typed :class:`DocumentProgress` with a
discriminated-union position.

Format-specific semantics preserved from the twins:
- PDF saves never touch status (the frontend drives PDF status explicitly).
- EPUB saves auto-derive status from progress_percentage unless the status
  was manually set.
- nav_metadata (EPUB word counts): an existing non-NULL value is never
  erased by an incoming None.
"""

import json
import logging
import sqlite3

from app.models.documents import (
    BookStatus,
    DocumentProgress,
    DocumentType,
    EpubPosition,
    PdfPosition,
)

from .base_database_service import BaseDatabaseService

logger = logging.getLogger(__name__)

_SELECT = """
    SELECT p.document_id, d.doc_type, d.filename,
           p.last_page, p.total_pages,
           p.current_nav_id, p.chapter_id, p.chapter_title,
           p.scroll_position, p.total_sections, p.nav_metadata,
           p.progress_percentage, p.last_updated,
           p.status, p.status_updated_at, p.manually_set
    FROM document_progress p
    JOIN documents d ON d.id = p.document_id
"""


class ProgressService(BaseDatabaseService):
    """Reading progress and book status for every document format."""

    def __init__(self, db_path: str = "data/reading_progress.db"):
        super().__init__(db_path)
        self._init_table()

    def _init_table(self):
        """
        The CREATE TABLE statement is the single source of truth for this
        table's schema; a fresh database gets the complete schema from it.
        """
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_progress (
                    document_id INTEGER PRIMARY KEY,

                    -- PDF position (NULL for EPUBs)
                    last_page INTEGER,
                    total_pages INTEGER,

                    -- EPUB position (NULL for PDFs)
                    current_nav_id TEXT,
                    chapter_id TEXT,
                    chapter_title TEXT,
                    scroll_position INTEGER DEFAULT 0,
                    total_sections INTEGER,
                    nav_metadata TEXT,          -- JSON navigation/word-count metadata

                    -- Shared
                    progress_percentage REAL DEFAULT 0.0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'new' CHECK (status IN ('new', 'reading', 'finished')),
                    status_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    manually_set BOOLEAN DEFAULT FALSE
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_progress_status
                ON document_progress(status, status_updated_at)
            """)

            conn.commit()

    # ------------------------------------------------------------------
    # Row parsing
    # ------------------------------------------------------------------

    def _row_to_progress(self, row: sqlite3.Row) -> DocumentProgress:
        doc_type = DocumentType(row["doc_type"])
        position: PdfPosition | EpubPosition
        if doc_type == DocumentType.PDF:
            position = PdfPosition(
                last_page=row["last_page"] or 0,
                total_pages=row["total_pages"],
            )
        else:
            position = EpubPosition(
                current_nav_id=row["current_nav_id"] or "start",
                chapter_id=row["chapter_id"],
                chapter_title=row["chapter_title"],
                scroll_position=row["scroll_position"] or 0,
                total_sections=row["total_sections"],
            )

        nav_metadata = None
        if row["nav_metadata"]:
            try:
                nav_metadata = json.loads(row["nav_metadata"])
            except json.JSONDecodeError:
                logger.warning(
                    "Invalid nav_metadata JSON for document_id=%s", row["document_id"]
                )

        return DocumentProgress(
            document_id=row["document_id"],
            doc_type=doc_type,
            filename=row["filename"],
            position=position,
            progress_percentage=row["progress_percentage"] or 0.0,
            nav_metadata=nav_metadata,
            last_updated=row["last_updated"],
            status=BookStatus(row["status"]) if row["status"] else BookStatus.NEW,
            status_updated_at=row["status_updated_at"],
            manually_set=bool(row["manually_set"])
            if row["manually_set"] is not None
            else False,
        )

    # ------------------------------------------------------------------
    # Saves
    # ------------------------------------------------------------------

    def save_pdf_progress(
        self, document_id: int, last_page: int, total_pages: int | None
    ) -> bool:
        """Save/update PDF reading position. Status fields are untouched on update."""
        try:
            percentage = (last_page / total_pages) * 100.0 if total_pages else 0.0
            query = """
                INSERT INTO document_progress
                    (document_id, last_page, total_pages, progress_percentage,
                     last_updated, status, status_updated_at, manually_set)
                VALUES (?, ?, ?, ?, ?, 'new', ?, FALSE)
                ON CONFLICT(document_id) DO UPDATE SET
                    last_page = excluded.last_page,
                    total_pages = excluded.total_pages,
                    progress_percentage = excluded.progress_percentage,
                    last_updated = excluded.last_updated
            """
            now = self.get_current_timestamp()
            result = self.execute_update_delete(
                query,
                (document_id, last_page, total_pages, percentage, now, now),
            )
            if result:
                logger.info(
                    "Saved PDF progress for document_id=%s: page %s",
                    document_id,
                    last_page,
                )
            return result
        except Exception as e:
            logger.error(f"Error saving PDF progress: {e}")
            return False

    def save_epub_progress(
        self,
        document_id: int,
        position: EpubPosition,
        progress_percentage: float = 0.0,
        nav_metadata: dict | None = None,
    ) -> bool:
        """
        Save/update EPUB reading position.

        Status is auto-derived from progress_percentage unless manually set;
        a stored non-NULL nav_metadata is never erased by an incoming None.
        """
        try:
            nav_metadata_json = json.dumps(nav_metadata) if nav_metadata else None
            query = """
                INSERT INTO document_progress
                    (document_id, current_nav_id, chapter_id, chapter_title,
                     scroll_position, total_sections, nav_metadata,
                     progress_percentage, last_updated,
                     status, status_updated_at, manually_set)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
                ON CONFLICT(document_id) DO UPDATE SET
                    current_nav_id = excluded.current_nav_id,
                    chapter_id = excluded.chapter_id,
                    chapter_title = excluded.chapter_title,
                    scroll_position = excluded.scroll_position,
                    total_sections = excluded.total_sections,
                    nav_metadata = COALESCE(excluded.nav_metadata, nav_metadata),
                    progress_percentage = excluded.progress_percentage,
                    last_updated = excluded.last_updated,
                    status = CASE
                        WHEN manually_set = 0 THEN
                            CASE
                                WHEN excluded.progress_percentage >= 95.0 THEN 'finished'
                                WHEN excluded.progress_percentage > 0 THEN 'reading'
                                ELSE 'new'
                            END
                        ELSE status
                    END,
                    status_updated_at = CASE
                        WHEN manually_set = 0 THEN excluded.status_updated_at
                        ELSE status_updated_at
                    END
            """
            now = self.get_current_timestamp()
            result = self.execute_update_delete(
                query,
                (
                    document_id,
                    position.current_nav_id,
                    position.chapter_id,
                    position.chapter_title,
                    position.scroll_position,
                    position.total_sections,
                    nav_metadata_json,
                    progress_percentage,
                    now,
                    "reading" if progress_percentage > 0 else "new",
                    now,
                ),
            )
            if result:
                logger.info(
                    "Saved EPUB progress for document_id=%s: %s (%.1f%%)",
                    document_id,
                    position.current_nav_id,
                    progress_percentage,
                )
            return result
        except Exception as e:
            logger.error(f"Error saving EPUB progress: {e}")
            return False

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_progress(self, document_id: int) -> DocumentProgress | None:
        try:
            row = self.execute_query(
                _SELECT + " WHERE p.document_id = ?",
                (document_id,),
                fetch_one=True,
            )
            return self._row_to_progress(row) if row else None
        except Exception as e:
            logger.error(f"Error getting progress for document_id={document_id}: {e}")
            return None

    def get_all_progress(
        self, doc_type: DocumentType | None = None
    ) -> list[DocumentProgress]:
        try:
            if doc_type is None:
                rows = self.execute_query(
                    _SELECT + " ORDER BY p.last_updated DESC", fetch_all=True
                )
            else:
                rows = self.execute_query(
                    _SELECT + " WHERE d.doc_type = ? ORDER BY p.last_updated DESC",
                    (doc_type.value,),
                    fetch_all=True,
                )
            return [self._row_to_progress(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error getting all progress: {e}")
            return []

    def get_books_by_status(
        self,
        status: BookStatus | None = None,
        doc_type: DocumentType | None = None,
    ) -> list[DocumentProgress]:
        try:
            conditions = []
            params: list = []
            if status is not None:
                conditions.append("p.status = ?")
                params.append(status.value)
            if doc_type is not None:
                conditions.append("d.doc_type = ?")
                params.append(doc_type.value)
            query = _SELECT
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY p.status_updated_at DESC, p.last_updated DESC"
            rows = self.execute_query(query, tuple(params), fetch_all=True)
            return [self._row_to_progress(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error getting books by status: {e}")
            return []

    def get_status_counts(self, doc_type: DocumentType | None = None) -> dict[str, int]:
        try:
            if doc_type is None:
                query = """
                    SELECT p.status, COUNT(*) FROM document_progress p
                    GROUP BY p.status
                """
                params: tuple = ()
            else:
                query = """
                    SELECT p.status, COUNT(*) FROM document_progress p
                    JOIN documents d ON d.id = p.document_id
                    WHERE d.doc_type = ?
                    GROUP BY p.status
                """
                params = (doc_type.value,)
            rows = self.execute_query(query, params, fetch_all=True)

            counts = {"new": 0, "reading": 0, "finished": 0}
            if rows:
                for row in rows:
                    status = row[0] if row[0] else "new"
                    if status in counts:
                        counts[status] = row[1] or 0
            counts["all"] = sum(counts.values())
            return counts
        except Exception as e:
            logger.error(f"Error getting status counts: {e}")
            return {"all": 0, "new": 0, "reading": 0, "finished": 0}

    # ------------------------------------------------------------------
    # Status + deletion
    # ------------------------------------------------------------------

    def update_status(
        self, document_id: int, status: BookStatus, manual: bool = True
    ) -> bool:
        """Update book status, creating the progress row if missing."""
        try:
            now = self.get_current_timestamp()
            query = """
                INSERT INTO document_progress
                    (document_id, last_updated, status, status_updated_at, manually_set)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    status = excluded.status,
                    status_updated_at = excluded.status_updated_at,
                    manually_set = excluded.manually_set
            """
            result = self.execute_update_delete(
                query, (document_id, now, status.value, now, manual)
            )
            if result:
                logger.info(
                    "Updated status for document_id=%s to '%s' (manual: %s)",
                    document_id,
                    status.value,
                    manual,
                )
            return result
        except Exception as e:
            logger.error(f"Error updating book status: {e}")
            return False

    def delete_progress(self, document_id: int) -> bool:
        try:
            return self.execute_update_delete(
                "DELETE FROM document_progress WHERE document_id = ?", (document_id,)
            )
        except Exception as e:
            logger.error(f"Error deleting progress: {e}")
            return False

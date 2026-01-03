"""
EPUB Highlights Service

Service for managing persistent text highlights in EPUB documents.
Uses XPath + offset pairs for both start and end boundaries.
"""

from __future__ import annotations

import logging

from ..models.epub_highlights import EPUBHighlight, EPUBHighlightCreate
from .base_database_service import BaseDatabaseService

logger = logging.getLogger(__name__)


class EPUBHighlightService(BaseDatabaseService):
    """SQLite helper for EPUB highlights."""

    def __init__(self, db_path: str = "data/reading_progress.db"):
        super().__init__(db_path)
        self._init_table()

    def _init_table(self) -> None:
        """Ensure the epub_highlights table exists with new schema."""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS epub_highlights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    epub_id INTEGER NOT NULL,
                    nav_id TEXT NOT NULL,
                    chapter_id TEXT,
                    start_xpath TEXT NOT NULL,
                    start_offset INTEGER NOT NULL,
                    end_xpath TEXT NOT NULL,
                    end_offset INTEGER NOT NULL,
                    highlight_text TEXT NOT NULL,
                    color TEXT DEFAULT 'yellow',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (epub_id) REFERENCES epub_documents(id) ON DELETE CASCADE
                )
            """)

            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_highlights_epub_nav
                ON epub_highlights(epub_id, nav_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_highlights_epub_chapter
                ON epub_highlights(epub_id, chapter_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_highlights_epub_id
                ON epub_highlights(epub_id)
            """)
            conn.commit()

    # ─────────────────────────────────────────────────────────────────
    # CRUD Operations
    # ─────────────────────────────────────────────────────────────────

    def save_highlight(self, data: EPUBHighlightCreate) -> int | None:
        """Create a new highlight and return its ID."""
        try:
            query = """
                INSERT INTO epub_highlights (
                    epub_id, nav_id, chapter_id,
                    start_xpath, start_offset, end_xpath, end_offset,
                    highlight_text, color, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                data.epub_id,
                data.nav_id,
                data.chapter_id,
                data.start_xpath,
                data.start_offset,
                data.end_xpath,
                data.end_offset,
                data.highlight_text,
                data.color,
                self.get_current_timestamp(),
            )
            highlight_id = self.execute_insert(query, params)
            logger.info(
                "Created highlight %s for epub %s nav=%s",
                highlight_id,
                data.epub_id,
                data.nav_id,
            )
            return highlight_id
        except Exception as exc:
            logger.exception("Error creating highlight: %s", exc)
            return None

    def _row_to_model(self, row) -> EPUBHighlight:
        """Convert a database row to EPUBHighlight model."""
        return EPUBHighlight(
            id=row["id"],
            epub_id=row["epub_id"],
            nav_id=row["nav_id"],
            chapter_id=row["chapter_id"],
            start_xpath=row["start_xpath"],
            start_offset=row["start_offset"],
            end_xpath=row["end_xpath"],
            end_offset=row["end_offset"],
            highlight_text=row["highlight_text"],
            color=row["color"],
            created_at=row["created_at"],
        )

    def get_highlight_by_id(self, highlight_id: int) -> EPUBHighlight | None:
        """Get a single highlight by ID."""
        try:
            query = "SELECT * FROM epub_highlights WHERE id = ?"
            row = self.execute_query(query, (highlight_id,), fetch_one=True)
            return self._row_to_model(row) if row else None
        except Exception as exc:
            logger.exception("Error fetching highlight by id: %s", exc)
            return None

    def get_highlights_for_section(
        self,
        epub_id: int,
        nav_id: str,
    ) -> list[EPUBHighlight]:
        """Get all highlights for a specific section."""
        try:
            query = """
                SELECT * FROM epub_highlights
                WHERE epub_id = ? AND nav_id = ?
                ORDER BY created_at ASC
            """
            rows = self.execute_query(query, (epub_id, nav_id), fetch_all=True)
            return [self._row_to_model(row) for row in rows] if rows else []
        except Exception as exc:
            logger.exception("Error fetching section highlights: %s", exc)
            return []

    def get_highlights_for_chapter(
        self,
        epub_id: int,
        chapter_id: str,
    ) -> list[EPUBHighlight]:
        """Get all highlights for a chapter."""
        try:
            query = """
                SELECT * FROM epub_highlights
                WHERE epub_id = ? AND chapter_id = ?
                ORDER BY nav_id, created_at ASC
            """
            rows = self.execute_query(query, (epub_id, chapter_id), fetch_all=True)
            return [self._row_to_model(row) for row in rows] if rows else []
        except Exception as exc:
            logger.exception("Error fetching chapter highlights: %s", exc)
            return []

    def get_all_highlights(self, epub_id: int) -> list[EPUBHighlight]:
        """Get all highlights for an EPUB."""
        try:
            query = """
                SELECT * FROM epub_highlights
                WHERE epub_id = ?
                ORDER BY nav_id, created_at ASC
            """
            rows = self.execute_query(query, (epub_id,), fetch_all=True)
            return [self._row_to_model(row) for row in rows] if rows else []
        except Exception as exc:
            logger.exception("Error fetching all highlights: %s", exc)
            return []

    def delete_highlight(self, highlight_id: int) -> bool:
        """Delete a highlight by ID."""
        try:
            query = "DELETE FROM epub_highlights WHERE id = ?"
            deleted = self.execute_update_delete(query, (highlight_id,))
            if deleted:
                logger.info("Deleted highlight %s", highlight_id)
            return deleted
        except Exception as exc:
            logger.exception("Error deleting highlight: %s", exc)
            return False

    def update_color(self, highlight_id: int, color: str) -> bool:
        """Update the color of a highlight."""
        try:
            query = """
                UPDATE epub_highlights
                SET color = ?
                WHERE id = ?
            """
            updated = self.execute_update_delete(query, (color, highlight_id))
            if updated:
                logger.info("Updated color for highlight %s to %s", highlight_id, color)
            return updated
        except Exception as exc:
            logger.exception("Error updating highlight color: %s", exc)
            return False

    def get_highlights_count_by_epub(self) -> dict[int, dict[str, int]]:
        """
        Get summary statistics about highlights for all EPUB documents.

        Returns:
            dict[int, dict[str, int]]: Dictionary mapping EPUB IDs to their highlight statistics
        """
        try:
            query = """
                SELECT
                    epub_id,
                    COUNT(*) as highlights_count
                FROM epub_highlights
                GROUP BY epub_id
            """
            rows = self.execute_query(query, fetch_all=True)

            highlights_info: dict[int, dict[str, int]] = {}
            if rows:
                for row in rows:
                    highlights_info[row["epub_id"]] = {
                        "highlights_count": row["highlights_count"],
                    }

            return highlights_info
        except Exception as exc:
            logger.exception("Error getting EPUB highlights count: %s", exc)
            return {}

    def delete_highlights_for_epub(self, epub_id: int) -> bool:
        """Delete all highlights for an EPUB document."""
        try:
            query = "DELETE FROM epub_highlights WHERE epub_id = ?"
            self.execute_update_delete(query, (epub_id,))
            logger.info("Deleted all highlights for epub_id %s", epub_id)
            return True
        except Exception as exc:
            logger.exception("Error deleting highlights for epub: %s", exc)
            return False

"""
EPUB Highlights Service Module

This module provides specialized database operations for managing text highlights
inside EPUB documents. Unlike PDF highlights that rely on pixel-based coordinates,
EPUB highlights use DOM positioning (XPath + character offsets) that are specific
to a navigation section (nav_id).

Schema (created via migration 002_create_epub_highlights.sql):
    epub_highlights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        epub_filename TEXT NOT NULL,
        nav_id TEXT NOT NULL,
        chapter_id TEXT,
        xpath TEXT NOT NULL,
        start_offset INTEGER NOT NULL,
        end_offset INTEGER NOT NULL,
        highlight_text TEXT NOT NULL,
        color TEXT DEFAULT '#ffff00',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )

The service provides CRUD helpers that will be wrapped by DatabaseService.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base_database_service import BaseDatabaseService

logger = logging.getLogger(__name__)


class EPUBHighlightService(BaseDatabaseService):
    """SQLite helper for EPUB text highlights."""

    def __init__(self, db_path: str = "data/reading_progress.db"):
        super().__init__(db_path)
        self._init_table()

    # NOTE: Table is created via migration; this is a safeguard to support fresh
    # databases during unit tests or first-time setups where migrations may not
    # run yet (e.g., in CI). It uses the exact same definition as the migration,
    # but wrapped in IF NOT EXISTS so it is idempotent.
    def _init_table(self) -> None:  # noqa: D401
        """Ensure the epub_highlights table & indexes exist."""
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS epub_highlights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    epub_filename TEXT NOT NULL,
                    nav_id TEXT NOT NULL,
                    chapter_id TEXT,
                    xpath TEXT NOT NULL,
                    start_offset INTEGER NOT NULL,
                    end_offset INTEGER NOT NULL,
                    highlight_text TEXT NOT NULL,
                    color TEXT DEFAULT '#ffff00',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_epub_highlights_epub_nav
                ON epub_highlights(epub_filename, nav_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_epub_highlights_epub_chapter
                ON epub_highlights(epub_filename, chapter_id)
                """
            )
            conn.commit()

    # ---------------------------------------------------------------------
    # CRUD helpers
    # ---------------------------------------------------------------------

    def save_highlight(
        self,
        epub_filename: str,
        nav_id: str,
        chapter_id: Optional[str],
        xpath: str,
        start_offset: int,
        end_offset: int,
        highlight_text: str,
        color: str,
    ) -> Optional[int]:
        """Persist a new highlight and return its auto-generated ID."""
        try:
            query = """
                INSERT INTO epub_highlights (
                    epub_filename, nav_id, chapter_id, xpath,
                    start_offset, end_offset, highlight_text, color, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                epub_filename,
                nav_id,
                chapter_id,
                xpath,
                start_offset,
                end_offset,
                highlight_text,
                color,
                self.get_current_timestamp(),
            )
            highlight_id = self.execute_insert(query, params)
            if highlight_id:
                logger.info(
                    "Saved EPUB highlight %s (%s) nav=%s xpath=%s",
                    epub_filename,
                    highlight_id,
                    nav_id,
                    xpath,
                )
            return highlight_id
        except Exception as exc:
            logger.exception("Error saving EPUB highlight: %s", exc)
            return None

    def get_highlights_for_section(
        self, epub_filename: str, nav_id: str
    ) -> List[Dict[str, Any]]:
        """Return all highlights within a specific nav_id section."""
        try:
            query = """
                SELECT * FROM epub_highlights
                WHERE epub_filename = ? AND nav_id = ?
                ORDER BY created_at ASC
            """
            rows = self.execute_query(query, (epub_filename, nav_id), fetch_all=True)
            return [dict(row) for row in rows] if rows else []
        except Exception as exc:
            logger.exception("Error fetching EPUB section highlights: %s", exc)
            return []

    def get_highlights_for_chapter(
        self, epub_filename: str, chapter_id: str
    ) -> List[Dict[str, Any]]:
        """Return all highlights aggregated for a whole chapter."""
        try:
            query = """
                SELECT * FROM epub_highlights
                WHERE epub_filename = ? AND chapter_id = ?
                ORDER BY nav_id, created_at ASC
            """
            rows = self.execute_query(
                query, (epub_filename, chapter_id), fetch_all=True
            )
            return [dict(row) for row in rows] if rows else []
        except Exception as exc:
            logger.exception("Error fetching EPUB chapter highlights: %s", exc)
            return []

    def get_highlight_by_id(self, highlight_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single highlight by primary key."""
        try:
            query = "SELECT * FROM epub_highlights WHERE id = ?"
            row = self.execute_query(query, (highlight_id,), fetch_one=True)
            return dict(row) if row else None
        except Exception as exc:
            logger.exception("Error fetching EPUB highlight by id: %s", exc)
            return None

    def delete_highlight(self, highlight_id: int) -> bool:
        """Remove a highlight permanently."""
        try:
            query = "DELETE FROM epub_highlights WHERE id = ?"
            deleted = self.execute_update_delete(query, (highlight_id,))
            if deleted:
                logger.info("Deleted EPUB highlight %s", highlight_id)
            return deleted
        except Exception as exc:
            logger.exception("Error deleting EPUB highlight: %s", exc)
            return False

    def update_color(self, highlight_id: int, color: str) -> bool:
        """Change the highlight's color."""
        try:
            query = """
                UPDATE epub_highlights
                SET color = ?
                WHERE id = ?
            """
            updated = self.execute_update_delete(query, (color, highlight_id))
            if updated:
                logger.info(
                    "Updated color for EPUB highlight %s to %s", highlight_id, color
                )
            return updated
        except Exception as exc:
            logger.exception("Error updating EPUB highlight color: %s", exc)
            return False

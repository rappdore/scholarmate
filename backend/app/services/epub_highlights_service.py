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
from .epub_documents_service import EPUBDocumentsService

logger = logging.getLogger(__name__)


class EPUBHighlightService(BaseDatabaseService):
    """SQLite helper for EPUB text highlights."""

    def __init__(self, db_path: str = "data/reading_progress.db"):
        super().__init__(db_path)
        # Phase 4c: Initialize EPUB documents service for epub_id lookups
        # Note: Must be initialized before _init_table() for consistency,
        # though backfill uses direct SQL joins, not the helper method
        self._epub_docs_service = EPUBDocumentsService(db_path)
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

            # Phase 4c: Add epub_id column if it doesn't exist (backward compatible migration)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(epub_highlights)")
            columns = [column[1] for column in cursor.fetchall()]

            if "epub_id" not in columns:
                logger.info("Adding epub_id column to epub_highlights table...")
                conn.execute("ALTER TABLE epub_highlights ADD COLUMN epub_id INTEGER")
                logger.info("epub_id column added successfully")

            # Create index on epub_id if it doesn't exist
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_epub_highlights_epub_id
                ON epub_highlights(epub_id)
                """
            )

            # =============================================================================
            # ONE-TIME BACKFILL: Populate epub_id for existing epub_highlights rows
            #
            # Unlike epub_reading_progress which gets updated on access, epub_highlights only
            # receives INSERTs, so existing rows would never get their epub_id populated.
            # This backfill runs once on startup and updates all rows where epub_id IS NULL.
            #
            # TODO: This backfill can be removed after all environments have been updated
            #       and no NULL epub_id values remain. Safe to remove after ~March 2026.
            # =============================================================================
            cursor.execute(
                """
                UPDATE epub_highlights
                SET epub_id = (
                    SELECT id FROM epub_documents
                    WHERE epub_documents.filename = epub_highlights.epub_filename
                )
                WHERE epub_id IS NULL
                AND EXISTS (
                    SELECT 1 FROM epub_documents
                    WHERE epub_documents.filename = epub_highlights.epub_filename
                )
                """
            )
            backfilled = cursor.rowcount
            if backfilled > 0:
                logger.info(
                    f"Backfilled epub_id for {backfilled} existing epub_highlights rows"
                )

            conn.commit()

    # ---------------------------------------------------------------------
    # CRUD helpers
    # ---------------------------------------------------------------------

    def _get_epub_id(self, epub_filename: str) -> Optional[int]:
        """
        Get the epub_id for a given EPUB filename.

        Phase 4c: Helper method for looking up epub_id from epub_documents table.

        Args:
            epub_filename (str): Name of the EPUB file

        Returns:
            Optional[int]: The epub_id if found, None otherwise
        """
        try:
            epub_doc = self._epub_docs_service.get_by_filename(epub_filename)
            if epub_doc:
                return epub_doc.get("id")
            return None
        except Exception as e:
            logger.warning(f"Could not look up epub_id for {epub_filename}: {e}")
            return None

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
            # Phase 4c: Look up epub_id for auto-population
            epub_id = self._get_epub_id(epub_filename)

            query = """
                INSERT INTO epub_highlights (
                    epub_filename, epub_id, nav_id, chapter_id, xpath,
                    start_offset, end_offset, highlight_text, color, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                epub_filename,
                epub_id,
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
                    "Saved EPUB highlight %s (%s) nav=%s xpath=%s (epub_id=%s)",
                    epub_filename,
                    highlight_id,
                    nav_id,
                    xpath,
                    epub_id,
                )
            return highlight_id
        except Exception as exc:
            logger.exception("Error saving EPUB highlight: %s", exc)
            return None

    def get_all_highlights(self, epub_filename: str) -> List[Dict[str, Any]]:
        """Return all highlights for an EPUB document."""
        try:
            query = """
                SELECT * FROM epub_highlights
                WHERE epub_filename = ?
                ORDER BY created_at ASC
            """
            rows = self.execute_query(query, (epub_filename,), fetch_all=True)
            return [dict(row) for row in rows] if rows else []
        except Exception as exc:
            logger.exception("Error fetching all EPUB highlights: %s", exc)
            return []

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

    def get_highlights_count_by_epub(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary statistics about highlights for all EPUB documents.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping EPUB filenames to their highlight statistics
        """
        try:
            # Query: Get count for each EPUB
            query = """
                SELECT
                    epub_filename,
                    COUNT(*) as highlights_count
                FROM epub_highlights
                GROUP BY epub_filename
            """
            rows = self.execute_query(query, fetch_all=True)

            highlights_info = {}
            if rows:
                for row in rows:
                    highlights_info[row["epub_filename"]] = {
                        "highlights_count": row["highlights_count"],
                    }

            return highlights_info
        except Exception as exc:
            logger.exception("Error getting EPUB highlights count: %s", exc)
            return {}

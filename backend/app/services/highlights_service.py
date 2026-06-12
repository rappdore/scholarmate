"""
Highlights Service - one interface, two anchor-specific tables (A-1).

PDF and EPUB highlight *anchors* are genuinely structurally different
(page + character offsets + rendered bounding boxes vs XPath ranges), so
they keep separate tables — ``document_highlights_pdf`` and
``document_highlights_epub`` — both keyed by document_id, behind this one
service. Replaces the former filename-keyed ``highlights`` table and the
``epub_highlights`` table/service pair.
"""

import json
import logging
import sqlite3

from app.models.documents import HighlightsSummary, PdfHighlightRecord
from app.models.epub_highlights import EPUBHighlight, EPUBHighlightCreate

from .base_database_service import BaseDatabaseService

logger = logging.getLogger(__name__)

_PDF_SELECT = """
    SELECT h.id, h.document_id, d.filename,
           h.page_number, h.selected_text, h.start_offset, h.end_offset,
           h.color, h.coordinates, h.created_at, h.updated_at
    FROM document_highlights_pdf h
    JOIN documents d ON d.id = h.document_id
"""

_EPUB_SELECT = """
    SELECT id, document_id, nav_id, chapter_id,
           start_xpath, start_offset, end_xpath, end_offset,
           highlight_text, color, created_at
    FROM document_highlights_epub
"""


class HighlightsService(BaseDatabaseService):
    """Text highlights for every document format."""

    def __init__(self, db_path: str = "data/reading_progress.db"):
        super().__init__(db_path)
        self._init_table()

    def _init_table(self):
        """
        The CREATE TABLE statements are the single source of truth for these
        tables' schemas; a fresh database gets the complete schema from them.
        """
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_highlights_pdf (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    page_number INTEGER NOT NULL,
                    selected_text TEXT NOT NULL,
                    start_offset INTEGER NOT NULL,
                    end_offset INTEGER NOT NULL,
                    color TEXT NOT NULL DEFAULT '#ffff00',
                    coordinates TEXT NOT NULL,          -- JSON bounding-box array
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_highlights_pdf_doc_page
                ON document_highlights_pdf(document_id, page_number)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_highlights_epub (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    nav_id TEXT NOT NULL,
                    chapter_id TEXT,
                    start_xpath TEXT NOT NULL,
                    start_offset INTEGER NOT NULL,
                    end_xpath TEXT NOT NULL,
                    end_offset INTEGER NOT NULL,
                    highlight_text TEXT NOT NULL,
                    color TEXT DEFAULT 'yellow',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_highlights_epub_doc_nav
                ON document_highlights_epub(document_id, nav_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_highlights_epub_doc_chapter
                ON document_highlights_epub(document_id, chapter_id)
            """)

            conn.commit()

    # ------------------------------------------------------------------
    # PDF highlights
    # ------------------------------------------------------------------

    def _row_to_pdf_highlight(self, row: sqlite3.Row) -> PdfHighlightRecord:
        try:
            coordinates = json.loads(row["coordinates"])
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid coordinates JSON for highlight %s", row["id"])
            coordinates = []
        return PdfHighlightRecord(
            id=row["id"],
            document_id=row["document_id"],
            filename=row["filename"],
            page_number=row["page_number"],
            selected_text=row["selected_text"],
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
            color=row["color"],
            coordinates=coordinates,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def save_pdf_highlight(
        self,
        document_id: int,
        page_number: int,
        selected_text: str,
        start_offset: int,
        end_offset: int,
        color: str,
        coordinates: list[dict],
    ) -> int | None:
        try:
            now = self.get_current_timestamp()
            highlight_id = self.execute_insert(
                """
                INSERT INTO document_highlights_pdf (
                    document_id, page_number, selected_text, start_offset,
                    end_offset, color, coordinates, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    page_number,
                    selected_text,
                    start_offset,
                    end_offset,
                    color,
                    json.dumps(coordinates),
                    now,
                    now,
                ),
            )
            if highlight_id:
                logger.info(
                    "Saved PDF highlight %s for document_id=%s page %s",
                    highlight_id,
                    document_id,
                    page_number,
                )
            return highlight_id
        except Exception as e:
            logger.error(f"Error saving PDF highlight: {e}")
            return None

    def get_pdf_highlights(
        self, document_id: int, page_number: int | None = None
    ) -> list[PdfHighlightRecord]:
        try:
            if page_number is not None:
                query = _PDF_SELECT + (
                    " WHERE h.document_id = ? AND h.page_number = ?"
                    " ORDER BY h.created_at DESC"
                )
                params: tuple = (document_id, page_number)
            else:
                query = _PDF_SELECT + (
                    " WHERE h.document_id = ? ORDER BY h.page_number, h.created_at DESC"
                )
                params = (document_id,)
            rows = self.execute_query(query, params, fetch_all=True)
            return [self._row_to_pdf_highlight(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error getting PDF highlights: {e}")
            return []

    def get_pdf_highlight_by_id(self, highlight_id: int) -> PdfHighlightRecord | None:
        try:
            row = self.execute_query(
                _PDF_SELECT + " WHERE h.id = ?", (highlight_id,), fetch_one=True
            )
            return self._row_to_pdf_highlight(row) if row else None
        except Exception as e:
            logger.error(f"Error getting PDF highlight: {e}")
            return None

    def delete_pdf_highlight(self, highlight_id: int) -> bool:
        try:
            deleted = self.execute_update_delete(
                "DELETE FROM document_highlights_pdf WHERE id = ?", (highlight_id,)
            )
            if deleted:
                logger.info(f"Deleted PDF highlight {highlight_id}")
            return deleted
        except Exception as e:
            logger.error(f"Error deleting PDF highlight: {e}")
            return False

    def update_pdf_highlight_color(self, highlight_id: int, color: str) -> bool:
        try:
            return self.execute_update_delete(
                "UPDATE document_highlights_pdf SET color = ?, updated_at = ? "
                "WHERE id = ?",
                (color, self.get_current_timestamp(), highlight_id),
            )
        except Exception as e:
            logger.error(f"Error updating PDF highlight color: {e}")
            return False

    def get_pdf_highlights_summary(self) -> dict[str, HighlightsSummary]:
        """Per-PDF highlight statistics keyed by filename (single query)."""
        try:
            query = """
                SELECT d.filename,
                       COUNT(*) AS highlights_count,
                       MAX(h.created_at) AS latest_highlight_date,
                       (
                           SELECT h2.selected_text FROM document_highlights_pdf h2
                           WHERE h2.document_id = h.document_id
                           ORDER BY h2.created_at DESC, h2.id DESC
                           LIMIT 1
                       ) AS latest_highlight_text
                FROM document_highlights_pdf h
                JOIN documents d ON d.id = h.document_id
                GROUP BY h.document_id
            """
            rows = self.execute_query(query, fetch_all=True)
            if not rows:
                return {}
            summaries = {}
            for row in rows:
                text = row["latest_highlight_text"] or "No text"
                if len(text) > 50:
                    text = text[:50] + "..."
                summaries[row["filename"]] = HighlightsSummary(
                    highlights_count=row["highlights_count"],
                    latest_highlight_date=row["latest_highlight_date"],
                    latest_highlight_text=text,
                )
            return summaries
        except Exception as e:
            logger.error(f"Error getting PDF highlights summary: {e}")
            return {}

    # ------------------------------------------------------------------
    # EPUB highlights
    # ------------------------------------------------------------------

    def _row_to_epub_highlight(self, row: sqlite3.Row) -> EPUBHighlight:
        return EPUBHighlight(
            id=row["id"],
            epub_id=row["document_id"],
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

    def save_epub_highlight(self, data: EPUBHighlightCreate) -> int | None:
        try:
            highlight_id = self.execute_insert(
                """
                INSERT INTO document_highlights_epub (
                    document_id, nav_id, chapter_id,
                    start_xpath, start_offset, end_xpath, end_offset,
                    highlight_text, color, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
                ),
            )
            if highlight_id:
                logger.info(
                    "Saved EPUB highlight %s for document_id=%s nav=%s",
                    highlight_id,
                    data.epub_id,
                    data.nav_id,
                )
            return highlight_id
        except Exception as e:
            logger.error(f"Error saving EPUB highlight: {e}")
            return None

    def get_epub_highlights(
        self,
        document_id: int,
        nav_id: str | None = None,
        chapter_id: str | None = None,
    ) -> list[EPUBHighlight]:
        try:
            if nav_id is not None:
                query = _EPUB_SELECT + (
                    " WHERE document_id = ? AND nav_id = ? ORDER BY created_at ASC"
                )
                params: tuple = (document_id, nav_id)
            elif chapter_id is not None:
                query = _EPUB_SELECT + (
                    " WHERE document_id = ? AND chapter_id = ?"
                    " ORDER BY nav_id, created_at ASC"
                )
                params = (document_id, chapter_id)
            else:
                query = _EPUB_SELECT + (
                    " WHERE document_id = ? ORDER BY nav_id, created_at ASC"
                )
                params = (document_id,)
            rows = self.execute_query(query, params, fetch_all=True)
            return [self._row_to_epub_highlight(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error getting EPUB highlights: {e}")
            return []

    def get_epub_highlight_by_id(self, highlight_id: int) -> EPUBHighlight | None:
        try:
            row = self.execute_query(
                _EPUB_SELECT + " WHERE id = ?", (highlight_id,), fetch_one=True
            )
            return self._row_to_epub_highlight(row) if row else None
        except Exception as e:
            logger.error(f"Error getting EPUB highlight: {e}")
            return None

    def delete_epub_highlight(self, highlight_id: int) -> bool:
        try:
            deleted = self.execute_update_delete(
                "DELETE FROM document_highlights_epub WHERE id = ?", (highlight_id,)
            )
            if deleted:
                logger.info(f"Deleted EPUB highlight {highlight_id}")
            return deleted
        except Exception as e:
            logger.error(f"Error deleting EPUB highlight: {e}")
            return False

    def update_epub_highlight_color(self, highlight_id: int, color: str) -> bool:
        try:
            return self.execute_update_delete(
                "UPDATE document_highlights_epub SET color = ? WHERE id = ?",
                (color, highlight_id),
            )
        except Exception as e:
            logger.error(f"Error updating EPUB highlight color: {e}")
            return False

    def get_epub_highlights_summary(self) -> dict[int, HighlightsSummary]:
        """Per-EPUB highlight statistics keyed by document id."""
        try:
            query = """
                SELECT document_id, COUNT(*) AS highlights_count
                FROM document_highlights_epub
                GROUP BY document_id
            """
            rows = self.execute_query(query, fetch_all=True)
            if not rows:
                return {}
            return {
                row["document_id"]: HighlightsSummary(
                    highlights_count=row["highlights_count"]
                )
                for row in rows
            }
        except Exception as e:
            logger.error(f"Error getting EPUB highlights summary: {e}")
            return {}

    # ------------------------------------------------------------------
    # Shared
    # ------------------------------------------------------------------

    def delete_highlights_for_document(self, document_id: int) -> bool:
        """Delete every highlight (either format) for a document."""
        try:
            self.execute_update_delete(
                "DELETE FROM document_highlights_pdf WHERE document_id = ?",
                (document_id,),
            )
            self.execute_update_delete(
                "DELETE FROM document_highlights_epub WHERE document_id = ?",
                (document_id,),
            )
            logger.info("Deleted all highlights for document_id=%s", document_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting highlights for document {document_id}: {e}")
            return False

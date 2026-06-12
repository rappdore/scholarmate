"""
Notes Service - unified chat-note storage for every document format (A-1).

One ``document_notes`` table keyed by document_id replaces the former
``chat_notes`` (PDF) and ``epub_chat_notes`` twins (69% duplicated).
Format-specific anchor fields live in nullable columns and parse into a
typed PdfNoteAnchor | EpubNoteAnchor union; reads JOIN the documents
registry so every record carries its filename and doc_type.
"""

import json
import logging
import sqlite3

from app.models.documents import (
    DocumentType,
    EpubNoteAnchor,
    NoteAnchor,
    NoteRecord,
    NotesSummary,
    PdfNoteAnchor,
)

from .base_database_service import BaseDatabaseService

logger = logging.getLogger(__name__)

_SELECT = """
    SELECT n.id, n.document_id, d.doc_type, d.filename,
           n.page_number,
           n.nav_id, n.chapter_id, n.chapter_title,
           n.scroll_position, n.context_sections,
           n.title, n.chat_content, n.created_at, n.updated_at
    FROM document_notes n
    JOIN documents d ON d.id = n.document_id
"""


class NotesService(BaseDatabaseService):
    """Chat notes anchored to a position inside any document."""

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
                CREATE TABLE IF NOT EXISTS document_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,

                    -- PDF anchor (NULL for EPUBs)
                    page_number INTEGER,

                    -- EPUB anchor (NULL for PDFs)
                    nav_id TEXT,
                    chapter_id TEXT,
                    chapter_title TEXT,
                    scroll_position INTEGER DEFAULT 0,
                    context_sections TEXT,      -- JSON array of section ids

                    -- Shared
                    title TEXT,
                    chat_content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_notes_doc_page
                ON document_notes(document_id, page_number)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_notes_doc_nav
                ON document_notes(document_id, nav_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_notes_doc_chapter
                ON document_notes(document_id, chapter_id)
            """)

            conn.commit()

    def _row_to_note(self, row: sqlite3.Row) -> NoteRecord:
        doc_type = DocumentType(row["doc_type"])
        anchor: PdfNoteAnchor | EpubNoteAnchor
        if doc_type == DocumentType.PDF:
            anchor = PdfNoteAnchor(page_number=row["page_number"] or 0)
        else:
            context_sections = None
            if row["context_sections"]:
                try:
                    context_sections = json.loads(row["context_sections"])
                except json.JSONDecodeError:
                    context_sections = []
            anchor = EpubNoteAnchor(
                nav_id=row["nav_id"] or "",
                chapter_id=row["chapter_id"],
                chapter_title=row["chapter_title"],
                scroll_position=row["scroll_position"] or 0,
                context_sections=context_sections,
            )
        return NoteRecord(
            id=row["id"],
            document_id=row["document_id"],
            doc_type=doc_type,
            filename=row["filename"],
            anchor=anchor,
            title=row["title"],
            chat_content=row["chat_content"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save_note(
        self,
        document_id: int,
        anchor: NoteAnchor,
        title: str,
        chat_content: str,
    ) -> int | None:
        """Save a note anchored at the given position. Returns the note id."""
        try:
            now = self.get_current_timestamp()
            if isinstance(anchor, PdfNoteAnchor):
                query = """
                    INSERT INTO document_notes
                        (document_id, page_number, title, chat_content,
                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (
                    document_id,
                    anchor.page_number,
                    title,
                    chat_content,
                    now,
                    now,
                )
            else:
                context_json = (
                    json.dumps(anchor.context_sections)
                    if anchor.context_sections
                    else None
                )
                query = """
                    INSERT INTO document_notes
                        (document_id, nav_id, chapter_id, chapter_title,
                         scroll_position, context_sections, title, chat_content,
                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    document_id,
                    anchor.nav_id,
                    anchor.chapter_id,
                    anchor.chapter_title,
                    anchor.scroll_position,
                    context_json,
                    title,
                    chat_content,
                    now,
                    now,
                )

            note_id = self.execute_insert(query, params)
            if note_id:
                logger.info(
                    "Saved %s note %s for document_id=%s",
                    anchor.kind,
                    note_id,
                    document_id,
                )
            return note_id
        except Exception as e:
            logger.error(f"Error saving note: {e}")
            return None

    def get_pdf_notes(
        self, document_id: int, page_number: int | None = None
    ) -> list[NoteRecord]:
        """Notes for a PDF, optionally filtered by page."""
        try:
            if page_number is not None:
                query = _SELECT + (
                    " WHERE n.document_id = ? AND n.page_number = ?"
                    " ORDER BY n.created_at DESC"
                )
                params: tuple = (document_id, page_number)
            else:
                query = _SELECT + (
                    " WHERE n.document_id = ? ORDER BY n.page_number, n.created_at DESC"
                )
                params = (document_id,)
            rows = self.execute_query(query, params, fetch_all=True)
            return [self._row_to_note(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error getting PDF notes: {e}")
            return []

    def get_epub_notes(
        self,
        document_id: int,
        nav_id: str | None = None,
        chapter_id: str | None = None,
    ) -> list[NoteRecord]:
        """Notes for an EPUB, optionally filtered by section or chapter."""
        try:
            if nav_id is not None:
                query = _SELECT + (
                    " WHERE n.document_id = ? AND n.nav_id = ?"
                    " ORDER BY n.created_at DESC"
                )
                params: tuple = (document_id, nav_id)
            elif chapter_id is not None:
                query = _SELECT + (
                    " WHERE n.document_id = ? AND n.chapter_id = ?"
                    " ORDER BY n.created_at DESC"
                )
                params = (document_id, chapter_id)
            else:
                query = _SELECT + (
                    " WHERE n.document_id = ? ORDER BY n.chapter_id, n.created_at DESC"
                )
                params = (document_id,)
            rows = self.execute_query(query, params, fetch_all=True)
            return [self._row_to_note(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error getting EPUB notes: {e}")
            return []

    def get_note_by_id(self, note_id: int) -> NoteRecord | None:
        try:
            row = self.execute_query(
                _SELECT + " WHERE n.id = ?", (note_id,), fetch_one=True
            )
            return self._row_to_note(row) if row else None
        except Exception as e:
            logger.error(f"Error getting note: {e}")
            return None

    def delete_note(self, note_id: int) -> bool:
        try:
            deleted = self.execute_update_delete(
                "DELETE FROM document_notes WHERE id = ?", (note_id,)
            )
            if deleted:
                logger.info(f"Deleted note {note_id}")
            return deleted
        except Exception as e:
            logger.error(f"Error deleting note: {e}")
            return False

    def delete_notes_for_document(self, document_id: int) -> bool:
        """Delete all notes for a document. True even when none existed."""
        try:
            self.execute_update_delete(
                "DELETE FROM document_notes WHERE document_id = ?", (document_id,)
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting notes for document {document_id}: {e}")
            return False

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def get_notes_summary(self, doc_type: DocumentType) -> dict[str, NotesSummary]:
        """
        Per-document note statistics for one format, keyed by filename.

        Single query (correlated subquery for the latest title) — replaces
        the old per-document N+1 title lookups.
        """
        try:
            query = """
                SELECT d.filename,
                       COUNT(*) AS notes_count,
                       MAX(n.created_at) AS latest_note_date,
                       (
                           SELECT n2.title FROM document_notes n2
                           WHERE n2.document_id = n.document_id
                           ORDER BY n2.created_at DESC, n2.id DESC
                           LIMIT 1
                       ) AS latest_note_title
                FROM document_notes n
                JOIN documents d ON d.id = n.document_id
                WHERE d.doc_type = ?
                GROUP BY n.document_id
            """
            rows = self.execute_query(query, (doc_type.value,), fetch_all=True)
            if not rows:
                return {}
            return {
                row["filename"]: NotesSummary(
                    notes_count=row["notes_count"],
                    latest_note_date=row["latest_note_date"],
                    latest_note_title=row["latest_note_title"] or "Untitled Note",
                )
                for row in rows
            }
        except Exception as e:
            logger.error(f"Error getting notes summary: {e}")
            return {}

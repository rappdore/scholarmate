"""
One-time data migration to the unified document schema (A-1).

Copies every row from the legacy per-format tables into the unified ones,
remapping the old per-format ids (pdf_documents.id / epub_documents.id,
whose id spaces overlap) to the new documents.id via filename joins, then
drops the legacy tables.

Run once against the live database, after backing it up:

    cd backend && uv run python scripts/migrate_to_unified_documents.py

Safe to delete after it has run; refuses to run twice (the documents table
must be empty).
"""

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_PATH = Path("data/reading_progress.db")

LEGACY_TABLES = [
    "reading_sessions",
    "epub_reading_sessions",
    "highlights",
    "epub_highlights",
    "chat_notes",
    "epub_chat_notes",
    "reading_progress",
    "epub_reading_progress",
    "pdf_documents",
    "epub_documents",
]


def ensure_new_schema(db_path: str) -> None:
    """Create the unified tables exactly the way app startup does."""
    from app.services.documents_repository import DocumentsRepository
    from app.services.highlights_service import HighlightsService
    from app.services.notes_service import NotesService
    from app.services.progress_service import ProgressService
    from app.services.sessions_service import SessionsService

    DocumentsRepository(db_path)
    ProgressService(db_path)
    NotesService(db_path)
    HighlightsService(db_path)
    SessionsService(db_path)


def migrate(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # ---- documents ----
    # The documents table may already hold rows from an app-startup filesystem
    # scan; upsert by filename (keeping any existing id) and prefer the legacy
    # registry's richer metadata + original added_at/last_accessed timestamps.
    _UPSERT_TAIL = """
        ON CONFLICT(filename) DO UPDATE SET
            title=excluded.title, author=excluded.author, subject=excluded.subject,
            num_pages=excluded.num_pages, creator=excluded.creator,
            producer=excluded.producer, chapters=excluded.chapters,
            publisher=excluded.publisher, language=excluded.language,
            file_size=excluded.file_size, file_path=excluded.file_path,
            thumbnail_path=excluded.thumbnail_path,
            created_date=excluded.created_date, modified_date=excluded.modified_date,
            added_at=excluded.added_at, last_accessed=excluded.last_accessed,
            metadata_json=excluded.metadata_json
    """
    cur.execute(
        """
        INSERT INTO documents (
            doc_type, filename, title, author, subject,
            num_pages, creator, producer,
            chapters, publisher, language,
            file_size, file_path, thumbnail_path,
            created_date, modified_date, added_at, last_accessed, metadata_json
        )
        SELECT 'pdf', filename, title, author, subject,
               num_pages, creator, producer,
               NULL, NULL, NULL,
               file_size, file_path, thumbnail_path,
               created_date, modified_date, added_at, last_accessed, metadata_json
        FROM pdf_documents WHERE true
        """
        + _UPSERT_TAIL
    )
    cur.execute(
        """
        INSERT INTO documents (
            doc_type, filename, title, author, subject,
            num_pages, creator, producer,
            chapters, publisher, language,
            file_size, file_path, thumbnail_path,
            created_date, modified_date, added_at, last_accessed, metadata_json
        )
        SELECT 'epub', filename, title, author, subject,
               NULL, NULL, NULL,
               chapters, publisher, language,
               file_size, file_path, thumbnail_path,
               created_date, modified_date, added_at, last_accessed, metadata_json
        FROM epub_documents WHERE true
        """
        + _UPSERT_TAIL
    )

    # ---- progress (filename join; orphans without a registry row are dropped) ----
    cur.execute("""
        INSERT INTO document_progress (
            document_id, last_page, total_pages, progress_percentage,
            last_updated, status, status_updated_at, manually_set
        )
        SELECT d.id, rp.last_page, rp.total_pages,
               CASE WHEN rp.total_pages > 0
                    THEN (rp.last_page * 100.0) / rp.total_pages
                    ELSE 0.0 END,
               rp.last_updated, COALESCE(rp.status, 'new'),
               rp.status_updated_at, COALESCE(rp.manually_set, 0)
        FROM reading_progress rp
        JOIN documents d ON d.filename = rp.pdf_filename AND d.doc_type = 'pdf'
    """)
    cur.execute("""
        INSERT INTO document_progress (
            document_id, current_nav_id, chapter_id, chapter_title,
            scroll_position, total_sections, nav_metadata,
            progress_percentage, last_updated,
            status, status_updated_at, manually_set
        )
        SELECT d.id, ep.current_nav_id, ep.chapter_id, ep.chapter_title,
               COALESCE(ep.scroll_position, 0), ep.total_sections, ep.nav_metadata,
               COALESCE(ep.progress_percentage, 0.0), ep.last_updated,
               COALESCE(ep.status, 'new'), ep.status_updated_at,
               COALESCE(ep.manually_set, 0)
        FROM epub_reading_progress ep
        JOIN documents d ON d.filename = ep.epub_filename AND d.doc_type = 'epub'
    """)

    # ---- notes ----
    cur.execute("""
        INSERT INTO document_notes (
            document_id, page_number, title, chat_content, created_at, updated_at
        )
        SELECT d.id, n.page_number, n.title, n.chat_content, n.created_at, n.updated_at
        FROM chat_notes n
        JOIN documents d ON d.filename = n.pdf_filename AND d.doc_type = 'pdf'
        ORDER BY n.created_at, n.id
    """)
    cur.execute("""
        INSERT INTO document_notes (
            document_id, nav_id, chapter_id, chapter_title,
            scroll_position, context_sections,
            title, chat_content, created_at, updated_at
        )
        SELECT d.id, n.nav_id, n.chapter_id, n.chapter_title,
               COALESCE(n.scroll_position, 0), n.context_sections,
               n.title, n.chat_content, n.created_at, n.updated_at
        FROM epub_chat_notes n
        JOIN documents d ON d.filename = n.epub_filename AND d.doc_type = 'epub'
        ORDER BY n.created_at, n.id
    """)

    # ---- highlights ----
    cur.execute("""
        INSERT INTO document_highlights_pdf (
            document_id, page_number, selected_text, start_offset, end_offset,
            color, coordinates, created_at, updated_at
        )
        SELECT d.id, h.page_number, h.selected_text, h.start_offset, h.end_offset,
               h.color, h.coordinates, h.created_at, h.updated_at
        FROM highlights h
        JOIN documents d ON d.filename = h.pdf_filename AND d.doc_type = 'pdf'
        ORDER BY h.created_at, h.id
    """)
    # epub_highlights are keyed by the OLD epub_documents.id — remap through it
    cur.execute("""
        INSERT INTO document_highlights_epub (
            document_id, nav_id, chapter_id,
            start_xpath, start_offset, end_xpath, end_offset,
            highlight_text, color, created_at
        )
        SELECT d.id, h.nav_id, h.chapter_id,
               h.start_xpath, h.start_offset, h.end_xpath, h.end_offset,
               h.highlight_text, h.color, h.created_at
        FROM epub_highlights h
        JOIN epub_documents old ON old.id = h.epub_id
        JOIN documents d ON d.filename = old.filename AND d.doc_type = 'epub'
        ORDER BY h.created_at, h.id
    """)

    # ---- sessions (PDF avg-per-page becomes total time_spent_seconds) ----
    cur.execute("""
        INSERT INTO document_sessions (
            session_id, document_id, session_start, last_updated,
            units_read, time_spent_seconds
        )
        SELECT s.session_id, d.id, s.session_start, s.last_updated,
               COALESCE(s.pages_read, 0),
               COALESCE(s.pages_read, 0) * COALESCE(s.average_time_per_page, 0.0)
        FROM reading_sessions s
        JOIN pdf_documents old ON old.id = s.pdf_id
        JOIN documents d ON d.filename = old.filename AND d.doc_type = 'pdf'
    """)
    cur.execute("""
        INSERT INTO document_sessions (
            session_id, document_id, session_start, last_updated,
            units_read, time_spent_seconds
        )
        SELECT s.session_id, d.id, s.session_start, s.last_updated,
               COALESCE(s.words_read, 0), COALESCE(s.time_spent_seconds, 0.0)
        FROM epub_reading_sessions s
        JOIN epub_documents old ON old.id = s.epub_id
        JOIN documents d ON d.filename = old.filename AND d.doc_type = 'epub'
    """)


def report(conn: sqlite3.Connection) -> None:
    pairs = [
        ("documents", "pdf_documents + epub_documents"),
        ("document_progress", "reading_progress + epub_reading_progress"),
        ("document_notes", "chat_notes + epub_chat_notes"),
        ("document_highlights_pdf", "highlights"),
        ("document_highlights_epub", "epub_highlights"),
        ("document_sessions", "reading_sessions + epub_reading_sessions"),
    ]
    print("\nMigrated row counts (new <- old):")
    for new, old_desc in pairs:
        count = conn.execute(f"SELECT COUNT(*) FROM {new}").fetchone()[0]
        old_count = sum(
            conn.execute(f"SELECT COUNT(*) FROM {t.strip()}").fetchone()[0]
            for t in old_desc.split("+")
        )
        marker = (
            "" if count == old_count else f"  (old total {old_count} — orphans dropped)"
        )
        print(f"  {new}: {count} <- {old_desc}{marker}")


def main() -> None:
    if not DB_PATH.exists():
        sys.exit(f"Database not found at {DB_PATH} — run from the backend/ directory.")

    backup = DB_PATH.with_name(
        f"{DB_PATH.name}.bak-pre-unified-{datetime.now():%Y%m%d-%H%M%S}"
    )
    shutil.copy2(DB_PATH, backup)
    print(f"Backup written to {backup}")

    ensure_new_schema(str(DB_PATH))

    conn = sqlite3.connect(DB_PATH)
    try:
        # The documents table may legitimately be pre-populated by an app
        # startup scan; the domain tables must be empty, though — non-empty
        # means this migration already ran.
        for table in (
            "document_progress",
            "document_notes",
            "document_highlights_pdf",
            "document_highlights_epub",
            "document_sessions",
        ):
            existing = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if existing:
                sys.exit(
                    f"{table} already has {existing} rows — refusing to "
                    "migrate twice. Restore the backup first if you need a re-run."
                )

        conn.execute("BEGIN")
        migrate(conn)
        report(conn)

        for table in LEGACY_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        conn.execute("VACUUM")
        print("\nLegacy tables dropped. Migration complete.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

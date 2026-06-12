"""
Documents Repository - unified database-backed document registry (A-1).

Manages the ``documents`` table, which is the single registry for every
document the app knows about regardless of format. It replaces the former
``pdf_documents`` and ``epub_documents`` twins (91% duplicated). The
CREATE TABLE statement here is the single source of truth for the schema.
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager

from app.models.documents import (
    DocumentRecord,
    DocumentType,
    DocumentUpsert,
    EpubDocumentUpsert,
)

logger = logging.getLogger(__name__)


class DocumentsRepository:
    """CRUD operations for the unified ``documents`` registry."""

    def __init__(self, db_path: str = "data/reading_progress.db"):
        self.db_path = db_path
        data_dir = os.path.dirname(db_path)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
        self._init_table()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_table(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_type TEXT NOT NULL CHECK (doc_type IN ('pdf', 'epub')),
                    filename TEXT NOT NULL UNIQUE,

                    -- Shared metadata
                    title TEXT,
                    author TEXT,
                    subject TEXT,

                    -- PDF-specific (NULL for EPUBs)
                    num_pages INTEGER,
                    creator TEXT,
                    producer TEXT,

                    -- EPUB-specific (NULL for PDFs)
                    chapters INTEGER,
                    publisher TEXT,
                    language TEXT,

                    -- File information
                    file_size INTEGER,
                    file_path TEXT,
                    thumbnail_path TEXT,

                    -- Timestamps
                    created_date TEXT,          -- ISO format datetime from filesystem
                    modified_date TEXT,         -- ISO format datetime from filesystem
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- Extensibility
                    metadata_json TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_doc_type
                ON documents(doc_type)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_accessed
                ON documents(last_accessed)
            """)

            conn.commit()

    def get_by_filename(self, filename: str) -> DocumentRecord | None:
        """Get a document by its (globally unique) filename."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE filename = ?", (filename,)
            ).fetchone()
            return DocumentRecord(**dict(row)) if row else None

    def get_by_id(
        self, document_id: int, doc_type: DocumentType | None = None
    ) -> DocumentRecord | None:
        """
        Get a document by id.

        When ``doc_type`` is given, a document of a different type returns
        None — format-specific routes use this so a PDF id can't resolve to
        an EPUB and vice versa.
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            if row is None:
                return None
            record = DocumentRecord(**dict(row))
            if doc_type is not None and record.doc_type != doc_type:
                return None
            return record

    def upsert(self, data: DocumentUpsert) -> int:
        """
        Create or update a document record (idempotent, keyed by filename).

        Returns:
            The document id (integer primary key).
        """
        metadata_json = json.dumps(data.metadata) if data.metadata else None
        is_epub = isinstance(data, EpubDocumentUpsert)
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents (
                    doc_type, filename, title, author, subject,
                    num_pages, creator, producer,
                    chapters, publisher, language,
                    file_size, file_path, thumbnail_path,
                    created_date, modified_date, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    doc_type=excluded.doc_type,
                    title=excluded.title,
                    author=excluded.author,
                    subject=excluded.subject,
                    num_pages=excluded.num_pages,
                    creator=excluded.creator,
                    producer=excluded.producer,
                    chapters=excluded.chapters,
                    publisher=excluded.publisher,
                    language=excluded.language,
                    file_size=excluded.file_size,
                    file_path=excluded.file_path,
                    thumbnail_path=excluded.thumbnail_path,
                    created_date=excluded.created_date,
                    modified_date=excluded.modified_date,
                    metadata_json=excluded.metadata_json,
                    last_accessed=CURRENT_TIMESTAMP
                RETURNING id
                """,
                (
                    data.doc_type.value,
                    data.filename,
                    data.title,
                    data.author,
                    data.subject,
                    None if is_epub else data.num_pages,
                    None if is_epub else data.creator,
                    None if is_epub else data.producer,
                    data.chapters if is_epub else None,
                    data.publisher if is_epub else None,
                    data.language if is_epub else None,
                    data.file_size,
                    data.file_path,
                    data.thumbnail_path,
                    data.created_date,
                    data.modified_date,
                    metadata_json,
                ),
            )
            document_id = cursor.fetchone()["id"]
            conn.commit()
            logger.info(
                "Saved %s document: %s (ID: %s)",
                data.doc_type.value,
                data.filename,
                document_id,
            )
            return document_id

    def update_last_accessed(self, document_id: int) -> None:
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE documents SET last_accessed = CURRENT_TIMESTAMP WHERE id = ?",
                (document_id,),
            )
            conn.commit()

    def delete_by_filename(self, filename: str) -> bool:
        """Delete a document by filename. Returns True if a row was deleted."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM documents WHERE filename = ?", (filename,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_all(self, doc_type: DocumentType | None = None) -> list[DocumentRecord]:
        """List documents (optionally one format), most recently accessed first."""
        with self.get_connection() as conn:
            if doc_type is None:
                rows = conn.execute(
                    "SELECT * FROM documents ORDER BY last_accessed DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE doc_type = ? "
                    "ORDER BY last_accessed DESC",
                    (doc_type.value,),
                ).fetchall()
            return [DocumentRecord(**dict(row)) for row in rows]

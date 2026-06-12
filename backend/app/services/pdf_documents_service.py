"""
PDF Documents Service - Database-backed PDF registry

This service manages the pdf_documents table and provides persistent storage
for PDF metadata. It replaces the in-memory-only cache with a database-backed
solution that persists across service restarts.

Part of Phase 1a: PDF Cache Database Backing
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager

from app.models.pdf_responses import PDFDocumentRecord

logger = logging.getLogger(__name__)


class PDFDocumentsService:
    """
    Service for managing the pdf_documents table.

    This service provides CRUD operations and filesystem sync functionality
    for the PDF documents registry. It serves as the persistent backend for
    the PDF cache.
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the PDF Documents Service.

        Args:
            db_path: Path to the SQLite database file
        """
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
        """
        Initialize the pdf_documents table and indexes.

        This service owns the pdf_documents schema; the CREATE TABLE statement
        is the single source of truth for it.
        """
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pdf_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL UNIQUE,

                    -- Basic metadata (loaded on cache initialization)
                    title TEXT,
                    author TEXT,
                    num_pages INTEGER NOT NULL,

                    -- Extended metadata (lazy-loaded on first request)
                    subject TEXT,
                    creator TEXT,
                    producer TEXT,

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
                    metadata_json TEXT          -- Full PDF metadata as JSON for future use
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pdf_documents_filename
                ON pdf_documents(filename)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pdf_documents_accessed
                ON pdf_documents(last_accessed)
            """)

            conn.commit()

    def get_by_filename(self, filename: str) -> PDFDocumentRecord | None:
        """
        Get PDF document by filename.

        Args:
            filename: Name of the PDF file

        Returns:
            PDFDocumentRecord with PDF metadata, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM pdf_documents WHERE filename = ?
                """,
                (filename,),
            )
            row = cursor.fetchone()
            if row:
                return PDFDocumentRecord(**dict(row))
            return None

    def get_by_id(self, pdf_id: int) -> PDFDocumentRecord | None:
        """
        Get PDF document by ID.

        Args:
            pdf_id: Unique identifier of the PDF document

        Returns:
            PDFDocumentRecord with PDF metadata, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM pdf_documents WHERE id = ?
                """,
                (pdf_id,),
            )
            row = cursor.fetchone()
            if row:
                return PDFDocumentRecord(**dict(row))
            return None

    def create_or_update(
        self,
        filename: str,
        num_pages: int,
        title: str | None = None,
        author: str | None = None,
        subject: str | None = None,
        creator: str | None = None,
        producer: str | None = None,
        file_size: int | None = None,
        file_path: str | None = None,
        thumbnail_path: str | None = None,
        created_date: str | None = None,
        modified_date: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """
        Create new PDF document record or update existing one.
        This method is idempotent - safe to call multiple times.

        Args:
            filename: PDF filename (unique identifier)
            num_pages: Total number of pages in the PDF
            title: PDF title from metadata
            author: PDF author from metadata
            subject: PDF subject from metadata
            creator: PDF creator application
            producer: PDF producer application
            file_size: File size in bytes
            file_path: Full path to PDF file
            thumbnail_path: Path to thumbnail image
            created_date: File creation date (ISO format)
            modified_date: File modification date (ISO format)
            metadata: Full metadata dictionary for extensibility

        Returns:
            The pdf_id (integer primary key)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            metadata_json = json.dumps(metadata) if metadata else None

            # Use UPSERT for atomic insert-or-update (concurrency-safe)
            cursor.execute(
                """
                INSERT INTO pdf_documents (
                    filename, title, author, subject, creator, producer, num_pages,
                    file_size, file_path, thumbnail_path, created_date, modified_date, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    title=excluded.title,
                    author=excluded.author,
                    subject=excluded.subject,
                    creator=excluded.creator,
                    producer=excluded.producer,
                    num_pages=excluded.num_pages,
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
                    filename,
                    title,
                    author,
                    subject,
                    creator,
                    producer,
                    num_pages,
                    file_size,
                    file_path,
                    thumbnail_path,
                    created_date,
                    modified_date,
                    metadata_json,
                ),
            )
            pdf_id = cursor.fetchone()["id"]
            conn.commit()
            logger.info(f"Saved PDF document: {filename} (ID: {pdf_id})")
            return pdf_id

    def update_last_accessed(self, pdf_id: int):
        """
        Update the last_accessed timestamp for a PDF document.

        Args:
            pdf_id: Unique identifier of the PDF document
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE pdf_documents
                SET last_accessed = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (pdf_id,),
            )
            conn.commit()

    def delete_by_filename(self, filename: str) -> bool:
        """
        Delete PDF document by filename.

        Args:
            filename: Name of the PDF file to delete

        Returns:
            True if a document was deleted, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pdf_documents WHERE filename = ?", (filename,))
            conn.commit()
            return cursor.rowcount > 0

    def list_all(self) -> list[PDFDocumentRecord]:
        """
        List all PDF documents in the registry.

        Returns:
            List of PDFDocumentRecord containing PDF metadata,
            sorted by last_accessed (most recent first)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM pdf_documents
                ORDER BY last_accessed DESC
                """
            )
            return [PDFDocumentRecord(**dict(row)) for row in cursor.fetchall()]

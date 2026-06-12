"""
EPUB Documents Service - Database-backed EPUB registry

This service manages the epub_documents table and provides persistent storage
for EPUB metadata. It replaces the in-memory-only cache with a database-backed
solution that persists across service restarts.

Part of Phase 1b: EPUB Cache Database Backing
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class EPUBDocumentsService:
    """
    Service for managing the epub_documents table.

    This service provides CRUD operations and filesystem sync functionality
    for the EPUB documents registry. It serves as the persistent backend for
    the EPUB cache.
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the EPUB Documents Service.

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
        Initialize the epub_documents table and indexes.

        This service owns the epub_documents schema; the CREATE TABLE statement
        is the single source of truth for it.
        """
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS epub_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL UNIQUE,

                    -- Basic metadata (loaded on cache initialization)
                    title TEXT,
                    author TEXT,
                    chapters INTEGER NOT NULL DEFAULT 0,

                    -- Extended metadata (lazy-loaded on first request)
                    subject TEXT,
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
                    metadata_json TEXT          -- Full EPUB metadata as JSON for future use
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_documents_filename
                ON epub_documents(filename)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_documents_accessed
                ON epub_documents(last_accessed)
            """)

            conn.commit()

    def get_by_filename(self, filename: str) -> dict | None:
        """
        Get EPUB document by filename.

        Args:
            filename: Name of the EPUB file

        Returns:
            Dictionary with EPUB metadata, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM epub_documents WHERE filename = ?
                """,
                (filename,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_by_id(self, epub_id: int) -> dict | None:
        """
        Get EPUB document by ID.

        Args:
            epub_id: Unique identifier of the EPUB document

        Returns:
            Dictionary with EPUB metadata, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM epub_documents WHERE id = ?
                """,
                (epub_id,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def create_or_update(
        self,
        filename: str,
        chapters: int,
        title: str | None = None,
        author: str | None = None,
        subject: str | None = None,
        publisher: str | None = None,
        language: str | None = None,
        file_size: int | None = None,
        file_path: str | None = None,
        thumbnail_path: str | None = None,
        created_date: str | None = None,
        modified_date: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """
        Create new EPUB document record or update existing one.
        This method is idempotent - safe to call multiple times.

        Args:
            filename: EPUB filename (unique identifier)
            chapters: Total number of chapters in the EPUB
            title: EPUB title from metadata
            author: EPUB author from metadata
            subject: EPUB subject/tags from metadata
            publisher: EPUB publisher from metadata
            language: EPUB language from metadata
            file_size: File size in bytes
            file_path: Full path to EPUB file
            thumbnail_path: Path to thumbnail image
            created_date: File creation date (ISO format)
            modified_date: File modification date (ISO format)
            metadata: Full metadata dictionary for extensibility

        Returns:
            The epub_id (integer primary key)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            metadata_json = json.dumps(metadata) if metadata else None

            # Use UPSERT for atomic insert-or-update (concurrency-safe)
            cursor.execute(
                """
                INSERT INTO epub_documents (
                    filename, title, author, subject, publisher, language, chapters,
                    file_size, file_path, thumbnail_path, created_date, modified_date, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    title=excluded.title,
                    author=excluded.author,
                    subject=excluded.subject,
                    publisher=excluded.publisher,
                    language=excluded.language,
                    chapters=excluded.chapters,
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
                    publisher,
                    language,
                    chapters,
                    file_size,
                    file_path,
                    thumbnail_path,
                    created_date,
                    modified_date,
                    metadata_json,
                ),
            )
            epub_id = cursor.fetchone()["id"]
            conn.commit()
            logger.info(f"Saved EPUB document: {filename} (ID: {epub_id})")
            return epub_id

    def update_last_accessed(self, epub_id: int):
        """
        Update the last_accessed timestamp for an EPUB document.

        Args:
            epub_id: Unique identifier of the EPUB document
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE epub_documents
                SET last_accessed = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (epub_id,),
            )
            conn.commit()

    def delete_by_filename(self, filename: str) -> bool:
        """
        Delete EPUB document by filename.

        Args:
            filename: Name of the EPUB file to delete

        Returns:
            True if a document was deleted, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM epub_documents WHERE filename = ?", (filename,))
            conn.commit()
            return cursor.rowcount > 0

    def list_all(self) -> list[dict]:
        """
        List all EPUB documents in the registry.

        Returns:
            List of dictionaries containing EPUB metadata,
            sorted by last_accessed (most recent first)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM epub_documents
                ORDER BY last_accessed DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

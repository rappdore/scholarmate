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
from pathlib import Path
from typing import Dict, List, Optional

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

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def get_by_filename(self, filename: str) -> Optional[Dict]:
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

    def get_by_id(self, epub_id: int) -> Optional[Dict]:
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
        title: Optional[str] = None,
        author: Optional[str] = None,
        subject: Optional[str] = None,
        publisher: Optional[str] = None,
        language: Optional[str] = None,
        file_size: Optional[int] = None,
        file_path: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
        created_date: Optional[str] = None,
        modified_date: Optional[str] = None,
        metadata: Optional[Dict] = None,
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

    def list_all(self) -> List[Dict]:
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

    def sync_from_filesystem(self, epubs_dir: str) -> Dict[str, int]:
        """
        Sync database with filesystem.

        This method:
        - Adds new EPUBs found in filesystem to database
        - Updates metadata for existing EPUBs
        - Removes EPUBs from database that no longer exist in filesystem

        Args:
            epubs_dir: Directory containing EPUB files

        Returns:
            Dictionary with sync statistics:
            {'added': count, 'removed': count, 'updated': count}
        """
        # Import here to avoid circular dependency
        from .epub_service import EPUBService

        epub_service = EPUBService(epub_dir=epubs_dir, db_path=self.db_path)
        stats = {"added": 0, "removed": 0, "updated": 0}

        # Get all EPUBs from filesystem
        epubs_path = Path(epubs_dir)
        filesystem_epubs = {f.name for f in epubs_path.glob("*.epub")}

        # Get all EPUBs from database
        db_epubs = {doc["filename"]: doc["id"] for doc in self.list_all()}

        # Add/update EPUBs from filesystem
        for epub_filename in filesystem_epubs:
            try:
                # Get EPUB metadata
                epub_info = epub_service.cache.get_epub_info(epub_filename)
                file_path = epubs_path / epub_filename
                file_size = os.path.getsize(file_path) if file_path.exists() else None

                # Get thumbnail path if it exists
                thumbnail_path = None
                try:
                    thumb_path = epub_service.cache.get_thumbnail_path(epub_filename)
                    thumbnail_path = str(thumb_path) if thumb_path else None
                except Exception:
                    pass  # Thumbnail may not exist yet

                is_new = epub_filename not in db_epubs
                self.create_or_update(
                    filename=epub_filename,
                    chapters=epub_info.get("chapters", 0),
                    title=epub_info.get("title"),
                    author=epub_info.get("author"),
                    subject=epub_info.get("subject", ""),
                    publisher=epub_info.get("publisher", ""),
                    language=epub_info.get("language", ""),
                    file_size=file_size,
                    file_path=str(file_path),
                    thumbnail_path=thumbnail_path,
                    created_date=epub_info.get("created_date"),
                    modified_date=epub_info.get("modified_date"),
                    metadata=epub_info,
                )

                if is_new:
                    stats["added"] += 1
                else:
                    stats["updated"] += 1

            except Exception as e:
                logger.error(f"Error syncing EPUB {epub_filename}: {e}")

        # Remove EPUBs from database that no longer exist
        for db_filename, epub_id in db_epubs.items():
            if db_filename not in filesystem_epubs:
                self.delete_by_filename(db_filename)
                stats["removed"] += 1
                logger.info(f"Removed missing EPUB from DB: {db_filename}")

        logger.info(
            f"Filesystem sync complete: {stats['added']} added, "
            f"{stats['updated']} updated, {stats['removed']} removed"
        )
        return stats

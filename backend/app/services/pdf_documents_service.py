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
from pathlib import Path
from typing import Dict, List, Optional

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
        Create a PDFDocumentsService configured to use the specified SQLite database file.
        
        Parameters:
            db_path (str): Filesystem path to the SQLite database used to store PDF metadata.
        """
        self.db_path = db_path

    @contextmanager
    def get_connection(self):
        """
        Provide a context-managed SQLite connection to the service's database.
        
        The yielded connection has its row_factory set to sqlite3.Row so rows support dict-like access. The connection is automatically closed when exiting the context.
        
        Returns:
            sqlite3.Connection: An open SQLite connection configured for dict-like row access.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def get_by_filename(self, filename: str) -> Optional[Dict]:
        """
        Retrieve the PDF document record matching the given filename.
        
        Returns:
            dict: PDF metadata as a dictionary if a matching record exists, `None` otherwise.
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
                return dict(row)
            return None

    def get_by_id(self, pdf_id: int) -> Optional[Dict]:
        """
        Get a PDF document record by its database id.
        
        Returns:
            dict: PDF metadata keyed by column name if found, `None` otherwise.
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
                return dict(row)
            return None

    def create_or_update(
        self,
        filename: str,
        num_pages: int,
        title: Optional[str] = None,
        author: Optional[str] = None,
        subject: Optional[str] = None,
        creator: Optional[str] = None,
        producer: Optional[str] = None,
        file_size: Optional[int] = None,
        file_path: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
        created_date: Optional[str] = None,
        modified_date: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> int:
        """
        Create a new PDF document record or update an existing record identified by filename.
        
        Parameters:
            filename (str): Unique PDF filename used to identify the record.
            num_pages (int): Total number of pages in the PDF.
            title (Optional[str]): PDF title from metadata.
            author (Optional[str]): PDF author from metadata.
            subject (Optional[str]): PDF subject from metadata.
            creator (Optional[str]): PDF creator application.
            producer (Optional[str]): PDF producer application.
            file_size (Optional[int]): File size in bytes.
            file_path (Optional[str]): Full filesystem path to the PDF.
            thumbnail_path (Optional[str]): Filesystem path to the thumbnail image, if available.
            created_date (Optional[str]): File creation date (ISO format), if known.
            modified_date (Optional[str]): File modification date (ISO format), if known.
            metadata (Optional[Dict]): Arbitrary metadata that will be stored as a JSON blob.
        
        Returns:
            int: The primary key (`id`) of the created or updated PDF document.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Check if document exists
            cursor.execute(
                "SELECT id FROM pdf_documents WHERE filename = ?", (filename,)
            )
            existing = cursor.fetchone()

            metadata_json = json.dumps(metadata) if metadata else None

            if existing:
                # Update existing record
                pdf_id = existing["id"]
                cursor.execute(
                    """
                    UPDATE pdf_documents
                    SET title = ?, author = ?, subject = ?, creator = ?, producer = ?,
                        num_pages = ?, file_size = ?, file_path = ?, thumbnail_path = ?,
                        created_date = ?, modified_date = ?, metadata_json = ?,
                        last_accessed = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
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
                        pdf_id,
                    ),
                )
                logger.info(f"Updated PDF document: {filename} (ID: {pdf_id})")
            else:
                # Insert new record
                cursor.execute(
                    """
                    INSERT INTO pdf_documents
                    (filename, title, author, subject, creator, producer, num_pages,
                     file_size, file_path, thumbnail_path, created_date, modified_date, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                pdf_id = cursor.lastrowid
                logger.info(f"Created PDF document: {filename} (ID: {pdf_id})")

            conn.commit()
            return pdf_id

    def update_last_accessed(self, pdf_id: int):
        """
        Updates the last_accessed timestamp for the PDF document with the given id.
        
        Parameters:
            pdf_id (int): Identifier of the PDF document whose last_accessed will be set to the current time.
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
        Delete the PDF document record with the given filename from the database.
        
        Parameters:
            filename (str): Filename of the PDF to remove.
        
        Returns:
            bool: `True` if a document was deleted, `False` otherwise.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pdf_documents WHERE filename = ?", (filename,))
            conn.commit()
            return cursor.rowcount > 0

    def list_all(self) -> List[Dict]:
        """
        Retrieve all PDF document records ordered by most recently accessed.
        
        Returns:
            List[Dict]: A list of dictionaries representing rows from `pdf_documents`, ordered by `last_accessed` descending.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM pdf_documents
                ORDER BY last_accessed DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def sync_from_filesystem(self, pdfs_dir: str) -> Dict[str, int]:
        """
        Sync database with filesystem.

        This method:
        - Adds new PDFs found in filesystem to database
        - Updates metadata for existing PDFs
        - Removes PDFs from database that no longer exist in filesystem

        Args:
            pdfs_dir: Directory containing PDF files

        Returns:
            Dictionary with sync statistics:
            {'added': count, 'removed': count, 'updated': count}
        """
        # Import here to avoid circular dependency
        from .pdf_service import PDFService

        pdf_service = PDFService()
        stats = {"added": 0, "removed": 0, "updated": 0}

        # Get all PDFs from filesystem
        pdfs_path = Path(pdfs_dir)
        filesystem_pdfs = {f.name for f in pdfs_path.glob("*.pdf")}

        # Get all PDFs from database
        db_pdfs = {doc["filename"]: doc["id"] for doc in self.list_all()}

        # Add/update PDFs from filesystem
        for pdf_filename in filesystem_pdfs:
            try:
                # Get PDF metadata
                pdf_info = pdf_service.cache.get_pdf_info(pdf_filename)
                file_path = pdfs_path / pdf_filename
                file_size = os.path.getsize(file_path) if file_path.exists() else None

                # Get thumbnail path if it exists
                thumbnail_path = None
                try:
                    thumb_path = pdf_service.cache.get_thumbnail_path(pdf_filename)
                    thumbnail_path = str(thumb_path) if thumb_path else None
                except Exception:
                    pass  # Thumbnail may not exist yet

                is_new = pdf_filename not in db_pdfs
                self.create_or_update(
                    filename=pdf_filename,
                    num_pages=pdf_info["num_pages"],
                    title=pdf_info.get("title"),
                    author=pdf_info.get("author"),
                    subject=pdf_info.get("subject", ""),
                    creator=pdf_info.get("creator", ""),
                    producer=pdf_info.get("producer", ""),
                    file_size=file_size,
                    file_path=str(file_path),
                    thumbnail_path=thumbnail_path,
                    created_date=pdf_info.get("created_date"),
                    modified_date=pdf_info.get("modified_date"),
                    metadata=pdf_info,
                )

                if is_new:
                    stats["added"] += 1
                else:
                    stats["updated"] += 1

            except Exception as e:
                logger.error(f"Error syncing PDF {pdf_filename}: {e}")

        # Remove PDFs from database that no longer exist
        for db_filename, pdf_id in db_pdfs.items():
            if db_filename not in filesystem_pdfs:
                self.delete_by_filename(db_filename)
                stats["removed"] += 1
                logger.info(f"Removed missing PDF from DB: {db_filename}")

        logger.info(
            f"Filesystem sync complete: {stats['added']} added, "
            f"{stats['updated']} updated, {stats['removed']} removed"
        )
        return stats
"""
EPUB Reading Progress Service Module

This module provides specialized database operations for managing EPUB reading progress.
It handles tracking navigation position, scroll position, and reading status for EPUB documents.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .base_database_service import BaseDatabaseService
from .epub_documents_service import EPUBDocumentsService

# Configure logger for this module
logger = logging.getLogger(__name__)


class EPUBProgressService(BaseDatabaseService):
    """
    Service class for managing EPUB reading progress using SQLite.

    This class provides database operations for storing and retrieving:
    - Navigation position tracking (current section, chapter info)
    - Scroll position within current section
    - Overall book progress percentage
    - Book status tracking (new, reading, finished)
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the EPUB progress service.

        Args:
            db_path (str): Path to the SQLite database file
        """
        super().__init__(db_path)
        # Phase 2b: Initialize EPUB documents service for epub_id lookups
        self._epub_docs_service = EPUBDocumentsService(db_path)
        self._init_table()

    def _init_table(self):
        """
        Initialize the EPUB progress table and indexes.
        """
        with self.get_connection() as conn:
            # Create EPUB reading progress table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS epub_reading_progress (
                    epub_filename TEXT PRIMARY KEY,           -- Unique identifier for each EPUB
                    current_nav_id TEXT NOT NULL,             -- Current finest navigation section
                    chapter_id TEXT,                          -- Chapter-level ID for display
                    chapter_title TEXT,                       -- Chapter title for UI display
                    scroll_position INTEGER DEFAULT 0,       -- Scroll position within current section
                    total_sections INTEGER,                   -- Total navigation sections in book
                    progress_percentage REAL DEFAULT 0.0,    -- Overall book progress (0.0-100.0)
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- Book Status Management (same as PDF system)
                    status TEXT DEFAULT 'new' CHECK (status IN ('new', 'reading', 'finished')),
                    status_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    manually_set BOOLEAN DEFAULT FALSE,      -- Whether status was manually set by user

                    -- EPUB-specific metadata for progress calculation
                    nav_metadata TEXT                         -- JSON metadata about navigation structure
                )
            """)

            # Phase 2b: Add epub_id column if it doesn't exist (backward compatible migration)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(epub_reading_progress)")
            columns = [column[1] for column in cursor.fetchall()]

            if "epub_id" not in columns:
                logger.info("Adding epub_id column to epub_reading_progress table...")
                conn.execute(
                    "ALTER TABLE epub_reading_progress ADD COLUMN epub_id INTEGER"
                )
                logger.info("epub_id column added successfully")

            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_progress_status
                ON epub_reading_progress(status)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_progress_updated
                ON epub_reading_progress(status, status_updated_at)
            """)

            # Phase 2b: Create index on epub_id if it doesn't exist
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_epub_progress_epub_id
                ON epub_reading_progress(epub_id)
            """)

            conn.commit()

    def _get_epub_id(self, epub_filename: str) -> Optional[int]:
        """
        Get the epub_id for a given EPUB filename.

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

    def save_progress(
        self,
        epub_filename: str,
        current_nav_id: str,
        chapter_id: str = None,
        chapter_title: str = None,
        scroll_position: int = 0,
        total_sections: int = None,
        progress_percentage: float = 0.0,
        nav_metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Save or update reading progress for an EPUB document.

        Args:
            epub_filename (str): Name of the EPUB file (used as unique identifier)
            current_nav_id (str): Current finest navigation section ID
            chapter_id (str): Chapter-level ID for display purposes
            chapter_title (str): Chapter title for UI display
            scroll_position (int): Scroll position within current section
            total_sections (int): Total number of navigation sections in book
            progress_percentage (float): Overall book progress (0.0-100.0)
            nav_metadata (Dict[str, Any]): Navigation metadata for progress calculation

        Returns:
            bool: True if the operation was successful, False otherwise
        """
        try:
            # Phase 2b: Look up epub_id for this filename
            epub_id = self._get_epub_id(epub_filename)

            # Convert metadata to JSON string
            nav_metadata_json = json.dumps(nav_metadata) if nav_metadata else None

            # Check if record exists
            existing = self.get_progress(epub_filename)

            if existing:
                # Update existing record, preserving status fields unless auto-updating
                # Phase 2b: Also update epub_id if it's not set
                query = """
                    UPDATE epub_reading_progress
                    SET current_nav_id = ?, chapter_id = ?, chapter_title = ?,
                        scroll_position = ?, total_sections = ?, progress_percentage = ?,
                        nav_metadata = ?, last_updated = ?, epub_id = ?
                    WHERE epub_filename = ?
                """
                params = (
                    current_nav_id,
                    chapter_id,
                    chapter_title,
                    scroll_position,
                    total_sections,
                    progress_percentage,
                    nav_metadata_json,
                    self.get_current_timestamp(),
                    epub_id,
                    epub_filename,
                )
                result = self.execute_update_delete(query, params)

                # Auto-update status based on progress if not manually set
                if existing.get("manually_set", False) is False:
                    self._auto_update_status_based_on_progress(
                        epub_filename, progress_percentage
                    )
            else:
                # Insert new record with default status values
                # Phase 2b: Include epub_id in insert
                query = """
                    INSERT INTO epub_reading_progress
                    (epub_filename, current_nav_id, chapter_id, chapter_title,
                     scroll_position, total_sections, progress_percentage, nav_metadata,
                     last_updated, status, status_updated_at, manually_set, epub_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    epub_filename,
                    current_nav_id,
                    chapter_id,
                    chapter_title,
                    scroll_position,
                    total_sections,
                    progress_percentage,
                    nav_metadata_json,
                    self.get_current_timestamp(),
                    "reading"
                    if progress_percentage > 0
                    else "new",  # Auto-set initial status
                    self.get_current_timestamp(),
                    False,  # Default manually_set for new records
                    epub_id,  # Phase 2b: Auto-populate epub_id
                )
                result = self.execute_insert(query, params)

            if result is not None:
                logger.info(
                    f"Saved EPUB progress for {epub_filename}: {current_nav_id} ({progress_percentage:.1f}%)"
                    + (f" (epub_id: {epub_id})" if epub_id else "")
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error saving EPUB progress: {e}")
            return False

    def _auto_update_status_based_on_progress(
        self, epub_filename: str, progress_percentage: float
    ):
        """
        Auto-update book status based on progress percentage if not manually set.
        """
        try:
            # Determine new status based on progress
            if progress_percentage >= 95.0:
                new_status = "finished"
            elif progress_percentage > 0:
                new_status = "reading"
            else:
                new_status = "new"

            # Only update if status is not manually set
            query = """
                UPDATE epub_reading_progress
                SET status = ?, status_updated_at = ?
                WHERE epub_filename = ? AND manually_set = FALSE
            """
            params = (new_status, self.get_current_timestamp(), epub_filename)
            self.execute_update_delete(query, params)

        except Exception as e:
            logger.error(f"Error auto-updating status for {epub_filename}: {e}")

    def get_progress(self, epub_filename: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve reading progress for a specific EPUB document.

        Args:
            epub_filename (str): Name of the EPUB file to get progress for

        Returns:
            Optional[Dict[str, Any]]: Dictionary containing progress information or None
        """
        try:
            # Phase 2b: Include epub_id in SELECT
            query = """
                SELECT epub_filename, current_nav_id, chapter_id, chapter_title,
                       scroll_position, total_sections, progress_percentage,
                       last_updated, status, status_updated_at, manually_set, nav_metadata, epub_id
                FROM epub_reading_progress
                WHERE epub_filename = ?
            """
            row = self.execute_query(query, (epub_filename,), fetch_one=True)

            if row:
                # Parse nav_metadata JSON
                nav_metadata = None
                if row[11]:  # nav_metadata field
                    try:
                        nav_metadata = json.loads(row[11])
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid nav_metadata JSON for {epub_filename}")

                return {
                    "epub_filename": row[0],
                    "current_nav_id": row[1],
                    "chapter_id": row[2],
                    "chapter_title": row[3],
                    "scroll_position": row[4],
                    "total_sections": row[5],
                    "progress_percentage": row[6],
                    "last_updated": row[7],
                    "status": row[8] if row[8] else "new",
                    "status_updated_at": row[9],
                    "manually_set": bool(row[10]) if row[10] is not None else False,
                    "nav_metadata": nav_metadata,
                    "epub_id": row[12]
                    if len(row) > 12
                    else None,  # Phase 2b: Include epub_id
                }
            return None
        except Exception as e:
            logger.error(f"Error getting EPUB progress: {e}")
            return None

    def get_all_progress(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve reading progress for all EPUB documents.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping EPUB filenames to their progress info
        """
        try:
            # Phase 2b: Include epub_id in SELECT
            query = """
                SELECT epub_filename, current_nav_id, chapter_id, chapter_title,
                       scroll_position, total_sections, progress_percentage,
                       last_updated, status, status_updated_at, manually_set, nav_metadata, epub_id
                FROM epub_reading_progress
                ORDER BY last_updated DESC
            """
            rows = self.execute_query(query, fetch_all=True)

            progress = {}
            if rows:
                for row in rows:
                    # Parse nav_metadata JSON
                    nav_metadata = None
                    if row[11]:  # nav_metadata field
                        try:
                            nav_metadata = json.loads(row[11])
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid nav_metadata JSON for {row[0]}")

                    progress[row[0]] = {
                        "current_nav_id": row[1],
                        "chapter_id": row[2],
                        "chapter_title": row[3],
                        "scroll_position": row[4],
                        "total_sections": row[5],
                        "progress_percentage": row[6],
                        "last_updated": row[7],
                        "status": row[8] if row[8] else "new",
                        "status_updated_at": row[9],
                        "manually_set": bool(row[10]) if row[10] is not None else False,
                        "nav_metadata": nav_metadata,
                        "epub_id": row[12]
                        if len(row) > 12
                        else None,  # Phase 2b: Include epub_id
                    }
            return progress
        except Exception as e:
            logger.error(f"Error getting all EPUB progress: {e}")
            return {}

    def update_book_status(
        self, epub_filename: str, status: str, manual: bool = True
    ) -> bool:
        """
        Update the reading status of an EPUB book.

        Args:
            epub_filename (str): Name of the EPUB file to update status for
            status (str): New status ('new', 'reading', 'finished')
            manual (bool): Whether this status was manually set by the user

        Returns:
            bool: True if the operation was successful, False otherwise
        """
        try:
            # Validate status
            valid_statuses = ["new", "reading", "finished"]
            if status not in valid_statuses:
                logger.error(
                    f"Invalid status '{status}'. Must be one of: {valid_statuses}"
                )
                return False

            # Phase 2b: Look up epub_id for this filename
            epub_id = self._get_epub_id(epub_filename)

            # Check if record exists
            existing = self.get_progress(epub_filename)
            current_time = self.get_current_timestamp()

            if existing:
                # Update existing record
                # Phase 2b: Also update epub_id if it's not set
                query = """
                    UPDATE epub_reading_progress
                    SET status = ?, status_updated_at = ?, manually_set = ?, epub_id = ?
                    WHERE epub_filename = ?
                """
                params = (status, current_time, manual, epub_id, epub_filename)
                result = self.execute_update_delete(query, params)
            else:
                # Create new record with minimal data
                # Phase 2b: Include epub_id in insert
                query = """
                    INSERT INTO epub_reading_progress
                    (epub_filename, current_nav_id, status, status_updated_at, manually_set, last_updated, epub_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    epub_filename,
                    "start",  # Default nav_id for new records
                    status,
                    current_time,
                    manual,
                    current_time,
                    epub_id,  # Phase 2b: Auto-populate epub_id
                )
                result = self.execute_insert(query, params)

            if result is not None:
                logger.info(
                    f"Updated EPUB status for {epub_filename}: {status}"
                    + (f" (epub_id: {epub_id})" if epub_id else "")
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating EPUB book status: {e}")
            return False

    def get_books_by_status(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all EPUB books filtered by status.

        Args:
            status (Optional[str]): Filter by specific status ('new', 'reading', 'finished').
                                   If None, returns all books.

        Returns:
            List[Dict[str, Any]]: List of EPUB books with their progress and status information
        """
        try:
            if status:
                # Phase 2b: Include epub_id in SELECT
                query = """
                    SELECT epub_filename, current_nav_id, chapter_id, chapter_title,
                           scroll_position, total_sections, progress_percentage,
                           last_updated, status, status_updated_at, manually_set, epub_id
                    FROM epub_reading_progress
                    WHERE status = ?
                    ORDER BY status_updated_at DESC, last_updated DESC
                """
                params = (status,)
            else:
                # Phase 2b: Include epub_id in SELECT
                query = """
                    SELECT epub_filename, current_nav_id, chapter_id, chapter_title,
                           scroll_position, total_sections, progress_percentage,
                           last_updated, status, status_updated_at, manually_set, epub_id
                    FROM epub_reading_progress
                    ORDER BY status_updated_at DESC, last_updated DESC
                """
                params = ()

            rows = self.execute_query(query, params, fetch_all=True)

            books = []
            if rows:
                for row in rows:
                    books.append(
                        {
                            "epub_filename": row[0],
                            "current_nav_id": row[1],
                            "chapter_id": row[2],
                            "chapter_title": row[3],
                            "scroll_position": row[4],
                            "total_sections": row[5],
                            "progress_percentage": row[6],
                            "last_updated": row[7],
                            "status": row[8] if row[8] else "new",
                            "status_updated_at": row[9],
                            "manually_set": bool(row[10])
                            if row[10] is not None
                            else False,
                            "epub_id": row[11]
                            if len(row) > 11
                            else None,  # Phase 2b: Include epub_id
                        }
                    )
            return books
        except Exception as e:
            logger.error(f"Error getting EPUB books by status: {e}")
            return []

    def get_status_counts(self) -> Dict[str, int]:
        """
        Get count of EPUB books for each status.

        Returns:
            Dict[str, int]: Dictionary with status counts
        """
        try:
            query = """
                SELECT status, COUNT(*) as count
                FROM epub_reading_progress
                GROUP BY status
            """
            rows = self.execute_query(query, fetch_all=True)

            counts = {"new": 0, "reading": 0, "finished": 0}
            if rows:
                for row in rows:
                    status = row[0] if row[0] else "new"
                    counts[status] = row[1]

            return counts
        except Exception as e:
            logger.error(f"Error getting EPUB status counts: {e}")
            return {"new": 0, "reading": 0, "finished": 0}

    def delete_progress(self, epub_filename: str) -> bool:
        """
        Delete reading progress record for a specific EPUB.

        Args:
            epub_filename (str): Name of the EPUB file to delete progress for

        Returns:
            bool: True if the record was deleted successfully, False otherwise
        """
        try:
            query = "DELETE FROM epub_reading_progress WHERE epub_filename = ?"
            result = self.execute_update_delete(query, (epub_filename,))

            if result:
                logger.info(f"Deleted EPUB progress for {epub_filename}")
            return result
        except Exception as e:
            logger.error(f"Error deleting EPUB progress: {e}")
            return False

    def calculate_progress_percentage(
        self, current_nav_id: str, nav_metadata: Dict[str, Any] = None
    ) -> float:
        """
        Calculate overall progress percentage based on current navigation position.

        Args:
            current_nav_id (str): Current navigation section ID
            nav_metadata (Dict[str, Any]): Navigation structure metadata

        Returns:
            float: Progress percentage (0.0-100.0)
        """
        try:
            if not nav_metadata:
                return 0.0

            # Get the flat list of all navigation sections from metadata
            all_sections = nav_metadata.get("all_sections", [])
            if not all_sections:
                return 0.0

            # Find the current section's position
            current_position = None
            for i, section in enumerate(all_sections):
                if section.get("id") == current_nav_id:
                    current_position = i
                    break

            if current_position is None:
                return 0.0

            # Calculate percentage (add 1 to current_position since we're "at" this section)
            progress = ((current_position + 1) / len(all_sections)) * 100.0
            return min(100.0, max(0.0, progress))  # Clamp between 0 and 100

        except Exception as e:
            logger.error(f"Error calculating progress percentage: {e}")
            return 0.0

    def get_chapter_progress_info(
        self, epub_filename: str, chapter_id: str = None
    ) -> Dict[str, Any]:
        """
        Get detailed progress information for a specific chapter or current chapter.

        Args:
            epub_filename (str): Name of the EPUB file
            chapter_id (str): Specific chapter ID, or None for current chapter

        Returns:
            Dict[str, Any]: Chapter progress information
        """
        try:
            progress = self.get_progress(epub_filename)
            if not progress:
                return {}

            target_chapter_id = chapter_id or progress.get("chapter_id")
            if not target_chapter_id:
                return {}

            nav_metadata = progress.get("nav_metadata", {})
            if not nav_metadata:
                return {}

            # Find chapter information in metadata
            chapters = nav_metadata.get("chapters", [])
            chapter_info = None
            for chapter in chapters:
                if chapter.get("id") == target_chapter_id:
                    chapter_info = chapter
                    break

            if not chapter_info:
                return {}

            # Calculate chapter-specific progress
            chapter_sections = chapter_info.get("sections", [])
            current_section_pos = None

            if target_chapter_id == progress.get("chapter_id"):
                # This is the current chapter, find current section position
                current_nav_id = progress.get("current_nav_id")
                for i, section in enumerate(chapter_sections):
                    if section.get("id") == current_nav_id:
                        current_section_pos = i
                        break

            return {
                "chapter_id": target_chapter_id,
                "chapter_title": chapter_info.get("title", ""),
                "total_sections": len(chapter_sections),
                "current_section_position": current_section_pos,
                "chapter_progress_percentage": (
                    ((current_section_pos + 1) / len(chapter_sections)) * 100.0
                    if current_section_pos is not None and chapter_sections
                    else 0.0
                ),
                "is_current_chapter": target_chapter_id == progress.get("chapter_id"),
            }

        except Exception as e:
            logger.error(f"Error getting chapter progress info: {e}")
            return {}

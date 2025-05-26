"""
Highlights Service Module

This module provides specialized database operations for managing text highlights
with coordinates and metadata. It handles storing highlights that users create
while reading PDFs.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .base_database_service import BaseDatabaseService

# Configure logger for this module
logger = logging.getLogger(__name__)


class HighlightsService(BaseDatabaseService):
    """
    Service class for managing text highlights using SQLite.

    This class provides database operations for storing and retrieving:
    - Text highlights with coordinates and visual properties
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the highlights service.

        Args:
            db_path (str): Path to the SQLite database file
        """
        super().__init__(db_path)
        self._init_table()

    def _init_table(self):
        """
        Initialize the highlights table and indexes.
        """
        with self.get_connection() as conn:
            # Create highlights table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS highlights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, -- Unique identifier for each highlight
                    pdf_filename TEXT NOT NULL,           -- Which PDF this highlight belongs to
                    page_number INTEGER NOT NULL,         -- Which page this highlight is on
                    selected_text TEXT NOT NULL,          -- The actual highlighted text content
                    start_offset INTEGER NOT NULL,        -- Character position where highlight starts
                    end_offset INTEGER NOT NULL,          -- Character position where highlight ends
                    color TEXT NOT NULL DEFAULT '#ffff00', -- Highlight color in hex format
                    coordinates TEXT NOT NULL,            -- JSON string with bounding box data array
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When the highlight was created
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- When the highlight was last modified
                )
            """)

            # Create indexes for faster lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_highlights_pdf_page
                ON highlights(pdf_filename, page_number)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_highlights_pdf
                ON highlights(pdf_filename)
            """)
            conn.commit()

    def save_highlight(
        self,
        pdf_filename: str,
        page_number: int,
        selected_text: str,
        start_offset: int,
        end_offset: int,
        color: str,
        coordinates: List[Dict[str, Any]],
    ) -> Optional[int]:
        """
        Save a text highlight with coordinates and metadata.

        Args:
            pdf_filename (str): Name of the PDF file this highlight belongs to
            page_number (int): Page number this highlight is on
            selected_text (str): The actual text content that was highlighted
            start_offset (int): Character position where highlight starts
            end_offset (int): Character position where highlight ends
            color (str): Highlight color in hex format (e.g., '#ffff00')
            coordinates (List[Dict[str, Any]]): List of coordinate dictionaries with bounding box data

        Returns:
            Optional[int]: The ID of the newly created highlight, or None if creation failed
        """
        try:
            # Convert coordinates list to JSON string for storage
            coordinates_json = json.dumps(coordinates)

            query = """
                INSERT INTO highlights (
                    pdf_filename, page_number, selected_text, start_offset, end_offset,
                    color, coordinates, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                pdf_filename,
                page_number,
                selected_text,
                start_offset,
                end_offset,
                color,
                coordinates_json,
                self.get_current_timestamp(),
                self.get_current_timestamp(),
            )

            highlight_id = self.execute_insert(query, params)
            if highlight_id:
                logger.info(f"Saved highlight for {pdf_filename}, page {page_number}")
            return highlight_id
        except Exception as e:
            logger.error(f"Error saving highlight: {e}")
            return None

    def get_highlights_for_pdf(
        self, pdf_filename: str, page_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve highlights for a PDF document, optionally filtered by page number.

        Args:
            pdf_filename (str): Name of the PDF file to get highlights for
            page_number (Optional[int]): Specific page number to filter by, or None for all pages

        Returns:
            List[Dict[str, Any]]: List of highlight dictionaries
        """
        try:
            if page_number is not None:
                query = """
                    SELECT id, pdf_filename, page_number, selected_text, start_offset, end_offset,
                           color, coordinates, created_at, updated_at
                    FROM highlights
                    WHERE pdf_filename = ? AND page_number = ?
                    ORDER BY created_at DESC
                """
                params = (pdf_filename, page_number)
            else:
                query = """
                    SELECT id, pdf_filename, page_number, selected_text, start_offset, end_offset,
                           color, coordinates, created_at, updated_at
                    FROM highlights
                    WHERE pdf_filename = ?
                    ORDER BY page_number, created_at DESC
                """
                params = (pdf_filename,)

            rows = self.execute_query(query, params, fetch_all=True)

            highlights = []
            if rows:
                for row in rows:
                    # Parse coordinates JSON back to Python objects
                    try:
                        coordinates_data = json.loads(row["coordinates"])
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(
                            f"Invalid coordinates JSON for highlight {row['id']}"
                        )
                        coordinates_data = []

                    highlights.append(
                        {
                            "id": row["id"],
                            "pdf_filename": row["pdf_filename"],
                            "page_number": row["page_number"],
                            "selected_text": row["selected_text"],
                            "start_offset": row["start_offset"],
                            "end_offset": row["end_offset"],
                            "color": row["color"],
                            "coordinates": coordinates_data,
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                        }
                    )
            return highlights
        except Exception as e:
            logger.error(f"Error getting highlights: {e}")
            return []

    def get_highlight_by_id(self, highlight_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific highlight by its unique ID.

        Args:
            highlight_id (int): Unique identifier of the highlight to retrieve

        Returns:
            Optional[Dict[str, Any]]: Highlight dictionary with all fields, or None if not found
        """
        try:
            query = """
                SELECT id, pdf_filename, page_number, selected_text, start_offset, end_offset,
                       color, coordinates, created_at, updated_at
                FROM highlights
                WHERE id = ?
            """
            row = self.execute_query(query, (highlight_id,), fetch_one=True)

            if row:
                # Parse coordinates JSON back to Python objects
                try:
                    coordinates_data = json.loads(row["coordinates"])
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        f"Invalid coordinates JSON for highlight {highlight_id}"
                    )
                    coordinates_data = []

                return {
                    "id": row["id"],
                    "pdf_filename": row["pdf_filename"],
                    "page_number": row["page_number"],
                    "selected_text": row["selected_text"],
                    "start_offset": row["start_offset"],
                    "end_offset": row["end_offset"],
                    "color": row["color"],
                    "coordinates": coordinates_data,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            return None
        except Exception as e:
            logger.error(f"Error getting highlight: {e}")
            return None

    def delete_highlight(self, highlight_id: int) -> bool:
        """
        Delete a specific highlight by its ID.

        Args:
            highlight_id (int): Unique identifier of the highlight to delete

        Returns:
            bool: True if a highlight was deleted, False if no highlight was found or deletion failed
        """
        try:
            query = "DELETE FROM highlights WHERE id = ?"
            deleted = self.execute_update_delete(query, (highlight_id,))
            if deleted:
                logger.info(f"Deleted highlight {highlight_id}")
            return deleted
        except Exception as e:
            logger.error(f"Error deleting highlight: {e}")
            return False

    def update_color(self, highlight_id: int, color: str) -> bool:
        """
        Update the color of a specific highlight.

        Args:
            highlight_id (int): Unique identifier of the highlight to update
            color (str): New highlight color in hex format (e.g., '#ff0000')

        Returns:
            bool: True if the highlight was updated, False if no highlight was found or update failed
        """
        try:
            query = """
                UPDATE highlights
                SET color = ?, updated_at = ?
                WHERE id = ?
            """
            params = (color, self.get_current_timestamp(), highlight_id)
            updated = self.execute_update_delete(query, params)
            if updated:
                logger.info(f"Updated highlight {highlight_id} color to {color}")
            return updated
        except Exception as e:
            logger.error(f"Error updating highlight color: {e}")
            return False

    def get_highlights_count_by_pdf(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary statistics about highlights for all PDF documents.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping PDF filenames to their highlight statistics
        """
        try:
            # First query: Get count and latest highlight date for each PDF
            query = """
                SELECT
                    pdf_filename,
                    COUNT(*) as highlights_count,
                    MAX(created_at) as latest_highlight_date
                FROM highlights
                GROUP BY pdf_filename
            """
            rows = self.execute_query(query, fetch_all=True)

            highlights_info = {}
            if rows:
                for row in rows:
                    # Second query: Get the text of the latest highlight
                    text_query = """
                        SELECT selected_text
                        FROM highlights
                        WHERE pdf_filename = ? AND created_at = ?
                        LIMIT 1
                    """
                    text_row = self.execute_query(
                        text_query,
                        (row["pdf_filename"], row["latest_highlight_date"]),
                        fetch_one=True,
                    )

                    # Truncate text for preview (first 50 characters)
                    latest_text = (
                        text_row["selected_text"][:50] + "..."
                        if text_row and len(text_row["selected_text"]) > 50
                        else (text_row["selected_text"] if text_row else "No text")
                    )

                    highlights_info[row["pdf_filename"]] = {
                        "highlights_count": row["highlights_count"],
                        "latest_highlight_date": row["latest_highlight_date"],
                        "latest_highlight_text": latest_text,
                    }

            logger.info(
                f"Found highlights for {len(highlights_info)} PDFs: {list(highlights_info.keys())}"
            )
            return highlights_info
        except Exception as e:
            logger.error(f"Error getting highlights count: {e}")
            return {}

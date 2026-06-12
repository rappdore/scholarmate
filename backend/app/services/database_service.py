"""
Database Service Module

This module provides a comprehensive database service for managing reading progress
and chat notes for PDF documents. It acts as a facade that coordinates specialized
services for different data domains while maintaining backward compatibility.

The service manages three main entities:
1. Reading Progress - tracks the last page read and total pages for each PDF
2. Chat Notes - stores conversation notes associated with specific PDF pages
3. Highlights - stores text highlights with coordinates and metadata
"""

import logging
import os
from typing import TYPE_CHECKING, Any

from ..models.epub_highlights import EPUBHighlight, EPUBHighlightCreate
from .chat_notes_service import ChatNotesService
from .epub_chat_notes_service import EPUBChatNotesService
from .epub_highlights_service import EPUBHighlightService
from .epub_reading_statistics_service import EPUBReadingStatisticsService
from .highlights_service import HighlightsService
from .progress_service import ProgressService
from .reading_statistics_service import ReadingStatisticsService

if TYPE_CHECKING:
    from app.models.pdf_responses import DatabaseDeletionResults

# Configure logger for this module
logger = logging.getLogger(__name__)


class DatabaseService:
    """
    A facade service class for managing PDF/EPUB reading progress, chat notes, and highlights using SQLite.

    This class coordinates specialized services for different data domains while maintaining
    the same public API for backward compatibility. It delegates operations to:
    - ProgressService: unified reading progress/status tracking (used here for deletion)
    - ChatNotesService: for conversation notes linked to PDF pages
    - EPUBChatNotesService: for conversation notes linked to EPUB navigation sections
    - HighlightsService: for text highlights with coordinates

    The database is automatically initialized with the required schema on first use.
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the database service and its specialized services.

        Args:
            db_path (str): Path to the SQLite database file. Defaults to "data/reading_progress.db"
                          The directory will be created if it doesn't exist.
        """
        self.db_path = db_path
        self._ensure_data_dir()

        # Initialize specialized services. Each service owns its tables and
        # creates its complete schema on construction; there is deliberately
        # no schema definition in this facade.
        self.progress = ProgressService(db_path)
        self.chat_notes = ChatNotesService(db_path)
        self.epub_chat_notes = EPUBChatNotesService(db_path)
        self.highlights = HighlightsService(db_path)
        self.epub_highlights = EPUBHighlightService(db_path)
        self.reading_statistics = ReadingStatisticsService(db_path)
        self.epub_reading_statistics = EPUBReadingStatisticsService(db_path)

    def _ensure_data_dir(self):
        """
        Ensure the data directory exists for the database file.

        Creates the directory structure if it doesn't exist. This prevents
        database connection errors when the data directory is missing.
        """
        data_dir = os.path.dirname(self.db_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)

    # ========================================
    # CHAT NOTES METHODS
    # ========================================

    def save_chat_note(
        self, pdf_filename: str, page_number: int, title: str, chat_content: str
    ) -> int | None:
        """
        Save a chat conversation as a note linked to a specific PDF page.

        This method stores conversation notes that users create while reading PDFs.
        Each note is associated with a specific page and can have an optional title.

        Args:
            pdf_filename (str): Name of the PDF file this note belongs to
            page_number (int): Page number this note is associated with
            title (str): Title for the note (can be empty)
            chat_content (str): The actual conversation or note content

        Returns:
            int | None: The ID of the newly created note, or None if creation failed
        """
        return self.chat_notes.save_note(pdf_filename, page_number, title, chat_content)

    def get_chat_notes_for_pdf(
        self, pdf_filename: str, page_number: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve chat notes for a PDF document, optionally filtered by page number.

        This method can return either:
        1. All notes for a PDF (when page_number is None)
        2. Notes for a specific page (when page_number is provided)

        Args:
            pdf_filename (str): Name of the PDF file to get notes for
            page_number (int | None): Specific page number to filter by, or None for all pages

        Returns:
            list[dict[str, Any]]: List of note dictionaries, each containing:
                - id: Unique note identifier
                - pdf_filename: PDF file name
                - page_number: Associated page number
                - title: Note title
                - chat_content: Note content
                - created_at: Creation timestamp
                - updated_at: Last update timestamp
        """
        return self.chat_notes.get_notes_for_pdf(pdf_filename, page_number)

    def get_chat_note_by_id(self, note_id: int) -> dict[str, Any] | None:
        """
        Retrieve a specific chat note by its unique ID.

        This method is useful for getting the full details of a specific note
        when you have its ID (e.g., for editing or viewing a particular note).

        Args:
            note_id (int): Unique identifier of the note to retrieve

        Returns:
            dict[str, Any] | None: Note dictionary with all fields, or None if not found
        """
        return self.chat_notes.get_note_by_id(note_id)

    def delete_chat_note(self, note_id: int) -> bool:
        """
        Delete a specific chat note by its ID.

        This permanently removes a note from the database. The operation
        cannot be undone, so it should be used with caution.

        Args:
            note_id (int): Unique identifier of the note to delete

        Returns:
            bool: True if a note was deleted, False if no note was found or deletion failed
        """
        return self.chat_notes.delete_note(note_id)

    def get_notes_count_by_pdf(self) -> dict[str, dict[str, Any]]:
        """
        Get summary statistics about notes for all PDF documents.

        This method provides an overview of note activity across all PDFs,
        including the total number of notes and information about the most recent note.
        This is useful for dashboard views or summary displays.

        Returns:
            dict[str, dict[str, Any]]: Dictionary mapping PDF filenames to their note statistics:
                {
                    "filename.pdf": {
                        "notes_count": int,           # Total number of notes for this PDF
                        "latest_note_date": str,      # Timestamp of the most recent note
                        "latest_note_title": str      # Title of the most recent note
                    }
                }
        """
        return self.chat_notes.get_notes_count_by_pdf()

    # ========================================
    # EPUB CHAT NOTES METHODS
    # ========================================

    def save_epub_chat_note(
        self,
        epub_filename: str,
        nav_id: str,
        chapter_id: str,
        chapter_title: str,
        title: str,
        chat_content: str,
        context_sections: list[str] = None,
        scroll_position: int = 0,
    ) -> int | None:
        """
        Save an EPUB chat conversation as a note linked to a navigation section.

        Args:
            epub_filename (str): Name of the EPUB file this note belongs to
            nav_id (str): Precise navigation section identifier
            chapter_id (str): Chapter identifier for grouping/display
            chapter_title (str): Human-readable chapter title
            title (str): Title for the note (can be empty)
            chat_content (str): The actual conversation or note content
            context_sections (list[str]): List of section IDs that provided context
            scroll_position (int): Scroll position within the section

        Returns:
            int | None: The ID of the newly created note, or None if creation failed
        """
        return self.epub_chat_notes.save_note(
            epub_filename,
            nav_id,
            chapter_id,
            chapter_title,
            title,
            chat_content,
            context_sections,
            scroll_position,
        )

    def get_epub_chat_notes(
        self,
        epub_filename: str,
        nav_id: str | None = None,
        chapter_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve chat notes for an EPUB document, with fine-grained or chapter-level filtering.

        Args:
            epub_filename (str): Name of the EPUB file to get notes for
            nav_id (str | None): Specific navigation section to filter by
            chapter_id (str | None): Specific chapter to filter by

        Returns:
            list[dict[str, Any]]: List of note dictionaries with navigation context
        """
        return self.epub_chat_notes.get_notes_for_epub(
            epub_filename, nav_id, chapter_id
        )

    def get_epub_chat_notes_by_chapter(
        self, epub_filename: str
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get EPUB chat notes grouped by chapter for UI display.

        Args:
            epub_filename (str): Name of the EPUB file to get notes for

        Returns:
            dict[str, list[dict[str, Any]]]: Dictionary mapping chapter IDs to their notes
        """
        return self.epub_chat_notes.get_notes_grouped_by_chapter(epub_filename)

    def get_epub_chat_note_by_id(self, note_id: int) -> dict[str, Any] | None:
        """
        Retrieve a specific EPUB chat note by its unique ID.

        Args:
            note_id (int): Unique identifier of the note to retrieve

        Returns:
            dict[str, Any] | None: Note dictionary with all fields, or None if not found
        """
        return self.epub_chat_notes.get_note_by_id(note_id)

    def delete_epub_chat_note(self, note_id: int) -> bool:
        """
        Delete a specific EPUB chat note by its ID.

        Args:
            note_id (int): Unique identifier of the note to delete

        Returns:
            bool: True if a note was deleted, False if no note was found or deletion failed
        """
        return self.epub_chat_notes.delete_note(note_id)

    def get_epub_notes_count_by_epub(self) -> dict[str, dict[str, Any]]:
        """
        Get summary statistics about notes for all EPUB documents.

        Returns:
            dict[str, dict[str, Any]]: Dictionary mapping EPUB filenames to their note statistics
        """
        return self.epub_chat_notes.get_notes_count_by_epub()

    # ========================================
    # HIGHLIGHT METHODS
    # ========================================

    def save_highlight(
        self,
        pdf_filename: str,
        page_number: int,
        selected_text: str,
        start_offset: int,
        end_offset: int,
        color: str,
        coordinates: list[dict[str, Any]],
    ) -> int | None:
        """
        Save a text highlight with coordinates and metadata.

        This method stores highlights that users create while reading PDFs.
        Each highlight contains the selected text, position offsets, visual properties,
        and coordinate data for accurate rendering.

        Args:
            pdf_filename (str): Name of the PDF file this highlight belongs to
            page_number (int): Page number this highlight is on
            selected_text (str): The actual text content that was highlighted
            start_offset (int): Character position where highlight starts
            end_offset (int): Character position where highlight ends
            color (str): Highlight color in hex format (e.g., '#ffff00')
            coordinates (list[dict[str, Any]]): List of coordinate dictionaries with bounding box data

        Returns:
            int | None: The ID of the newly created highlight, or None if creation failed
        """
        return self.highlights.save_highlight(
            pdf_filename,
            page_number,
            selected_text,
            start_offset,
            end_offset,
            color,
            coordinates,
        )

    def get_highlights_for_pdf(
        self, pdf_filename: str, page_number: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve highlights for a PDF document, optionally filtered by page number.

        This method can return either:
        1. All highlights for a PDF (when page_number is None)
        2. Highlights for a specific page (when page_number is provided)

        Args:
            pdf_filename (str): Name of the PDF file to get highlights for
            page_number (int | None): Specific page number to filter by, or None for all pages

        Returns:
            list[dict[str, Any]]: List of highlight dictionaries, each containing:
                - id: Unique highlight identifier
                - pdf_filename: PDF file name
                - page_number: Associated page number
                - selected_text: Highlighted text content
                - start_offset: Character start position
                - end_offset: Character end position
                - color: Highlight color in hex format
                - coordinates: Parsed coordinate data (as Python objects)
                - created_at: Creation timestamp
                - updated_at: Last update timestamp
        """
        return self.highlights.get_highlights_for_pdf(pdf_filename, page_number)

    def get_highlight_by_id(self, highlight_id: int) -> dict[str, Any] | None:
        """
        Retrieve a specific highlight by its unique ID.

        This method is useful for getting the full details of a specific highlight
        when you have its ID (e.g., for editing or viewing a particular highlight).

        Args:
            highlight_id (int): Unique identifier of the highlight to retrieve

        Returns:
            dict[str, Any] | None: Highlight dictionary with all fields, or None if not found
        """
        return self.highlights.get_highlight_by_id(highlight_id)

    def delete_highlight(self, highlight_id: int) -> bool:
        """
        Delete a specific highlight by its ID.

        This permanently removes a highlight from the database. The operation
        cannot be undone, so it should be used with caution.

        Args:
            highlight_id (int): Unique identifier of the highlight to delete

        Returns:
            bool: True if a highlight was deleted, False if no highlight was found or deletion failed
        """
        return self.highlights.delete_highlight(highlight_id)

    def update_highlight_color(self, highlight_id: int, color: str) -> bool:
        """
        Update the color of a specific highlight.

        This method allows users to change the color of an existing highlight
        without affecting other properties.

        Args:
            highlight_id (int): Unique identifier of the highlight to update
            color (str): New highlight color in hex format (e.g., '#ff0000')

        Returns:
            bool: True if the highlight was updated, False if no highlight was found or update failed
        """
        return self.highlights.update_color(highlight_id, color)

    def get_highlights_count_by_pdf(self) -> dict[str, dict[str, Any]]:
        """
        Get summary statistics about highlights for all PDF documents.

        This method provides an overview of highlight activity across all PDFs,
        including the total number of highlights and information about the most recent highlight.
        This is useful for dashboard views or summary displays.

        Returns:
            dict[str, dict[str, Any]]: Dictionary mapping PDF filenames to their highlight statistics:
                {
                    "filename.pdf": {
                        "highlights_count": int,           # Total number of highlights for this PDF
                        "latest_highlight_date": str,      # Timestamp of the most recent highlight
                        "latest_highlight_text": str       # Preview of the most recent highlight text
                    }
                }
        """
        return self.highlights.get_highlights_count_by_pdf()

    def delete_all_book_data(
        self, pdf_filename: str, document_id: int
    ) -> "DatabaseDeletionResults":
        """
        Delete all database data for a specific book.

        Args:
            pdf_filename (str): Name of the PDF file to delete all data for
            document_id (int): The document's registry id (keys the progress table)

        Returns:
            DatabaseDeletionResults: Results indicating success/failure for each data type
        """
        from app.models.pdf_responses import DatabaseDeletionResults

        # Delete reading progress
        reading_progress_deleted = self.progress.delete_progress(document_id)

        # Delete notes
        notes_deleted = False
        try:
            with self.chat_notes.get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM chat_notes WHERE pdf_filename = ?", (pdf_filename,)
                )
                conn.commit()
                notes_deleted = (
                    cursor.rowcount >= 0
                )  # Consider successful even if no rows were deleted
        except Exception as e:
            logger.error(f"Error deleting notes for {pdf_filename}: {e}")

        # Delete highlights
        highlights_deleted = False
        try:
            with self.highlights.get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM highlights WHERE pdf_filename = ?", (pdf_filename,)
                )
                conn.commit()
                highlights_deleted = (
                    cursor.rowcount >= 0
                )  # Consider successful even if no rows were deleted
        except Exception as e:
            logger.error(f"Error deleting highlights for {pdf_filename}: {e}")

        return DatabaseDeletionResults(
            reading_progress=reading_progress_deleted,
            notes=notes_deleted,
            highlights=highlights_deleted,
        )

    def delete_all_epub_data(
        self, epub_filename: str, document_id: int
    ) -> dict[str, bool]:
        """
        Delete all database data for a specific EPUB book.

        Args:
            epub_filename (str): Name of the EPUB file to delete all data for
            document_id (int): The document's registry id (keys progress + highlights)

        Returns:
            dict[str, bool]: Dictionary indicating success/failure for each data type
        """
        results = {}

        # Delete EPUB reading progress
        results["epub_progress"] = self.progress.delete_progress(document_id)

        # Delete EPUB chat notes
        try:
            with self.epub_chat_notes.get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM epub_chat_notes WHERE epub_filename = ?",
                    (epub_filename,),
                )
                conn.commit()
                results["epub_chat_notes"] = (
                    cursor.rowcount >= 0
                )  # Consider successful even if no rows were deleted
        except Exception as e:
            logger.error(f"Error deleting EPUB chat notes for {epub_filename}: {e}")
            results["epub_chat_notes"] = False

        # Delete EPUB highlights (keyed by the document id)
        try:
            results["epub_highlights"] = self.delete_epub_highlights_for_epub(
                document_id
            )
        except Exception as e:
            logger.error(f"Error deleting EPUB highlights for {epub_filename}: {e}")
            results["epub_highlights"] = False

        return results

    # ------------------------------------------------------------------
    # EPUB Highlight Delegation Methods
    # ------------------------------------------------------------------

    def save_epub_highlight(self, data: EPUBHighlightCreate) -> int | None:
        """Create a highlight for an EPUB section."""
        return self.epub_highlights.save_highlight(data)

    def get_epub_all_highlights(self, epub_id: int) -> list[EPUBHighlight]:
        """Return all highlights for an EPUB document."""
        return self.epub_highlights.get_all_highlights(epub_id)

    def get_epub_section_highlights(
        self, epub_id: int, nav_id: str
    ) -> list[EPUBHighlight]:
        """Return highlights for a specific nav_id section."""
        return self.epub_highlights.get_highlights_for_section(epub_id, nav_id)

    def get_epub_chapter_highlights(
        self, epub_id: int, chapter_id: str
    ) -> list[EPUBHighlight]:
        """Return all highlights within a chapter."""
        return self.epub_highlights.get_highlights_for_chapter(epub_id, chapter_id)

    def get_epub_highlight_by_id(self, highlight_id: int) -> EPUBHighlight | None:
        return self.epub_highlights.get_highlight_by_id(highlight_id)

    def delete_epub_highlight(self, highlight_id: int) -> bool:
        return self.epub_highlights.delete_highlight(highlight_id)

    def update_epub_highlight_color(self, highlight_id: int, color: str) -> bool:
        return self.epub_highlights.update_color(highlight_id, color)

    def get_epub_highlights_count_by_epub(self) -> dict[int, dict[str, int]]:
        """Return highlight count statistics for all EPUB documents."""
        return self.epub_highlights.get_highlights_count_by_epub()

    def delete_epub_highlights_for_epub(self, epub_id: int) -> bool:
        """Delete all highlights for an EPUB document."""
        return self.epub_highlights.delete_highlights_for_epub(epub_id)

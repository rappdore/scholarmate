"""
EPUB Notes API Routes

Handles EPUB-specific note operations, completely separate from PDF notes.
Provides endpoints for saving, retrieving, and managing chat notes linked to EPUB navigation sections.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.database_service import db_service
from ..services.epub_documents_service import EPUBDocumentsService

# Configure logger for this module
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/epub-notes", tags=["epub-notes"])

# Initialize service
epub_documents_service = EPUBDocumentsService()


# Helper function to get EPUB document by ID or raise 404
def get_epub_doc_or_404(epub_id: int) -> dict[str, Any]:
    """
    Look up EPUB document by ID and return it, or raise HTTPException(404) if not found.

    Args:
        epub_id: The EPUB document ID

    Returns:
        The EPUB document dictionary with 'id' and 'filename' keys

    Raises:
        HTTPException: 404 if EPUB not found
    """
    epub_doc = epub_documents_service.get_by_id(epub_id)
    if not epub_doc:
        raise HTTPException(status_code=404, detail="EPUB not found")
    return epub_doc


class EPUBChatNoteRequest(BaseModel):
    """Request model for creating EPUB chat notes."""

    epub_id: int
    nav_id: str
    chapter_id: str
    chapter_title: str
    title: str
    chat_content: str
    context_sections: list[str] | None = None
    scroll_position: int | None = 0


class EPUBChatNoteResponse(BaseModel):
    """Response model for EPUB chat notes."""

    id: int
    epub_filename: str
    nav_id: str
    chapter_id: str
    chapter_title: str
    title: str
    chat_content: str
    context_sections: list[str] | None
    scroll_position: int
    created_at: str
    updated_at: str


@router.post("/chat", response_model=dict[str, Any])
async def save_epub_chat_note(note: EPUBChatNoteRequest) -> dict[str, Any]:
    """
    Save EPUB chat conversation as a note

    Args:
        note: EPUB chat note data with navigation context

    Returns:
        Dict containing note ID and success message

    Raises:
        HTTPException: If note creation fails
    """
    try:
        # Resolve epub_id to epub_filename
        epub_doc = get_epub_doc_or_404(note.epub_id)
        epub_filename = epub_doc["filename"]

        note_id = db_service.save_epub_chat_note(
            epub_filename=epub_filename,
            nav_id=note.nav_id,
            chapter_id=note.chapter_id,
            chapter_title=note.chapter_title,
            title=note.title,
            chat_content=note.chat_content,
            context_sections=note.context_sections,
            scroll_position=note.scroll_position or 0,
        )

        if note_id:
            logger.info(f"EPUB chat note saved with ID {note_id} for {epub_filename}")
            return {
                "note_id": note_id,
                "message": "EPUB chat note saved successfully",
                "epub_id": note.epub_id,
                "epub_filename": epub_filename,
                "nav_id": note.nav_id,
                "chapter_id": note.chapter_id,
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save EPUB chat note")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving EPUB chat note: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error saving EPUB chat note: {str(e)}"
        )


@router.get("/chat/{epub_id}", response_model=list[EPUBChatNoteResponse])
async def get_epub_chat_notes(
    epub_id: int, nav_id: str | None = None, chapter_id: str | None = None
) -> list[EPUBChatNoteResponse]:
    """
    Get EPUB chat notes with optional filtering

    Args:
        epub_id: ID of the EPUB document
        nav_id: Optional specific navigation section to filter by
        chapter_id: Optional specific chapter to filter by

    Returns:
        List of EPUB chat notes

    Raises:
        HTTPException: If retrieval fails
    """
    try:
        # Resolve epub_id to epub_filename
        epub_doc = get_epub_doc_or_404(epub_id)
        epub_filename = epub_doc["filename"]

        notes = db_service.get_epub_chat_notes(epub_filename, nav_id, chapter_id)
        return [EPUBChatNoteResponse(**note) for note in notes]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting EPUB chat notes: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting EPUB chat notes: {str(e)}"
        )


@router.get(
    "/chat/{epub_id}/by-chapter",
    response_model=dict[str, list[EPUBChatNoteResponse]],
)
async def get_epub_chat_notes_by_chapter(
    epub_id: int,
) -> dict[str, list[EPUBChatNoteResponse]]:
    """
    Get EPUB chat notes grouped by chapter for UI display

    Args:
        epub_id: ID of the EPUB document

    Returns:
        Dictionary mapping chapter IDs to their notes

    Raises:
        HTTPException: If retrieval fails
    """
    try:
        # Resolve epub_id to epub_filename
        epub_doc = get_epub_doc_or_404(epub_id)
        epub_filename = epub_doc["filename"]

        notes_by_chapter = db_service.get_epub_chat_notes_by_chapter(epub_filename)

        # Convert to response models
        result = {}
        for chapter_id, notes in notes_by_chapter.items():
            result[chapter_id] = [EPUBChatNoteResponse(**note) for note in notes]

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting EPUB chat notes by chapter: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting EPUB chat notes by chapter: {str(e)}",
        )


@router.get("/chat/id/{note_id}", response_model=EPUBChatNoteResponse)
async def get_epub_chat_note_by_id(note_id: int) -> EPUBChatNoteResponse:
    """
    Get specific EPUB chat note by ID

    Args:
        note_id: Unique identifier of the note

    Returns:
        EPUB chat note details

    Raises:
        HTTPException: If note not found or retrieval fails
    """
    try:
        note = db_service.get_epub_chat_note_by_id(note_id)
        if note:
            return EPUBChatNoteResponse(**note)
        else:
            raise HTTPException(status_code=404, detail="EPUB chat note not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting EPUB chat note: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting EPUB chat note: {str(e)}"
        )


@router.delete("/chat/{note_id}")
async def delete_epub_chat_note(note_id: int) -> dict[str, Any]:
    """
    Delete EPUB chat note

    Args:
        note_id: Unique identifier of the note to delete

    Returns:
        Success confirmation message

    Raises:
        HTTPException: If note not found or deletion fails
    """
    try:
        success = db_service.delete_epub_chat_note(note_id)
        if success:
            logger.info(f"EPUB chat note {note_id} deleted successfully")
            return {
                "success": True,
                "message": f"EPUB chat note {note_id} deleted successfully",
                "note_id": note_id,
            }
        else:
            raise HTTPException(status_code=404, detail="EPUB chat note not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting EPUB chat note: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error deleting EPUB chat note: {str(e)}"
        )


@router.get("/stats", response_model=dict[str, dict[str, Any]])
async def get_epub_notes_statistics() -> dict[str, dict[str, Any]]:
    """
    Get summary statistics about notes for all EPUB documents

    Returns:
        Dictionary mapping EPUB filenames to their note statistics

    Raises:
        HTTPException: If retrieval fails
    """
    try:
        stats = db_service.get_epub_notes_count_by_epub()
        return stats
    except Exception as e:
        logger.error(f"Error getting EPUB notes statistics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting EPUB notes statistics: {str(e)}"
        )

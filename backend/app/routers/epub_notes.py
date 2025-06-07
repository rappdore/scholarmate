"""
EPUB Notes API Routes

Handles EPUB-specific note operations, completely separate from PDF notes.
Provides endpoints for saving, retrieving, and managing chat notes linked to EPUB navigation sections.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.database_service import db_service

# Configure logger for this module
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/epub-notes", tags=["epub-notes"])


class EPUBChatNoteRequest(BaseModel):
    """Request model for creating EPUB chat notes."""

    epub_filename: str
    nav_id: str
    chapter_id: str
    chapter_title: str
    title: str
    chat_content: str
    context_sections: Optional[List[str]] = None
    scroll_position: Optional[int] = 0


class EPUBChatNoteResponse(BaseModel):
    """Response model for EPUB chat notes."""

    id: int
    epub_filename: str
    nav_id: str
    chapter_id: str
    chapter_title: str
    title: str
    chat_content: str
    context_sections: Optional[List[str]]
    scroll_position: int
    created_at: str
    updated_at: str


@router.post("/chat", response_model=Dict[str, Any])
async def save_epub_chat_note(note: EPUBChatNoteRequest) -> Dict[str, Any]:
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
        note_id = db_service.save_epub_chat_note(
            epub_filename=note.epub_filename,
            nav_id=note.nav_id,
            chapter_id=note.chapter_id,
            chapter_title=note.chapter_title,
            title=note.title,
            chat_content=note.chat_content,
            context_sections=note.context_sections,
            scroll_position=note.scroll_position or 0,
        )

        if note_id:
            logger.info(
                f"EPUB chat note saved with ID {note_id} for {note.epub_filename}"
            )
            return {
                "note_id": note_id,
                "message": "EPUB chat note saved successfully",
                "epub_filename": note.epub_filename,
                "nav_id": note.nav_id,
                "chapter_id": note.chapter_id,
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save EPUB chat note")
    except Exception as e:
        logger.error(f"Error saving EPUB chat note: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error saving EPUB chat note: {str(e)}"
        )


@router.get("/chat/{epub_filename}", response_model=List[EPUBChatNoteResponse])
async def get_epub_chat_notes(
    epub_filename: str, nav_id: Optional[str] = None, chapter_id: Optional[str] = None
) -> List[EPUBChatNoteResponse]:
    """
    Get EPUB chat notes with optional filtering

    Args:
        epub_filename: Name of the EPUB file
        nav_id: Optional specific navigation section to filter by
        chapter_id: Optional specific chapter to filter by

    Returns:
        List of EPUB chat notes

    Raises:
        HTTPException: If retrieval fails
    """
    try:
        notes = db_service.get_epub_chat_notes(epub_filename, nav_id, chapter_id)
        return [EPUBChatNoteResponse(**note) for note in notes]
    except Exception as e:
        logger.error(f"Error getting EPUB chat notes: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting EPUB chat notes: {str(e)}"
        )


@router.get(
    "/chat/{epub_filename}/by-chapter",
    response_model=Dict[str, List[EPUBChatNoteResponse]],
)
async def get_epub_chat_notes_by_chapter(
    epub_filename: str,
) -> Dict[str, List[EPUBChatNoteResponse]]:
    """
    Get EPUB chat notes grouped by chapter for UI display

    Args:
        epub_filename: Name of the EPUB file

    Returns:
        Dictionary mapping chapter IDs to their notes

    Raises:
        HTTPException: If retrieval fails
    """
    try:
        notes_by_chapter = db_service.get_epub_chat_notes_by_chapter(epub_filename)

        # Convert to response models
        result = {}
        for chapter_id, notes in notes_by_chapter.items():
            result[chapter_id] = [EPUBChatNoteResponse(**note) for note in notes]

        return result
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
async def delete_epub_chat_note(note_id: int) -> Dict[str, Any]:
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


@router.get("/stats", response_model=Dict[str, Dict[str, Any]])
async def get_epub_notes_statistics() -> Dict[str, Dict[str, Any]]:
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

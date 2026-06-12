"""
EPUB Notes API Routes

Handles EPUB-specific note operations on the unified notes service.
Provides endpoints for saving, retrieving, and managing chat notes linked to EPUB navigation sections.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models.documents import (
    DocumentRecord,
    DocumentType,
    EpubNoteAnchor,
    NoteRecord,
)
from ..services.documents_repository import DocumentsRepository
from ..services.notes_service import NotesService
from ..services.registry import get_documents_repository, get_notes_service

# Configure logger for this module
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/epub-notes", tags=["epub-notes"])


# Helper function to get EPUB document by ID or raise 404
def get_epub_doc_or_404(
    epub_id: int, documents_repository: DocumentsRepository
) -> DocumentRecord:
    """
    Look up EPUB document by ID and return it, or raise HTTPException(404) if not found.
    """
    if epub_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid EPUB ID: must be positive")
    epub_doc = documents_repository.get_by_id(epub_id, DocumentType.EPUB)
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


def _to_response(note: NoteRecord) -> EPUBChatNoteResponse:
    assert isinstance(note.anchor, EpubNoteAnchor)
    return EPUBChatNoteResponse(
        id=note.id,
        epub_filename=note.filename,
        nav_id=note.anchor.nav_id,
        chapter_id=note.anchor.chapter_id or "",
        chapter_title=note.anchor.chapter_title or "",
        title=note.title or "",
        chat_content=note.chat_content,
        context_sections=note.anchor.context_sections,
        scroll_position=note.anchor.scroll_position,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.post("/chat", response_model=dict[str, Any])
def save_epub_chat_note(
    note: EPUBChatNoteRequest,
    notes_service: NotesService = Depends(get_notes_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
) -> dict[str, Any]:
    """
    Save EPUB chat conversation as a note
    """
    try:
        epub_doc = get_epub_doc_or_404(note.epub_id, documents_repository)

        note_id = notes_service.save_note(
            document_id=note.epub_id,
            anchor=EpubNoteAnchor(
                nav_id=note.nav_id,
                chapter_id=note.chapter_id,
                chapter_title=note.chapter_title,
                scroll_position=note.scroll_position or 0,
                context_sections=note.context_sections,
            ),
            title=note.title,
            chat_content=note.chat_content,
        )

        if note_id:
            logger.info(
                f"EPUB chat note saved with ID {note_id} for {epub_doc.filename}"
            )
            return {
                "note_id": note_id,
                "message": "EPUB chat note saved successfully",
                "epub_id": note.epub_id,
                "epub_filename": epub_doc.filename,
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
def get_epub_chat_notes(
    epub_id: int,
    nav_id: str | None = None,
    chapter_id: str | None = None,
    notes_service: NotesService = Depends(get_notes_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
) -> list[EPUBChatNoteResponse]:
    """
    Get EPUB chat notes with optional filtering by section or chapter
    """
    try:
        get_epub_doc_or_404(epub_id, documents_repository)

        notes = notes_service.get_epub_notes(epub_id, nav_id, chapter_id)
        return [_to_response(note) for note in notes]
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
def get_epub_chat_notes_by_chapter(
    epub_id: int,
    notes_service: NotesService = Depends(get_notes_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
) -> dict[str, list[EPUBChatNoteResponse]]:
    """
    Get EPUB chat notes grouped by chapter for UI display
    """
    try:
        get_epub_doc_or_404(epub_id, documents_repository)

        result: dict[str, list[EPUBChatNoteResponse]] = {}
        for note in notes_service.get_epub_notes(epub_id):
            assert isinstance(note.anchor, EpubNoteAnchor)
            chapter_key = note.anchor.chapter_id or "unknown"
            result.setdefault(chapter_key, []).append(_to_response(note))

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
def get_epub_chat_note_by_id(
    note_id: int, notes_service: NotesService = Depends(get_notes_service)
) -> EPUBChatNoteResponse:
    """
    Get specific EPUB chat note by ID
    """
    try:
        note = notes_service.get_note_by_id(note_id)
        if note and note.doc_type == DocumentType.EPUB:
            return _to_response(note)
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
def delete_epub_chat_note(
    note_id: int, notes_service: NotesService = Depends(get_notes_service)
) -> dict[str, Any]:
    """
    Delete EPUB chat note
    """
    try:
        success = notes_service.delete_note(note_id)
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
def get_epub_notes_statistics(
    notes_service: NotesService = Depends(get_notes_service),
) -> dict[str, dict[str, Any]]:
    """
    Get summary statistics about notes for all EPUB documents
    """
    try:
        stats = notes_service.get_notes_summary(DocumentType.EPUB)
        return {filename: summary.model_dump() for filename, summary in stats.items()}
    except Exception as e:
        logger.error(f"Error getting EPUB notes statistics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting EPUB notes statistics: {str(e)}"
        )

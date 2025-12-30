from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.database_service import db_service
from ..services.pdf_documents_service import PDFDocumentsService

router = APIRouter(prefix="/notes", tags=["notes"])

# Initialize services
pdf_documents_service = PDFDocumentsService()


class ChatNoteRequest(BaseModel):
    pdf_id: Optional[int] = None  # NEW: ID-based reference
    pdf_filename: Optional[str] = None  # Legacy: filename-based reference
    page_number: int
    title: str
    chat_content: str


class ChatNoteResponse(BaseModel):
    id: int
    pdf_filename: str
    page_number: int
    title: str
    chat_content: str
    created_at: str
    updated_at: str


@router.post("/chat", response_model=Dict[str, Any])
async def save_chat_note(note: ChatNoteRequest) -> Dict[str, Any]:
    """
    Save a chat conversation as a note.
    Can use either pdf_id (preferred) or pdf_filename (legacy).
    """
    try:
        # Resolve filename from pdf_id if provided, otherwise use pdf_filename
        if note.pdf_id is not None:
            pdf_doc = pdf_documents_service.get_by_id(note.pdf_id)
            if not pdf_doc:
                raise HTTPException(status_code=404, detail="PDF not found")
            pdf_filename = pdf_doc.filename
        elif note.pdf_filename is not None:
            pdf_filename = note.pdf_filename
        else:
            raise HTTPException(
                status_code=400, detail="Either pdf_id or pdf_filename must be provided"
            )

        note_id = db_service.save_chat_note(
            pdf_filename=pdf_filename,
            page_number=note.page_number,
            title=note.title,
            chat_content=note.chat_content,
        )

        if note_id:
            return {
                "success": True,
                "message": "Chat note saved successfully",
                "note_id": note_id,
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save chat note")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving chat note: {str(e)}")


# ========================================
# ID-BASED ENDPOINTS (Phase 5)
# ========================================


@router.get("/chat/pdf/{pdf_id:int}", response_model=List[ChatNoteResponse])
async def get_chat_notes_for_pdf_by_id(
    pdf_id: int, page_number: Optional[int] = None
) -> List[ChatNoteResponse]:
    """
    Get chat notes for a PDF by ID, optionally filtered by page
    """
    try:
        # Lookup filename from ID
        pdf_doc = pdf_documents_service.get_by_id(pdf_id)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        notes = db_service.get_chat_notes_for_pdf(pdf_doc.filename, page_number)
        return [ChatNoteResponse(**note) for note in notes]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting chat notes: {str(e)}"
        )


# ========================================
# FILENAME-BASED ENDPOINTS (Legacy)
# ========================================


@router.get("/chat/{pdf_filename}", response_model=List[ChatNoteResponse])
async def get_chat_notes_for_pdf(
    pdf_filename: str, page_number: Optional[int] = None
) -> List[ChatNoteResponse]:
    """
    Get chat notes for a PDF, optionally filtered by page
    """
    try:
        notes = db_service.get_chat_notes_for_pdf(pdf_filename, page_number)
        return [ChatNoteResponse(**note) for note in notes]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting chat notes: {str(e)}"
        )


@router.get("/chat/id/{note_id}", response_model=ChatNoteResponse)
async def get_chat_note_by_id(note_id: int) -> ChatNoteResponse:
    """
    Get a specific chat note by ID
    """
    try:
        note = db_service.get_chat_note_by_id(note_id)
        if note:
            return ChatNoteResponse(**note)
        else:
            raise HTTPException(status_code=404, detail="Chat note not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting chat note: {str(e)}"
        )


@router.delete("/chat/{note_id}")
async def delete_chat_note(note_id: int) -> Dict[str, Any]:
    """
    Delete a chat note
    """
    try:
        success = db_service.delete_chat_note(note_id)
        if success:
            return {
                "success": True,
                "message": f"Chat note {note_id} deleted successfully",
            }
        else:
            raise HTTPException(status_code=404, detail="Chat note not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting chat note: {str(e)}"
        )

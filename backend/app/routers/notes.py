from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.database_service import db_service

router = APIRouter(prefix="/notes", tags=["notes"])


class ChatNoteRequest(BaseModel):
    pdf_filename: str
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
    Save a chat conversation as a note
    """
    try:
        note_id = db_service.save_chat_note(
            pdf_filename=note.pdf_filename,
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving chat note: {str(e)}")


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

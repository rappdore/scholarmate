from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models.documents import DocumentType, NoteRecord, PdfNoteAnchor
from ..services.documents_repository import DocumentsRepository
from ..services.notes_service import NotesService
from ..services.registry import get_documents_repository, get_notes_service

router = APIRouter(prefix="/notes", tags=["notes"])


class ChatNoteRequest(BaseModel):
    pdf_id: int
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


def _to_response(note: NoteRecord) -> ChatNoteResponse:
    assert isinstance(note.anchor, PdfNoteAnchor)
    return ChatNoteResponse(
        id=note.id,
        pdf_filename=note.filename,
        page_number=note.anchor.page_number,
        title=note.title or "",
        chat_content=note.chat_content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.post("/chat", response_model=Dict[str, Any])
def save_chat_note(
    note: ChatNoteRequest,
    notes_service: NotesService = Depends(get_notes_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
) -> Dict[str, Any]:
    """
    Save a chat conversation as a note.
    """
    try:
        pdf_doc = documents_repository.get_by_id(note.pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        note_id = notes_service.save_note(
            document_id=note.pdf_id,
            anchor=PdfNoteAnchor(page_number=note.page_number),
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


@router.get("/chat/pdf/{pdf_id:int}", response_model=List[ChatNoteResponse])
def get_chat_notes_for_pdf_by_id(
    pdf_id: int,
    page_number: Optional[int] = None,
    notes_service: NotesService = Depends(get_notes_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
) -> List[ChatNoteResponse]:
    """
    Get chat notes for a PDF by ID, optionally filtered by page
    """
    try:
        pdf_doc = documents_repository.get_by_id(pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        notes = notes_service.get_pdf_notes(pdf_id, page_number)
        return [_to_response(note) for note in notes]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting chat notes: {str(e)}"
        )


@router.get("/chat/id/{note_id}", response_model=ChatNoteResponse)
def get_chat_note_by_id(
    note_id: int, notes_service: NotesService = Depends(get_notes_service)
) -> ChatNoteResponse:
    """
    Get a specific chat note by ID
    """
    try:
        note = notes_service.get_note_by_id(note_id)
        if note and note.doc_type == DocumentType.PDF:
            return _to_response(note)
        else:
            raise HTTPException(status_code=404, detail="Chat note not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting chat note: {str(e)}"
        )


@router.delete("/chat/{note_id}")
def delete_chat_note(
    note_id: int, notes_service: NotesService = Depends(get_notes_service)
) -> Dict[str, Any]:
    """
    Delete a chat note
    """
    try:
        success = notes_service.delete_note(note_id)
        if success:
            return {
                "success": True,
                "message": f"Chat note {note_id} deleted successfully",
            }
        else:
            raise HTTPException(status_code=404, detail="Chat note not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting chat note: {str(e)}"
        )

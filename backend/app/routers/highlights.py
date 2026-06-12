from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models.documents import DocumentType, PdfHighlightRecord
from ..services.documents_repository import DocumentsRepository
from ..services.highlights_service import HighlightsService
from ..services.registry import get_documents_repository, get_highlights_service

router = APIRouter(prefix="/highlights", tags=["highlights"])


class HighlightCoordinates(BaseModel):
    x: float
    y: float
    width: float
    height: float
    pageWidth: float
    pageHeight: float
    zoom: float


class HighlightRequest(BaseModel):
    pdf_id: int
    page_number: int
    selected_text: str
    start_offset: int
    end_offset: int
    color: str
    coordinates: List[HighlightCoordinates]


class HighlightResponse(BaseModel):
    id: int
    pdf_filename: str
    page_number: int
    selected_text: str
    start_offset: int
    end_offset: int
    color: str
    coordinates: List[Dict[str, Any]]  # Will be parsed from JSON
    created_at: str
    updated_at: str


class UpdateColorRequest(BaseModel):
    color: str


def _to_response(highlight: PdfHighlightRecord) -> HighlightResponse:
    return HighlightResponse(
        id=highlight.id,
        pdf_filename=highlight.filename,
        page_number=highlight.page_number,
        selected_text=highlight.selected_text,
        start_offset=highlight.start_offset,
        end_offset=highlight.end_offset,
        color=highlight.color,
        coordinates=highlight.coordinates,
        created_at=highlight.created_at,
        updated_at=highlight.updated_at,
    )


@router.post("/", response_model=HighlightResponse)
def create_highlight(
    highlight_data: HighlightRequest,
    highlights_service: HighlightsService = Depends(get_highlights_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
):
    """
    Create a new highlight for a PDF document.
    """
    try:
        pdf_doc = documents_repository.get_by_id(
            highlight_data.pdf_id, DocumentType.PDF
        )
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        # Convert Pydantic models to dictionaries for database storage
        coordinates_dicts = [coord.model_dump() for coord in highlight_data.coordinates]

        highlight_id = highlights_service.save_pdf_highlight(
            document_id=highlight_data.pdf_id,
            page_number=highlight_data.page_number,
            selected_text=highlight_data.selected_text,
            start_offset=highlight_data.start_offset,
            end_offset=highlight_data.end_offset,
            color=highlight_data.color,
            coordinates=coordinates_dicts,
        )

        if highlight_id is None:
            raise HTTPException(status_code=500, detail="Failed to create highlight")

        # Retrieve the created highlight to return complete data
        created_highlight = highlights_service.get_pdf_highlight_by_id(highlight_id)
        if created_highlight is None:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created highlight"
            )

        return _to_response(created_highlight)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating highlight: {str(e)}"
        )


@router.get("/pdf/{pdf_id:int}", response_model=List[HighlightResponse])
def get_highlights_for_pdf_by_id(
    pdf_id: int,
    page_number: Optional[int] = None,
    highlights_service: HighlightsService = Depends(get_highlights_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
):
    """
    Get all highlights for a PDF document by ID, optionally filtered by page number.
    """
    try:
        pdf_doc = documents_repository.get_by_id(pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        highlights = highlights_service.get_pdf_highlights(pdf_id, page_number)
        return [_to_response(highlight) for highlight in highlights]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving highlights: {str(e)}"
        )


@router.get(
    "/pdf/{pdf_id:int}/page/{page_number}", response_model=List[HighlightResponse]
)
def get_highlights_for_page_by_id(
    pdf_id: int,
    page_number: int,
    highlights_service: HighlightsService = Depends(get_highlights_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
):
    """
    Get all highlights for a specific page of a PDF document by ID.
    """
    try:
        pdf_doc = documents_repository.get_by_id(pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        highlights = highlights_service.get_pdf_highlights(pdf_id, page_number)
        return [_to_response(highlight) for highlight in highlights]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving page highlights: {str(e)}"
        )


@router.get("/id/{highlight_id}", response_model=HighlightResponse)
def get_highlight_by_id(
    highlight_id: int,
    highlights_service: HighlightsService = Depends(get_highlights_service),
):
    """
    Get a specific highlight by its ID.
    """
    try:
        highlight = highlights_service.get_pdf_highlight_by_id(highlight_id)
        if highlight is None:
            raise HTTPException(status_code=404, detail="Highlight not found")

        return _to_response(highlight)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving highlight: {str(e)}"
        )


@router.delete("/{highlight_id}")
def delete_highlight(
    highlight_id: int,
    highlights_service: HighlightsService = Depends(get_highlights_service),
):
    """
    Delete a specific highlight by its ID.
    """
    try:
        success = highlights_service.delete_pdf_highlight(highlight_id)
        if not success:
            raise HTTPException(status_code=404, detail="Highlight not found")

        return {"message": "Highlight deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting highlight: {str(e)}"
        )


@router.put("/{highlight_id}/color")
def update_highlight_color(
    highlight_id: int,
    color_data: UpdateColorRequest,
    highlights_service: HighlightsService = Depends(get_highlights_service),
):
    """
    Update the color of a specific highlight.
    """
    try:
        success = highlights_service.update_pdf_highlight_color(
            highlight_id, color_data.color
        )
        if not success:
            raise HTTPException(status_code=404, detail="Highlight not found")

        return {"message": "Highlight color updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating highlight color: {str(e)}"
        )


@router.get("/stats/count", response_model=Dict[str, Dict[str, Any]])
def get_highlights_count_by_pdf(
    highlights_service: HighlightsService = Depends(get_highlights_service),
):
    """
    Get summary statistics about highlights for all PDF documents.
    """
    try:
        stats = highlights_service.get_pdf_highlights_summary()
        return {filename: summary.model_dump() for filename, summary in stats.items()}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving highlight statistics: {str(e)}"
        )

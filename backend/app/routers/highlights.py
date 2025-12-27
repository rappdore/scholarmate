from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.database_service import db_service
from ..services.pdf_documents_service import PDFDocumentsService

router = APIRouter(prefix="/highlights", tags=["highlights"])

# Initialize services
pdf_documents_service = PDFDocumentsService()


class HighlightCoordinates(BaseModel):
    x: float
    y: float
    width: float
    height: float
    pageWidth: float
    pageHeight: float
    zoom: float


class HighlightRequest(BaseModel):
    pdf_id: Optional[int] = None  # NEW: ID-based reference
    pdf_filename: Optional[str] = None  # Legacy: filename-based reference
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


@router.post("/", response_model=HighlightResponse)
async def create_highlight(highlight_data: HighlightRequest):
    """
    Create a new highlight for a PDF document.

    Args:
        highlight_data: Highlight information including text, coordinates, and metadata
                       Can use either pdf_id (preferred) or pdf_filename (legacy)

    Returns:
        HighlightResponse: The created highlight with assigned ID

    Raises:
        HTTPException: If highlight creation fails
    """
    try:
        # Resolve filename from pdf_id if provided, otherwise use pdf_filename
        if highlight_data.pdf_id is not None:
            pdf_doc = pdf_documents_service.get_by_id(highlight_data.pdf_id)
            if not pdf_doc:
                raise HTTPException(status_code=404, detail="PDF not found")
            pdf_filename = pdf_doc["filename"]
        elif highlight_data.pdf_filename is not None:
            pdf_filename = highlight_data.pdf_filename
        else:
            raise HTTPException(
                status_code=400, detail="Either pdf_id or pdf_filename must be provided"
            )

        # Convert Pydantic models to dictionaries for database storage
        coordinates_dicts = [coord.model_dump() for coord in highlight_data.coordinates]

        highlight_id = db_service.save_highlight(
            pdf_filename=pdf_filename,
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
        created_highlight = db_service.get_highlight_by_id(highlight_id)
        if created_highlight is None:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created highlight"
            )

        return HighlightResponse(**created_highlight)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating highlight: {str(e)}"
        )


# ========================================
# ID-BASED ENDPOINTS (Phase 5)
# ========================================


@router.get("/pdf/{pdf_id:int}", response_model=List[HighlightResponse])
async def get_highlights_for_pdf_by_id(pdf_id: int, page_number: Optional[int] = None):
    """
    Get all highlights for a PDF document by ID, optionally filtered by page number.

    Args:
        pdf_id: ID of the PDF
        page_number: Optional page number to filter highlights

    Returns:
        List[HighlightResponse]: List of highlights for the PDF
    """
    try:
        # Lookup filename from ID
        pdf_doc = pdf_documents_service.get_by_id(pdf_id)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        highlights = db_service.get_highlights_for_pdf(pdf_doc["filename"], page_number)
        return [HighlightResponse(**highlight) for highlight in highlights]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving highlights: {str(e)}"
        )


@router.get(
    "/pdf/{pdf_id:int}/page/{page_number}", response_model=List[HighlightResponse]
)
async def get_highlights_for_page_by_id(pdf_id: int, page_number: int):
    """
    Get all highlights for a specific page of a PDF document by ID.

    Args:
        pdf_id: ID of the PDF
        page_number: Page number to get highlights for

    Returns:
        List[HighlightResponse]: List of highlights for the specific page
    """
    try:
        # Lookup filename from ID
        pdf_doc = pdf_documents_service.get_by_id(pdf_id)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        highlights = db_service.get_highlights_for_pdf(pdf_doc["filename"], page_number)
        return [HighlightResponse(**highlight) for highlight in highlights]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving page highlights: {str(e)}"
        )


# ========================================
# FILENAME-BASED ENDPOINTS (Legacy)
# ========================================


@router.get("/{pdf_filename}", response_model=List[HighlightResponse])
async def get_highlights_for_pdf(pdf_filename: str, page_number: Optional[int] = None):
    """
    Get all highlights for a PDF document, optionally filtered by page number.

    Args:
        pdf_filename: Name of the PDF file
        page_number: Optional page number to filter highlights

    Returns:
        List[HighlightResponse]: List of highlights for the PDF
    """
    try:
        highlights = db_service.get_highlights_for_pdf(pdf_filename, page_number)
        return [HighlightResponse(**highlight) for highlight in highlights]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving highlights: {str(e)}"
        )


@router.get(
    "/{pdf_filename}/page/{page_number}", response_model=List[HighlightResponse]
)
async def get_highlights_for_page(pdf_filename: str, page_number: int):
    """
    Get all highlights for a specific page of a PDF document.

    Args:
        pdf_filename: Name of the PDF file
        page_number: Page number to get highlights for

    Returns:
        List[HighlightResponse]: List of highlights for the specific page
    """
    try:
        highlights = db_service.get_highlights_for_pdf(pdf_filename, page_number)
        return [HighlightResponse(**highlight) for highlight in highlights]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving page highlights: {str(e)}"
        )


@router.get("/id/{highlight_id}", response_model=HighlightResponse)
async def get_highlight_by_id(highlight_id: int):
    """
    Get a specific highlight by its ID.

    Args:
        highlight_id: Unique identifier of the highlight

    Returns:
        HighlightResponse: The highlight data

    Raises:
        HTTPException: If highlight is not found
    """
    try:
        highlight = db_service.get_highlight_by_id(highlight_id)
        if highlight is None:
            raise HTTPException(status_code=404, detail="Highlight not found")

        return HighlightResponse(**highlight)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving highlight: {str(e)}"
        )


@router.delete("/{highlight_id}")
async def delete_highlight(highlight_id: int):
    """
    Delete a specific highlight by its ID.

    Args:
        highlight_id: Unique identifier of the highlight to delete

    Returns:
        Dict: Success message

    Raises:
        HTTPException: If highlight is not found or deletion fails
    """
    try:
        success = db_service.delete_highlight(highlight_id)
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
async def update_highlight_color(highlight_id: int, color_data: UpdateColorRequest):
    """
    Update the color of a specific highlight.

    Args:
        highlight_id: Unique identifier of the highlight to update
        color_data: New color information

    Returns:
        Dict: Success message

    Raises:
        HTTPException: If highlight is not found or update fails
    """
    try:
        success = db_service.update_highlight_color(highlight_id, color_data.color)
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
async def get_highlights_count_by_pdf():
    """
    Get summary statistics about highlights for all PDF documents.

    Returns:
        Dict: Mapping of PDF filenames to their highlight statistics
    """
    try:
        return db_service.get_highlights_count_by_pdf()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving highlight statistics: {str(e)}"
        )

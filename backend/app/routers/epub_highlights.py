from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models.documents import DocumentRecord, DocumentType
from ..models.epub_highlights import EPUBHighlight, EPUBHighlightCreate
from ..services.documents_repository import DocumentsRepository
from ..services.highlights_service import HighlightsService
from ..services.registry import get_documents_repository, get_highlights_service

router = APIRouter(prefix="/epub-highlights", tags=["epub-highlights"])


def get_epub_doc_or_404(
    epub_id: int, documents_repository: DocumentsRepository
) -> DocumentRecord:
    """
    Look up EPUB document by ID and return it, or raise HTTPException(404) if not found.
    """
    epub_doc = documents_repository.get_by_id(epub_id, DocumentType.EPUB)
    if not epub_doc:
        raise HTTPException(status_code=404, detail="EPUB not found")
    return epub_doc


class UpdateColorRequest(BaseModel):
    color: str


@router.post("/create", response_model=EPUBHighlight)
def create_epub_highlight(
    payload: EPUBHighlightCreate,
    highlights_service: HighlightsService = Depends(get_highlights_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
) -> EPUBHighlight:
    """Create a new highlight in an EPUB section."""
    try:
        # Validate EPUB exists
        get_epub_doc_or_404(payload.epub_id, documents_repository)

        highlight_id = highlights_service.save_epub_highlight(payload)

        if highlight_id is None:
            raise HTTPException(status_code=500, detail="Failed to create highlight")

        highlight = highlights_service.get_epub_highlight_by_id(highlight_id)
        if not highlight:
            raise HTTPException(
                status_code=500, detail="Failed to fetch created highlight"
            )

        return highlight
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating highlight: {str(e)}"
        )


@router.get("/{epub_id:int}", response_model=list[EPUBHighlight])
def get_all_highlights(
    epub_id: int,
    highlights_service: HighlightsService = Depends(get_highlights_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
) -> list[EPUBHighlight]:
    """Retrieve all highlights for an EPUB document by ID."""
    try:
        get_epub_doc_or_404(epub_id, documents_repository)
        return highlights_service.get_epub_highlights(epub_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving highlights: {str(e)}"
        )


@router.get("/{epub_id:int}/section/{nav_id}", response_model=list[EPUBHighlight])
def get_section_highlights(
    epub_id: int,
    nav_id: str,
    highlights_service: HighlightsService = Depends(get_highlights_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
) -> list[EPUBHighlight]:
    """Retrieve all highlights for a specific navigation section."""
    try:
        get_epub_doc_or_404(epub_id, documents_repository)
        return highlights_service.get_epub_highlights(epub_id, nav_id=nav_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving section highlights: {str(e)}"
        )


@router.get("/{epub_id:int}/chapter/{chapter_id}", response_model=list[EPUBHighlight])
def get_chapter_highlights(
    epub_id: int,
    chapter_id: str,
    highlights_service: HighlightsService = Depends(get_highlights_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
) -> list[EPUBHighlight]:
    """Retrieve all highlights for a chapter by EPUB ID."""
    try:
        get_epub_doc_or_404(epub_id, documents_repository)
        return highlights_service.get_epub_highlights(epub_id, chapter_id=chapter_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving chapter highlights: {str(e)}"
        )


@router.delete("/{highlight_id}")
def delete_epub_highlight(
    highlight_id: int,
    highlights_service: HighlightsService = Depends(get_highlights_service),
) -> dict[str, str]:
    """Delete a highlight by ID."""
    try:
        success = highlights_service.delete_epub_highlight(highlight_id)
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
def update_epub_highlight_color(
    highlight_id: int,
    color_data: UpdateColorRequest,
    highlights_service: HighlightsService = Depends(get_highlights_service),
) -> dict[str, str]:
    """Update the color of a highlight."""
    try:
        success = highlights_service.update_epub_highlight_color(
            highlight_id, color_data.color
        )
        if not success:
            raise HTTPException(
                status_code=404, detail="Highlight not found or update failed"
            )
        return {"message": "Highlight color updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating highlight color: {str(e)}"
        )

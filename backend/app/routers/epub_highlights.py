from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models.epub_highlights import EPUBHighlight, EPUBHighlightCreate
from ..services.database_service import db_service
from ..services.epub_documents_service import EPUBDocumentsService

router = APIRouter(prefix="/epub-highlights", tags=["epub-highlights"])
epub_documents_service = EPUBDocumentsService()


def get_epub_doc_or_404(epub_id: int) -> dict:
    """
    Look up EPUB document by ID and return it, or raise HTTPException(404) if not found.
    """
    epub_doc = epub_documents_service.get_by_id(epub_id)
    if not epub_doc:
        raise HTTPException(status_code=404, detail="EPUB not found")
    return epub_doc


class UpdateColorRequest(BaseModel):
    color: str


@router.post("/create", response_model=EPUBHighlight)
async def create_epub_highlight(payload: EPUBHighlightCreate) -> EPUBHighlight:
    """Create a new highlight in an EPUB section."""
    # Validate EPUB exists
    get_epub_doc_or_404(payload.epub_id)

    highlight_id = db_service.save_epub_highlight(payload)

    if highlight_id is None:
        raise HTTPException(status_code=500, detail="Failed to create highlight")

    highlight = db_service.get_epub_highlight_by_id(highlight_id)
    if not highlight:
        raise HTTPException(status_code=500, detail="Failed to fetch created highlight")

    return highlight


@router.get("/{epub_id:int}", response_model=list[EPUBHighlight])
async def get_all_highlights(epub_id: int) -> list[EPUBHighlight]:
    """Retrieve all highlights for an EPUB document by ID."""
    get_epub_doc_or_404(epub_id)
    return db_service.get_epub_all_highlights(epub_id)


@router.get("/{epub_id:int}/section/{nav_id}", response_model=list[EPUBHighlight])
async def get_section_highlights(epub_id: int, nav_id: str) -> list[EPUBHighlight]:
    """Retrieve all highlights for a specific navigation section."""
    get_epub_doc_or_404(epub_id)
    return db_service.get_epub_section_highlights(epub_id, nav_id)


@router.get("/{epub_id:int}/chapter/{chapter_id}", response_model=list[EPUBHighlight])
async def get_chapter_highlights(epub_id: int, chapter_id: str) -> list[EPUBHighlight]:
    """Retrieve all highlights for a chapter by EPUB ID."""
    get_epub_doc_or_404(epub_id)
    return db_service.get_epub_chapter_highlights(epub_id, chapter_id)


@router.get("/id/{highlight_id}", response_model=EPUBHighlight)
async def get_epub_highlight_by_id(highlight_id: int) -> EPUBHighlight:
    """Retrieve a specific highlight by its ID."""
    highlight = db_service.get_epub_highlight_by_id(highlight_id)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")
    return highlight


@router.delete("/{highlight_id}")
async def delete_epub_highlight(highlight_id: int) -> dict[str, str]:
    """Delete a highlight by ID."""
    success = db_service.delete_epub_highlight(highlight_id)
    if not success:
        raise HTTPException(status_code=404, detail="Highlight not found")
    return {"message": "Highlight deleted successfully"}


@router.put("/{highlight_id}/color")
async def update_epub_highlight_color(
    highlight_id: int, color_data: UpdateColorRequest
) -> dict[str, str]:
    """Update the color of a highlight."""
    success = db_service.update_epub_highlight_color(highlight_id, color_data.color)
    if not success:
        raise HTTPException(
            status_code=404, detail="Highlight not found or update failed"
        )
    return {"message": "Highlight color updated"}

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.database_service import db_service
from ..services.epub_documents_service import EPUBDocumentsService

router = APIRouter(prefix="/epub-highlights", tags=["epub-highlights"])
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


class EPUBHighlightRequest(BaseModel):
    epub_id: int
    nav_id: str
    chapter_id: str | None = None
    xpath: str
    start_offset: int
    end_offset: int
    highlight_text: str
    color: str = "#ffff00"


class EPUBHighlightResponse(BaseModel):
    id: int
    epub_id: int
    nav_id: str
    chapter_id: str | None = None
    xpath: str
    start_offset: int
    end_offset: int
    highlight_text: str
    color: str
    created_at: str


class UpdateColorRequest(BaseModel):
    color: str


@router.post("/create", response_model=EPUBHighlightResponse)
async def create_epub_highlight(payload: EPUBHighlightRequest) -> EPUBHighlightResponse:
    """Create a new highlight in an EPUB section."""
    # Validate EPUB exists and get filename
    epub_doc = get_epub_doc_or_404(payload.epub_id)

    highlight_id = db_service.save_epub_highlight(
        epub_filename=epub_doc["filename"],
        nav_id=payload.nav_id,
        chapter_id=payload.chapter_id,
        xpath=payload.xpath,
        start_offset=payload.start_offset,
        end_offset=payload.end_offset,
        highlight_text=payload.highlight_text,
        color=payload.color,
    )

    if highlight_id is None:
        raise HTTPException(status_code=500, detail="Failed to create highlight")

    highlight = db_service.get_epub_highlight_by_id(highlight_id)
    if not highlight:
        raise HTTPException(status_code=500, detail="Failed to fetch created highlight")

    # Add epub_id to response
    highlight["epub_id"] = payload.epub_id
    return EPUBHighlightResponse(**highlight)


@router.get("/{epub_id:int}", response_model=list[EPUBHighlightResponse])
async def get_all_highlights(epub_id: int) -> list[EPUBHighlightResponse]:
    """Retrieve all highlights for an EPUB document by ID."""
    # Validate EPUB exists and get filename
    epub_doc = get_epub_doc_or_404(epub_id)

    highlights = db_service.get_epub_all_highlights(epub_doc["filename"])
    # Add epub_id to each highlight
    return [EPUBHighlightResponse(**{**h, "epub_id": epub_id}) for h in highlights]


@router.get(
    "/{epub_id:int}/section/{nav_id}", response_model=list[EPUBHighlightResponse]
)
async def get_section_highlights(
    epub_id: int, nav_id: str
) -> list[EPUBHighlightResponse]:
    """Retrieve all highlights for a specific navigation section by EPUB ID."""
    # Validate EPUB exists and get filename
    epub_doc = get_epub_doc_or_404(epub_id)

    highlights = db_service.get_epub_section_highlights(epub_doc["filename"], nav_id)
    # Add epub_id to each highlight
    return [EPUBHighlightResponse(**{**h, "epub_id": epub_id}) for h in highlights]


@router.get(
    "/{epub_id:int}/chapter/{chapter_id}", response_model=list[EPUBHighlightResponse]
)
async def get_chapter_highlights(
    epub_id: int, chapter_id: str
) -> list[EPUBHighlightResponse]:
    """Retrieve all highlights for a chapter by EPUB ID."""
    # Validate EPUB exists and get filename
    epub_doc = get_epub_doc_or_404(epub_id)

    highlights = db_service.get_epub_chapter_highlights(
        epub_doc["filename"], chapter_id
    )
    # Add epub_id to each highlight
    return [EPUBHighlightResponse(**{**h, "epub_id": epub_id}) for h in highlights]


@router.get("/id/{highlight_id}", response_model=EPUBHighlightResponse)
async def get_epub_highlight_by_id(highlight_id: int) -> EPUBHighlightResponse:
    highlight = db_service.get_epub_highlight_by_id(highlight_id)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")

    # Get EPUB ID from filename
    epub_doc = epub_documents_service.get_by_filename(highlight["epub_filename"])
    if epub_doc:
        highlight["epub_id"] = epub_doc["id"]
    else:
        raise HTTPException(
            status_code=404, detail="EPUB document not found for highlight"
        )

    return EPUBHighlightResponse(**highlight)


@router.delete("/{highlight_id}")
async def delete_epub_highlight(highlight_id: int) -> dict[str, str]:
    success = db_service.delete_epub_highlight(highlight_id)
    if not success:
        raise HTTPException(status_code=404, detail="Highlight not found")
    return {"message": "Highlight deleted successfully"}


@router.put("/{highlight_id}/color")
async def update_epub_highlight_color(
    highlight_id: int, color_data: UpdateColorRequest
) -> dict[str, str]:
    success = db_service.update_epub_highlight_color(highlight_id, color_data.color)
    if not success:
        raise HTTPException(
            status_code=404, detail="Highlight not found or update failed"
        )
    return {"message": "Highlight color updated"}

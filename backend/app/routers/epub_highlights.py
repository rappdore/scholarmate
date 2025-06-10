from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.database_service import db_service

router = APIRouter(prefix="/epub-highlights", tags=["epub-highlights"])


class EPUBHighlightRequest(BaseModel):
    epub_filename: str = Field(..., alias="document_id")
    nav_id: str
    chapter_id: Optional[str] = None
    xpath: str
    start_offset: int
    end_offset: int
    highlight_text: str
    color: str = "#ffff00"

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }


class EPUBHighlightResponse(BaseModel):
    id: int
    epub_filename: str
    nav_id: str
    chapter_id: Optional[str] = None
    xpath: str
    start_offset: int
    end_offset: int
    highlight_text: str
    color: str
    created_at: str


class UpdateColorRequest(BaseModel):
    color: str


@router.post("/create", response_model=EPUBHighlightResponse)
async def create_epub_highlight(payload: EPUBHighlightRequest):
    """Create a new highlight in an EPUB section."""
    highlight_id = db_service.save_epub_highlight(
        epub_filename=payload.epub_filename,
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

    return EPUBHighlightResponse(**highlight)


@router.get(
    "/{epub_filename}/section/{nav_id}", response_model=List[EPUBHighlightResponse]
)
async def get_section_highlights(epub_filename: str, nav_id: str):
    """Retrieve all highlights for a specific navigation section."""
    highlights = db_service.get_epub_section_highlights(epub_filename, nav_id)
    return [EPUBHighlightResponse(**h) for h in highlights]


@router.get(
    "/{epub_filename}/chapter/{chapter_id}", response_model=List[EPUBHighlightResponse]
)
async def get_chapter_highlights(epub_filename: str, chapter_id: str):
    """Retrieve all highlights for a chapter."""
    highlights = db_service.get_epub_chapter_highlights(epub_filename, chapter_id)
    return [EPUBHighlightResponse(**h) for h in highlights]


@router.get("/id/{highlight_id}", response_model=EPUBHighlightResponse)
async def get_epub_highlight_by_id(highlight_id: int):
    highlight = db_service.get_epub_highlight_by_id(highlight_id)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")
    return EPUBHighlightResponse(**highlight)


@router.delete("/{highlight_id}")
async def delete_epub_highlight(highlight_id: int):
    success = db_service.delete_epub_highlight(highlight_id)
    if not success:
        raise HTTPException(status_code=404, detail="Highlight not found")
    return {"message": "Highlight deleted successfully"}


@router.put("/{highlight_id}/color")
async def update_epub_highlight_color(
    highlight_id: int, color_data: UpdateColorRequest
):
    success = db_service.update_epub_highlight_color(highlight_id, color_data.color)
    if not success:
        raise HTTPException(
            status_code=404, detail="Highlight not found or update failed"
        )
    return {"message": "Highlight color updated"}

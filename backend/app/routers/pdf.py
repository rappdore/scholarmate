from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..services.database_service import db_service
from ..services.pdf_service import PDFService

router = APIRouter(prefix="/pdf", tags=["pdf"])

# Initialize PDF service
pdf_service = PDFService()


class ReadingProgressRequest(BaseModel):
    last_page: int
    total_pages: int


@router.get("/list")
async def list_pdfs() -> List[Dict[str, Any]]:
    """
    List all PDFs in the pdfs directory with metadata, reading progress, and notes info
    """
    try:
        pdfs = pdf_service.list_pdfs()
        all_progress = db_service.get_all_reading_progress()
        all_notes = db_service.get_notes_count_by_pdf()

        # Add reading progress and notes info to each PDF
        for pdf in pdfs:
            filename = pdf.get("filename")

            # Add reading progress
            if filename and filename in all_progress:
                progress = all_progress[filename]
                pdf["reading_progress"] = {
                    "last_page": progress["last_page"],
                    "total_pages": progress["total_pages"],
                    "progress_percentage": round(
                        (progress["last_page"] / progress["total_pages"]) * 100
                    )
                    if progress["total_pages"]
                    else 0,
                    "last_updated": progress["last_updated"],
                }
            else:
                pdf["reading_progress"] = None

            # Add notes information
            if filename and filename in all_notes:
                notes_info = all_notes[filename]
                pdf["notes_info"] = {
                    "notes_count": notes_info["notes_count"],
                    "latest_note_date": notes_info["latest_note_date"],
                    "latest_note_title": notes_info["latest_note_title"],
                }
            else:
                pdf["notes_info"] = None

        return pdfs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing PDFs: {str(e)}")


@router.get("/{filename}/info")
async def get_pdf_info(filename: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific PDF
    """
    try:
        info = pdf_service.get_pdf_info(filename)
        return info
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting PDF info: {str(e)}")


@router.get("/{filename}/file")
async def get_pdf_file(filename: str):
    """
    Serve the actual PDF file for viewing
    """
    try:
        file_path = pdf_service.get_pdf_path(filename)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found")

        return FileResponse(
            path=str(file_path), media_type="application/pdf", filename=filename
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving PDF: {str(e)}")


@router.get("/{filename}/text/{page_num}")
async def get_page_text(filename: str, page_num: int) -> Dict[str, Any]:
    """
    Extract text from a specific page of the PDF
    """
    try:
        text = pdf_service.extract_page_text(filename, page_num)
        return {"filename": filename, "page_number": page_num, "text": text}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting text: {str(e)}")


@router.put("/{filename}/progress")
async def save_reading_progress(
    filename: str, progress: ReadingProgressRequest
) -> Dict[str, Any]:
    """
    Save reading progress for a PDF
    """
    try:
        success = db_service.save_reading_progress(
            pdf_filename=filename,
            last_page=progress.last_page,
            total_pages=progress.total_pages,
        )

        if success:
            return {
                "success": True,
                "message": f"Reading progress saved for {filename}",
                "last_page": progress.last_page,
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to save reading progress"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error saving reading progress: {str(e)}"
        )


@router.get("/{filename}/progress")
async def get_reading_progress(filename: str) -> Dict[str, Any]:
    """
    Get reading progress for a PDF
    """
    try:
        progress = db_service.get_reading_progress(filename)

        if progress:
            return progress
        else:
            # Return default progress if none found
            return {
                "pdf_filename": filename,
                "last_page": 1,
                "total_pages": None,
                "last_updated": None,
            }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting reading progress: {str(e)}"
        )


@router.get("/{filename}/thumbnail")
async def get_pdf_thumbnail(filename: str):
    """
    Get a thumbnail image of the first page of the PDF
    """
    try:
        thumbnail_path = pdf_service.get_thumbnail_path(filename)
        
        if not thumbnail_path.exists():
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        
        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/png",
            filename=f"{filename}_thumb.png"
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating thumbnail: {str(e)}")


@router.get("/progress/all")
async def get_all_reading_progress() -> Dict[str, Any]:
    """
    Get reading progress for all PDFs
    """
    try:
        progress = db_service.get_all_reading_progress()
        return {"progress": progress}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting reading progress: {str(e)}"
        )


@router.get("/{filename}/thumbnail")
async def get_pdf_thumbnail(filename: str):
    """
    Get a thumbnail image of the first page of the PDF
    """
    try:
        thumbnail_path = pdf_service.get_thumbnail_path(filename)
        
        if not thumbnail_path.exists():
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        
        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/png",
            filename=f"{filename}_thumb.png"
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating thumbnail: {str(e)}")

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..services.epub_service import EPUBService

router = APIRouter(prefix="/epub", tags=["epub"])

# Initialize EPUB service
epub_service = EPUBService()


@router.get("/list")
async def list_epubs() -> List[Dict[str, Any]]:
    """
    List all EPUB files in the epubs directory with metadata
    """
    try:
        epubs = epub_service.list_epubs()
        return epubs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing EPUBs: {str(e)}")


@router.get("/{filename}/info")
async def get_epub_info(filename: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific EPUB
    """
    try:
        info = epub_service.get_epub_info(filename)
        return info
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting EPUB info: {str(e)}"
        )


@router.get("/{filename}/file")
async def get_epub_file(filename: str):
    """
    Serve the actual EPUB file for viewing (placeholder for now)
    """
    try:
        file_path = epub_service.get_epub_path(filename)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="EPUB file not found")

        # For now, return 404 as specified in the plan
        # This will be implemented in Phase 2
        raise HTTPException(status_code=404, detail="EPUB viewer not yet implemented")

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving EPUB: {str(e)}")


@router.get("/{filename}/thumbnail")
async def get_epub_thumbnail(filename: str):
    """
    Get thumbnail image for an EPUB cover
    """
    try:
        thumbnail_path = epub_service.get_thumbnail_path(filename)

        # Generate thumbnail if it doesn't exist
        if not thumbnail_path.exists():
            thumbnail_path = epub_service.generate_thumbnail(filename)

        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/png",
            filename=f"{filename}_thumbnail.png",
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating thumbnail: {str(e)}"
        )

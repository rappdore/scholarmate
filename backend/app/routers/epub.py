from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

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
    Serve the actual EPUB file for viewing
    """
    try:
        file_path = epub_service.get_epub_path(filename)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="EPUB file not found")

        # Return success response indicating EPUB viewer is available
        return {
            "status": "success",
            "message": "EPUB viewer available",
            "filename": filename,
        }

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
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


@router.get("/{filename}/navigation")
async def get_epub_navigation(filename: str) -> Dict[str, Any]:
    """
    Get the hierarchical navigation structure (table of contents) for an EPUB
    """
    try:
        navigation = epub_service.get_navigation_tree(filename)
        return navigation
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting navigation: {str(e)}"
        )


@router.get("/{filename}/content/{nav_id}")
async def get_epub_content(filename: str, nav_id: str) -> Dict[str, Any]:
    """
    Get HTML content for a specific navigation section
    """
    try:
        content = epub_service.get_content_by_nav_id(filename, nav_id)
        return content
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting content: {str(e)}")


@router.get("/{filename}/styles")
async def get_epub_styles(filename: str) -> Dict[str, Any]:
    """
    Get CSS styles from an EPUB file
    Returns sanitized CSS content for safe browser rendering
    """
    try:
        styles = epub_service.get_epub_styles(filename)
        return styles
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting styles: {str(e)}")


@router.get("/{filename}/image/{image_path:path}")
async def get_epub_image(filename: str, image_path: str):
    """
    Serve an image from an EPUB file
    """
    try:
        image_data = epub_service.get_epub_image(filename, image_path)

        # Determine content type based on file extension
        content_type = "image/jpeg"  # default
        if image_path.lower().endswith(".png"):
            content_type = "image/png"
        elif image_path.lower().endswith(".gif"):
            content_type = "image/gif"
        elif image_path.lower().endswith(".svg"):
            content_type = "image/svg+xml"
        elif image_path.lower().endswith(".webp"):
            content_type = "image/webp"

        return Response(
            content=image_data,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=3600"},  # Cache for 1 hour
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving image: {str(e)}")


@router.get("/{filename}/images")
async def list_epub_images(filename: str) -> List[Dict[str, str]]:
    """
    List all images in an EPUB file
    """
    try:
        images = epub_service.get_epub_images_list(filename)
        return images
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing images: {str(e)}")

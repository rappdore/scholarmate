from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ..services.database_service import db_service
from ..services.epub_service import EPUBService

router = APIRouter(prefix="/epub", tags=["epub"])

# Initialize EPUB service
epub_service = EPUBService()


class EPUBProgressRequest(BaseModel):
    current_nav_id: str
    chapter_id: Optional[str] = None
    chapter_title: Optional[str] = None
    scroll_position: int = 0
    total_sections: Optional[int] = None
    progress_percentage: float = 0.0
    nav_metadata: Optional[Dict[str, Any]] = None


class BookStatusRequest(BaseModel):
    status: str
    manually_set: bool = True


@router.get("/list")
async def list_epubs(
    status: Optional[str] = Query(
        None, description="Filter by book status (new, reading, finished)"
    ),
) -> List[Dict[str, Any]]:
    """
    List all EPUB files in the epubs directory with metadata, reading progress, and notes info.
    Optionally filter by book status.
    """
    try:
        epubs = epub_service.list_epubs()

        # Get reading progress with status information
        if status:
            # Filter by status using the database service
            books_by_status = db_service.get_epub_books_by_status(status)
            # Create a set of filenames that match the status
            status_filenames = {book["epub_filename"] for book in books_by_status}
            # Filter EPUBs to only include those with the matching status
            epubs = [epub for epub in epubs if epub.get("filename") in status_filenames]

        all_progress = db_service.get_all_epub_progress()

        # Add reading progress to each EPUB
        for epub in epubs:
            filename = epub.get("filename")

            # Add reading progress with status information
            if filename and filename in all_progress:
                progress = all_progress[filename]
                epub["reading_progress"] = {
                    "current_nav_id": progress["current_nav_id"],
                    "chapter_id": progress["chapter_id"],
                    "chapter_title": progress["chapter_title"],
                    "scroll_position": progress["scroll_position"],
                    "total_sections": progress["total_sections"],
                    "progress_percentage": progress["progress_percentage"],
                    "last_updated": progress["last_updated"],
                    "status": progress.get("status", "new"),
                    "status_updated_at": progress.get("status_updated_at"),
                    "manually_set": progress.get("manually_set", False),
                }
            else:
                epub["reading_progress"] = None

            # Note: EPUB notes and highlights will be added in future phases
            epub["notes_info"] = None
            epub["highlights_info"] = None

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


# ========================================
# EPUB PROGRESS TRACKING ENDPOINTS
# ========================================


@router.put("/{filename}/progress")
async def save_epub_progress(
    filename: str, progress: EPUBProgressRequest
) -> Dict[str, Any]:
    """
    Save reading progress for an EPUB
    """
    try:
        success = db_service.save_epub_progress(
            epub_filename=filename,
            current_nav_id=progress.current_nav_id,
            chapter_id=progress.chapter_id,
            chapter_title=progress.chapter_title,
            scroll_position=progress.scroll_position,
            total_sections=progress.total_sections,
            progress_percentage=progress.progress_percentage,
            nav_metadata=progress.nav_metadata,
        )

        if success:
            return {
                "success": True,
                "message": f"Reading progress saved for {filename}",
                "current_nav_id": progress.current_nav_id,
                "progress_percentage": progress.progress_percentage,
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
async def get_epub_progress(filename: str) -> Dict[str, Any]:
    """
    Get reading progress for an EPUB
    """
    try:
        progress = db_service.get_epub_progress(filename)

        if progress:
            return progress
        else:
            # Return default progress if none found
            return {
                "epub_filename": filename,
                "current_nav_id": "start",
                "chapter_id": None,
                "chapter_title": None,
                "scroll_position": 0,
                "total_sections": None,
                "progress_percentage": 0.0,
                "last_updated": None,
                "status": "new",
                "status_updated_at": None,
                "manually_set": False,
                "nav_metadata": None,
            }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting reading progress: {str(e)}"
        )


@router.get("/progress/all")
async def get_all_epub_progress() -> Dict[str, Any]:
    """
    Get reading progress for all EPUB books
    """
    try:
        progress = db_service.get_all_epub_progress()
        return {"epub_progress": progress}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting all reading progress: {str(e)}"
        )


@router.put("/{filename}/status")
async def update_epub_book_status(
    filename: str, status_request: BookStatusRequest
) -> Dict[str, Any]:
    """
    Update the reading status of an EPUB book
    """
    try:
        # Validate status
        valid_statuses = ["new", "reading", "finished"]
        if status_request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}",
            )

        success = db_service.update_epub_book_status(
            epub_filename=filename,
            status=status_request.status,
            manual=status_request.manually_set,
        )

        if success:
            return {
                "success": True,
                "message": f"Status updated for {filename}",
                "status": status_request.status,
                "manually_set": status_request.manually_set,
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update book status")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating book status: {str(e)}"
        )


@router.get("/status/counts")
async def get_epub_status_counts() -> Dict[str, int]:
    """
    Get count of EPUB books for each status
    """
    try:
        counts = db_service.get_epub_status_counts()
        return counts
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting status counts: {str(e)}"
        )


@router.delete("/{filename}")
async def delete_epub_book(filename: str) -> Dict[str, Any]:
    """
    Delete an EPUB book and all associated data (progress, notes, highlights)
    """
    try:
        # Check if EPUB exists
        try:
            epub_service.get_epub_path(filename)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="EPUB not found")

        # Delete all associated data from database
        deletion_results = db_service.delete_all_epub_data(filename)

        return {
            "success": True,
            "message": f"EPUB book {filename} and associated data deleted",
            "deletion_results": deletion_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting EPUB book: {str(e)}"
        )


@router.get("/{filename}/chapter-progress/{chapter_id}")
async def get_epub_chapter_progress(filename: str, chapter_id: str) -> Dict[str, Any]:
    """
    Get detailed progress information for a specific EPUB chapter
    """
    try:
        chapter_info = db_service.get_epub_chapter_progress_info(filename, chapter_id)

        if not chapter_info:
            raise HTTPException(
                status_code=404, detail="Chapter progress information not found"
            )

        return chapter_info

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting chapter progress: {str(e)}"
        )

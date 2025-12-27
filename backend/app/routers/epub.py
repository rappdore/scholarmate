import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ..services.database_service import db_service
from ..services.epub_documents_service import EPUBDocumentsService
from ..services.epub_service import EPUBService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/epub", tags=["epub"])

# Initialize services
epub_service = EPUBService()
epub_documents_service = EPUBDocumentsService()


# Helper function to get EPUB document by ID or raise 404
def get_epub_doc_or_404(epub_id: int) -> Dict[str, Any]:
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


# ========================================
# ID-BASED ENDPOINTS (Phase 5)
# ========================================


@router.get("/{epub_id:int}/info")
async def get_epub_info_by_id(epub_id: int) -> Dict[str, Any]:
    """
    Get detailed information about a specific EPUB by ID
    """
    try:
        epub_doc = get_epub_doc_or_404(epub_id)

        info = epub_service.get_epub_info(epub_doc["filename"])
        # Add ID to response
        info["id"] = epub_id
        return info
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting EPUB info: {str(e)}"
        )


@router.get("/{epub_id:int}/thumbnail")
async def get_epub_thumbnail_by_id(epub_id: int):
    """
    Get thumbnail image for an EPUB cover by ID
    """
    try:
        epub_doc = get_epub_doc_or_404(epub_id)

        thumbnail_path = epub_service.get_thumbnail_path(epub_doc["filename"])

        # Generate thumbnail if it doesn't exist
        if not thumbnail_path.exists():
            thumbnail_path = epub_service.generate_thumbnail(epub_doc["filename"])

        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/png",
            filename=f"{epub_doc['filename']}_thumbnail.png",
        )

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating thumbnail: {str(e)}"
        )


@router.get("/{epub_id:int}/navigation")
async def get_epub_navigation_by_id(epub_id: int) -> Dict[str, Any]:
    """
    Get the hierarchical navigation structure (table of contents) for an EPUB by ID
    """
    try:
        epub_doc = get_epub_doc_or_404(epub_id)

        navigation = epub_service.get_navigation_tree(epub_doc["filename"])
        return navigation
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting navigation: {str(e)}"
        )


@router.get("/{epub_id:int}/content/{nav_id}")
async def get_epub_content_by_id(epub_id: int, nav_id: str) -> Dict[str, Any]:
    """
    Get HTML content for a specific navigation section by EPUB ID
    """
    try:
        epub_doc = get_epub_doc_or_404(epub_id)

        content = epub_service.get_content_by_nav_id(epub_doc["filename"], nav_id)
        return content
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting content: {str(e)}")


@router.get("/{epub_id:int}/styles")
async def get_epub_styles_by_id(epub_id: int) -> Dict[str, Any]:
    """
    Get CSS styles from an EPUB file by ID
    Returns sanitized CSS content for safe browser rendering
    """
    try:
        epub_doc = get_epub_doc_or_404(epub_id)

        styles = epub_service.get_epub_styles(epub_doc["filename"])
        return styles
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting styles: {str(e)}")


@router.put("/{epub_id:int}/progress")
async def save_epub_progress_by_id(
    epub_id: int, progress: EPUBProgressRequest
) -> Dict[str, Any]:
    """
    Save reading progress for an EPUB by ID
    """
    try:
        epub_doc = get_epub_doc_or_404(epub_id)

        success = db_service.save_epub_progress(
            epub_filename=epub_doc["filename"],
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
                "message": f"Reading progress saved for EPUB ID {epub_id}",
                "id": epub_id,
                "current_nav_id": progress.current_nav_id,
                "progress_percentage": progress.progress_percentage,
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to save reading progress"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error saving reading progress: {str(e)}"
        )


@router.get("/{epub_id:int}/progress")
async def get_epub_progress_by_id(epub_id: int) -> Dict[str, Any]:
    """
    Get reading progress for an EPUB by ID
    """
    try:
        epub_doc = get_epub_doc_or_404(epub_id)

        progress = db_service.get_epub_progress(epub_doc["filename"])

        if progress:
            # Add ID to response
            progress["id"] = epub_id
            return progress
        else:
            # Return default progress if none found
            return {
                "id": epub_id,
                "epub_filename": epub_doc["filename"],
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting reading progress: {str(e)}"
        )


@router.put("/{epub_id:int}/status")
async def update_epub_book_status_by_id(
    epub_id: int, status_request: BookStatusRequest
) -> Dict[str, Any]:
    """
    Update the reading status of an EPUB book by ID
    """
    try:
        epub_doc = get_epub_doc_or_404(epub_id)

        # Validate status
        valid_statuses = ["new", "reading", "finished"]
        if status_request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}",
            )

        success = db_service.update_epub_book_status(
            epub_filename=epub_doc["filename"],
            status=status_request.status,
            manual=status_request.manually_set,
        )

        if success:
            return {
                "success": True,
                "message": f"Status updated for EPUB ID {epub_id}",
                "id": epub_id,
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


@router.delete("/{epub_id:int}")
async def delete_epub_book_by_id(epub_id: int) -> Dict[str, Any]:
    """
    Delete an EPUB book by ID and all its associated data (file, thumbnails, progress, notes, highlights)
    """
    try:
        epub_doc = get_epub_doc_or_404(epub_id)

        filename = epub_doc["filename"]
        deletion_results = {}

        # Delete the EPUB file
        try:
            epub_file_path = epub_service.get_epub_path(filename)
            if epub_file_path.exists():
                epub_file_path.unlink()
                deletion_results["epub_file"] = True
            else:
                deletion_results["epub_file"] = False
        except Exception:
            deletion_results["epub_file"] = False
            logger.warning("Could not delete EPUB file %s", filename, exc_info=True)

        # Delete thumbnail
        try:
            thumbnail_path = epub_service.get_thumbnail_path(filename)
            if thumbnail_path.exists():
                thumbnail_path.unlink()
                deletion_results["thumbnail"] = True
            else:
                deletion_results["thumbnail"] = False
        except Exception:
            deletion_results["thumbnail"] = False
            logger.warning("Could not delete thumbnail for %s", filename, exc_info=True)

        # Delete all database data
        db_deletion_results = db_service.delete_all_epub_data(filename)
        deletion_results.update(db_deletion_results)

        # Check if any critical operations failed
        critical_failures = []
        if not deletion_results.get("epub_file", False):
            critical_failures.append("EPUB file")

        return {
            "success": True,
            "message": f"EPUB book with ID {epub_id} deleted successfully"
            + (
                f" (warnings: {', '.join(critical_failures)} not found)"
                if critical_failures
                else ""
            ),
            "id": epub_id,
            "filename": filename,
            "deletion_details": deletion_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting EPUB book: {str(e)}"
        )


# ========================================
# FILENAME-BASED ENDPOINTS (Legacy)
# ========================================


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
        all_notes = db_service.get_epub_notes_count_by_epub()
        all_highlights = db_service.get_epub_highlights_count_by_epub()

        # Get all EPUB documents from database once (avoid N+1 query)
        all_epub_docs = epub_documents_service.list_all()
        filename_to_id = {doc["filename"]: doc["id"] for doc in all_epub_docs}

        # Add reading progress, notes info, and highlights info to each EPUB
        for epub in epubs:
            filename = epub.get("filename")

            # Add EPUB ID from database using the pre-built map (O(1) lookup)
            if filename and filename in filename_to_id:
                epub["id"] = filename_to_id[filename]

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

            # Add notes information
            if filename and filename in all_notes:
                notes_info = all_notes[filename]
                epub["notes_info"] = {
                    "notes_count": notes_info["notes_count"],
                    "latest_note_date": notes_info["latest_note_date"],
                    "latest_note_title": notes_info["latest_note_title"],
                }
            else:
                epub["notes_info"] = None

            # Add highlights information
            if filename and filename in all_highlights:
                highlights_info = all_highlights[filename]
                epub["highlights_info"] = {
                    "highlights_count": highlights_info["highlights_count"],
                }
            else:
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
    Delete an EPUB book and all its associated data (file, thumbnails, progress, notes, highlights)
    """
    try:
        deletion_results = {}

        # Delete the EPUB file
        try:
            epub_file_path = epub_service.get_epub_path(filename)
            if epub_file_path.exists():
                epub_file_path.unlink()
                deletion_results["epub_file"] = True
            else:
                deletion_results["epub_file"] = False
        except Exception:
            deletion_results["epub_file"] = False
            logger.warning("Could not delete EPUB file %s", filename, exc_info=True)

        # Delete thumbnail
        try:
            thumbnail_path = epub_service.get_thumbnail_path(filename)
            if thumbnail_path.exists():
                thumbnail_path.unlink()
                deletion_results["thumbnail"] = True
            else:
                deletion_results["thumbnail"] = False
        except Exception:
            deletion_results["thumbnail"] = False
            logger.warning("Could not delete thumbnail for %s", filename, exc_info=True)

        # Delete all database data
        db_deletion_results = db_service.delete_all_epub_data(filename)
        deletion_results.update(db_deletion_results)

        # Check if any critical operations failed
        critical_failures = []
        if not deletion_results.get("epub_file", False):
            critical_failures.append("EPUB file")

        return {
            "success": True,
            "message": f"EPUB book {filename} deleted successfully"
            + (
                f" (warnings: {', '.join(critical_failures)} not found)"
                if critical_failures
                else ""
            ),
            "filename": filename,
            "deletion_details": deletion_results,
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


# ========================================
# EPUB CACHE MANAGEMENT ENDPOINTS
# ========================================


class CacheRefreshResponse(BaseModel):
    success: bool
    cache_built_at: str
    epub_count: int
    message: str


@router.post("/refresh-cache")
async def refresh_epub_cache() -> CacheRefreshResponse:
    """
    Refresh the EPUB cache by rebuilding from filesystem.
    This will rescan all EPUBs and regenerate thumbnails.
    """
    try:
        cache_info = epub_service.refresh_cache()

        return CacheRefreshResponse(
            success=True,
            cache_built_at=cache_info["cache_built_at"],
            epub_count=cache_info["epub_count"],
            message=f"Cache refreshed successfully. {cache_info['epub_count']} EPUBs cached.",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing cache: {str(e)}")

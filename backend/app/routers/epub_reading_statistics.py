"""
EPUB Reading Statistics Router

API endpoints for managing EPUB reading session statistics.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services.database_service import db_service

router = APIRouter(prefix="/epub/reading-statistics", tags=["epub-reading-statistics"])


class EPUBSessionUpdateRequest(BaseModel):
    """Request model for updating/creating an EPUB reading session."""

    session_id: str
    epub_id: int
    words_read: int
    time_spent_seconds: float


@router.api_route("/session/update", methods=["PUT", "POST"])
async def update_session(request: EPUBSessionUpdateRequest):
    """
    Update or create an EPUB reading session.

    Args:
        request: EPUBSessionUpdateRequest containing:
            - session_id: Unique UUID for the session
            - epub_id: EPUB document ID
            - words_read: Total words read in this session
            - time_spent_seconds: Time spent reading in seconds

    Returns:
        dict: Success message

    Raises:
        HTTPException: If the database operation fails
    """
    try:
        success = db_service.epub_reading_statistics.upsert_session(
            session_id=request.session_id,
            epub_id=request.epub_id,
            words_read=request.words_read,
            time_spent_seconds=request.time_spent_seconds,
        )

        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to update EPUB reading session"
            )

        return {
            "message": "Session updated successfully",
            "session_id": request.session_id,
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating session: {str(e)}")


@router.get("/sessions/{epub_id:int}")
async def get_sessions_by_id(
    epub_id: int,
    limit: Optional[int] = Query(
        None, ge=1, description="Maximum number of sessions to return"
    ),
    offset: Optional[int] = Query(None, ge=0, description="Number of sessions to skip"),
):
    """
    Get all reading sessions for a specific EPUB by ID.

    Args:
        epub_id: ID of the EPUB (URL path parameter)
        limit: Optional maximum number of sessions to return
        offset: Optional number of sessions to skip (for pagination)

    Returns:
        dict: Dictionary containing epub_id, total_sessions, and sessions list

    Raises:
        HTTPException: If the database operation fails
    """
    try:
        result = db_service.epub_reading_statistics.get_sessions_by_epub_id(
            epub_id=epub_id, limit=limit, offset=offset
        )
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving sessions: {str(e)}"
        )

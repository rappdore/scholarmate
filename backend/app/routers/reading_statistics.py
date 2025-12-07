"""
Reading Statistics Router

API endpoints for managing reading session statistics.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services.database_service import db_service

router = APIRouter(prefix="/reading-statistics", tags=["reading-statistics"])


class SessionUpdateRequest(BaseModel):
    """Request model for updating/creating a reading session."""

    session_id: str
    pdf_filename: str
    pages_read: int
    average_time_per_page: float


@router.put("/session/update")
async def update_session(request: SessionUpdateRequest):
    """
    Update or create a reading session.

    This endpoint uses upsert logic - it will create a new session if the session_id
    doesn't exist, or update the existing session if it does.

    Args:
        request: SessionUpdateRequest containing:
            - session_id: Unique UUID for the session
            - pdf_filename: Name of the PDF being read
            - pages_read: Total pages read in this session
            - average_time_per_page: Average time per page in seconds

    Returns:
        dict: Success message

    Raises:
        HTTPException: If the database operation fails
    """
    try:
        success = db_service.reading_statistics.upsert_session(
            session_id=request.session_id,
            pdf_filename=request.pdf_filename,
            pages_read=request.pages_read,
            average_time_per_page=request.average_time_per_page,
        )

        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to update reading session"
            )

        return {
            "message": "Session updated successfully",
            "session_id": request.session_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating session: {str(e)}")


@router.get("/sessions/{pdf_filename}")
async def get_sessions(
    pdf_filename: str,
    limit: Optional[int] = Query(
        None, ge=1, description="Maximum number of sessions to return"
    ),
    offset: Optional[int] = Query(None, ge=0, description="Number of sessions to skip"),
):
    """
    Get all reading sessions for a specific PDF.

    This endpoint returns all sessions for the given PDF filename, ordered by
    session_start descending (most recent first). All statistics calculations
    should be performed on the frontend.

    Args:
        pdf_filename: Name of the PDF file (URL path parameter)
        limit: Optional maximum number of sessions to return
        offset: Optional number of sessions to skip (for pagination)

    Returns:
        dict: Dictionary containing:
            - pdf_filename: The PDF filename
            - total_sessions: Total number of sessions for this PDF
            - sessions: List of session objects

    Raises:
        HTTPException: If the database operation fails
    """
    try:
        result = db_service.reading_statistics.get_sessions_by_pdf(
            pdf_filename=pdf_filename, limit=limit, offset=offset
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving sessions: {str(e)}"
        )

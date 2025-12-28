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
    pdf_id: int
    pages_read: int
    average_time_per_page: float


@router.put("/session/update")
async def update_session(request: SessionUpdateRequest):
    """
    Update or create a reading session.

    Args:
        request: SessionUpdateRequest containing:
            - session_id: Unique UUID for the session
            - pdf_id: PDF document ID
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
            pdf_id=request.pdf_id,
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

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating session: {str(e)}")


@router.get("/sessions/pdf/{pdf_id:int}")
async def get_sessions_by_id(
    pdf_id: int,
    limit: Optional[int] = Query(
        None, ge=1, description="Maximum number of sessions to return"
    ),
    offset: Optional[int] = Query(None, ge=0, description="Number of sessions to skip"),
):
    """
    Get all reading sessions for a specific PDF by ID.

    Args:
        pdf_id: ID of the PDF (URL path parameter)
        limit: Optional maximum number of sessions to return
        offset: Optional number of sessions to skip (for pagination)

    Returns:
        dict: Dictionary containing pdf_id, total_sessions, and sessions list

    Raises:
        HTTPException: If the database operation fails
    """
    try:
        result = db_service.reading_statistics.get_sessions_by_pdf_id(
            pdf_id=pdf_id, limit=limit, offset=offset
        )
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving sessions: {str(e)}"
        )

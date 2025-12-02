"""
Reading Statistics Router

API endpoints for managing reading session statistics.
"""

from fastapi import APIRouter, HTTPException
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

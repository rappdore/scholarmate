"""
Reading Statistics Router

API endpoints for managing PDF reading session statistics on the unified
sessions service. ``pages_read``/``average_time_per_page`` remain the PDF
wire vocabulary; storage is units_read + time_spent_seconds.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..services.registry import get_sessions_service
from ..services.sessions_service import SessionsService

router = APIRouter(prefix="/reading-statistics", tags=["reading-statistics"])


class SessionUpdateRequest(BaseModel):
    """Request model for updating/creating a reading session."""

    session_id: str
    pdf_id: int
    pages_read: int
    average_time_per_page: float


@router.put("/session/update")
def update_session(
    request: SessionUpdateRequest,
    sessions_service: SessionsService = Depends(get_sessions_service),
):
    """
    Update or create a reading session.
    """
    try:
        success = sessions_service.upsert_session(
            session_id=request.session_id,
            document_id=request.pdf_id,
            units_read=request.pages_read,
            time_spent_seconds=request.pages_read * request.average_time_per_page,
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
def get_sessions_by_id(
    pdf_id: int,
    limit: Optional[int] = Query(
        None, ge=1, description="Maximum number of sessions to return"
    ),
    offset: Optional[int] = Query(None, ge=0, description="Number of sessions to skip"),
    sessions_service: SessionsService = Depends(get_sessions_service),
):
    """
    Get all reading sessions for a specific PDF by ID.
    """
    try:
        page = sessions_service.get_sessions(pdf_id, limit=limit, offset=offset)
        return {
            "pdf_id": pdf_id,
            "total_sessions": page.total_sessions,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "session_start": s.session_start,
                    "last_updated": s.last_updated,
                    "pages_read": s.units_read,
                    "average_time_per_page": (
                        s.time_spent_seconds / s.units_read if s.units_read else 0.0
                    ),
                }
                for s in page.sessions
            ],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving sessions: {str(e)}"
        )

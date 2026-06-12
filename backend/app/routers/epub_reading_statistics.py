"""
EPUB Reading Statistics Router

API endpoints for managing EPUB reading session statistics on the unified
sessions service. ``words_read`` remains the EPUB wire vocabulary; storage
is units_read + time_spent_seconds.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..services.registry import get_sessions_service
from ..services.sessions_service import SessionsService

router = APIRouter(prefix="/epub/reading-statistics", tags=["epub-reading-statistics"])


class EPUBSessionUpdateRequest(BaseModel):
    """Request model for updating/creating an EPUB reading session."""

    session_id: str
    epub_id: int
    words_read: int
    time_spent_seconds: float


@router.put("/session/update")
def update_session(
    request: EPUBSessionUpdateRequest,
    sessions_service: SessionsService = Depends(get_sessions_service),
):
    """
    Update or create an EPUB reading session.
    """
    try:
        success = sessions_service.upsert_session(
            session_id=request.session_id,
            document_id=request.epub_id,
            units_read=request.words_read,
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
def get_sessions_by_id(
    epub_id: int,
    limit: Optional[int] = Query(
        None, ge=1, description="Maximum number of sessions to return"
    ),
    offset: Optional[int] = Query(None, ge=0, description="Number of sessions to skip"),
    sessions_service: SessionsService = Depends(get_sessions_service),
):
    """
    Get all reading sessions for a specific EPUB by ID.
    """
    try:
        page = sessions_service.get_sessions(epub_id, limit=limit, offset=offset)
        return {
            "epub_id": epub_id,
            "total_sessions": page.total_sessions,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "session_start": s.session_start,
                    "last_updated": s.last_updated,
                    "words_read": s.units_read,
                    "time_spent_seconds": s.time_spent_seconds,
                }
                for s in page.sessions
            ],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving sessions: {str(e)}"
        )

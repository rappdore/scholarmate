"""
Reading Statistics Router

API endpoints for managing reading session statistics.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services.database_service import db_service
from ..services.pdf_documents_service import PDFDocumentsService

router = APIRouter(prefix="/reading-statistics", tags=["reading-statistics"])

# Initialize services
pdf_documents_service = PDFDocumentsService()


class SessionUpdateRequest(BaseModel):
    """Request model for updating/creating a reading session."""

    session_id: str
    pdf_id: Optional[int] = None  # NEW: ID-based reference
    pdf_filename: Optional[str] = None  # Legacy: filename-based reference
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
            - pdf_id (preferred) or pdf_filename (legacy): PDF identifier
            - pages_read: Total pages read in this session
            - average_time_per_page: Average time per page in seconds

    Returns:
        dict: Success message

    Raises:
        HTTPException: If the database operation fails
    """
    try:
        # Resolve filename from pdf_id if provided, otherwise use pdf_filename
        if request.pdf_id is not None:
            pdf_doc = pdf_documents_service.get_by_id(request.pdf_id)
            if not pdf_doc:
                raise HTTPException(status_code=404, detail="PDF not found")
            pdf_filename = pdf_doc["filename"]
        elif request.pdf_filename is not None:
            pdf_filename = request.pdf_filename
        else:
            raise HTTPException(
                status_code=400, detail="Either pdf_id or pdf_filename must be provided"
            )

        success = db_service.reading_statistics.upsert_session(
            session_id=request.session_id,
            pdf_filename=pdf_filename,
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating session: {str(e)}")


# ========================================
# ID-BASED ENDPOINTS (Phase 5)
# ========================================


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

    This endpoint returns all sessions for the given PDF ID, ordered by
    session_start descending (most recent first). All statistics calculations
    should be performed on the frontend.

    Args:
        pdf_id: ID of the PDF (URL path parameter)
        limit: Optional maximum number of sessions to return
        offset: Optional number of sessions to skip (for pagination)

    Returns:
        dict: Dictionary containing:
            - pdf_id: The PDF ID
            - pdf_filename: The PDF filename
            - total_sessions: Total number of sessions for this PDF
            - sessions: List of session objects

    Raises:
        HTTPException: If the database operation fails
    """
    try:
        # Lookup filename from ID
        pdf_doc = pdf_documents_service.get_by_id(pdf_id)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        result = db_service.reading_statistics.get_sessions_by_pdf(
            pdf_filename=pdf_doc["filename"], limit=limit, offset=offset
        )

        # Add ID to response
        result["pdf_id"] = pdf_id
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving sessions: {str(e)}"
        )


# ========================================
# FILENAME-BASED ENDPOINTS (Legacy)
# ========================================


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

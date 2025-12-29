"""
Request Tracking Service

This service tracks active streaming chat requests to enable cancellation functionality.
It maintains a registry of active requests with their associated tasks for graceful cancellation.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ActiveRequest:
    """Represents an active streaming request"""

    request_id: str
    filename: str
    document_type: str  # 'pdf' or 'epub'
    page_num: int | None = None  # For PDF
    nav_id: str | None = None  # For EPUB
    created_at: datetime = None
    task: asyncio.Task | None = None
    cancelled: bool = False

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class RequestTrackingService:
    """Service to track and manage active streaming chat requests"""

    def __init__(self):
        self._active_requests: dict[str, ActiveRequest] = {}
        self._cleanup_interval = 3600  # Cleanup every hour
        self._max_request_age = timedelta(hours=2)  # Remove requests older than 2 hours

    def generate_request_id(self) -> str:
        """Generate a unique request ID"""
        return str(uuid.uuid4())

    def register_request(
        self,
        filename: str,
        document_type: str,
        page_num: int | None = None,
        nav_id: str | None = None,
        request_id: str | None = None,
    ) -> str:
        """
        Register a new streaming request

        Args:
            filename: Document filename
            document_type: 'pdf' or 'epub'
            page_num: Page number for PDF documents
            nav_id: Navigation ID for EPUB documents
            request_id: Optional specific request ID, generates new one if not provided

        Returns:
            The request ID for this request
        """
        if request_id is None:
            request_id = self.generate_request_id()

        active_request = ActiveRequest(
            request_id=request_id,
            filename=filename,
            document_type=document_type,
            page_num=page_num,
            nav_id=nav_id,
        )

        self._active_requests[request_id] = active_request
        logger.info(f"Registered streaming request {request_id} for {filename}")

        return request_id

    def set_request_task(self, request_id: str, task: asyncio.Task) -> bool:
        """
        Associate an asyncio task with a request for cancellation

        Args:
            request_id: The request ID
            task: The asyncio task handling the streaming

        Returns:
            True if task was set, False if request not found
        """
        if request_id in self._active_requests:
            self._active_requests[request_id].task = task
            logger.debug(f"Set task for request {request_id}")
            return True
        return False

    def cancel_request(self, request_id: str) -> bool:
        """
        Cancel a streaming request

        Args:
            request_id: The request ID to cancel

        Returns:
            True if request was cancelled, False if not found or already completed
        """
        if request_id not in self._active_requests:
            logger.warning(f"Request {request_id} not found for cancellation")
            return False

        active_request = self._active_requests[request_id]

        if active_request.cancelled:
            logger.info(f"Request {request_id} already cancelled")
            return True

        # Mark as cancelled
        active_request.cancelled = True

        # Cancel the associated task if it exists
        if active_request.task and not active_request.task.done():
            active_request.task.cancel()
            logger.info(f"Cancelled request {request_id} and its associated task")
        else:
            logger.info(f"Cancelled request {request_id} (no active task)")

        return True

    def is_cancelled(self, request_id: str) -> bool:
        """
        Check if a request has been cancelled

        Args:
            request_id: The request ID to check

        Returns:
            True if request is cancelled, False otherwise
        """
        if request_id in self._active_requests:
            return self._active_requests[request_id].cancelled
        return False

    def complete_request(self, request_id: str) -> bool:
        """
        Mark a request as completed and remove it from tracking

        Args:
            request_id: The request ID to complete

        Returns:
            True if request was found and removed, False otherwise
        """
        if request_id in self._active_requests:
            del self._active_requests[request_id]
            logger.info(f"Completed and removed request {request_id}")
            return True
        return False

    def get_active_requests(self) -> dict[str, ActiveRequest]:
        """Get all active requests (for debugging/monitoring)"""
        return self._active_requests.copy()

    def cleanup_old_requests(self) -> int:
        """
        Clean up old requests that may have been abandoned

        Returns:
            Number of requests cleaned up
        """
        now = datetime.now()
        to_remove = []

        for request_id, request in self._active_requests.items():
            if now - request.created_at > self._max_request_age:
                to_remove.append(request_id)

        for request_id in to_remove:
            if self._active_requests[request_id].task:
                self._active_requests[request_id].task.cancel()
            del self._active_requests[request_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old requests")

        return len(to_remove)


# Global instance
request_tracking_service = RequestTrackingService()

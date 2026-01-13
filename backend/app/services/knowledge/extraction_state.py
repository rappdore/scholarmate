"""
Extraction State Management Module

This module provides thread-safe tracking of running extractions and cancellation support.
It enables:
- Tracking which extractions are currently running
- Cooperative cancellation of running extractions
- Progress monitoring for running extractions
"""

import logging
import threading
import time
from dataclasses import dataclass, field, replace
from enum import Enum, auto

logger = logging.getLogger(__name__)


class ExtractionStatus(Enum):
    """Status of an extraction operation."""

    PENDING = auto()
    RUNNING = auto()
    CANCELLING = auto()
    CANCELLED = auto()
    COMPLETED = auto()
    FAILED = auto()


class ExtractionPhase(Enum):
    """Phase of an extraction operation."""

    CONCEPTS = auto()
    RELATIONSHIPS = auto()


@dataclass
class ExtractionState:
    """State of a single extraction operation."""

    book_id: int
    book_type: str
    section_id: str
    status: ExtractionStatus = ExtractionStatus.PENDING
    phase: ExtractionPhase = ExtractionPhase.CONCEPTS
    started_at: float = field(default_factory=time.time)
    # Concept extraction progress
    chunks_processed: int = 0
    total_chunks: int = 0
    concepts_stored: int = 0
    # Relationship extraction progress
    rel_chunks_processed: int = 0
    rel_total_chunks: int = 0
    relationships_stored: int = 0
    error_message: str | None = None

    def _calculate_progress(self, processed: int, total: int) -> float:
        """Calculate progress percentage."""
        if total > 0:
            return round(processed / total * 100, 1)
        return 0.0

    def to_dict(self) -> dict:
        """Convert state to dictionary for API response."""
        concept_progress = self._calculate_progress(
            self.chunks_processed, self.total_chunks
        )
        rel_progress = self._calculate_progress(
            self.rel_chunks_processed, self.rel_total_chunks
        )
        phase_progress = (
            concept_progress if self.phase == ExtractionPhase.CONCEPTS else rel_progress
        )

        return {
            "book_id": self.book_id,
            "book_type": self.book_type,
            "section_id": self.section_id,
            "status": self.status.name.lower(),
            "phase": self.phase.name.lower(),
            "started_at": self.started_at,
            "elapsed_seconds": time.time() - self.started_at,
            # Concept extraction progress
            "chunks_processed": self.chunks_processed,
            "total_chunks": self.total_chunks,
            "concepts_stored": self.concepts_stored,
            "progress_percent": concept_progress,
            # Relationship extraction progress
            "rel_chunks_processed": self.rel_chunks_processed,
            "rel_total_chunks": self.rel_total_chunks,
            "relationships_stored": self.relationships_stored,
            "phase_progress_percent": phase_progress,
            "error_message": self.error_message,
        }

    def to_dict_v2(self) -> dict:
        """Convert state to dictionary for API response (v2 single-phase extraction).

        This method provides a simplified progress structure for single-pass triple
        extraction where concepts and relationships are extracted together in one LLM call.
        Unlike to_dict(), this method:
        - Does not include separate phase tracking (no 'phase' field)
        - Does not include relationship-specific chunk progress fields
        - Uses a single progress_percent based on overall chunk progress
        """
        progress = self._calculate_progress(self.chunks_processed, self.total_chunks)

        return {
            "book_id": self.book_id,
            "book_type": self.book_type,
            "section_id": self.section_id,
            "status": self.status.name.lower(),
            "started_at": self.started_at,
            "elapsed_seconds": time.time() - self.started_at,
            "chunks_processed": self.chunks_processed,
            "total_chunks": self.total_chunks,
            "concepts_stored": self.concepts_stored,
            "relationships_stored": self.relationships_stored,
            "progress_percent": progress,
            "error_message": self.error_message,
        }


class ExtractionRegistry:
    """
    Thread-safe registry for tracking running extractions.

    Provides cooperative cancellation - extractions must check the registry
    between chunks to see if they should stop.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Key: "{book_id}:{book_type}:{section_id}"
        self._extractions: dict[str, ExtractionState] = {}

    def _make_key(self, book_id: int, book_type: str, section_id: str) -> str:
        """Create unique key for an extraction."""
        return f"{book_id}:{book_type}:{section_id}"

    def register_extraction(
        self,
        book_id: int,
        book_type: str,
        section_id: str,
    ) -> str:
        """
        Register a new extraction as running.

        Also performs opportunistic cleanup of old finished extractions
        to prevent unbounded memory growth.

        Returns:
            The extraction key for later reference.
        """
        key = self._make_key(book_id, book_type, section_id)
        with self._lock:
            self._extractions[key] = ExtractionState(
                book_id=book_id,
                book_type=book_type,
                section_id=section_id,
                status=ExtractionStatus.RUNNING,
            )
            logger.info(f"Registered extraction: {key}")

        # Opportunistic cleanup of old finished extractions (outside lock)
        # This prevents unbounded growth of _extractions dict
        self.cleanup_finished(max_age_seconds=300)

        return key

    def unregister_extraction(
        self,
        book_id: int,
        book_type: str,
        section_id: str,
    ) -> None:
        """Remove an extraction from the registry."""
        key = self._make_key(book_id, book_type, section_id)
        with self._lock:
            if key in self._extractions:
                del self._extractions[key]
                logger.info(f"Unregistered extraction: {key}")

    def update_progress(
        self,
        book_id: int,
        book_type: str,
        section_id: str,
        chunks_processed: int,
        total_chunks: int,
        concepts_stored: int,
    ) -> None:
        """Update progress for a running extraction (concept phase)."""
        key = self._make_key(book_id, book_type, section_id)
        with self._lock:
            if key in self._extractions:
                state = self._extractions[key]
                state.chunks_processed = chunks_processed
                state.total_chunks = total_chunks
                state.concepts_stored = concepts_stored

    def update_phase(
        self,
        book_id: int,
        book_type: str,
        section_id: str,
        phase: ExtractionPhase,
    ) -> None:
        """Update the current extraction phase."""
        key = self._make_key(book_id, book_type, section_id)
        with self._lock:
            if key in self._extractions:
                self._extractions[key].phase = phase
                logger.info(f"Updated phase to {phase.name} for: {key}")

    def update_relationship_progress(
        self,
        book_id: int,
        book_type: str,
        section_id: str,
        rel_chunks_processed: int,
        rel_total_chunks: int,
        relationships_stored: int,
    ) -> None:
        """Update progress for relationship extraction phase."""
        key = self._make_key(book_id, book_type, section_id)
        with self._lock:
            if key in self._extractions:
                state = self._extractions[key]
                state.rel_chunks_processed = rel_chunks_processed
                state.rel_total_chunks = rel_total_chunks
                state.relationships_stored = relationships_stored

    def mark_completed(
        self,
        book_id: int,
        book_type: str,
        section_id: str,
    ) -> None:
        """Mark an extraction as completed."""
        key = self._make_key(book_id, book_type, section_id)
        with self._lock:
            if key in self._extractions:
                self._extractions[key].status = ExtractionStatus.COMPLETED
                logger.info(f"Extraction completed: {key}")

    def mark_failed(
        self,
        book_id: int,
        book_type: str,
        section_id: str,
        error: str,
    ) -> None:
        """Mark an extraction as failed."""
        key = self._make_key(book_id, book_type, section_id)
        with self._lock:
            if key in self._extractions:
                self._extractions[key].status = ExtractionStatus.FAILED
                self._extractions[key].error_message = error
                logger.info(f"Extraction failed: {key} - {error}")

    def request_cancellation(
        self,
        book_id: int,
        book_type: str,
        section_id: str,
    ) -> bool:
        """
        Request cancellation of a running extraction.

        Returns:
            True if cancellation was requested, False if extraction not found.
        """
        key = self._make_key(book_id, book_type, section_id)
        with self._lock:
            if key in self._extractions:
                state = self._extractions[key]
                if state.status == ExtractionStatus.RUNNING:
                    state.status = ExtractionStatus.CANCELLING
                    logger.info(f"Cancellation requested for: {key}")
                    return True
        return False

    def is_cancellation_requested(
        self,
        book_id: int,
        book_type: str,
        section_id: str,
    ) -> bool:
        """
        Check if cancellation has been requested for an extraction.

        This should be called by the extraction process between chunks.
        """
        key = self._make_key(book_id, book_type, section_id)
        with self._lock:
            if key in self._extractions:
                return self._extractions[key].status == ExtractionStatus.CANCELLING
        return False

    def mark_cancelled(
        self,
        book_id: int,
        book_type: str,
        section_id: str,
    ) -> None:
        """Mark an extraction as cancelled (after it has stopped)."""
        key = self._make_key(book_id, book_type, section_id)
        with self._lock:
            if key in self._extractions:
                self._extractions[key].status = ExtractionStatus.CANCELLED
                logger.info(f"Extraction cancelled: {key}")

    def get_extraction_state(
        self,
        book_id: int,
        book_type: str,
        section_id: str,
    ) -> ExtractionState | None:
        """Get the state of a specific extraction.

        Returns a copy to prevent external mutation of internal state.
        """
        key = self._make_key(book_id, book_type, section_id)
        with self._lock:
            state = self._extractions.get(key)
            if state is None:
                return None
            # Return a copy to prevent external mutation
            return replace(state)

    def get_running_extractions(
        self,
        book_id: int | None = None,
        book_type: str | None = None,
    ) -> list[ExtractionState]:
        """
        Get all running extractions, optionally filtered by book.

        Args:
            book_id: Filter by book ID (optional)
            book_type: Filter by book type (optional)

        Returns:
            List of extraction states (copies to prevent external mutation).
        """
        with self._lock:
            results = []
            for state in self._extractions.values():
                if state.status not in (
                    ExtractionStatus.RUNNING,
                    ExtractionStatus.CANCELLING,
                ):
                    continue
                if book_id is not None and state.book_id != book_id:
                    continue
                if book_type is not None and state.book_type != book_type:
                    continue
                # Return copies to prevent external mutation
                results.append(replace(state))
            return results

    def cancel_all_for_book(
        self,
        book_id: int,
        book_type: str,
    ) -> int:
        """
        Request cancellation for all running extractions for a book.

        Returns:
            Number of extractions for which cancellation was requested.
        """
        count = 0
        with self._lock:
            for key, state in self._extractions.items():
                if (
                    state.book_id == book_id
                    and state.book_type == book_type
                    and state.status == ExtractionStatus.RUNNING
                ):
                    state.status = ExtractionStatus.CANCELLING
                    count += 1
                    logger.info(f"Cancellation requested for: {key}")
        return count

    def cleanup_finished(self, max_age_seconds: float = 300) -> int:
        """
        Remove finished extractions older than max_age_seconds.

        Returns:
            Number of extractions cleaned up.
        """
        now = time.time()
        count = 0
        with self._lock:
            keys_to_remove = []
            for key, state in self._extractions.items():
                if state.status in (
                    ExtractionStatus.COMPLETED,
                    ExtractionStatus.CANCELLED,
                    ExtractionStatus.FAILED,
                ):
                    if now - state.started_at > max_age_seconds:
                        keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._extractions[key]
                count += 1
        return count


# Global singleton instance
_extraction_registry: ExtractionRegistry | None = None
_singleton_lock = threading.Lock()


def get_extraction_registry() -> ExtractionRegistry:
    """Get the global extraction registry instance (thread-safe)."""
    global _extraction_registry
    if _extraction_registry is None:
        with _singleton_lock:
            if _extraction_registry is None:
                _extraction_registry = ExtractionRegistry()
    return _extraction_registry

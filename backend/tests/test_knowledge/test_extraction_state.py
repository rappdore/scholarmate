"""Tests for the extraction state management module."""

import time

import pytest

from app.services.knowledge.extraction_state import (
    ExtractionPhase,
    ExtractionRegistry,
    ExtractionState,
    ExtractionStatus,
)


class TestExtractionState:
    """Tests for ExtractionState dataclass."""

    def test_state_initialization(self) -> None:
        """Test ExtractionState initializes with correct defaults."""
        state = ExtractionState(
            book_id=1,
            book_type="epub",
            section_id="chapter1",
        )

        assert state.book_id == 1
        assert state.book_type == "epub"
        assert state.section_id == "chapter1"
        assert state.status == ExtractionStatus.PENDING
        assert state.phase == ExtractionPhase.CONCEPTS
        assert state.chunks_processed == 0
        assert state.total_chunks == 0
        assert state.concepts_stored == 0
        # Relationship progress fields
        assert state.rel_chunks_processed == 0
        assert state.rel_total_chunks == 0
        assert state.relationships_stored == 0
        assert state.error_message is None

    def test_state_to_dict(self) -> None:
        """Test ExtractionState.to_dict() returns correct dictionary."""
        state = ExtractionState(
            book_id=1,
            book_type="epub",
            section_id="chapter1",
            status=ExtractionStatus.RUNNING,
            chunks_processed=5,
            total_chunks=10,
            concepts_stored=15,
        )

        result = state.to_dict()

        assert result["book_id"] == 1
        assert result["book_type"] == "epub"
        assert result["section_id"] == "chapter1"
        assert result["status"] == "running"
        assert result["phase"] == "concepts"
        assert result["chunks_processed"] == 5
        assert result["total_chunks"] == 10
        assert result["concepts_stored"] == 15
        assert result["progress_percent"] == 50.0
        # Relationship progress fields
        assert result["rel_chunks_processed"] == 0
        assert result["rel_total_chunks"] == 0
        assert result["relationships_stored"] == 0
        assert result["phase_progress_percent"] == 50.0  # Same as concept progress
        assert "elapsed_seconds" in result
        assert "started_at" in result

    def test_state_to_dict_relationship_phase(self) -> None:
        """Test ExtractionState.to_dict() for relationship phase."""
        state = ExtractionState(
            book_id=1,
            book_type="epub",
            section_id="chapter1",
            status=ExtractionStatus.RUNNING,
            phase=ExtractionPhase.RELATIONSHIPS,
            chunks_processed=10,
            total_chunks=10,
            concepts_stored=20,
            rel_chunks_processed=3,
            rel_total_chunks=5,
            relationships_stored=8,
        )

        result = state.to_dict()

        assert result["phase"] == "relationships"
        assert result["progress_percent"] == 100.0  # Concept progress
        assert result["rel_chunks_processed"] == 3
        assert result["rel_total_chunks"] == 5
        assert result["relationships_stored"] == 8
        assert result["phase_progress_percent"] == 60.0  # 3/5 = 60%

    def test_state_progress_percent_zero_chunks(self) -> None:
        """Test progress percent is 0 when total_chunks is 0."""
        state = ExtractionState(
            book_id=1,
            book_type="epub",
            section_id="chapter1",
            total_chunks=0,
        )

        result = state.to_dict()
        assert result["progress_percent"] == 0


class TestExtractionRegistry:
    """Tests for ExtractionRegistry."""

    @pytest.fixture
    def registry(self) -> ExtractionRegistry:
        """Create a fresh registry for each test."""
        return ExtractionRegistry()

    def test_register_extraction(self, registry: ExtractionRegistry) -> None:
        """Test registering a new extraction."""
        key = registry.register_extraction(1, "epub", "chapter1")

        assert key == "1:epub:chapter1"

        state = registry.get_extraction_state(1, "epub", "chapter1")
        assert state is not None
        assert state.status == ExtractionStatus.RUNNING

    def test_unregister_extraction(self, registry: ExtractionRegistry) -> None:
        """Test unregistering an extraction."""
        registry.register_extraction(1, "epub", "chapter1")
        registry.unregister_extraction(1, "epub", "chapter1")

        state = registry.get_extraction_state(1, "epub", "chapter1")
        assert state is None

    def test_update_progress(self, registry: ExtractionRegistry) -> None:
        """Test updating extraction progress."""
        registry.register_extraction(1, "epub", "chapter1")
        registry.update_progress(1, "epub", "chapter1", 5, 10, 15)

        state = registry.get_extraction_state(1, "epub", "chapter1")
        assert state is not None
        assert state.chunks_processed == 5
        assert state.total_chunks == 10
        assert state.concepts_stored == 15

    def test_mark_completed(self, registry: ExtractionRegistry) -> None:
        """Test marking an extraction as completed."""
        registry.register_extraction(1, "epub", "chapter1")
        registry.mark_completed(1, "epub", "chapter1")

        state = registry.get_extraction_state(1, "epub", "chapter1")
        assert state is not None
        assert state.status == ExtractionStatus.COMPLETED

    def test_mark_failed(self, registry: ExtractionRegistry) -> None:
        """Test marking an extraction as failed."""
        registry.register_extraction(1, "epub", "chapter1")
        registry.mark_failed(1, "epub", "chapter1", "Test error")

        state = registry.get_extraction_state(1, "epub", "chapter1")
        assert state is not None
        assert state.status == ExtractionStatus.FAILED
        assert state.error_message == "Test error"

    def test_request_cancellation(self, registry: ExtractionRegistry) -> None:
        """Test requesting cancellation of a running extraction."""
        registry.register_extraction(1, "epub", "chapter1")

        result = registry.request_cancellation(1, "epub", "chapter1")

        assert result is True
        state = registry.get_extraction_state(1, "epub", "chapter1")
        assert state is not None
        assert state.status == ExtractionStatus.CANCELLING

    def test_request_cancellation_nonexistent(
        self, registry: ExtractionRegistry
    ) -> None:
        """Test requesting cancellation of nonexistent extraction."""
        result = registry.request_cancellation(1, "epub", "chapter1")
        assert result is False

    def test_request_cancellation_not_running(
        self, registry: ExtractionRegistry
    ) -> None:
        """Test requesting cancellation of non-running extraction."""
        registry.register_extraction(1, "epub", "chapter1")
        registry.mark_completed(1, "epub", "chapter1")

        result = registry.request_cancellation(1, "epub", "chapter1")
        assert result is False

    def test_is_cancellation_requested(self, registry: ExtractionRegistry) -> None:
        """Test checking if cancellation is requested."""
        registry.register_extraction(1, "epub", "chapter1")

        # Not requested yet
        assert registry.is_cancellation_requested(1, "epub", "chapter1") is False

        # Request cancellation
        registry.request_cancellation(1, "epub", "chapter1")

        # Now it should return True
        assert registry.is_cancellation_requested(1, "epub", "chapter1") is True

    def test_mark_cancelled(self, registry: ExtractionRegistry) -> None:
        """Test marking an extraction as cancelled."""
        registry.register_extraction(1, "epub", "chapter1")
        registry.request_cancellation(1, "epub", "chapter1")
        registry.mark_cancelled(1, "epub", "chapter1")

        state = registry.get_extraction_state(1, "epub", "chapter1")
        assert state is not None
        assert state.status == ExtractionStatus.CANCELLED

    def test_get_running_extractions(self, registry: ExtractionRegistry) -> None:
        """Test getting all running extractions."""
        registry.register_extraction(1, "epub", "chapter1")
        registry.register_extraction(1, "epub", "chapter2")
        registry.register_extraction(2, "pdf", "page_1")

        # Complete one
        registry.mark_completed(1, "epub", "chapter2")

        running = registry.get_running_extractions()

        assert len(running) == 2
        section_ids = {e.section_id for e in running}
        assert "chapter1" in section_ids
        assert "page_1" in section_ids
        assert "chapter2" not in section_ids

    def test_get_running_extractions_filtered(
        self, registry: ExtractionRegistry
    ) -> None:
        """Test getting running extractions filtered by book."""
        registry.register_extraction(1, "epub", "chapter1")
        registry.register_extraction(1, "epub", "chapter2")
        registry.register_extraction(2, "pdf", "page_1")

        running = registry.get_running_extractions(book_id=1)
        assert len(running) == 2

        running = registry.get_running_extractions(book_type="pdf")
        assert len(running) == 1
        assert running[0].section_id == "page_1"

    def test_cancel_all_for_book(self, registry: ExtractionRegistry) -> None:
        """Test cancelling all extractions for a book."""
        registry.register_extraction(1, "epub", "chapter1")
        registry.register_extraction(1, "epub", "chapter2")
        registry.register_extraction(2, "epub", "chapter1")

        count = registry.cancel_all_for_book(1, "epub")

        assert count == 2

        # Book 1 chapters should be cancelling
        state1 = registry.get_extraction_state(1, "epub", "chapter1")
        state2 = registry.get_extraction_state(1, "epub", "chapter2")
        assert state1 is not None and state1.status == ExtractionStatus.CANCELLING
        assert state2 is not None and state2.status == ExtractionStatus.CANCELLING

        # Book 2 should still be running
        state3 = registry.get_extraction_state(2, "epub", "chapter1")
        assert state3 is not None and state3.status == ExtractionStatus.RUNNING

    def test_cleanup_finished(self, registry: ExtractionRegistry) -> None:
        """Test cleanup of old finished extractions."""
        # Create some extractions
        registry.register_extraction(1, "epub", "chapter1")
        registry.register_extraction(1, "epub", "chapter2")
        registry.register_extraction(1, "epub", "chapter3")

        # Complete them
        registry.mark_completed(1, "epub", "chapter1")
        registry.mark_cancelled(1, "epub", "chapter2")

        # Manually set old start time on the internal state objects
        # (get_extraction_state returns copies, so we need to access internal state directly)
        key1 = registry._make_key(1, "epub", "chapter1")
        key2 = registry._make_key(1, "epub", "chapter2")
        with registry._lock:
            registry._extractions[key1].started_at = (
                time.time() - 400
            )  # 400 seconds old
            registry._extractions[key2].started_at = (
                time.time() - 400
            )  # 400 seconds old

        # Cleanup with 300 second max age
        count = registry.cleanup_finished(max_age_seconds=300)

        assert count == 2

        # Old ones should be gone
        assert registry.get_extraction_state(1, "epub", "chapter1") is None
        assert registry.get_extraction_state(1, "epub", "chapter2") is None

        # Running one should still be there
        assert registry.get_extraction_state(1, "epub", "chapter3") is not None

    def test_cancelling_state_included_in_running(
        self, registry: ExtractionRegistry
    ) -> None:
        """Test that CANCELLING state is included in get_running_extractions."""
        registry.register_extraction(1, "epub", "chapter1")
        registry.request_cancellation(1, "epub", "chapter1")

        running = registry.get_running_extractions()
        assert len(running) == 1
        assert running[0].status == ExtractionStatus.CANCELLING

    def test_update_phase(self, registry: ExtractionRegistry) -> None:
        """Test updating extraction phase."""
        registry.register_extraction(1, "epub", "chapter1")

        # Initially should be CONCEPTS phase
        state = registry.get_extraction_state(1, "epub", "chapter1")
        assert state is not None
        assert state.phase == ExtractionPhase.CONCEPTS

        # Update to RELATIONSHIPS phase
        registry.update_phase(1, "epub", "chapter1", ExtractionPhase.RELATIONSHIPS)

        state = registry.get_extraction_state(1, "epub", "chapter1")
        assert state is not None
        assert state.phase == ExtractionPhase.RELATIONSHIPS

    def test_update_relationship_progress(self, registry: ExtractionRegistry) -> None:
        """Test updating relationship extraction progress."""
        registry.register_extraction(1, "epub", "chapter1")
        registry.update_phase(1, "epub", "chapter1", ExtractionPhase.RELATIONSHIPS)
        registry.update_relationship_progress(1, "epub", "chapter1", 3, 5, 10)

        state = registry.get_extraction_state(1, "epub", "chapter1")
        assert state is not None
        assert state.rel_chunks_processed == 3
        assert state.rel_total_chunks == 5
        assert state.relationships_stored == 10

    def test_update_phase_nonexistent(self, registry: ExtractionRegistry) -> None:
        """Test updating phase for nonexistent extraction does not fail."""
        # Should not raise, just silently do nothing
        registry.update_phase(999, "epub", "nonexistent", ExtractionPhase.RELATIONSHIPS)

    def test_update_relationship_progress_nonexistent(
        self, registry: ExtractionRegistry
    ) -> None:
        """Test updating relationship progress for nonexistent extraction."""
        # Should not raise, just silently do nothing
        registry.update_relationship_progress(999, "epub", "nonexistent", 1, 2, 3)


class TestExtractionStateV2:
    """Tests for ExtractionState.to_dict_v2 method for single-phase extraction."""

    def test_to_dict_v2_returns_simplified_progress(self) -> None:
        """Test to_dict_v2 returns simplified single-phase progress structure."""
        state = ExtractionState(
            book_id=1,
            book_type="epub",
            section_id="chapter1",
            status=ExtractionStatus.RUNNING,
            chunks_processed=5,
            total_chunks=10,
            concepts_stored=15,
            relationships_stored=8,
        )

        result = state.to_dict_v2()

        # Basic fields
        assert result["book_id"] == 1
        assert result["book_type"] == "epub"
        assert result["section_id"] == "chapter1"
        assert result["status"] == "running"

        # Timing fields
        assert "started_at" in result
        assert "elapsed_seconds" in result

        # Progress fields
        assert result["chunks_processed"] == 5
        assert result["total_chunks"] == 10
        assert result["concepts_stored"] == 15
        assert result["relationships_stored"] == 8
        assert result["progress_percent"] == 50.0
        assert result["error_message"] is None

    def test_to_dict_v2_no_phase_field(self) -> None:
        """Test to_dict_v2 does not include phase field (single-phase extraction)."""
        state = ExtractionState(
            book_id=1,
            book_type="epub",
            section_id="chapter1",
            phase=ExtractionPhase.RELATIONSHIPS,  # This should be ignored in v2
        )

        result = state.to_dict_v2()

        # v2 should NOT have phase field since extraction is single-phase
        assert "phase" not in result
        # v2 should NOT have phase_progress_percent since there's only one phase
        assert "phase_progress_percent" not in result

    def test_to_dict_v2_no_rel_chunk_fields(self) -> None:
        """Test to_dict_v2 does not include rel_chunks fields (not needed for v2)."""
        state = ExtractionState(
            book_id=1,
            book_type="epub",
            section_id="chapter1",
            rel_chunks_processed=3,
            rel_total_chunks=5,
        )

        result = state.to_dict_v2()

        # v2 should NOT have separate relationship chunk tracking fields
        # since relationships are extracted in the same pass as concepts
        assert "rel_chunks_processed" not in result
        assert "rel_total_chunks" not in result

    def test_to_dict_v2_progress_zero_chunks(self) -> None:
        """Test to_dict_v2 progress is 0 when total_chunks is 0."""
        state = ExtractionState(
            book_id=1,
            book_type="epub",
            section_id="chapter1",
            total_chunks=0,
        )

        result = state.to_dict_v2()

        assert result["progress_percent"] == 0.0

    def test_to_dict_v2_completed_state(self) -> None:
        """Test to_dict_v2 for completed extraction."""
        state = ExtractionState(
            book_id=1,
            book_type="epub",
            section_id="chapter1",
            status=ExtractionStatus.COMPLETED,
            chunks_processed=10,
            total_chunks=10,
            concepts_stored=25,
            relationships_stored=15,
        )

        result = state.to_dict_v2()

        assert result["status"] == "completed"
        assert result["progress_percent"] == 100.0
        assert result["concepts_stored"] == 25
        assert result["relationships_stored"] == 15

    def test_to_dict_v2_failed_state_includes_error(self) -> None:
        """Test to_dict_v2 includes error message for failed extraction."""
        state = ExtractionState(
            book_id=1,
            book_type="epub",
            section_id="chapter1",
            status=ExtractionStatus.FAILED,
            error_message="LLM rate limit exceeded",
        )

        result = state.to_dict_v2()

        assert result["status"] == "failed"
        assert result["error_message"] == "LLM rate limit exceeded"

    def test_to_dict_v2_elapsed_seconds_positive(self) -> None:
        """Test to_dict_v2 elapsed_seconds is calculated correctly."""
        state = ExtractionState(
            book_id=1,
            book_type="epub",
            section_id="chapter1",
        )

        result = state.to_dict_v2()

        # elapsed_seconds should be a non-negative number
        assert result["elapsed_seconds"] >= 0
        assert isinstance(result["elapsed_seconds"], float)

"""
Unit tests for EmbeddingService.

Tests cover:
- Embedding generation
- Storage and retrieval
- Similarity search
- Deduplication checking
"""

import tempfile
from pathlib import Path

import pytest

from app.services.knowledge.embedding_service import EmbeddingService


@pytest.fixture
def temp_embedding_service():
    """Create an embedding service with temporary storage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        service = EmbeddingService(
            persist_directory=str(Path(temp_dir) / "chroma_test"),
            collection_name="test_embeddings",
        )
        yield service


class TestEmbeddingGeneration:
    """Tests for embedding generation."""

    def test_generate_embedding(self, temp_embedding_service: EmbeddingService):
        """Test generating an embedding for text."""
        embedding = temp_embedding_service.generate_embedding("test text")

        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)

    def test_generate_concept_text(self, temp_embedding_service: EmbeddingService):
        """Test generating text for embedding from concept."""
        text = temp_embedding_service.generate_concept_text(
            name="Quantum Entanglement",
            definition="A phenomenon where particles become correlated.",
        )

        assert "Quantum Entanglement" in text
        assert "phenomenon" in text

    def test_generate_concept_text_no_definition(
        self, temp_embedding_service: EmbeddingService
    ):
        """Test generating text when no definition provided."""
        text = temp_embedding_service.generate_concept_text(
            name="Test Concept",
            definition=None,
        )

        assert text == "Test Concept"


class TestStorageAndRetrieval:
    """Tests for storing and retrieving embeddings."""

    def test_store_concept_embedding(self, temp_embedding_service: EmbeddingService):
        """Test storing a concept embedding."""
        temp_embedding_service.store_concept_embedding(
            concept_id=1,
            name="Test Concept",
            definition="A test definition",
            metadata={"book_id": 1, "book_type": "epub"},
        )

        count = temp_embedding_service.get_collection_count()
        assert count == 1

    def test_store_multiple_embeddings(self, temp_embedding_service: EmbeddingService):
        """Test storing multiple embeddings."""
        for i in range(3):
            temp_embedding_service.store_concept_embedding(
                concept_id=i + 1,
                name=f"Concept {i}",
                definition=f"Definition {i}",
                metadata={"book_id": 1, "book_type": "epub"},
            )

        count = temp_embedding_service.get_collection_count()
        assert count == 3

    def test_delete_concept_embedding(self, temp_embedding_service: EmbeddingService):
        """Test deleting an embedding."""
        temp_embedding_service.store_concept_embedding(
            concept_id=1,
            name="To Delete",
            definition="Will be deleted",
        )
        assert temp_embedding_service.get_collection_count() == 1

        temp_embedding_service.delete_concept_embedding(1)

        assert temp_embedding_service.get_collection_count() == 0


class TestSimilaritySearch:
    """Tests for similarity search functionality."""

    def test_find_similar(self, temp_embedding_service: EmbeddingService):
        """Test finding similar concepts."""
        # Store some concepts
        temp_embedding_service.store_concept_embedding(
            concept_id=1,
            name="Quantum Entanglement",
            definition="Particles become correlated at quantum level",
            metadata={"book_id": 1, "book_type": "epub"},
        )
        temp_embedding_service.store_concept_embedding(
            concept_id=2,
            name="Classical Physics",
            definition="Study of motion and forces in everyday world",
            metadata={"book_id": 1, "book_type": "epub"},
        )

        # Search for something similar to quantum
        results = temp_embedding_service.find_similar(
            text="quantum particles and correlation",
            n_results=2,
        )

        assert len(results) > 0
        # The quantum concept should be most similar
        assert results[0]["name"] == "Quantum Entanglement"

    def test_find_similar_with_book_filter(
        self, temp_embedding_service: EmbeddingService
    ):
        """Test finding similar concepts filtered by book."""
        temp_embedding_service.store_concept_embedding(
            concept_id=1,
            name="Concept A",
            definition="From book 1",
            metadata={"book_id": 1, "book_type": "epub"},
        )
        temp_embedding_service.store_concept_embedding(
            concept_id=2,
            name="Concept B",
            definition="From book 2",
            metadata={"book_id": 2, "book_type": "epub"},
        )

        results = temp_embedding_service.find_similar(
            text="concept",
            n_results=5,
            book_id=1,
        )

        assert len(results) == 1
        assert results[0]["concept_id"] == 1

    def test_find_similar_with_threshold(
        self, temp_embedding_service: EmbeddingService
    ):
        """Test finding similar concepts with similarity threshold."""
        temp_embedding_service.store_concept_embedding(
            concept_id=1,
            name="Apple",
            definition="A fruit",
            metadata={"book_id": 1, "book_type": "epub"},
        )

        # Search with high threshold for something very different
        results = temp_embedding_service.find_similar(
            text="quantum physics theories",
            n_results=5,
            threshold=0.95,  # Very high threshold
        )

        # Should return empty or very few results due to low similarity
        assert len(results) <= 1


class TestDeduplication:
    """Tests for deduplication checking."""

    def test_check_duplicate_finds_match(
        self, temp_embedding_service: EmbeddingService
    ):
        """Test that check_duplicate finds similar existing concept."""
        temp_embedding_service.store_concept_embedding(
            concept_id=1,
            name="Machine Learning",
            definition="Algorithms that learn from data",
            metadata={"book_id": 1, "book_type": "epub"},
        )

        result = temp_embedding_service.check_duplicate(
            name="Machine Learning",
            definition="AI algorithms that learn from data",
            book_id=1,
            book_type="epub",
            similarity_threshold=0.8,
        )

        assert result is not None
        assert result["concept_id"] == 1

    def test_check_duplicate_no_match(self, temp_embedding_service: EmbeddingService):
        """Test that check_duplicate returns None for different concept."""
        temp_embedding_service.store_concept_embedding(
            concept_id=1,
            name="Photosynthesis",
            definition="How plants convert sunlight to energy",
            metadata={"book_id": 1, "book_type": "epub"},
        )

        result = temp_embedding_service.check_duplicate(
            name="Quantum Computing",
            definition="Computing using quantum mechanics",
            book_id=1,
            book_type="epub",
            similarity_threshold=0.9,
        )

        assert result is None


class TestBookEmbeddingDeletion:
    """Tests for deleting all embeddings for a book."""

    def test_delete_book_embeddings(self, temp_embedding_service: EmbeddingService):
        """Test deleting all embeddings for a book."""
        # Add embeddings for two books
        for i in range(3):
            temp_embedding_service.store_concept_embedding(
                concept_id=i + 1,
                name=f"Book1 Concept {i}",
                metadata={"book_id": 1, "book_type": "epub"},
            )
        for i in range(2):
            temp_embedding_service.store_concept_embedding(
                concept_id=i + 10,
                name=f"Book2 Concept {i}",
                metadata={"book_id": 2, "book_type": "epub"},
            )

        assert temp_embedding_service.get_collection_count() == 5

        # Delete book 1 embeddings
        deleted = temp_embedding_service.delete_book_embeddings(1, "epub")

        assert deleted == 3
        assert temp_embedding_service.get_collection_count() == 2

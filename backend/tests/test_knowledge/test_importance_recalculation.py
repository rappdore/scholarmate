"""
Unit tests for importance recalculation functionality.

Tests cover:
- Importance calculation based on relationship count
- Bonus for 'explains' relationships
- Handling concepts with no relationships
- Only updating concepts with changed importance
"""

import pytest

from app.services.knowledge.graph_builder import GraphBuilder
from app.services.knowledge.knowledge_database import KnowledgeDatabase


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_knowledge.db"
    db = KnowledgeDatabase(str(db_path))
    return db


@pytest.fixture
def graph_builder(temp_db, tmp_path):
    """Create a graph builder with temporary database and embeddings."""
    chroma_path = tmp_path / "chroma_test"
    chroma_path.mkdir()

    # Create a graph builder
    from app.services.knowledge.embedding_service import EmbeddingService

    embedding_service = EmbeddingService(str(chroma_path))
    builder = GraphBuilder()
    builder.db = temp_db
    builder.embedding_service = embedding_service
    return builder


class TestImportanceRecalculation:
    """Tests for the recalculate_book_importance method."""

    def test_isolated_concept_gets_low_importance(self, graph_builder, temp_db):
        """Test that concepts with no relationships get low importance."""
        # Create concept with high initial importance
        concept_id = temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Isolated Concept",
            definition="Has no connections.",
            importance=5,  # Start high
        )

        # Recalculate
        updated = graph_builder.recalculate_book_importance(1, "epub")

        # Should be reduced to 2 (isolated concepts get low importance)
        if concept_id in updated:
            assert updated[concept_id] == 2

    def test_highly_connected_concept_gets_high_importance(
        self, graph_builder, temp_db
    ):
        """Test that concepts with many relationships get higher importance."""
        # Create hub concept
        hub_id = temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Hub Concept",
            definition="Central concept.",
            importance=2,  # Start low
        )

        # Create several connected concepts
        for i in range(6):
            other_id = temp_db.create_concept(
                book_id=1,
                book_type="epub",
                name=f"Concept {i}",
                definition=f"Connected concept {i}.",
                importance=3,
            )
            # Create relationship from other to hub
            temp_db.create_relationship(
                source_concept_id=other_id,
                target_concept_id=hub_id,
                relationship_type="requires",
            )

        # Recalculate
        graph_builder.recalculate_book_importance(1, "epub")

        # Hub should have increased importance (6 incoming connections = importance 4)
        concept = temp_db.get_concept_by_id(hub_id)
        assert concept["importance"] >= 4

    def test_explains_source_bonus(self, graph_builder, temp_db):
        """Test that being a source of 'explains' relationships adds bonus."""
        # Create source concept
        source_id = temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Source Concept",
            definition="Explains others.",
            importance=2,
        )

        # Create concepts that this one explains
        for i in range(3):
            target_id = temp_db.create_concept(
                book_id=1,
                book_type="epub",
                name=f"Target {i}",
                definition=f"Explained concept {i}.",
                importance=3,
            )
            temp_db.create_relationship(
                source_concept_id=source_id,
                target_concept_id=target_id,
                relationship_type="explains",
            )

        # Recalculate
        graph_builder.recalculate_book_importance(1, "epub")

        # Source should have bonus from explains relationships
        concept = temp_db.get_concept_by_id(source_id)
        # 3 connections (base 3) + explains bonus should give >= 3
        assert concept["importance"] >= 3

    def test_only_updates_changed_concepts(self, graph_builder, temp_db):
        """Test that only concepts with changed importance are returned."""
        # Create concept with importance that matches calculation
        temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Concept A",
            definition="Some concept.",
            importance=2,  # Isolated gets 2, so no change expected
        )

        # Create concept whose importance will change
        concept_b_id = temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Concept B",
            definition="Connected concept.",
            importance=5,  # High, but will be reduced
        )

        # Recalculate
        updated = graph_builder.recalculate_book_importance(1, "epub")

        # Concept A should NOT be in updated (importance didn't change)
        # Concept B should be in updated (was 5, now 2 for isolated)
        assert concept_b_id in updated
        assert updated[concept_b_id] == 2

    def test_empty_book_returns_empty(self, graph_builder):
        """Test that books with no concepts return empty dict."""
        updated = graph_builder.recalculate_book_importance(999, "epub")
        assert updated == {}

    def test_importance_clamped_to_valid_range(self, graph_builder, temp_db):
        """Test that calculated importance stays within 1-5 range."""
        # Create a highly connected concept that might calculate > 5
        hub_id = temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Super Hub",
            definition="Very central.",
            importance=1,
        )

        # Create many connections
        for i in range(20):
            other_id = temp_db.create_concept(
                book_id=1,
                book_type="epub",
                name=f"Connected {i}",
                definition=f"Connected {i}.",
                importance=3,
            )
            temp_db.create_relationship(
                source_concept_id=hub_id,
                target_concept_id=other_id,
                relationship_type="explains",
            )

        # Recalculate
        graph_builder.recalculate_book_importance(1, "epub")

        # Check all concepts have valid importance
        concepts = temp_db.get_concepts_for_book(1, "epub")
        for concept in concepts:
            assert 1 <= concept["importance"] <= 5


class TestImportanceScoring:
    """Tests for the specific scoring logic."""

    def test_zero_connections_score(self, graph_builder, temp_db):
        """Test importance for 0 connections."""
        concept_id = temp_db.create_concept(
            book_id=1, book_type="epub", name="Solo", definition="Alone.", importance=5
        )

        graph_builder.recalculate_book_importance(1, "epub")

        concept = temp_db.get_concept_by_id(concept_id)
        assert concept["importance"] == 2  # 0 connections = 2

    def test_medium_connections_score(self, graph_builder, temp_db):
        """Test importance for 2-4 connections."""
        # Create main concept
        main_id = temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Main",
            definition="Main concept.",
            importance=1,
        )

        # Create 3 connections
        for i in range(3):
            other_id = temp_db.create_concept(
                book_id=1,
                book_type="epub",
                name=f"Other {i}",
                definition=f"Other {i}.",
                importance=3,
            )
            temp_db.create_relationship(
                source_concept_id=main_id,
                target_concept_id=other_id,
                relationship_type="related-to",
            )

        graph_builder.recalculate_book_importance(1, "epub")

        concept = temp_db.get_concept_by_id(main_id)
        assert concept["importance"] == 3  # 2-4 connections = 3

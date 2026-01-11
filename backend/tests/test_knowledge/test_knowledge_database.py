"""
Unit tests for KnowledgeDatabase.

Tests cover:
- Database initialization and schema creation
- Concept CRUD operations
- Relationship CRUD operations
- Extraction progress tracking
- Graph query functionality
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.services.knowledge.knowledge_database import KnowledgeDatabase


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "test_knowledge.db")
        db = KnowledgeDatabase(db_path=db_path)
        yield db


class TestKnowledgeDatabaseInit:
    """Tests for database initialization."""

    def test_database_creates_tables(self, temp_db: KnowledgeDatabase):
        """Test that all required tables are created."""
        with temp_db.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

        assert "concepts" in tables
        assert "relationships" in tables
        assert "flashcards" in tables
        assert "extraction_progress" in tables

    def test_database_creates_indexes(self, temp_db: KnowledgeDatabase):
        """Test that indexes are created."""
        with temp_db.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cursor.fetchall()}

        assert "idx_concepts_book" in indexes
        assert "idx_relationships_source" in indexes


class TestConceptCRUD:
    """Tests for concept operations."""

    def test_create_concept(self, temp_db: KnowledgeDatabase):
        """Test creating a concept."""
        concept_id = temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Test Concept",
            definition="A test definition",
            importance=4,
            nav_id="chapter1",
        )

        assert concept_id is not None
        assert concept_id > 0

    def test_get_concept_by_id(self, temp_db: KnowledgeDatabase):
        """Test retrieving a concept by ID."""
        concept_id = temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Test Concept",
            definition="A test definition",
        )

        concept = temp_db.get_concept_by_id(concept_id)

        assert concept is not None
        assert concept["name"] == "Test Concept"
        assert concept["definition"] == "A test definition"
        assert concept["book_id"] == 1
        assert concept["book_type"] == "epub"

    def test_get_concept_by_name(self, temp_db: KnowledgeDatabase):
        """Test retrieving a concept by name within a book."""
        temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Unique Concept",
            definition="Definition",
        )

        concept = temp_db.get_concept_by_name(1, "epub", "Unique Concept")

        assert concept is not None
        assert concept["name"] == "Unique Concept"

    def test_get_concepts_for_book(self, temp_db: KnowledgeDatabase):
        """Test getting all concepts for a book."""
        # Create multiple concepts
        temp_db.create_concept(
            book_id=1, book_type="epub", name="Concept 1", importance=5
        )
        temp_db.create_concept(
            book_id=1, book_type="epub", name="Concept 2", importance=3
        )
        temp_db.create_concept(
            book_id=2, book_type="epub", name="Other Book", importance=4
        )

        concepts = temp_db.get_concepts_for_book(book_id=1, book_type="epub")

        assert len(concepts) == 2
        # Should be ordered by importance desc
        assert concepts[0]["name"] == "Concept 1"

    def test_get_concepts_with_importance_filter(self, temp_db: KnowledgeDatabase):
        """Test filtering concepts by minimum importance."""
        temp_db.create_concept(book_id=1, book_type="epub", name="High", importance=5)
        temp_db.create_concept(book_id=1, book_type="epub", name="Medium", importance=3)
        temp_db.create_concept(book_id=1, book_type="epub", name="Low", importance=1)

        concepts = temp_db.get_concepts_for_book(
            book_id=1, book_type="epub", importance_min=4
        )

        assert len(concepts) == 1
        assert concepts[0]["name"] == "High"

    def test_update_concept(self, temp_db: KnowledgeDatabase):
        """Test updating a concept."""
        concept_id = temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Test",
            definition="Old definition",
            importance=3,
        )

        success = temp_db.update_concept(
            concept_id=concept_id,
            definition="New definition",
            importance=5,
        )

        assert success
        updated = temp_db.get_concept_by_id(concept_id)
        assert updated["definition"] == "New definition"
        assert updated["importance"] == 5

    def test_delete_concept(self, temp_db: KnowledgeDatabase):
        """Test deleting a concept."""
        concept_id = temp_db.create_concept(
            book_id=1, book_type="epub", name="To Delete"
        )

        success = temp_db.delete_concept(concept_id)

        assert success
        assert temp_db.get_concept_by_id(concept_id) is None

    def test_duplicate_concept_name_fails(self, temp_db: KnowledgeDatabase):
        """Test that creating duplicate concept names in same book fails."""
        temp_db.create_concept(book_id=1, book_type="epub", name="Duplicate")

        result = temp_db.create_concept(book_id=1, book_type="epub", name="Duplicate")

        assert result is None  # Should fail


class TestRelationshipCRUD:
    """Tests for relationship operations."""

    def test_create_relationship(self, temp_db: KnowledgeDatabase):
        """Test creating a relationship."""
        # Create two concepts first
        concept1 = temp_db.create_concept(book_id=1, book_type="epub", name="Source")
        concept2 = temp_db.create_concept(book_id=1, book_type="epub", name="Target")

        rel_id = temp_db.create_relationship(
            source_concept_id=concept1,
            target_concept_id=concept2,
            relationship_type="explains",
            description="Source explains Target",
        )

        assert rel_id is not None
        assert rel_id > 0

    def test_get_relationships_for_concept(self, temp_db: KnowledgeDatabase):
        """Test getting relationships for a concept."""
        c1 = temp_db.create_concept(book_id=1, book_type="epub", name="A")
        c2 = temp_db.create_concept(book_id=1, book_type="epub", name="B")
        c3 = temp_db.create_concept(book_id=1, book_type="epub", name="C")

        temp_db.create_relationship(c1, c2, "explains")
        temp_db.create_relationship(c3, c1, "requires")

        # Get relationships where c1 is source
        as_source = temp_db.get_relationships_for_concept(
            c1, as_source=True, as_target=False
        )
        assert len(as_source) == 1
        assert as_source[0]["target_name"] == "B"

        # Get relationships where c1 is target
        as_target = temp_db.get_relationships_for_concept(
            c1, as_source=False, as_target=True
        )
        assert len(as_target) == 1
        assert as_target[0]["source_name"] == "C"

    def test_duplicate_relationship_updates_weight(self, temp_db: KnowledgeDatabase):
        """Test that creating duplicate relationship updates weight."""
        c1 = temp_db.create_concept(book_id=1, book_type="epub", name="A")
        c2 = temp_db.create_concept(book_id=1, book_type="epub", name="B")

        temp_db.create_relationship(c1, c2, "explains", weight=1.0)
        temp_db.create_relationship(c1, c2, "explains", weight=0.5)

        # Check that weight was updated
        with temp_db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT weight FROM relationships WHERE source_concept_id = ? AND target_concept_id = ?",
                (c1, c2),
            )
            row = cursor.fetchone()
            assert row["weight"] == 1.5  # Initial + added


class TestGraphQueries:
    """Tests for graph query functionality."""

    def test_get_graph_for_book(self, temp_db: KnowledgeDatabase):
        """Test getting full graph data for a book."""
        # Create concepts
        c1 = temp_db.create_concept(book_id=1, book_type="epub", name="A", importance=5)
        c2 = temp_db.create_concept(book_id=1, book_type="epub", name="B", importance=3)
        # Create concept in different book to verify filtering
        temp_db.create_concept(book_id=2, book_type="epub", name="Other")

        # Create relationships
        temp_db.create_relationship(c1, c2, "explains")

        graph = temp_db.get_graph_for_book(book_id=1, book_type="epub")

        assert len(graph["nodes"]) == 2
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["type"] == "explains"


class TestExtractionProgress:
    """Tests for extraction progress tracking."""

    def test_mark_section_extracted(self, temp_db: KnowledgeDatabase):
        """Test marking a section as extracted."""
        success = temp_db.mark_section_extracted(
            book_id=1, book_type="epub", nav_id="chapter1"
        )

        assert success

    def test_is_section_extracted(self, temp_db: KnowledgeDatabase):
        """Test checking if section was extracted."""
        # Not extracted yet
        assert not temp_db.is_section_extracted(1, "epub", nav_id="chapter1")

        # Mark as extracted
        temp_db.mark_section_extracted(1, "epub", nav_id="chapter1")

        # Now should be True
        assert temp_db.is_section_extracted(1, "epub", nav_id="chapter1")

    def test_get_extraction_progress(self, temp_db: KnowledgeDatabase):
        """Test getting extraction progress for a book."""
        temp_db.mark_section_extracted(1, "epub", nav_id="chapter1")
        temp_db.mark_section_extracted(1, "epub", nav_id="chapter2")

        progress = temp_db.get_extraction_progress(1, "epub")

        assert len(progress) == 2


class TestDeleteBookKnowledge:
    """Tests for deleting all book knowledge."""

    def test_delete_book_knowledge(self, temp_db: KnowledgeDatabase):
        """Test deleting all knowledge for a book."""
        # Create concepts and relationships
        c1 = temp_db.create_concept(book_id=1, book_type="epub", name="A")
        c2 = temp_db.create_concept(book_id=1, book_type="epub", name="B")
        temp_db.create_relationship(c1, c2, "explains")
        temp_db.mark_section_extracted(1, "epub", nav_id="chapter1")

        # Delete
        success = temp_db.delete_book_knowledge(1, "epub")

        assert success
        assert len(temp_db.get_concepts_for_book(1, "epub")) == 0
        assert len(temp_db.get_extraction_progress(1, "epub")) == 0


class TestStats:
    """Tests for database statistics."""

    def test_get_stats(self, temp_db: KnowledgeDatabase):
        """Test getting database statistics."""
        # Empty database
        stats = temp_db.get_stats()
        assert stats["total_concepts"] == 0
        assert stats["total_relationships"] == 0

        # Add some data
        c1 = temp_db.create_concept(book_id=1, book_type="epub", name="A")
        c2 = temp_db.create_concept(book_id=1, book_type="epub", name="B")
        temp_db.create_relationship(c1, c2, "explains")

        stats = temp_db.get_stats()
        assert stats["total_concepts"] == 2
        assert stats["total_relationships"] == 1

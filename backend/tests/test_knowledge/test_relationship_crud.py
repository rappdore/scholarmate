"""
Unit tests for relationship CRUD operations.

Tests cover:
- Creating relationships
- Getting relationships by ID
- Updating relationships
- Deleting relationships
- Getting relationships for a concept
- Weight accumulation
- Error handling
"""

import pytest

from app.services.knowledge.knowledge_database import KnowledgeDatabase


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_knowledge.db"
    db = KnowledgeDatabase(str(db_path))
    return db


@pytest.fixture
def db_with_concepts(temp_db):
    """Create a database with test concepts for relationship testing."""
    # Create concepts
    concept1_id = temp_db.create_concept(
        book_id=1,
        book_type="epub",
        name="Machine Learning",
        definition="A branch of AI.",
        importance=5,
    )
    concept2_id = temp_db.create_concept(
        book_id=1,
        book_type="epub",
        name="Neural Network",
        definition="Computing systems inspired by brains.",
        importance=4,
    )
    concept3_id = temp_db.create_concept(
        book_id=1,
        book_type="epub",
        name="Deep Learning",
        definition="Neural networks with many layers.",
        importance=4,
    )

    return temp_db, concept1_id, concept2_id, concept3_id


class TestGetRelationshipById:
    """Tests for get_relationship_by_id method."""

    def test_get_existing_relationship(self, db_with_concepts):
        """Test getting a relationship that exists."""
        db, c1, c2, c3 = db_with_concepts

        # Create a relationship
        rel_id = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
            description="ML explains neural networks",
            weight=1.5,
        )

        # Get the relationship
        rel = db.get_relationship_by_id(rel_id)

        assert rel is not None
        assert rel["id"] == rel_id
        assert rel["source_concept_id"] == c1
        assert rel["target_concept_id"] == c2
        assert rel["relationship_type"] == "explains"
        assert rel["description"] == "ML explains neural networks"
        assert rel["weight"] == 1.5

    def test_get_relationship_includes_concept_info(self, db_with_concepts):
        """Test that relationship includes joined concept information."""
        db, c1, c2, c3 = db_with_concepts

        rel_id = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
        )

        rel = db.get_relationship_by_id(rel_id)

        # Should include source and target concept names
        assert rel["source_name"] == "Machine Learning"
        assert rel["target_name"] == "Neural Network"
        assert rel["source_definition"] is not None
        assert rel["target_definition"] is not None

    def test_get_nonexistent_relationship(self, temp_db):
        """Test getting a relationship that doesn't exist."""
        rel = temp_db.get_relationship_by_id(9999)
        assert rel is None


class TestUpdateRelationship:
    """Tests for update_relationship method."""

    def test_update_relationship_type(self, db_with_concepts):
        """Test updating the relationship type."""
        db, c1, c2, c3 = db_with_concepts

        rel_id = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
        )

        success = db.update_relationship(
            relationship_id=rel_id,
            relationship_type="builds-on",
        )

        assert success is True

        rel = db.get_relationship_by_id(rel_id)
        assert rel["relationship_type"] == "builds-on"

    def test_update_description(self, db_with_concepts):
        """Test updating the description."""
        db, c1, c2, c3 = db_with_concepts

        rel_id = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
            description="Original description",
        )

        success = db.update_relationship(
            relationship_id=rel_id,
            description="Updated description",
        )

        assert success is True

        rel = db.get_relationship_by_id(rel_id)
        assert rel["description"] == "Updated description"

    def test_update_weight(self, db_with_concepts):
        """Test updating the weight."""
        db, c1, c2, c3 = db_with_concepts

        rel_id = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
            weight=1.0,
        )

        success = db.update_relationship(
            relationship_id=rel_id,
            weight=5.0,
        )

        assert success is True

        rel = db.get_relationship_by_id(rel_id)
        assert rel["weight"] == 5.0

    def test_update_multiple_fields(self, db_with_concepts):
        """Test updating multiple fields at once."""
        db, c1, c2, c3 = db_with_concepts

        rel_id = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
            description="Old",
            weight=1.0,
        )

        success = db.update_relationship(
            relationship_id=rel_id,
            relationship_type="requires",
            description="New description",
            weight=3.0,
        )

        assert success is True

        rel = db.get_relationship_by_id(rel_id)
        assert rel["relationship_type"] == "requires"
        assert rel["description"] == "New description"
        assert rel["weight"] == 3.0

    def test_update_nonexistent_relationship(self, temp_db):
        """Test updating a relationship that doesn't exist."""
        success = temp_db.update_relationship(
            relationship_id=9999,
            description="This won't work",
        )
        assert success is False

    def test_update_with_no_changes(self, db_with_concepts):
        """Test update with no fields to change."""
        db, c1, c2, c3 = db_with_concepts

        rel_id = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
        )

        # Update with no fields should succeed without changing anything
        success = db.update_relationship(relationship_id=rel_id)
        assert success is True


class TestDeleteRelationship:
    """Tests for delete_relationship method."""

    def test_delete_existing_relationship(self, db_with_concepts):
        """Test deleting a relationship that exists."""
        db, c1, c2, c3 = db_with_concepts

        rel_id = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
        )

        # Verify it exists
        assert db.get_relationship_by_id(rel_id) is not None

        # Delete it
        success = db.delete_relationship(rel_id)
        assert success is True

        # Verify it's gone
        assert db.get_relationship_by_id(rel_id) is None

    def test_delete_nonexistent_relationship(self, temp_db):
        """Test deleting a relationship that doesn't exist."""
        success = temp_db.delete_relationship(9999)
        assert success is False


class TestGetRelationshipsForConcept:
    """Tests for get_relationships_for_concept method."""

    def test_get_outgoing_relationships(self, db_with_concepts):
        """Test getting relationships where concept is the source."""
        db, c1, c2, c3 = db_with_concepts

        # c1 -> c2
        db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
        )
        # c1 -> c3
        db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c3,
            relationship_type="requires",
        )

        # Get only outgoing
        rels = db.get_relationships_for_concept(c1, as_source=True, as_target=False)

        assert len(rels) == 2
        for rel in rels:
            assert rel["source_concept_id"] == c1

    def test_get_incoming_relationships(self, db_with_concepts):
        """Test getting relationships where concept is the target."""
        db, c1, c2, c3 = db_with_concepts

        # c1 -> c2
        db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
        )
        # c3 -> c2
        db.create_relationship(
            source_concept_id=c3,
            target_concept_id=c2,
            relationship_type="builds-on",
        )

        # Get only incoming for c2
        rels = db.get_relationships_for_concept(c2, as_source=False, as_target=True)

        assert len(rels) == 2
        for rel in rels:
            assert rel["target_concept_id"] == c2

    def test_get_all_relationships(self, db_with_concepts):
        """Test getting all relationships (both directions)."""
        db, c1, c2, c3 = db_with_concepts

        # c1 -> c2
        db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
        )
        # c3 -> c2
        db.create_relationship(
            source_concept_id=c3,
            target_concept_id=c2,
            relationship_type="builds-on",
        )
        # c2 -> c3
        db.create_relationship(
            source_concept_id=c2,
            target_concept_id=c3,
            relationship_type="requires",
        )

        # Get all for c2 (1 outgoing, 2 incoming)
        rels = db.get_relationships_for_concept(c2, as_source=True, as_target=True)

        assert len(rels) == 3

    def test_concept_with_no_relationships(self, db_with_concepts):
        """Test concept with no relationships."""
        db, c1, c2, c3 = db_with_concepts

        rels = db.get_relationships_for_concept(c1)
        assert len(rels) == 0


class TestWeightAccumulation:
    """Tests for weight accumulation on duplicate relationships."""

    def test_weight_accumulates_on_duplicate(self, db_with_concepts):
        """Test that creating duplicate relationship adds to weight."""
        db, c1, c2, c3 = db_with_concepts

        # Create initial relationship
        rel_id_1 = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
            weight=1.0,
        )

        # Create "duplicate" with same source, target, and type
        rel_id_2 = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
            weight=2.0,
        )

        # Should return same ID
        assert rel_id_1 == rel_id_2

        # Weight should be accumulated (1.0 + 2.0 = 3.0)
        rel = db.get_relationship_by_id(rel_id_1)
        assert rel["weight"] == 3.0

    def test_different_types_dont_accumulate(self, db_with_concepts):
        """Test that different relationship types create separate records."""
        db, c1, c2, c3 = db_with_concepts

        rel_id_1 = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="explains",
            weight=1.0,
        )

        rel_id_2 = db.create_relationship(
            source_concept_id=c1,
            target_concept_id=c2,
            relationship_type="requires",
            weight=1.0,
        )

        # Should be different relationships
        assert rel_id_1 != rel_id_2

        # Both should exist with their own weights
        rel1 = db.get_relationship_by_id(rel_id_1)
        rel2 = db.get_relationship_by_id(rel_id_2)

        assert rel1["weight"] == 1.0
        assert rel2["weight"] == 1.0

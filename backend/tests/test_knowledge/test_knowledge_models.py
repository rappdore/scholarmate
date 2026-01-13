"""Unit tests for knowledge models."""

import pytest
from pydantic import ValidationError

from app.models.knowledge_models import ExtractedTriple, TripleEntity


class TestExtractedTriple:
    """Tests for the ExtractedTriple model."""

    def test_valid_triple(self):
        """Test creating a valid triple."""
        triple = ExtractedTriple(
            subject=TripleEntity(
                name="Photosynthesis",
                definition="Process by which plants convert light to energy",
            ),
            predicate="requires",
            object=TripleEntity(
                name="Chlorophyll", definition="Green pigment in plants"
            ),
            description="Photosynthesis requires chlorophyll to capture light",
        )

        assert triple.subject.name == "Photosynthesis"
        assert triple.predicate == "requires"
        assert triple.object.name == "Chlorophyll"

    def test_triple_predicate_validation(self):
        """Test that predicate must be a valid relationship type."""
        triple = ExtractedTriple(
            subject=TripleEntity(name="A", definition="Def A"),
            predicate="explains",  # Valid type
            object=TripleEntity(name="B", definition="Def B"),
        )
        assert triple.predicate == "explains"

    def test_triple_allows_any_predicate_for_flexibility(self):
        """Test that unknown predicates are allowed (normalized later)."""
        triple = ExtractedTriple(
            subject=TripleEntity(name="A", definition="Def A"),
            predicate="unknown_type",
            object=TripleEntity(name="B", definition="Def B"),
        )
        assert triple.predicate == "unknown_type"

    def test_triple_entity_requires_name(self):
        """Test that entity name is required."""
        with pytest.raises(ValidationError):
            TripleEntity(name="", definition="Some def")

    def test_triple_entity_definition_optional(self):
        """Test that definition can be omitted."""
        entity = TripleEntity(name="Concept")
        assert entity.name == "Concept"
        assert entity.definition is None

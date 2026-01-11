"""
Unit tests for concept text search functionality.

Tests cover:
- Exact name matching
- Partial name matching
- Definition search
- Special character handling
- Book filtering
- Relevance ordering
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
def populated_db(temp_db):
    """Create a database with test concepts."""
    # Create diverse concepts for search testing
    concepts = [
        {
            "book_id": 1,
            "book_type": "epub",
            "name": "Machine Learning",
            "definition": "A branch of AI that enables systems to learn from data.",
            "importance": 5,
        },
        {
            "book_id": 1,
            "book_type": "epub",
            "name": "Deep Learning",
            "definition": "A subset of machine learning using neural networks.",
            "importance": 4,
        },
        {
            "book_id": 1,
            "book_type": "epub",
            "name": "Neural Network",
            "definition": "Computing systems inspired by biological brains.",
            "importance": 4,
        },
        {
            "book_id": 2,
            "book_type": "epub",
            "name": "Algorithm",
            "definition": "A step-by-step procedure for calculations.",
            "importance": 3,
        },
        {
            "book_id": 2,
            "book_type": "pdf",
            "name": "Learning Rate",
            "definition": "A hyperparameter that controls the step size during optimization.",
            "importance": 3,
        },
        {
            "book_id": 3,
            "book_type": "pdf",
            "name": "Machine Code",
            "definition": "Low-level programming language understood by computers.",
            "importance": 2,
        },
    ]

    for concept in concepts:
        temp_db.create_concept(**concept)

    return temp_db


class TestTextSearch:
    """Tests for the text search functionality."""

    def test_exact_name_match(self, populated_db):
        """Test that exact name matches are returned first."""
        results = populated_db.search_concepts("Machine Learning")
        assert len(results) > 0
        # Exact match should be first
        assert results[0]["name"] == "Machine Learning"

    def test_partial_name_match_starts_with(self, populated_db):
        """Test searching with prefix of name."""
        results = populated_db.search_concepts("Machine")
        assert len(results) >= 2
        # Should find both "Machine Learning" and "Machine Code"
        names = [r["name"] for r in results]
        assert "Machine Learning" in names
        assert "Machine Code" in names

    def test_partial_name_match_contains(self, populated_db):
        """Test searching for substring in name."""
        results = populated_db.search_concepts("Learning")
        assert len(results) >= 2
        names = [r["name"] for r in results]
        assert "Machine Learning" in names
        assert "Deep Learning" in names

    def test_definition_search(self, populated_db):
        """Test that definition content is also searched."""
        results = populated_db.search_concepts("neural")
        assert len(results) >= 1
        # Should find concepts with "neural" in definition
        found_names = [r["name"] for r in results]
        # "Deep Learning" has neural in definition, "Neural Network" has it in name
        assert "Neural Network" in found_names or "Deep Learning" in found_names

    def test_case_insensitive_search(self, populated_db):
        """Test that search is case insensitive."""
        results_lower = populated_db.search_concepts("machine learning")
        results_upper = populated_db.search_concepts("MACHINE LEARNING")
        results_mixed = populated_db.search_concepts("Machine Learning")

        assert len(results_lower) == len(results_upper) == len(results_mixed)

    def test_book_id_filter(self, populated_db):
        """Test filtering results by book ID."""
        results = populated_db.search_concepts("Learning", book_id=1)

        # Should only find concepts from book 1
        for result in results:
            assert result["book_id"] == 1

        # Should find Machine Learning and Deep Learning (both in book 1)
        names = [r["name"] for r in results]
        assert "Machine Learning" in names
        assert "Deep Learning" in names
        assert "Learning Rate" not in names  # This is in book 2

    def test_book_type_filter(self, populated_db):
        """Test filtering results by book type."""
        results = populated_db.search_concepts("Learning", book_type="pdf")

        # Should only find concepts from PDF books
        for result in results:
            assert result["book_type"] == "pdf"

        # Should find "Learning Rate" (PDF book)
        names = [r["name"] for r in results]
        assert "Learning Rate" in names

    def test_combined_filters(self, populated_db):
        """Test combining book_id and book_type filters."""
        results = populated_db.search_concepts("Machine", book_id=3, book_type="pdf")

        assert len(results) == 1
        assert results[0]["name"] == "Machine Code"

    def test_limit_parameter(self, populated_db):
        """Test that limit parameter works."""
        results = populated_db.search_concepts("a", limit=2)
        assert len(results) <= 2

    def test_no_results(self, populated_db):
        """Test search with no matching concepts."""
        results = populated_db.search_concepts("xyz123nonexistent")
        assert len(results) == 0

    def test_empty_query(self, populated_db):
        """Test that empty query returns empty results."""
        results = populated_db.search_concepts("")
        assert len(results) == 0

        results = populated_db.search_concepts("   ")
        assert len(results) == 0


class TestSpecialCharacters:
    """Tests for handling special characters in search."""

    def test_sql_injection_attempt(self, populated_db):
        """Test that SQL injection is properly escaped."""
        # These should not cause errors or return unexpected results
        results = populated_db.search_concepts("'; DROP TABLE concepts; --")
        assert len(results) == 0

        results = populated_db.search_concepts("' OR '1'='1")
        assert len(results) == 0

    def test_percent_character(self, temp_db):
        """Test searching for literal % character."""
        # Create a concept with % in name
        temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="100% Accuracy",
            definition="Perfect accuracy metric.",
        )

        results = temp_db.search_concepts("100%")
        assert len(results) >= 1
        assert any("100%" in r["name"] for r in results)

    def test_underscore_character(self, temp_db):
        """Test searching for literal _ character."""
        # Create a concept with _ in name
        temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="test_function",
            definition="A test function.",
        )

        results = temp_db.search_concepts("test_")
        assert len(results) >= 1
        assert any("test_function" == r["name"] for r in results)


class TestRelevanceOrdering:
    """Tests for relevance ordering of search results."""

    def test_exact_match_first(self, populated_db):
        """Test that exact name matches appear before partial matches."""
        results = populated_db.search_concepts("Deep Learning")

        # First result should be exact match
        assert results[0]["name"] == "Deep Learning"

    def test_name_match_before_definition_match(self, temp_db):
        """Test that name matches rank higher than definition matches."""
        # Create concepts where one has the term in name, other in definition
        temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Quantum Computing",
            definition="Uses quantum mechanics for computation.",
            importance=3,
        )
        temp_db.create_concept(
            book_id=1,
            book_type="epub",
            name="Physics",
            definition="Study of matter, including quantum mechanics.",
            importance=3,
        )

        results = temp_db.search_concepts("Quantum")

        # "Quantum Computing" should rank higher (name match)
        names = [r["name"] for r in results]
        assert names.index("Quantum Computing") < names.index("Physics")

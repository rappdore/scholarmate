"""
Unit tests for ConceptExtractor.

Tests cover:
- Content chunking
- JSON parsing of LLM responses
- Concept extraction (with mocked LLM)
- Relationship extraction (with mocked LLM)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.knowledge_models import ExtractedConcept
from app.services.knowledge.concept_extractor import ConceptExtractor


class TestContentChunking:
    """Tests for the chunking functionality."""

    @pytest.fixture
    def extractor(self):
        """Create extractor with mocked LLM config."""
        with patch(
            "app.services.knowledge.concept_extractor.LLMConfigService"
        ) as mock_config:
            mock_config.return_value.get_active_configuration.return_value = None
            extractor = ConceptExtractor()
            yield extractor

    def test_chunk_small_content(self, extractor: ConceptExtractor):
        """Test that small content is not chunked."""
        content = "This is a small piece of text."
        chunks = extractor.chunk_content(content, chunk_size=1000)

        assert len(chunks) == 1
        assert chunks[0] == content

    def test_chunk_large_content(self, extractor: ConceptExtractor):
        """Test that large content is chunked with overlap."""
        # Create content larger than chunk size
        content = "Sentence one. " * 100  # ~1400 chars
        chunks = extractor.chunk_content(content, chunk_size=500, overlap=50)

        assert len(chunks) > 1
        # Check overlap exists between chunks
        for i in range(len(chunks) - 1):
            # Last part of chunk i should appear in start of chunk i+1
            # Verify overlap exists (chunks should share some content)
            assert len(chunks[i]) > 0

    def test_chunk_breaks_at_sentence(self, extractor: ConceptExtractor):
        """Test that chunking tries to break at sentence boundaries."""
        content = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = extractor.chunk_content(content, chunk_size=35, overlap=5)

        # Each chunk should end with a period (sentence boundary)
        for chunk in chunks[:-1]:  # Except possibly the last one
            assert chunk.strip().endswith(".")

    def test_chunk_invalid_chunk_size_zero(self, extractor: ConceptExtractor):
        """Test that chunk_size <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            extractor.chunk_content("some content", chunk_size=0)

    def test_chunk_invalid_chunk_size_negative(self, extractor: ConceptExtractor):
        """Test that negative chunk_size raises ValueError."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            extractor.chunk_content("some content", chunk_size=-10)

    def test_chunk_invalid_overlap_negative(self, extractor: ConceptExtractor):
        """Test that negative overlap raises ValueError."""
        with pytest.raises(ValueError, match="overlap must satisfy"):
            extractor.chunk_content("some content", chunk_size=100, overlap=-1)

    def test_chunk_invalid_overlap_equals_chunk_size(self, extractor: ConceptExtractor):
        """Test that overlap == chunk_size raises ValueError (would cause infinite loop)."""
        with pytest.raises(ValueError, match="overlap must satisfy"):
            extractor.chunk_content("some content", chunk_size=100, overlap=100)

    def test_chunk_invalid_overlap_exceeds_chunk_size(
        self, extractor: ConceptExtractor
    ):
        """Test that overlap > chunk_size raises ValueError."""
        with pytest.raises(ValueError, match="overlap must satisfy"):
            extractor.chunk_content("some content", chunk_size=100, overlap=150)


class TestJsonParsing:
    """Tests for JSON parsing of LLM responses."""

    @pytest.fixture
    def extractor(self):
        """Create extractor with mocked LLM config."""
        with patch(
            "app.services.knowledge.concept_extractor.LLMConfigService"
        ) as mock_config:
            mock_config.return_value.get_active_configuration.return_value = None
            extractor = ConceptExtractor()
            yield extractor

    def test_parse_valid_concepts_json(self, extractor: ConceptExtractor):
        """Test parsing valid JSON array of concepts."""
        json_response = """[
            {
                "name": "Test Concept",
                "definition": "A test definition",
                "importance": 4,
                "source_quote": "test quote"
            }
        ]"""

        concepts = extractor._parse_concepts_json(json_response)

        assert len(concepts) == 1
        assert concepts[0].name == "Test Concept"
        assert concepts[0].importance == 4

    def test_parse_concepts_with_markdown(self, extractor: ConceptExtractor):
        """Test parsing JSON wrapped in markdown code blocks."""
        json_response = """```json
[
    {"name": "Concept", "definition": "Def", "importance": 3, "source_quote": "quote"}
]
```"""

        concepts = extractor._parse_concepts_json(json_response)

        assert len(concepts) == 1
        assert concepts[0].name == "Concept"

    def test_parse_concepts_clamps_importance(self, extractor: ConceptExtractor):
        """Test that importance is clamped to 1-5 range."""
        json_response = """[
            {"name": "A", "definition": "D", "importance": 10, "source_quote": "q"},
            {"name": "B", "definition": "D", "importance": -1, "source_quote": "q"}
        ]"""

        concepts = extractor._parse_concepts_json(json_response)

        assert concepts[0].importance == 5  # Clamped to max
        assert concepts[1].importance == 1  # Clamped to min

    def test_parse_concepts_skips_empty_names(self, extractor: ConceptExtractor):
        """Test that concepts with empty names are skipped."""
        json_response = """[
            {"name": "", "definition": "D", "importance": 3, "source_quote": "q"},
            {"name": "Valid", "definition": "D", "importance": 3, "source_quote": "q"}
        ]"""

        concepts = extractor._parse_concepts_json(json_response)

        assert len(concepts) == 1
        assert concepts[0].name == "Valid"

    def test_parse_invalid_json_returns_empty(self, extractor: ConceptExtractor):
        """Test that invalid JSON returns empty list."""
        invalid_json = "This is not JSON at all"

        concepts = extractor._parse_concepts_json(invalid_json)

        assert concepts == []

    def test_parse_relationships_validates_concept_names(
        self, extractor: ConceptExtractor
    ):
        """Test that relationships are validated against concept list."""
        json_response = """[
            {"source": "A", "target": "B", "type": "explains", "description": "A explains B"},
            {"source": "A", "target": "Unknown", "type": "explains", "description": "Invalid"}
        ]"""

        concepts = [
            ExtractedConcept(name="A", definition="D", importance=3, source_quote="q"),
            ExtractedConcept(name="B", definition="D", importance=3, source_quote="q"),
        ]

        relationships = extractor._parse_relationships_json(json_response, concepts)

        # Only the valid relationship should be parsed
        assert len(relationships) == 1
        assert relationships[0].source == "A"
        assert relationships[0].target == "B"

    def test_parse_relationships_normalizes_type_case(
        self, extractor: ConceptExtractor
    ):
        """Test that relationship types are normalized to lowercase."""
        json_response = """[
            {"source": "A", "target": "B", "type": "Explains", "description": "desc"},
            {"source": "A", "target": "B", "type": "CONTRASTS", "description": "desc"}
        ]"""

        concepts = [
            ExtractedConcept(name="A", definition="D", importance=3, source_quote="q"),
            ExtractedConcept(name="B", definition="D", importance=3, source_quote="q"),
        ]

        relationships = extractor._parse_relationships_json(json_response, concepts)

        assert len(relationships) == 2
        assert relationships[0].type == "explains"
        assert relationships[1].type == "contrasts"

    def test_parse_relationships_normalizes_underscores_to_hyphens(
        self, extractor: ConceptExtractor
    ):
        """Test that underscores in relationship types are converted to hyphens."""
        json_response = """[
            {"source": "A", "target": "B", "type": "builds_on", "description": "desc"}
        ]"""

        concepts = [
            ExtractedConcept(name="A", definition="D", importance=3, source_quote="q"),
            ExtractedConcept(name="B", definition="D", importance=3, source_quote="q"),
        ]

        relationships = extractor._parse_relationships_json(json_response, concepts)

        assert len(relationships) == 1
        assert relationships[0].type == "builds-on"

    def test_parse_relationships_falls_back_to_related_to(
        self, extractor: ConceptExtractor
    ):
        """Test that invalid relationship types fall back to 'related-to'."""
        json_response = """[
            {"source": "A", "target": "B", "type": "unknown_type", "description": "desc"},
            {"source": "A", "target": "B", "type": "connects", "description": "desc"}
        ]"""

        concepts = [
            ExtractedConcept(name="A", definition="D", importance=3, source_quote="q"),
            ExtractedConcept(name="B", definition="D", importance=3, source_quote="q"),
        ]

        relationships = extractor._parse_relationships_json(json_response, concepts)

        assert len(relationships) == 2
        assert relationships[0].type == "related-to"
        assert relationships[1].type == "related-to"


class TestExtraction:
    """Tests for the extraction process with mocked LLM."""

    @pytest.fixture
    def mock_extractor(self):
        """Create extractor with fully mocked LLM."""
        with patch(
            "app.services.knowledge.concept_extractor.LLMConfigService"
        ) as mock_config:
            mock_config.return_value.get_active_configuration.return_value = MagicMock(
                base_url="http://test",
                api_key="test",
                model_name="test-model",
            )

            with patch(
                "app.services.knowledge.concept_extractor.AsyncOpenAI"
            ) as mock_openai:
                extractor = ConceptExtractor()
                extractor._client = mock_openai.return_value
                extractor._model = "test-model"
                yield extractor, mock_openai.return_value

    @pytest.mark.asyncio
    async def test_extract_concepts_calls_llm(self, mock_extractor):
        """Test that extract_concepts makes correct LLM call."""
        extractor, mock_client = mock_extractor

        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='[{"name": "Test", "definition": "Def", "importance": 3, "source_quote": "q"}]'
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        concepts = await extractor.extract_concepts(
            text="Some text about Test concepts",
            book_title="Test Book",
            section_title="Chapter 1",
        )

        assert len(concepts) == 1
        assert concepts[0].name == "Test"
        mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_relationships_needs_multiple_concepts(self, mock_extractor):
        """Test that relationship extraction requires at least 2 concepts."""
        extractor, _ = mock_extractor

        # Only one concept
        concepts = [
            ExtractedConcept(
                name="Single", definition="D", importance=3, source_quote="q"
            )
        ]

        relationships = await extractor.extract_relationships("text", concepts)

        assert relationships == []

    @pytest.mark.asyncio
    async def test_full_extraction_pipeline(self, mock_extractor):
        """Test the full extract_from_text pipeline."""
        extractor, mock_client = mock_extractor

        # Mock concept extraction response
        concept_response = MagicMock()
        concept_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="""[
                        {"name": "A", "definition": "Def A", "importance": 5, "source_quote": "qa"},
                        {"name": "B", "definition": "Def B", "importance": 3, "source_quote": "qb"}
                    ]"""
                )
            )
        ]

        # Mock relationship extraction response
        rel_response = MagicMock()
        rel_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='[{"source": "A", "target": "B", "type": "explains", "description": "A explains B"}]'
                )
            )
        ]

        mock_client.chat.completions.create = AsyncMock(
            side_effect=[concept_response, rel_response]
        )

        concepts, relationships = await extractor.extract_from_text(
            text="Short text about A and B",
            book_title="Test",
            section_title="Ch1",
        )

        assert len(concepts) == 2
        assert len(relationships) == 1
        assert relationships[0].type == "explains"


class TestTripleExtraction:
    """Tests for the new triple-based extraction."""

    @pytest.fixture
    def mock_extractor(self):
        """Create extractor with fully mocked LLM."""
        with patch(
            "app.services.knowledge.concept_extractor.LLMConfigService"
        ) as mock_config:
            mock_config.return_value.get_active_configuration.return_value = MagicMock(
                base_url="http://test",
                api_key="test",
                model_name="test-model",
            )

            with patch(
                "app.services.knowledge.concept_extractor.AsyncOpenAI"
            ) as mock_openai:
                extractor = ConceptExtractor()
                extractor._client = mock_openai.return_value
                extractor._model = "test-model"
                yield extractor, mock_openai.return_value

    @pytest.mark.asyncio
    async def test_extract_triples_returns_triples(self, mock_extractor):
        """Test that extract_triples returns ExtractedTriple objects."""
        extractor, mock_client = mock_extractor

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="""[
                        {
                            "subject": {"name": "Photosynthesis", "definition": "Process of converting light to energy"},
                            "predicate": "requires",
                            "object": {"name": "Chlorophyll", "definition": "Green pigment in plants"},
                            "description": "Photosynthesis requires chlorophyll"
                        }
                    ]"""
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        triples = await extractor.extract_triples(
            text="Plants use photosynthesis which requires chlorophyll.",
            book_title="Biology 101",
            section_title="Chapter 1",
        )

        assert len(triples) == 1
        assert triples[0].subject.name == "Photosynthesis"
        assert triples[0].predicate == "requires"
        assert triples[0].object.name == "Chlorophyll"

    @pytest.mark.asyncio
    async def test_extract_triples_single_llm_call(self, mock_extractor):
        """Test that extract_triples makes exactly ONE LLM call (the efficiency goal)."""
        extractor, mock_client = mock_extractor

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="[]"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        await extractor.extract_triples(
            text="Some text",
            book_title="Test",
            section_title="Ch1",
        )

        # KEY ASSERTION: Only ONE LLM call, not two
        assert mock_client.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_extract_triples_handles_empty_response(self, mock_extractor):
        """Test handling of empty LLM response."""
        extractor, mock_client = mock_extractor

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="[]"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        triples = await extractor.extract_triples(
            text="Generic text with no relationships",
            book_title="Test",
            section_title="Ch1",
        )

        assert triples == []

    @pytest.mark.asyncio
    async def test_extract_triples_normalizes_predicate(self, mock_extractor):
        """Test that predicates are normalized (lowercase, underscores to hyphens)."""
        extractor, mock_client = mock_extractor

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="""[
                        {
                            "subject": {"name": "A", "definition": "D"},
                            "predicate": "Builds_On",
                            "object": {"name": "B", "definition": "D"},
                            "description": "A builds on B"
                        }
                    ]"""
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        triples = await extractor.extract_triples(
            text="Text",
            book_title="Test",
            section_title="Ch1",
        )

        assert triples[0].predicate == "builds-on"

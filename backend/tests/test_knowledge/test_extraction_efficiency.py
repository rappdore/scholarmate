"""
Efficiency benchmark tests for knowledge extraction.

These tests verify that triple-based extraction uses fewer LLM calls
than the two-pass approach.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.knowledge.concept_extractor import ConceptExtractor


class TestExtractionEfficiency:
    """Tests comparing LLM call efficiency between extraction approaches."""

    @pytest.fixture
    def mock_extractor(self):
        """Create extractor with call-counting mock."""
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

    def _make_concept_response(self):
        """Create a mock LLM response for concept extraction."""
        response = MagicMock()
        response.choices = [
            MagicMock(
                message=MagicMock(
                    content="""[
                        {"name": "A", "definition": "Def A", "importance": 3, "source_quote": "q"},
                        {"name": "B", "definition": "Def B", "importance": 3, "source_quote": "q"}
                    ]"""
                )
            )
        ]
        return response

    def _make_relationship_response(self):
        """Create a mock LLM response for relationship extraction."""
        response = MagicMock()
        response.choices = [
            MagicMock(
                message=MagicMock(
                    content="""[
                        {"source": "A", "target": "B", "type": "explains", "description": "A explains B"}
                    ]"""
                )
            )
        ]
        return response

    def _make_triple_response(self):
        """Create a mock LLM response for triple extraction."""
        response = MagicMock()
        response.choices = [
            MagicMock(
                message=MagicMock(
                    content="""[
                        {
                            "subject": {"name": "A", "definition": "Def A"},
                            "predicate": "explains",
                            "object": {"name": "B", "definition": "Def B"},
                            "description": "A explains B"
                        }
                    ]"""
                )
            )
        ]
        return response

    @pytest.mark.asyncio
    async def test_old_approach_makes_two_calls_per_chunk(self, mock_extractor):
        """Verify old approach: 2 LLM calls per chunk (concepts + relationships)."""
        extractor, mock_client = mock_extractor

        # Alternate between concept and relationship responses
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[
                self._make_concept_response(),
                self._make_relationship_response(),
            ]
        )

        # Old approach: extract_from_text calls both extract_concepts and extract_relationships
        # For a single chunk of text
        text = "Short text that won't be chunked."
        concepts, relationships = await extractor.extract_from_text(
            text=text,
            book_title="Test",
            section_title="Ch1",
        )

        # OLD APPROACH: 2 calls (1 for concepts, 1 for relationships)
        assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_new_approach_makes_one_call_per_chunk(self, mock_extractor):
        """Verify new approach: 1 LLM call per chunk (triples only)."""
        extractor, mock_client = mock_extractor

        mock_client.chat.completions.create = AsyncMock(
            return_value=self._make_triple_response()
        )

        # New approach: extract_triples
        text = "Short text that won't be chunked."
        triples = await extractor.extract_triples(
            text=text,
            book_title="Test",
            section_title="Ch1",
        )

        # NEW APPROACH: 1 call (triples include both concepts and relationships)
        assert mock_client.chat.completions.create.call_count == 1

        # Verify we still get the data we need
        concepts = extractor.triples_to_concepts(triples)
        relationships = extractor.triples_to_relationships(triples)

        assert len(concepts) == 2
        assert len(relationships) == 1

    @pytest.mark.asyncio
    async def test_efficiency_gain_multiple_chunks(self, mock_extractor):
        """Test that efficiency gain scales with number of chunks."""
        extractor, mock_client = mock_extractor

        # Create text that will be split into multiple chunks
        text = "This is sentence number one. " * 200  # ~6000 chars = ~2-3 chunks

        chunks = extractor.chunk_content(text, chunk_size=3000)
        num_chunks = len(chunks)
        assert num_chunks >= 2, "Test requires at least 2 chunks"

        # Test OLD approach call count
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[
                (
                    self._make_concept_response()
                    if i % 2 == 0
                    else self._make_relationship_response()
                )
                for i in range(num_chunks * 2)
            ]
        )

        await extractor.extract_from_text(text, "Test", "Ch1")
        old_call_count = mock_client.chat.completions.create.call_count

        # Reset mock
        mock_client.chat.completions.create.reset_mock()

        # Test NEW approach call count
        mock_client.chat.completions.create = AsyncMock(
            return_value=self._make_triple_response()
        )

        all_triples = []
        async for _, _, triples, _ in extractor.extract_triples_incrementally(
            text, "Test", "Ch1", chunk_size=3000
        ):
            all_triples.extend(triples)

        new_call_count = mock_client.chat.completions.create.call_count

        # EFFICIENCY ASSERTION: New approach should use half the calls
        assert new_call_count == num_chunks, (
            f"New approach should make {num_chunks} calls"
        )
        assert old_call_count == num_chunks * 2, (
            f"Old approach should make {num_chunks * 2} calls"
        )
        assert new_call_count == old_call_count / 2, (
            "New approach should use 50% fewer calls"
        )

        print("\n=== EFFICIENCY BENCHMARK ===")
        print(f"Chunks: {num_chunks}")
        print(f"Old approach (2-pass): {old_call_count} LLM calls")
        print(f"New approach (triple): {new_call_count} LLM calls")
        print(f"Savings: {(1 - new_call_count / old_call_count) * 100:.0f}%")

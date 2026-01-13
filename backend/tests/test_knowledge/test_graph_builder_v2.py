"""
Tests for the new triple-based GraphBuilder extraction.
"""

from unittest.mock import MagicMock

import pytest

from app.models.knowledge_models import ExtractedTriple, TripleEntity
from app.services.knowledge.graph_builder import GraphBuilder


class TestGraphBuilderTripleExtraction:
    """Tests for extract_and_store_v2 using triple-based extraction."""

    @pytest.fixture
    def mock_graph_builder(self):
        """Create GraphBuilder with mocked dependencies."""
        mock_db = MagicMock()
        mock_db.is_section_extracted.return_value = False
        mock_db.get_extracted_chunks.return_value = set()
        mock_db.create_concept.side_effect = (
            lambda **kwargs: hash(kwargs["name"]) % 1000
        )
        mock_db.create_relationship.return_value = 1
        mock_db.get_concepts_for_book.return_value = []

        mock_embedding = MagicMock()
        mock_embedding.check_duplicate.return_value = None

        mock_extractor = MagicMock()
        mock_registry = MagicMock()
        mock_registry.is_cancellation_requested.return_value = False

        builder = GraphBuilder(
            db=mock_db,
            embedding_service=mock_embedding,
            concept_extractor=mock_extractor,
            extraction_registry=mock_registry,
        )

        return builder, mock_db, mock_extractor, mock_registry

    @pytest.mark.asyncio
    async def test_extract_and_store_v2_uses_triple_extraction(
        self, mock_graph_builder
    ):
        """Test that v2 uses extract_triples_incrementally."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        # Setup mock to yield triples
        async def mock_triple_generator(*args, **kwargs):
            yield (
                0,  # chunk_index
                1,  # total_chunks
                [
                    ExtractedTriple(
                        subject=TripleEntity(name="A", definition="Def A"),
                        predicate="explains",
                        object=TripleEntity(name="B", definition="Def B"),
                        description="A explains B",
                    )
                ],
                False,  # was_skipped
            )

        mock_extractor.extract_triples_incrementally = mock_triple_generator
        mock_extractor.triples_to_concepts.return_value = [
            MagicMock(name="A", definition="Def A", importance=3, source_quote=""),
            MagicMock(name="B", definition="Def B", importance=3, source_quote=""),
        ]
        mock_extractor.triples_to_relationships.return_value = [
            MagicMock(
                source="A", target="B", type="explains", description="A explains B"
            ),
        ]
        mock_extractor.chunk_content.return_value = ["chunk1"]

        result = await builder.extract_and_store_v2(
            content="Test content about A and B",
            book_id=1,
            book_type="epub",
            book_title="Test Book",
            section_title="Chapter 1",
            nav_id="ch1",
        )

        assert result["concepts_extracted"] >= 0
        assert "already_extracted" in result
        assert result["already_extracted"] is False

    @pytest.mark.asyncio
    async def test_extract_and_store_v2_returns_already_extracted(
        self, mock_graph_builder
    ):
        """Test that v2 returns early if section already extracted."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        mock_db.is_section_extracted.return_value = True

        result = await builder.extract_and_store_v2(
            content="Test content",
            book_id=1,
            book_type="epub",
            book_title="Test",
            section_title="Ch1",
            nav_id="ch1",
        )

        assert result["already_extracted"] is True
        assert result["concepts_extracted"] == 0

    @pytest.mark.asyncio
    async def test_extract_and_store_v2_handles_cancellation(self, mock_graph_builder):
        """Test that v2 handles cancellation correctly."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        # First call returns False, second returns True (simulating cancellation)
        mock_registry.is_cancellation_requested.side_effect = [False, True]

        async def mock_triple_generator(*args, **kwargs):
            yield (0, 2, [], False)
            yield (1, 2, [], False)

        mock_extractor.extract_triples_incrementally = mock_triple_generator
        mock_extractor.chunk_content.return_value = ["chunk1", "chunk2"]

        result = await builder.extract_and_store_v2(
            content="Test content",
            book_id=1,
            book_type="epub",
            book_title="Test",
            section_title="Ch1",
            nav_id="ch1",
        )

        assert result["cancelled"] is True
        # Should NOT mark section as extracted when cancelled
        mock_db.mark_section_extracted.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_and_store_v2_stores_concepts_per_chunk(
        self, mock_graph_builder
    ):
        """Test that v2 stores concepts incrementally per chunk."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        # Create ExtractedConcept mock that has proper attributes
        concept_a = MagicMock()
        concept_a.name = "A"
        concept_a.definition = "Def A"
        concept_a.importance = 3
        concept_a.source_quote = ""

        concept_b = MagicMock()
        concept_b.name = "B"
        concept_b.definition = "Def B"
        concept_b.importance = 3
        concept_b.source_quote = ""

        async def mock_triple_generator(*args, **kwargs):
            yield (
                0,
                2,
                [
                    ExtractedTriple(
                        subject=TripleEntity(name="A", definition="Def A"),
                        predicate="explains",
                        object=TripleEntity(name="B", definition="Def B"),
                    )
                ],
                False,
            )
            yield (
                1,
                2,
                [
                    ExtractedTriple(
                        subject=TripleEntity(name="C", definition="Def C"),
                        predicate="requires",
                        object=TripleEntity(name="D", definition="Def D"),
                    )
                ],
                False,
            )

        mock_extractor.extract_triples_incrementally = mock_triple_generator
        mock_extractor.triples_to_concepts.side_effect = [
            [concept_a, concept_b],
            [
                MagicMock(name="C", definition="Def C", importance=3, source_quote=""),
                MagicMock(name="D", definition="Def D", importance=3, source_quote=""),
            ],
        ]
        mock_extractor.triples_to_relationships.side_effect = [
            [MagicMock(source="A", target="B", type="explains", description="")],
            [MagicMock(source="C", target="D", type="requires", description="")],
        ]
        mock_extractor.chunk_content.return_value = ["chunk1", "chunk2"]

        result = await builder.extract_and_store_v2(
            content="Test content",
            book_id=1,
            book_type="epub",
            book_title="Test",
            section_title="Ch1",
            nav_id="ch1",
        )

        # Should have processed 2 chunks
        assert result["chunks_processed"] == 2
        # Should have stored concepts and relationships
        assert mock_db.create_concept.call_count >= 2

    @pytest.mark.asyncio
    async def test_extract_and_store_v2_resumes_from_skip_chunks(
        self, mock_graph_builder
    ):
        """Test that v2 skips already-extracted chunks during resume."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        # Simulate chunk 0 already extracted
        mock_db.get_extracted_chunks.return_value = {0}
        mock_db.get_concepts_for_book.return_value = [
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"},
        ]

        async def mock_triple_generator(*args, **kwargs):
            # Chunk 0 is skipped
            yield (0, 2, [], True)
            # Chunk 1 is processed
            yield (
                1,
                2,
                [
                    ExtractedTriple(
                        subject=TripleEntity(name="C", definition="Def C"),
                        predicate="requires",
                        object=TripleEntity(name="D", definition="Def D"),
                    )
                ],
                False,
            )

        mock_extractor.extract_triples_incrementally = mock_triple_generator
        mock_extractor.triples_to_concepts.return_value = [
            MagicMock(name="C", definition="Def C", importance=3, source_quote=""),
            MagicMock(name="D", definition="Def D", importance=3, source_quote=""),
        ]
        mock_extractor.triples_to_relationships.return_value = []
        mock_extractor.chunk_content.return_value = ["chunk1", "chunk2"]

        result = await builder.extract_and_store_v2(
            content="Test content",
            book_id=1,
            book_type="epub",
            book_title="Test",
            section_title="Ch1",
            nav_id="ch1",
        )

        assert result["chunks_skipped"] == 1
        assert result["resumed"] is True

    @pytest.mark.asyncio
    async def test_extract_and_store_v2_requires_nav_id_or_page_num(
        self, mock_graph_builder
    ):
        """Test that v2 raises error if neither nav_id nor page_num provided."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        with pytest.raises(
            ValueError, match="Either nav_id or page_num must be provided"
        ):
            await builder.extract_and_store_v2(
                content="Test content",
                book_id=1,
                book_type="epub",
                book_title="Test",
                section_title="Ch1",
                # Neither nav_id nor page_num provided
            )

    @pytest.mark.asyncio
    async def test_extract_and_store_v2_marks_section_extracted_on_completion(
        self, mock_graph_builder
    ):
        """Test that v2 marks section as extracted when all chunks complete."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        async def mock_triple_generator(*args, **kwargs):
            yield (0, 1, [], False)

        mock_extractor.extract_triples_incrementally = mock_triple_generator
        mock_extractor.chunk_content.return_value = ["chunk1"]

        await builder.extract_and_store_v2(
            content="Test content",
            book_id=1,
            book_type="epub",
            book_title="Test",
            section_title="Ch1",
            nav_id="ch1",
        )

        mock_db.mark_section_extracted.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_and_store_v2_updates_progress_registry(
        self, mock_graph_builder
    ):
        """Test that v2 updates the extraction registry with progress."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        async def mock_triple_generator(*args, **kwargs):
            yield (0, 2, [], False)
            yield (1, 2, [], False)

        mock_extractor.extract_triples_incrementally = mock_triple_generator
        mock_extractor.chunk_content.return_value = ["chunk1", "chunk2"]

        await builder.extract_and_store_v2(
            content="Test content",
            book_id=1,
            book_type="epub",
            book_title="Test",
            section_title="Ch1",
            nav_id="ch1",
        )

        # Should have registered the extraction
        mock_registry.register_extraction.assert_called_once()
        # Should have updated progress multiple times
        assert mock_registry.update_progress.call_count >= 2

    @pytest.mark.asyncio
    async def test_extract_and_store_v2_handles_extraction_error(
        self, mock_graph_builder
    ):
        """Test that v2 handles errors during extraction gracefully."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        async def mock_triple_generator(*args, **kwargs):
            yield (0, 2, [], False)
            raise RuntimeError("LLM connection failed")

        mock_extractor.extract_triples_incrementally = mock_triple_generator
        mock_extractor.chunk_content.return_value = ["chunk1", "chunk2"]

        result = await builder.extract_and_store_v2(
            content="Test content",
            book_id=1,
            book_type="epub",
            book_title="Test",
            section_title="Ch1",
            nav_id="ch1",
        )

        assert result["failed"] is True
        assert result["error"] is not None
        # Should have marked as failed in registry
        mock_registry.mark_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_and_store_v2_force_clears_progress(self, mock_graph_builder):
        """Test that v2 with force=True clears existing chunk progress."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        async def mock_triple_generator(*args, **kwargs):
            yield (0, 1, [], False)

        mock_extractor.extract_triples_incrementally = mock_triple_generator
        mock_extractor.chunk_content.return_value = ["chunk1"]

        await builder.extract_and_store_v2(
            content="Test content",
            book_id=1,
            book_type="epub",
            book_title="Test",
            section_title="Ch1",
            nav_id="ch1",
            force=True,
        )

        mock_db.clear_chunk_progress.assert_called()


class TestGraphBuilderAutoExtraction:
    """Tests for USE_TRIPLE_EXTRACTION flag and extract_and_store_auto method."""

    @pytest.fixture
    def mock_graph_builder(self):
        """Create GraphBuilder with mocked dependencies."""
        mock_db = MagicMock()
        mock_db.is_section_extracted.return_value = False
        mock_db.get_extracted_chunks.return_value = set()
        mock_db.create_concept.side_effect = (
            lambda **kwargs: hash(kwargs["name"]) % 1000
        )
        mock_db.create_relationship.return_value = 1
        mock_db.get_concepts_for_book.return_value = []

        mock_embedding = MagicMock()
        mock_embedding.check_duplicate.return_value = None

        mock_extractor = MagicMock()
        mock_registry = MagicMock()
        mock_registry.is_cancellation_requested.return_value = False

        builder = GraphBuilder(
            db=mock_db,
            embedding_service=mock_embedding,
            concept_extractor=mock_extractor,
            extraction_registry=mock_registry,
        )

        return builder, mock_db, mock_extractor, mock_registry

    def test_use_triple_extraction_flag_exists_as_class_variable(self):
        """Test that USE_TRIPLE_EXTRACTION flag exists as a class variable."""
        assert hasattr(GraphBuilder, "USE_TRIPLE_EXTRACTION")
        # Default value should be True (using the efficient v2 extraction)
        assert GraphBuilder.USE_TRIPLE_EXTRACTION is True

    @pytest.mark.asyncio
    async def test_extract_and_store_auto_calls_v2_when_flag_true(
        self, mock_graph_builder
    ):
        """Test that extract_and_store_auto calls extract_and_store_v2 when flag is True."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        # Set the flag to True
        original_flag = GraphBuilder.USE_TRIPLE_EXTRACTION
        try:
            GraphBuilder.USE_TRIPLE_EXTRACTION = True

            async def mock_triple_generator(*args, **kwargs):
                yield (0, 1, [], False)

            mock_extractor.extract_triples_incrementally = mock_triple_generator
            mock_extractor.chunk_content.return_value = ["chunk1"]

            result = await builder.extract_and_store_auto(
                content="Test content",
                book_id=1,
                book_type="epub",
                book_title="Test",
                section_title="Ch1",
                nav_id="ch1",
            )

            # v2 uses extract_triples_incrementally (not extract_concepts_incrementally)
            # We can verify v2 was called by checking that the registry was properly updated
            mock_registry.register_extraction.assert_called_once()
            assert result is not None
            assert "already_extracted" in result
        finally:
            GraphBuilder.USE_TRIPLE_EXTRACTION = original_flag

    @pytest.mark.asyncio
    async def test_extract_and_store_auto_calls_v1_when_flag_false(
        self, mock_graph_builder
    ):
        """Test that extract_and_store_auto calls extract_and_store (v1) when flag is False."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        # Set the flag to False
        original_flag = GraphBuilder.USE_TRIPLE_EXTRACTION
        try:
            GraphBuilder.USE_TRIPLE_EXTRACTION = False

            async def mock_concept_generator(*args, **kwargs):
                yield (0, 1, [], False)

            mock_extractor.extract_concepts_incrementally = mock_concept_generator
            mock_extractor.chunk_content.return_value = ["chunk1"]

            result = await builder.extract_and_store_auto(
                content="Test content",
                book_id=1,
                book_type="epub",
                book_title="Test",
                section_title="Ch1",
                nav_id="ch1",
            )

            # v1 uses extract_concepts_incrementally (not extract_triples_incrementally)
            mock_registry.register_extraction.assert_called_once()
            assert result is not None
            assert "already_extracted" in result
        finally:
            GraphBuilder.USE_TRIPLE_EXTRACTION = original_flag

    @pytest.mark.asyncio
    async def test_extract_and_store_auto_passes_all_parameters(
        self, mock_graph_builder
    ):
        """Test that extract_and_store_auto passes all parameters correctly."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        original_flag = GraphBuilder.USE_TRIPLE_EXTRACTION
        try:
            GraphBuilder.USE_TRIPLE_EXTRACTION = True

            async def mock_triple_generator(*args, **kwargs):
                yield (0, 1, [], False)

            mock_extractor.extract_triples_incrementally = mock_triple_generator
            mock_extractor.chunk_content.return_value = ["chunk1"]

            # Call with all parameters
            await builder.extract_and_store_auto(
                content="Test content",
                book_id=42,
                book_type="pdf",
                book_title="My Book",
                section_title="Chapter 5",
                nav_id=None,
                page_num=10,
                force=True,
            )

            # Verify db.clear_chunk_progress was called (force=True triggers this)
            mock_db.clear_chunk_progress.assert_called()
        finally:
            GraphBuilder.USE_TRIPLE_EXTRACTION = original_flag

    @pytest.mark.asyncio
    async def test_extract_and_store_auto_returns_v2_result_format(
        self, mock_graph_builder
    ):
        """Test that extract_and_store_auto returns proper result format from v2."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        original_flag = GraphBuilder.USE_TRIPLE_EXTRACTION
        try:
            GraphBuilder.USE_TRIPLE_EXTRACTION = True

            async def mock_triple_generator(*args, **kwargs):
                yield (0, 1, [], False)

            mock_extractor.extract_triples_incrementally = mock_triple_generator
            mock_extractor.chunk_content.return_value = ["chunk1"]

            result = await builder.extract_and_store_auto(
                content="Test content",
                book_id=1,
                book_type="epub",
                book_title="Test",
                section_title="Ch1",
                nav_id="ch1",
            )

            # Verify result structure matches v2 format
            assert "concepts_extracted" in result
            assert "relationships_found" in result
            assert "already_extracted" in result
            assert "chunks_processed" in result
            assert "cancelled" in result
            assert "failed" in result
        finally:
            GraphBuilder.USE_TRIPLE_EXTRACTION = original_flag

    @pytest.mark.asyncio
    async def test_extract_and_store_auto_requires_nav_id_or_page_num(
        self, mock_graph_builder
    ):
        """Test that extract_and_store_auto raises error if neither nav_id nor page_num provided."""
        builder, mock_db, mock_extractor, mock_registry = mock_graph_builder

        with pytest.raises(
            ValueError, match="Either nav_id or page_num must be provided"
        ):
            await builder.extract_and_store_auto(
                content="Test content",
                book_id=1,
                book_type="epub",
                book_title="Test",
                section_title="Ch1",
                # Neither nav_id nor page_num provided
            )

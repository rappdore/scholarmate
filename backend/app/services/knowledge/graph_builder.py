"""
Graph Builder Service Module

This module orchestrates the knowledge graph construction:
- Coordinates extraction, deduplication, and storage
- Manages concept merging for duplicates
- Tracks extraction progress
"""

import hashlib
import logging
import threading
from typing import Any

from app.models.knowledge_models import (
    Concept,
    ExtractedConcept,
    ExtractedRelationship,
)

from .concept_extractor import ConceptExtractor, get_concept_extractor
from .embedding_service import EmbeddingService, get_embedding_service
from .extraction_state import (
    ExtractionPhase,
    ExtractionRegistry,
    get_extraction_registry,
)
from .knowledge_database import KnowledgeDatabase, knowledge_db

logger = logging.getLogger(__name__)

# Similarity thresholds for deduplication
DUPLICATE_THRESHOLD = 0.92  # Very similar - merge
RELATED_THRESHOLD = 0.80  # Somewhat similar - create relationship


class GraphBuilder:
    """
    Service for building and managing the knowledge graph.

    Coordinates between extraction, embedding, and storage services
    to construct a coherent knowledge graph from document content.
    """

    def __init__(
        self,
        db: KnowledgeDatabase | None = None,
        embedding_service: EmbeddingService | None = None,
        concept_extractor: ConceptExtractor | None = None,
        extraction_registry: ExtractionRegistry | None = None,
    ):
        """
        Initialize the graph builder.

        Args:
            db: Knowledge database instance
            embedding_service: Embedding service instance
            concept_extractor: Concept extractor instance
            extraction_registry: Extraction state registry instance
        """
        self.db = db or knowledge_db
        self.embedding_service = embedding_service or get_embedding_service()
        self.concept_extractor = concept_extractor or get_concept_extractor()
        self.extraction_registry = extraction_registry or get_extraction_registry()

    def _compute_content_hash(self, content: str) -> str:
        """Compute a hash of content for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _build_relationship_keys_from_graph(
        self,
        book_id: int,
        book_type: str,
        section_concepts: list[dict[str, Any]],
    ) -> set[str]:
        """Build set of existing relationship keys for deduplication.

        Args:
            book_id: ID of the book
            book_type: Type of book
            section_concepts: List of concept dicts with 'id' and 'name' keys

        Returns:
            Set of relationship keys in format "source|target|type"
        """
        concept_id_to_name = {c["id"]: c["name"] for c in section_concepts}
        existing_rels = self.db.get_graph_for_book(book_id, book_type).get("edges", [])

        known_keys: set[str] = set()
        for rel in existing_rels:
            source_name = concept_id_to_name.get(rel.get("source"))
            target_name = concept_id_to_name.get(rel.get("target"))
            if source_name and target_name:
                key = f"{source_name}|{target_name}|{rel.get('type', '')}"
                known_keys.add(key)

        return known_keys

    def _convert_db_concepts_to_extracted(
        self, db_concepts: list[dict[str, Any]]
    ) -> list[ExtractedConcept]:
        """Convert database concept dicts to ExtractedConcept objects."""
        return [
            ExtractedConcept(
                name=c["name"],
                definition=c.get("definition", ""),
                importance=c.get("importance", 3),
                source_quote=c.get("source_quote", ""),
            )
            for c in db_concepts
        ]

    async def extract_and_store(
        self,
        content: str,
        book_id: int,
        book_type: str,
        book_title: str,
        section_title: str,
        nav_id: str | None = None,
        page_num: int | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Full pipeline: extract concepts/relationships and store them INCREMENTALLY.

        Concepts are extracted and stored chunk by chunk, so partial progress
        is preserved even if the process fails partway through. This is critical
        for large sections that may take tens of minutes to process.

        Supports RESUMABILITY: if extraction was interrupted, re-running will
        skip already-extracted chunks and continue from where it left off.

        Args:
            content: Text content to extract from
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')
            book_title: Title of the book
            section_title: Title of the section
            nav_id: Navigation ID (for EPUBs)
            page_num: Page number (for PDFs)
            force: Force re-extraction even if already done

        Returns:
            Dictionary with extraction results
        """
        if nav_id is None and page_num is None:
            raise ValueError("Either nav_id or page_num must be provided")
        section_id = nav_id or f"page_{page_num}"
        content_hash = self._compute_content_hash(content)

        logger.info(
            f"Starting extract_and_store for book_id={book_id}, "
            f"book_type={book_type}, section={section_id}, force={force}"
        )
        logger.info(f"Content length: {len(content)} characters, hash: {content_hash}")

        # Check if already fully extracted
        try:
            if not force and self.db.is_section_extracted(
                book_id, book_type, nav_id, page_num
            ):
                logger.info(
                    f"Section already extracted: book={book_id}, section={section_id}"
                )
                return {
                    "concepts_extracted": 0,
                    "relationships_found": 0,
                    "already_extracted": True,
                }
        except ValueError as e:
            # Handle case where nav_id and page_num validation fails
            logger.warning(
                f"Validation error checking extraction status: {e}. Proceeding with extraction."
            )

        # Check for partial chunk progress (for resumability)
        skip_chunks: set[int] = set()
        known_concept_names: set[str] = set()

        if force:
            # Clear any existing chunk progress when forcing re-extraction
            self.db.clear_chunk_progress(book_id, book_type, nav_id, page_num)
            logger.info("Cleared chunk progress for forced re-extraction")
        else:
            # Check for existing chunk progress with matching content hash
            skip_chunks = self.db.get_extracted_chunks(
                book_id, book_type, content_hash, nav_id, page_num
            )
            if skip_chunks:
                logger.info(
                    f"RESUMING extraction: found {len(skip_chunks)} already-extracted chunks"
                )
                # Get existing concept names to avoid duplicates
                existing_concepts = self.db.get_concepts_for_book(
                    book_id, book_type, nav_id=nav_id, page_num=page_num
                )
                known_concept_names = {c["name"].lower() for c in existing_concepts}
                logger.info(
                    f"Loaded {len(known_concept_names)} existing concept names for deduplication"
                )

        # INCREMENTAL EXTRACTION: Extract and store concepts chunk by chunk
        logger.info(
            f"Starting INCREMENTAL concept extraction for section {section_id}..."
        )

        all_extracted_concepts: list[ExtractedConcept] = []
        stored_concepts: dict[str, int] = {}
        chunks_processed = 0
        chunks_skipped = 0
        was_cancelled = False
        extraction_failed = False
        extraction_error: str | None = None

        # Pre-compute chunk count so we can report accurate progress from the start
        chunks = self.concept_extractor.chunk_content(content)
        total_chunks = len(chunks)
        logger.info(f"Content will be split into {total_chunks} chunks")

        # Register this extraction for progress tracking and cancellation support
        self.extraction_registry.register_extraction(book_id, book_type, section_id)

        # Update progress immediately with total chunk count (0 processed so far)
        self.extraction_registry.update_progress(
            book_id, book_type, section_id, 0, total_chunks, 0
        )

        try:
            async for (
                chunk_idx,
                total,
                chunk_concepts,
                was_skipped,
            ) in self.concept_extractor.extract_concepts_incrementally(
                text=content,
                book_title=book_title,
                section_title=section_title,
                skip_chunks=skip_chunks,
                known_concept_names=known_concept_names,
                pre_chunked=chunks,
            ):
                total_chunks = total
                chunks_processed = chunk_idx + 1

                # Check for cancellation between chunks
                if self.extraction_registry.is_cancellation_requested(
                    book_id, book_type, section_id
                ):
                    logger.info(
                        f"Extraction CANCELLED for section {section_id} "
                        f"at chunk {chunks_processed}/{total_chunks}. "
                        f"Stored {len(stored_concepts)} concepts before cancellation."
                    )
                    was_cancelled = True
                    self.extraction_registry.mark_cancelled(
                        book_id, book_type, section_id
                    )
                    break

                if was_skipped:
                    chunks_skipped += 1
                    # Update progress even for skipped chunks
                    self.extraction_registry.update_progress(
                        book_id,
                        book_type,
                        section_id,
                        chunks_processed,
                        total_chunks,
                        len(stored_concepts),
                    )
                    continue

                if chunk_concepts:
                    logger.info(
                        f"Chunk {chunks_processed}/{total_chunks}: "
                        f"Storing {len(chunk_concepts)} concepts immediately..."
                    )

                    # Store this chunk's concepts immediately
                    chunk_stored = await self._store_concepts(
                        extracted_concepts=chunk_concepts,
                        book_id=book_id,
                        book_type=book_type,
                        nav_id=nav_id,
                        page_num=page_num,
                    )

                    # Accumulate for relationship extraction later
                    all_extracted_concepts.extend(chunk_concepts)
                    stored_concepts.update(chunk_stored)

                    logger.info(
                        f"Chunk {chunks_processed}/{total_chunks}: "
                        f"Stored {len(chunk_stored)} concepts. "
                        f"Total so far: {len(stored_concepts)}"
                    )

                # Mark this chunk as extracted (for resumability)
                self.db.mark_chunk_extracted(
                    book_id=book_id,
                    book_type=book_type,
                    chunk_index=chunk_idx,
                    total_chunks=total,
                    content_hash=content_hash,
                    nav_id=nav_id,
                    page_num=page_num,
                )

                # Update progress in registry
                self.extraction_registry.update_progress(
                    book_id,
                    book_type,
                    section_id,
                    chunks_processed,
                    total_chunks,
                    len(stored_concepts),
                )

                if not chunk_concepts:
                    logger.info(
                        f"Chunk {chunks_processed}/{total_chunks}: No concepts extracted"
                    )

        except Exception as e:
            extraction_failed = True
            extraction_error = str(e)
            logger.error(
                f"Error during incremental extraction at chunk {chunks_processed}/{total_chunks}: {e}",
                exc_info=True,
            )
            # Mark as failed in registry
            self.extraction_registry.mark_failed(book_id, book_type, section_id, str(e))
            # Don't raise - we want to keep whatever concepts we've stored so far
            logger.warning(
                f"Incremental extraction failed after {chunks_processed} chunks. "
                f"Stored {len(stored_concepts)} concepts before failure. "
                f"Re-run to resume from chunk {chunks_processed}."
            )

        logger.info(
            f"Concept extraction complete for section {section_id}: "
            f"{chunks_processed}/{total_chunks} chunks processed, "
            f"{chunks_skipped} skipped (resumed), "
            f"{len(stored_concepts)} concepts stored this run, "
            f"cancelled={was_cancelled}"
        )

        # Extract relationships (using all stored concepts)
        # For resumed extractions, we need to get ALL concepts for the section
        # Skip relationship extraction if cancelled
        stored_relationships: list[int] = []
        rel_chunks_processed = 0
        rel_total_chunks = 0
        rel_was_cancelled = False

        if chunks_processed == total_chunks and not was_cancelled:
            # Get all concepts for this section (including from previous runs)
            all_section_concepts = self.db.get_concepts_for_book(
                book_id, book_type, nav_id=nav_id, page_num=page_num
            )

            if len(all_section_concepts) >= 2:
                logger.info(
                    f"Starting relationship extraction for section {section_id} "
                    f"with {len(all_section_concepts)} total concepts..."
                )

                # Switch to relationship phase
                self.extraction_registry.update_phase(
                    book_id, book_type, section_id, ExtractionPhase.RELATIONSHIPS
                )

                # Convert DB concepts back to ExtractedConcept for relationship extraction
                concepts_for_rel = self._convert_db_concepts_to_extracted(
                    all_section_concepts
                )

                # Build stored_concepts map from all section concepts
                all_stored = {c["name"]: c["id"] for c in all_section_concepts}

                # Check for partial relationship chunk progress (for resumability)
                skip_rel_chunks: set[int] = set()
                known_rel_keys: set[str] = set()

                if force:
                    # Clear any existing relationship chunk progress
                    self.db.clear_relationship_chunk_progress(
                        book_id, book_type, nav_id, page_num
                    )
                    logger.info(
                        "Cleared relationship chunk progress for forced re-extraction"
                    )
                else:
                    # Check for existing relationship chunk progress
                    skip_rel_chunks = self.db.get_extracted_relationship_chunks(
                        book_id, book_type, content_hash, nav_id, page_num
                    )
                    if skip_rel_chunks:
                        logger.info(
                            f"RESUMING relationship extraction: found {len(skip_rel_chunks)} already-extracted chunks"
                        )
                        known_rel_keys = self._build_relationship_keys_from_graph(
                            book_id, book_type, all_section_concepts
                        )
                        logger.info(
                            f"Loaded {len(known_rel_keys)} existing relationship keys for deduplication"
                        )

                # Pre-compute relationship chunks
                rel_chunks = self.concept_extractor.chunk_content(content)
                rel_total_chunks = len(rel_chunks)

                # Initialize relationship progress
                self.extraction_registry.update_relationship_progress(
                    book_id, book_type, section_id, 0, rel_total_chunks, 0
                )

                try:
                    # Incremental relationship extraction
                    async for (
                        rel_chunk_idx,
                        rel_total,
                        chunk_relationships,
                        rel_was_skipped,
                    ) in self.concept_extractor.extract_relationships_incrementally(
                        text=content,
                        all_concepts=concepts_for_rel,
                        skip_chunks=skip_rel_chunks,
                        known_relationship_keys=known_rel_keys,
                        pre_chunked=rel_chunks,
                    ):
                        rel_total_chunks = rel_total
                        rel_chunks_processed = rel_chunk_idx + 1

                        # Check for cancellation between relationship chunks
                        if self.extraction_registry.is_cancellation_requested(
                            book_id, book_type, section_id
                        ):
                            logger.info(
                                f"Relationship extraction CANCELLED for section {section_id} "
                                f"at chunk {rel_chunks_processed}/{rel_total_chunks}. "
                                f"Stored {len(stored_relationships)} relationships before cancellation."
                            )
                            rel_was_cancelled = True
                            self.extraction_registry.mark_cancelled(
                                book_id, book_type, section_id
                            )
                            break

                        if rel_was_skipped:
                            # Update progress even for skipped chunks
                            self.extraction_registry.update_relationship_progress(
                                book_id,
                                book_type,
                                section_id,
                                rel_chunks_processed,
                                rel_total_chunks,
                                len(stored_relationships),
                            )
                            continue

                        if chunk_relationships:
                            logger.info(
                                f"Relationship chunk {rel_chunks_processed}/{rel_total_chunks}: "
                                f"Storing {len(chunk_relationships)} relationships immediately..."
                            )

                            # Store this chunk's relationships immediately
                            chunk_stored_ids = self._store_relationships(
                                extracted_relationships=chunk_relationships,
                                stored_concepts=all_stored,
                            )
                            stored_relationships.extend(chunk_stored_ids)

                            logger.info(
                                f"Relationship chunk {rel_chunks_processed}/{rel_total_chunks}: "
                                f"Stored {len(chunk_stored_ids)} relationships. "
                                f"Total so far: {len(stored_relationships)}"
                            )

                        # Mark this relationship chunk as extracted (for resumability)
                        self.db.mark_relationship_chunk_extracted(
                            book_id=book_id,
                            book_type=book_type,
                            chunk_index=rel_chunk_idx,
                            total_chunks=rel_total,
                            content_hash=content_hash,
                            nav_id=nav_id,
                            page_num=page_num,
                        )

                        # Update relationship progress in registry
                        self.extraction_registry.update_relationship_progress(
                            book_id,
                            book_type,
                            section_id,
                            rel_chunks_processed,
                            rel_total_chunks,
                            len(stored_relationships),
                        )

                        if not chunk_relationships:
                            logger.info(
                                f"Relationship chunk {rel_chunks_processed}/{rel_total_chunks}: "
                                "No relationships extracted"
                            )

                    logger.info(
                        f"Relationship extraction complete for section {section_id}: "
                        f"{rel_chunks_processed}/{rel_total_chunks} chunks processed, "
                        f"{len(stored_relationships)} relationships stored"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to extract/store relationships for section {section_id}: {e}",
                        exc_info=True,
                    )
                    # Don't raise - concepts are more important
            else:
                logger.info(
                    f"Skipping relationship extraction: only {len(all_section_concepts)} concepts"
                )

        # Mark section as extracted (only if we completed all phases and not cancelled)
        both_phases_complete = (
            chunks_processed == total_chunks
            and total_chunks > 0
            and not was_cancelled
            and (
                rel_total_chunks == 0  # No relationships to extract
                or (rel_chunks_processed == rel_total_chunks and not rel_was_cancelled)
            )
        )

        if both_phases_complete:
            try:
                self.db.mark_section_extracted(book_id, book_type, nav_id, page_num)
                # Clear chunk progress since section is now fully extracted
                self.db.clear_chunk_progress(book_id, book_type, nav_id, page_num)
                self.db.clear_relationship_chunk_progress(
                    book_id, book_type, nav_id, page_num
                )
                logger.info(f"Marked section {section_id} as fully extracted")
                # Mark as completed in registry
                self.extraction_registry.mark_completed(book_id, book_type, section_id)
            except Exception as e:
                logger.error(
                    f"Failed to mark section {section_id} as extracted: {e}",
                    exc_info=True,
                )
        elif was_cancelled or rel_was_cancelled:
            phase_cancelled = "concept" if was_cancelled else "relationship"
            logger.info(
                f"NOT marking section {section_id} as extracted: "
                f"extraction was cancelled during {phase_cancelled} phase. "
                f"Re-run to resume."
            )
        else:
            logger.warning(
                f"NOT marking section {section_id} as extracted: "
                f"concept chunks: {chunks_processed}/{total_chunks}, "
                f"relationship chunks: {rel_chunks_processed}/{rel_total_chunks}. "
                f"Re-run to resume."
            )

        # Don't unregister extraction immediately so frontend can query final status.
        # Call cleanup_finished periodically to remove stale finished extractions.

        result = {
            "concepts_extracted": len(stored_concepts),
            "relationships_found": len(stored_relationships),
            "already_extracted": False,
            "chunks_processed": chunks_processed,
            "chunks_skipped": chunks_skipped,
            "total_chunks": total_chunks,
            "resumed": chunks_skipped > 0,
            "cancelled": was_cancelled or rel_was_cancelled,
            "failed": extraction_failed,
            "error": extraction_error,
            # Relationship extraction details
            "rel_chunks_processed": rel_chunks_processed,
            "rel_total_chunks": rel_total_chunks,
        }
        logger.info(f"extract_and_store complete for section {section_id}: {result}")
        return result

    async def extract_and_store_v2(
        self,
        content: str,
        book_id: int,
        book_type: str,
        book_title: str,
        section_title: str,
        nav_id: str | None = None,
        page_num: int | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Extract concepts and relationships using SINGLE-PASS triple extraction.

        This method uses extract_triples_incrementally to extract both concepts
        and relationships in a single LLM call per chunk, making it more efficient
        than the two-pass approach in extract_and_store.

        Supports RESUMABILITY: if extraction was interrupted, re-running will
        skip already-extracted chunks and continue from where it left off.

        Args:
            content: Text content to extract from
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')
            book_title: Title of the book
            section_title: Title of the section
            nav_id: Navigation ID (for EPUBs)
            page_num: Page number (for PDFs)
            force: Force re-extraction even if already done

        Returns:
            Dictionary with extraction results
        """
        if nav_id is None and page_num is None:
            raise ValueError("Either nav_id or page_num must be provided")
        section_id = nav_id or f"page_{page_num}"
        content_hash = self._compute_content_hash(content)

        logger.info(
            f"Starting extract_and_store_v2 for book_id={book_id}, "
            f"book_type={book_type}, section={section_id}, force={force}"
        )
        logger.info(f"Content length: {len(content)} characters, hash: {content_hash}")

        # Check if already fully extracted
        try:
            if not force and self.db.is_section_extracted(
                book_id, book_type, nav_id, page_num
            ):
                logger.info(
                    f"Section already extracted: book={book_id}, section={section_id}"
                )
                return {
                    "concepts_extracted": 0,
                    "relationships_found": 0,
                    "already_extracted": True,
                    "chunks_processed": 0,
                    "chunks_skipped": 0,
                    "total_chunks": 0,
                    "resumed": False,
                    "cancelled": False,
                    "failed": False,
                    "error": None,
                }
        except ValueError as e:
            logger.warning(
                f"Validation error checking extraction status: {e}. Proceeding with extraction."
            )

        # Check for partial chunk progress (for resumability)
        skip_chunks: set[int] = set()
        known_concept_names: set[str] = set()

        if force:
            # Clear any existing chunk progress when forcing re-extraction
            self.db.clear_chunk_progress(book_id, book_type, nav_id, page_num)
            logger.info("Cleared chunk progress for forced re-extraction")
        else:
            # Check for existing chunk progress with matching content hash
            skip_chunks = self.db.get_extracted_chunks(
                book_id, book_type, content_hash, nav_id, page_num
            )
            if skip_chunks:
                logger.info(
                    f"RESUMING extraction: found {len(skip_chunks)} already-extracted chunks"
                )
                # Get existing concept names to avoid duplicates
                existing_concepts = self.db.get_concepts_for_book(
                    book_id, book_type, nav_id=nav_id, page_num=page_num
                )
                known_concept_names = {c["name"].lower() for c in existing_concepts}
                logger.info(
                    f"Loaded {len(known_concept_names)} existing concept names for deduplication"
                )

        # Pre-compute chunk count so we can report accurate progress from the start
        chunks = self.concept_extractor.chunk_content(content)
        total_chunks = len(chunks)
        logger.info(f"Content will be split into {total_chunks} chunks")

        # Register this extraction for progress tracking and cancellation support
        self.extraction_registry.register_extraction(book_id, book_type, section_id)

        # Update progress immediately with total chunk count (0 processed so far)
        self.extraction_registry.update_progress(
            book_id, book_type, section_id, 0, total_chunks, 0
        )

        # Tracking state
        stored_concepts: dict[str, int] = {}
        stored_relationships: list[int] = []
        chunks_processed = 0
        chunks_skipped = 0
        was_cancelled = False
        extraction_failed = False
        extraction_error: str | None = None

        try:
            async for (
                chunk_idx,
                total,
                chunk_triples,
                was_skipped,
            ) in self.concept_extractor.extract_triples_incrementally(
                text=content,
                book_title=book_title,
                section_title=section_title,
                skip_chunks=skip_chunks,
                pre_chunked=chunks,
            ):
                total_chunks = total
                chunks_processed = chunk_idx + 1

                # Check for cancellation between chunks
                if self.extraction_registry.is_cancellation_requested(
                    book_id, book_type, section_id
                ):
                    logger.info(
                        f"Extraction CANCELLED for section {section_id} "
                        f"at chunk {chunks_processed}/{total_chunks}. "
                        f"Stored {len(stored_concepts)} concepts before cancellation."
                    )
                    was_cancelled = True
                    self.extraction_registry.mark_cancelled(
                        book_id, book_type, section_id
                    )
                    break

                if was_skipped:
                    chunks_skipped += 1
                    # Update progress even for skipped chunks
                    self.extraction_registry.update_progress(
                        book_id,
                        book_type,
                        section_id,
                        chunks_processed,
                        total_chunks,
                        len(stored_concepts),
                    )
                    continue

                if chunk_triples:
                    logger.info(
                        f"Chunk {chunks_processed}/{total_chunks}: "
                        f"Processing {len(chunk_triples)} triples..."
                    )

                    # Convert triples to concepts (deduplicated)
                    chunk_concepts = self.concept_extractor.triples_to_concepts(
                        chunk_triples
                    )

                    # Filter out concepts we already have
                    new_concepts = [
                        c
                        for c in chunk_concepts
                        if c.name.lower() not in known_concept_names
                    ]

                    if new_concepts:
                        logger.info(
                            f"Chunk {chunks_processed}/{total_chunks}: "
                            f"Storing {len(new_concepts)} new concepts..."
                        )

                        # Store this chunk's concepts immediately
                        chunk_stored = await self._store_concepts(
                            extracted_concepts=new_concepts,
                            book_id=book_id,
                            book_type=book_type,
                            nav_id=nav_id,
                            page_num=page_num,
                        )
                        stored_concepts.update(chunk_stored)

                        # Track known concept names for future chunks
                        for c in new_concepts:
                            known_concept_names.add(c.name.lower())

                    # Convert triples to relationships and store
                    chunk_relationships = (
                        self.concept_extractor.triples_to_relationships(chunk_triples)
                    )

                    if chunk_relationships:
                        # Get all stored concepts (including from previous runs)
                        all_section_concepts = self.db.get_concepts_for_book(
                            book_id, book_type, nav_id=nav_id, page_num=page_num
                        )
                        all_stored = {c["name"]: c["id"] for c in all_section_concepts}

                        chunk_rel_ids = self._store_relationships(
                            extracted_relationships=chunk_relationships,
                            stored_concepts=all_stored,
                        )
                        stored_relationships.extend(chunk_rel_ids)

                        logger.info(
                            f"Chunk {chunks_processed}/{total_chunks}: "
                            f"Stored {len(chunk_rel_ids)} relationships. "
                            f"Total so far: {len(stored_relationships)}"
                        )

                # Mark this chunk as extracted (for resumability)
                self.db.mark_chunk_extracted(
                    book_id=book_id,
                    book_type=book_type,
                    chunk_index=chunk_idx,
                    total_chunks=total,
                    content_hash=content_hash,
                    nav_id=nav_id,
                    page_num=page_num,
                )

                # Update progress in registry
                self.extraction_registry.update_progress(
                    book_id,
                    book_type,
                    section_id,
                    chunks_processed,
                    total_chunks,
                    len(stored_concepts),
                )

                if not chunk_triples:
                    logger.info(
                        f"Chunk {chunks_processed}/{total_chunks}: No triples extracted"
                    )

        except Exception as e:
            extraction_failed = True
            extraction_error = str(e)
            logger.error(
                f"Error during triple extraction at chunk {chunks_processed}/{total_chunks}: {e}",
                exc_info=True,
            )
            # Mark as failed in registry
            self.extraction_registry.mark_failed(book_id, book_type, section_id, str(e))
            # Don't raise - we want to keep whatever we've stored so far
            logger.warning(
                f"Triple extraction failed after {chunks_processed} chunks. "
                f"Stored {len(stored_concepts)} concepts before failure. "
                f"Re-run to resume from chunk {chunks_processed}."
            )

        logger.info(
            f"Triple extraction complete for section {section_id}: "
            f"{chunks_processed}/{total_chunks} chunks processed, "
            f"{chunks_skipped} skipped (resumed), "
            f"{len(stored_concepts)} concepts stored this run, "
            f"{len(stored_relationships)} relationships stored this run, "
            f"cancelled={was_cancelled}"
        )

        # Mark section as extracted (only if we completed all chunks and not cancelled)
        if (
            chunks_processed == total_chunks
            and total_chunks > 0
            and not was_cancelled
            and not extraction_failed
        ):
            try:
                self.db.mark_section_extracted(book_id, book_type, nav_id, page_num)
                # Clear chunk progress since section is now fully extracted
                self.db.clear_chunk_progress(book_id, book_type, nav_id, page_num)
                logger.info(f"Marked section {section_id} as fully extracted")
                # Mark as completed in registry
                self.extraction_registry.mark_completed(book_id, book_type, section_id)
            except Exception as e:
                logger.error(
                    f"Failed to mark section {section_id} as extracted: {e}",
                    exc_info=True,
                )
        elif was_cancelled:
            logger.info(
                f"NOT marking section {section_id} as extracted: "
                f"extraction was cancelled. Re-run to resume."
            )
        elif extraction_failed:
            logger.warning(
                f"NOT marking section {section_id} as extracted: "
                f"extraction failed. Re-run to resume."
            )
        else:
            logger.warning(
                f"NOT marking section {section_id} as extracted: "
                f"chunks: {chunks_processed}/{total_chunks}. Re-run to resume."
            )

        result = {
            "concepts_extracted": len(stored_concepts),
            "relationships_found": len(stored_relationships),
            "already_extracted": False,
            "chunks_processed": chunks_processed,
            "chunks_skipped": chunks_skipped,
            "total_chunks": total_chunks,
            "resumed": chunks_skipped > 0,
            "cancelled": was_cancelled,
            "failed": extraction_failed,
            "error": extraction_error,
        }
        logger.info(f"extract_and_store_v2 complete for section {section_id}: {result}")
        return result

    async def _store_concepts(
        self,
        extracted_concepts: list[ExtractedConcept],
        book_id: int,
        book_type: str,
        nav_id: str | None,
        page_num: int | None,
    ) -> dict[str, int]:
        """
        Store extracted concepts with deduplication.

        Args:
            extracted_concepts: List of concepts extracted by LLM
            book_id: ID of the book
            book_type: Type of book
            nav_id: Navigation ID
            page_num: Page number

        Returns:
            Dictionary mapping concept names to their database IDs
        """
        stored_concepts: dict[str, int] = {}

        # Tracking counters for debugging
        stats = {
            "total": len(extracted_concepts),
            "duplicates_found": 0,
            "new_created": 0,
            "existing_by_name": 0,
            "failed_to_store": 0,
            "embedding_errors": 0,
        }

        logger.info(
            f"Starting to store {stats['total']} extracted concepts for "
            f"book_id={book_id}, book_type={book_type}, nav_id={nav_id}, page_num={page_num}"
        )

        for i, extracted in enumerate(extracted_concepts):
            logger.debug(
                f"Processing concept {i + 1}/{stats['total']}: '{extracted.name}'"
            )

            try:
                # Check for existing similar concept
                existing = self.embedding_service.check_duplicate(
                    name=extracted.name,
                    definition=extracted.definition,
                    book_id=book_id,
                    book_type=book_type,
                    similarity_threshold=DUPLICATE_THRESHOLD,
                )

                if existing:
                    # Duplicate found - use existing concept
                    concept_id = existing["concept_id"]
                    stats["duplicates_found"] += 1
                    logger.debug(
                        f"Found duplicate concept: '{extracted.name}' matches '{existing['name']}' "
                        f"(similarity: {existing['similarity']:.2f})"
                    )

                    # Update existing concept if new one has higher importance
                    db_concept = self.db.get_concept_by_id(concept_id)
                    if db_concept and extracted.importance > db_concept.get(
                        "importance", 0
                    ):
                        self.db.update_concept(
                            concept_id=concept_id,
                            importance=extracted.importance,
                        )

                    stored_concepts[extracted.name] = concept_id
                else:
                    # Check for somewhat similar concept (create relationship)
                    similar = self.embedding_service.find_similar(
                        text=self.embedding_service.generate_concept_text(
                            extracted.name, extracted.definition
                        ),
                        n_results=1,
                        book_id=book_id,
                        book_type=book_type,
                        threshold=RELATED_THRESHOLD,
                    )

                    # Create new concept
                    concept_id = self.db.create_concept(
                        book_id=book_id,
                        book_type=book_type,
                        name=extracted.name,
                        definition=extracted.definition,
                        source_quote=extracted.source_quote,
                        importance=extracted.importance,
                        nav_id=nav_id,
                        page_num=page_num,
                    )

                    if concept_id:
                        stats["new_created"] += 1
                        logger.debug(
                            f"Created new concept: '{extracted.name}' (id={concept_id})"
                        )

                        # Store embedding - catch errors to avoid losing the concept
                        try:
                            self.embedding_service.store_concept_embedding(
                                concept_id=concept_id,
                                name=extracted.name,
                                definition=extracted.definition,
                                metadata={
                                    "book_id": book_id,
                                    "book_type": book_type,
                                    "importance": extracted.importance,
                                },
                            )
                        except Exception as embed_err:
                            stats["embedding_errors"] += 1
                            logger.error(
                                f"Failed to store embedding for concept '{extracted.name}' "
                                f"(id={concept_id}): {embed_err}. "
                                "Concept was saved to DB but embedding search won't work."
                            )

                        stored_concepts[extracted.name] = concept_id

                        # Create "related-to" relationship with similar concept
                        if similar and similar[0]["similarity"] >= RELATED_THRESHOLD:
                            self.db.create_relationship(
                                source_concept_id=concept_id,
                                target_concept_id=similar[0]["concept_id"],
                                relationship_type="related-to",
                                description=f"Similar concepts (similarity: {similar[0]['similarity']:.2f})",
                                weight=similar[0]["similarity"],
                            )
                            logger.debug(
                                f"Created related-to relationship: '{extracted.name}' -> '{similar[0]['name']}'"
                            )
                    else:
                        # create_concept returned None - likely IntegrityError (duplicate name)
                        # Try to find existing concept by exact name
                        existing_concept = self.db.get_concept_by_name(
                            book_id, book_type, extracted.name
                        )
                        if existing_concept:
                            stats["existing_by_name"] += 1
                            stored_concepts[extracted.name] = existing_concept["id"]
                            logger.debug(
                                f"Using existing concept (exact name match): '{extracted.name}' "
                                f"(id={existing_concept['id']})"
                            )
                        else:
                            # Concept was not created and not found - this is a data loss!
                            stats["failed_to_store"] += 1
                            logger.error(
                                f"FAILED to store concept '{extracted.name}': "
                                f"create_concept returned None and no existing concept found. "
                                f"This concept is LOST. Definition: {extracted.definition[:100]}..."
                            )

            except Exception as e:
                stats["failed_to_store"] += 1
                logger.error(
                    f"Exception while processing concept '{extracted.name}': {e}",
                    exc_info=True,
                )

        # Log summary
        logger.info(
            f"Concept storage complete for book_id={book_id}, nav_id={nav_id}: "
            f"total={stats['total']}, new_created={stats['new_created']}, "
            f"duplicates_found={stats['duplicates_found']}, "
            f"existing_by_name={stats['existing_by_name']}, "
            f"failed={stats['failed_to_store']}, "
            f"embedding_errors={stats['embedding_errors']}, "
            f"stored_count={len(stored_concepts)}"
        )

        if stats["failed_to_store"] > 0:
            logger.warning(
                f"WARNING: {stats['failed_to_store']} concepts were lost during storage!"
            )

        return stored_concepts

    def _store_relationships(
        self,
        extracted_relationships: list[ExtractedRelationship],
        stored_concepts: dict[str, int],
    ) -> list[int]:
        """
        Store extracted relationships.

        Args:
            extracted_relationships: List of relationships extracted by LLM
            stored_concepts: Dictionary mapping concept names to IDs

        Returns:
            List of stored relationship IDs
        """
        stored_relationship_ids: list[int] = []

        for rel in extracted_relationships:
            # Look up concept IDs (case-insensitive)
            source_id = None
            target_id = None

            for name, concept_id in stored_concepts.items():
                if name.lower() == rel.source.lower():
                    source_id = concept_id
                if name.lower() == rel.target.lower():
                    target_id = concept_id

            if source_id and target_id and source_id != target_id:
                relationship_id = self.db.create_relationship(
                    source_concept_id=source_id,
                    target_concept_id=target_id,
                    relationship_type=rel.type,
                    description=rel.description,
                    weight=1.0,
                )

                if relationship_id:
                    stored_relationship_ids.append(relationship_id)
                    logger.debug(
                        f"Stored relationship: '{rel.source}' --[{rel.type}]--> '{rel.target}'"
                    )
            else:
                logger.debug(
                    f"Skipping relationship: could not resolve concepts "
                    f"'{rel.source}' -> '{rel.target}'"
                )

        return stored_relationship_ids

    def add_concept_manually(
        self,
        book_id: int,
        book_type: str,
        name: str,
        definition: str | None = None,
        importance: int = 3,
        nav_id: str | None = None,
        page_num: int | None = None,
    ) -> int | None:
        """
        Add a concept manually (not from extraction).

        Args:
            book_id: ID of the book
            book_type: Type of book
            name: Concept name
            definition: Concept definition
            importance: Importance level (1-5)
            nav_id: Navigation ID
            page_num: Page number

        Returns:
            ID of the created concept, or None if failed
        """
        concept_id = self.db.create_concept(
            book_id=book_id,
            book_type=book_type,
            name=name,
            definition=definition,
            importance=importance,
            nav_id=nav_id,
            page_num=page_num,
        )

        if concept_id:
            # Store embedding
            self.embedding_service.store_concept_embedding(
                concept_id=concept_id,
                name=name,
                definition=definition,
                metadata={
                    "book_id": book_id,
                    "book_type": book_type,
                    "importance": importance,
                },
            )

        return concept_id

    def merge_concepts(self, source_id: int, target_id: int) -> bool:
        """
        Merge two concepts (source into target).

        This will:
        - Move all relationships from source to target
        - Delete the source concept

        Args:
            source_id: ID of concept to merge from (will be deleted)
            target_id: ID of concept to merge into (will be kept)

        Returns:
            True if merge successful
        """
        try:
            with self.db.get_connection() as conn:
                # Update relationships where source is the source_concept
                conn.execute(
                    """
                    UPDATE relationships
                    SET source_concept_id = ?
                    WHERE source_concept_id = ?
                    """,
                    (target_id, source_id),
                )

                # Update relationships where source is the target_concept
                conn.execute(
                    """
                    UPDATE relationships
                    SET target_concept_id = ?
                    WHERE target_concept_id = ?
                    """,
                    (target_id, source_id),
                )

                # Delete duplicate relationships (same source, target, type)
                conn.execute(
                    """
                    DELETE FROM relationships
                    WHERE id NOT IN (
                        SELECT MIN(id)
                        FROM relationships
                        GROUP BY source_concept_id, target_concept_id, relationship_type
                    )
                    """
                )

                # Delete source concept within same transaction
                # Note: CASCADE will handle flashcards, but we already moved relationships above
                conn.execute("DELETE FROM concepts WHERE id = ?", (source_id,))

                conn.commit()

            # Delete source embedding (outside transaction - ChromaDB is separate)
            self.embedding_service.delete_concept_embedding(source_id)

            logger.info(f"Merged concept {source_id} into {target_id}")
            return True

        except Exception as e:
            logger.error(f"Error merging concepts: {e}")
            return False

    def get_concepts(
        self,
        book_id: int,
        book_type: str,
        nav_id: str | None = None,
        page_num: int | None = None,
        importance_min: int | None = None,
    ) -> list[Concept]:
        """Get concepts for a book."""
        rows = self.db.get_concepts_for_book(
            book_id=book_id,
            book_type=book_type,
            nav_id=nav_id,
            page_num=page_num,
            importance_min=importance_min,
        )
        return [Concept(**row) for row in rows]

    def get_graph(self, book_id: int, book_type: str) -> dict[str, Any]:
        """Get graph data for visualization."""
        return self.db.get_graph_for_book(book_id, book_type)

    def find_similar_concepts(
        self,
        concept_id: int,
        n_results: int = 5,
        cross_book: bool = False,
    ) -> list[dict[str, Any]]:
        """Find concepts similar to a given concept."""
        concept = self.db.get_concept_by_id(concept_id)
        if not concept:
            return []

        return self.embedding_service.find_similar_to_concept(
            concept_id=concept_id,
            n_results=n_results,
            exclude_same_book=not cross_book,
            book_id=concept.get("book_id"),
        )

    async def extract_relationships_only(
        self,
        content: str,
        book_id: int,
        book_type: str,
        nav_id: str | None = None,
        page_num: int | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Extract relationships for a section that already has concepts.

        Use this to:
        - Resume failed relationship extraction
        - Re-extract relationships after manual concept edits
        - Force refresh relationships

        Args:
            content: Text content to extract from
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')
            nav_id: Navigation ID (for EPUBs)
            page_num: Page number (for PDFs)
            force: Force re-extraction even if relationships exist

        Returns:
            Dictionary with extraction results
        """
        if nav_id is None and page_num is None:
            raise ValueError("Either nav_id or page_num must be provided")

        section_id = nav_id or f"page_{page_num}"
        content_hash = self._compute_content_hash(content)

        logger.info(
            f"Starting extract_relationships_only for book_id={book_id}, "
            f"book_type={book_type}, section={section_id}, force={force}"
        )

        # Get all concepts for this section
        all_section_concepts = self.db.get_concepts_for_book(
            book_id, book_type, nav_id=nav_id, page_num=page_num
        )

        if len(all_section_concepts) < 2:
            logger.info(
                f"Fewer than 2 concepts for section {section_id}, "
                "cannot extract relationships"
            )
            return {
                "relationships_found": 0,
                "chunks_processed": 0,
                "total_chunks": 0,
                "resumed": False,
                "error": "Need at least 2 concepts to extract relationships",
            }

        # Convert DB concepts back to ExtractedConcept
        concepts_for_rel = self._convert_db_concepts_to_extracted(all_section_concepts)

        # Build stored_concepts map
        all_stored = {c["name"]: c["id"] for c in all_section_concepts}

        # Check for partial relationship chunk progress
        skip_rel_chunks: set[int] = set()
        known_rel_keys: set[str] = set()

        if force:
            self.db.clear_relationship_chunk_progress(
                book_id, book_type, nav_id, page_num
            )
            logger.info("Cleared relationship chunk progress for forced re-extraction")
        else:
            skip_rel_chunks = self.db.get_extracted_relationship_chunks(
                book_id, book_type, content_hash, nav_id, page_num
            )
            if skip_rel_chunks:
                logger.info(
                    f"RESUMING relationship extraction: found {len(skip_rel_chunks)} already-extracted chunks"
                )
                known_rel_keys = self._build_relationship_keys_from_graph(
                    book_id, book_type, all_section_concepts
                )

        # Register this extraction for progress tracking
        self.extraction_registry.register_extraction(book_id, book_type, section_id)
        self.extraction_registry.update_phase(
            book_id, book_type, section_id, ExtractionPhase.RELATIONSHIPS
        )

        # Pre-compute chunks
        rel_chunks = self.concept_extractor.chunk_content(content)
        rel_total_chunks = len(rel_chunks)

        # Initialize progress
        self.extraction_registry.update_relationship_progress(
            book_id, book_type, section_id, 0, rel_total_chunks, 0
        )

        stored_relationships: list[int] = []
        rel_chunks_processed = 0
        rel_was_cancelled = False

        try:
            async for (
                rel_chunk_idx,
                rel_total,
                chunk_relationships,
                rel_was_skipped,
            ) in self.concept_extractor.extract_relationships_incrementally(
                text=content,
                all_concepts=concepts_for_rel,
                skip_chunks=skip_rel_chunks,
                known_relationship_keys=known_rel_keys,
                pre_chunked=rel_chunks,
            ):
                rel_total_chunks = rel_total
                rel_chunks_processed = rel_chunk_idx + 1

                # Check for cancellation
                if self.extraction_registry.is_cancellation_requested(
                    book_id, book_type, section_id
                ):
                    logger.info(
                        f"Relationship extraction CANCELLED for section {section_id} "
                        f"at chunk {rel_chunks_processed}/{rel_total_chunks}"
                    )
                    rel_was_cancelled = True
                    self.extraction_registry.mark_cancelled(
                        book_id, book_type, section_id
                    )
                    break

                if rel_was_skipped:
                    self.extraction_registry.update_relationship_progress(
                        book_id,
                        book_type,
                        section_id,
                        rel_chunks_processed,
                        rel_total_chunks,
                        len(stored_relationships),
                    )
                    continue

                if chunk_relationships:
                    chunk_stored_ids = self._store_relationships(
                        extracted_relationships=chunk_relationships,
                        stored_concepts=all_stored,
                    )
                    stored_relationships.extend(chunk_stored_ids)

                self.db.mark_relationship_chunk_extracted(
                    book_id=book_id,
                    book_type=book_type,
                    chunk_index=rel_chunk_idx,
                    total_chunks=rel_total,
                    content_hash=content_hash,
                    nav_id=nav_id,
                    page_num=page_num,
                )

                self.extraction_registry.update_relationship_progress(
                    book_id,
                    book_type,
                    section_id,
                    rel_chunks_processed,
                    rel_total_chunks,
                    len(stored_relationships),
                )

            if rel_chunks_processed == rel_total_chunks and not rel_was_cancelled:
                # Clear progress on completion
                self.db.clear_relationship_chunk_progress(
                    book_id, book_type, nav_id, page_num
                )
                self.extraction_registry.mark_completed(book_id, book_type, section_id)

            logger.info(
                f"Relationship-only extraction complete for section {section_id}: "
                f"{rel_chunks_processed}/{rel_total_chunks} chunks, "
                f"{len(stored_relationships)} relationships"
            )

        except Exception as e:
            logger.error(
                f"Failed relationship-only extraction for section {section_id}: {e}",
                exc_info=True,
            )
            self.extraction_registry.mark_failed(book_id, book_type, section_id, str(e))
            return {
                "relationships_found": len(stored_relationships),
                "chunks_processed": rel_chunks_processed,
                "total_chunks": rel_total_chunks,
                "resumed": len(skip_rel_chunks) > 0,
                "cancelled": rel_was_cancelled,
                "error": str(e),
            }

        return {
            "relationships_found": len(stored_relationships),
            "chunks_processed": rel_chunks_processed,
            "total_chunks": rel_total_chunks,
            "resumed": len(skip_rel_chunks) > 0,
            "cancelled": rel_was_cancelled,
            "error": None,
        }

    def recalculate_book_importance(
        self, book_id: int, book_type: str
    ) -> dict[int, int]:
        """
        Recalculate importance for all concepts in a book based on graph structure.

        Importance is calculated based on:
        - Number of relationships (more connections = higher importance)
        - Types of relationships (being a source of 'explains' = higher importance)

        Args:
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')

        Returns:
            Dictionary mapping concept_id to new importance value
        """
        # Get all concepts for the book
        concepts = self.db.get_concepts_for_book(book_id, book_type)
        if not concepts:
            return {}

        # Get the full graph
        graph = self.db.get_graph_for_book(book_id, book_type)
        edges = graph.get("edges", [])

        # Build adjacency info for each concept
        concept_stats: dict[int, dict[str, Any]] = {}
        for concept in concepts:
            concept_id = concept["id"]
            concept_stats[concept_id] = {
                "original_importance": concept.get("importance", 3),
                "outgoing_count": 0,
                "incoming_count": 0,
                "explains_source": 0,  # Being a source of 'explains' is valuable
            }

        # Count relationships
        for edge in edges:
            source_id = edge.get("source")
            target_id = edge.get("target")
            rel_type = edge.get("type", "")

            if source_id in concept_stats:
                concept_stats[source_id]["outgoing_count"] += 1
                if rel_type == "explains":
                    concept_stats[source_id]["explains_source"] += 1

            if target_id in concept_stats:
                concept_stats[target_id]["incoming_count"] += 1

        # Calculate scores and determine new importance
        updated: dict[int, int] = {}

        for concept_id, stats in concept_stats.items():
            # Base score from relationship count
            total_connections = stats["outgoing_count"] + stats["incoming_count"]

            # Score calculation:
            # - Base: 2-3 based on connections (0-1 conn = 2, 2-4 = 3, 5+ = 4)
            # - Bonus for 'explains' relationships (+0.5 per explains source)
            # - High connectivity bonus (10+ connections = +1)

            if total_connections == 0:
                score = 2.0
            elif total_connections <= 1:
                score = 2.0
            elif total_connections <= 4:
                score = 3.0
            elif total_connections <= 9:
                score = 4.0
            else:
                score = 4.5

            # Bonus for being a source of 'explains'
            score += min(stats["explains_source"] * 0.3, 1.0)

            # Convert to 1-5 scale
            new_importance = max(1, min(5, round(score)))

            # Only update if changed
            if new_importance != stats["original_importance"]:
                self.db.update_concept(concept_id, importance=new_importance)
                updated[concept_id] = new_importance

        logger.info(
            f"Recalculated importance for book {book_id}: {len(updated)} concepts updated"
        )
        return updated


# Factory function with thread-safe singleton
_graph_builder: GraphBuilder | None = None
_singleton_lock = threading.Lock()


def get_graph_builder() -> GraphBuilder:
    """Get the global graph builder instance (thread-safe)."""
    global _graph_builder
    if _graph_builder is None:
        with _singleton_lock:
            # Double-check after acquiring lock
            if _graph_builder is None:
                _graph_builder = GraphBuilder()
    return _graph_builder

"""
Graph Builder Service Module

This module orchestrates the knowledge graph construction:
- Coordinates extraction, deduplication, and storage
- Manages concept merging for duplicates
- Tracks extraction progress
"""

import logging
from typing import Any

from app.models.knowledge_models import (
    Concept,
    ExtractedConcept,
    ExtractedRelationship,
)

from .concept_extractor import ConceptExtractor, get_concept_extractor
from .embedding_service import EmbeddingService, get_embedding_service
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
    ):
        """
        Initialize the graph builder.

        Args:
            db: Knowledge database instance
            embedding_service: Embedding service instance
            concept_extractor: Concept extractor instance
        """
        self.db = db or knowledge_db
        self.embedding_service = embedding_service or get_embedding_service()
        self.concept_extractor = concept_extractor or get_concept_extractor()

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
        Full pipeline: extract concepts/relationships and store them.

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
        # Check if already extracted
        if not force and self.db.is_section_extracted(
            book_id, book_type, nav_id, page_num
        ):
            logger.info(
                f"Section already extracted: book={book_id}, nav_id={nav_id}, page={page_num}"
            )
            return {
                "concepts_extracted": 0,
                "relationships_found": 0,
                "already_extracted": True,
            }

        # Extract concepts and relationships
        (
            extracted_concepts,
            extracted_relationships,
        ) = await self.concept_extractor.extract_from_text(
            text=content,
            book_title=book_title,
            section_title=section_title,
        )

        # Store concepts with deduplication
        stored_concepts = await self._store_concepts(
            extracted_concepts=extracted_concepts,
            book_id=book_id,
            book_type=book_type,
            nav_id=nav_id,
            page_num=page_num,
        )

        # Store relationships
        stored_relationships = self._store_relationships(
            extracted_relationships=extracted_relationships,
            stored_concepts=stored_concepts,
        )

        # Mark section as extracted
        self.db.mark_section_extracted(book_id, book_type, nav_id, page_num)

        return {
            "concepts_extracted": len(stored_concepts),
            "relationships_found": len(stored_relationships),
            "already_extracted": False,
        }

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

        for extracted in extracted_concepts:
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
                    # Store embedding
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

                    logger.debug(
                        f"Stored new concept: '{extracted.name}' (id={concept_id})"
                    )
                else:
                    # Concept might already exist with same name (exact match)
                    existing_concept = self.db.get_concept_by_name(
                        book_id, book_type, extracted.name
                    )
                    if existing_concept:
                        stored_concepts[extracted.name] = existing_concept["id"]
                        logger.debug(
                            f"Using existing concept (exact name match): '{extracted.name}'"
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


# Factory function
_graph_builder: GraphBuilder | None = None


def get_graph_builder() -> GraphBuilder:
    """Get the global graph builder instance."""
    global _graph_builder
    if _graph_builder is None:
        _graph_builder = GraphBuilder()
    return _graph_builder

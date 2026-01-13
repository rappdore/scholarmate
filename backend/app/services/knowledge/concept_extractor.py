"""
Concept Extractor Service Module

This module handles LLM-based extraction of concepts and relationships from text.
It implements a two-pass extraction approach:
- Pass 1: Extract concepts (entities) from text
- Pass 2: Extract relationships between concepts
"""

import json
import logging
import re
import threading

from openai import AsyncOpenAI

from app.models.knowledge_models import (
    ExtractedConcept,
    ExtractedRelationship,
    ExtractedTriple,
    TripleEntity,
)
from app.services.llm_config_service import LLMConfigService

logger = logging.getLogger(__name__)

# Prompt templates for extraction
CONCEPT_EXTRACTION_PROMPT = """Extract key important concepts from this text. For each concept provide:
- name: canonical form of the concept (capitalize properly)
- definition: 1-2 sentence explanation based on the text
- importance: 1-5 scale (5 = core concept central to understanding, 1 = minor mention)
- source_quote: exact phrase from the text where concept appears (keep brief, max 100 chars)

Focus on concepts that would be valuable for learning and long-term retention. Skip trivial or overly generic terms.

Text:
{chunk_text}

Context: This is from "{book_title}", section: {section_title}

Return a JSON array of concepts. Example format:
[
  {{
    "name": "Quantum Entanglement",
    "definition": "A phenomenon where particles become correlated such that the quantum state of each particle cannot be described independently.",
    "importance": 5,
    "source_quote": "particles become inextricably linked"
  }}
]

Return ONLY valid JSON, no markdown or explanation."""

RELATIONSHIP_EXTRACTION_PROMPT = """Given these concepts extracted from the text, identify relationships between them.

Concepts:
{concept_list}

Text:
{chunk_text}

For each relationship provide:
- source: source concept name (must match exactly from the list above)
- target: target concept name (must match exactly from the list above)
- type: one of [explains, contrasts, requires, builds-on, examples, causes]
- description: brief explanation of how they relate (1 sentence)

Relationship types:
- explains: source explains or clarifies target
- contrasts: source is contrasted with or opposed to target
- requires: source requires understanding of target first
- builds-on: source builds upon or extends target
- examples: source is an example or instance of target
- causes: source causes or leads to target

Return a JSON array of relationships. Example:
[
  {{
    "source": "Wave-Particle Duality",
    "target": "Uncertainty Principle",
    "type": "explains",
    "description": "Wave-particle duality provides the foundation for understanding why the uncertainty principle exists."
  }}
]

Return ONLY valid JSON, no markdown or explanation. If no clear relationships exist, return an empty array []."""

TRIPLE_EXTRACTION_PROMPT = """Extract knowledge triples from this text. Each triple represents a fact: (subject, relationship, object).

For each triple provide:
- subject: the source entity with name and 1-2 sentence definition
- predicate: relationship type (one of: explains, contrasts, requires, builds-on, examples, causes)
- object: the target entity with name and 1-2 sentence definition
- description: brief explanation of how they relate (1 sentence)

Relationship types:
- explains: subject explains or clarifies object
- contrasts: subject is contrasted with or opposed to object
- requires: subject requires understanding of object first
- builds-on: subject builds upon or extends object
- examples: subject is an example or instance of object
- causes: subject causes or leads to object

Text:
{chunk_text}

Context: This is from "{book_title}", section: {section_title}

Return a JSON array of triples. Example:
[
  {{
    "subject": {{"name": "Wave-Particle Duality", "definition": "The concept that quantum entities exhibit both wave and particle properties."}},
    "predicate": "explains",
    "object": {{"name": "Uncertainty Principle", "definition": "The principle that certain pairs of physical properties cannot both be precisely measured."}},
    "description": "Wave-particle duality provides the foundation for understanding why the uncertainty principle exists."
  }}
]

Focus on extracting meaningful educational relationships. Skip trivial or overly generic connections.
Return ONLY valid JSON, no markdown or explanation. If no clear relationships exist, return an empty array []."""


class ConceptExtractor:
    """
    Service for extracting concepts and relationships from text using LLM.

    Implements a two-pass approach:
    1. Extract concepts from text chunks
    2. Extract relationships between identified concepts
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the concept extractor.

        Args:
            db_path: Path to the database (for loading LLM config)
        """
        self.db_path = db_path
        self._client: AsyncOpenAI | None = None
        self._model: str | None = None
        self._load_llm_config()

    def _load_llm_config(self) -> None:
        """Load the active LLM configuration."""
        try:
            llm_config_service = LLMConfigService(self.db_path)
            config = llm_config_service.get_active_configuration()

            if config:
                self._client = AsyncOpenAI(
                    base_url=config.base_url,
                    api_key=config.api_key,
                )
                self._model = config.model_name
                logger.info(f"ConceptExtractor loaded LLM config: {config.name}")
            else:
                # Use defaults
                self._client = AsyncOpenAI(
                    base_url="http://localhost:1234/v1",
                    api_key="not-needed",
                )
                self._model = ""
                logger.warning("ConceptExtractor using default LLM config")
        except Exception as e:
            logger.error(f"Error loading LLM config: {e}")
            raise

    def reload_config(self) -> None:
        """Reload LLM configuration (call when config changes)."""
        self._load_llm_config()

    def chunk_content(
        self,
        content: str,
        chunk_size: int = 3000,
        overlap: int = 200,
    ) -> list[str]:
        """
        Split content into overlapping chunks for processing.

        Args:
            content: Full text content to chunk
            chunk_size: Target size of each chunk in characters
            overlap: Number of characters to overlap between chunks

        Returns:
            List of text chunks

        Raises:
            ValueError: If chunk_size <= 0 or overlap >= chunk_size
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError(
                f"overlap must satisfy 0 <= overlap < chunk_size, "
                f"got overlap={overlap}, chunk_size={chunk_size}"
            )

        if len(content) <= chunk_size:
            return [content]

        chunks = []
        start = 0

        while start < len(content):
            end = start + chunk_size

            # Try to break at a sentence boundary
            if end < len(content):
                # Look for sentence ending punctuation
                for punct in [". ", ".\n", "! ", "!\n", "? ", "?\n"]:
                    last_punct = content.rfind(punct, start + chunk_size // 2, end)
                    if last_punct != -1:
                        end = last_punct + 1
                        break

            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    async def extract_concepts(
        self,
        text: str,
        book_title: str,
        section_title: str,
    ) -> list[ExtractedConcept]:
        """
        Extract concepts from text using LLM.

        Args:
            text: Text to extract concepts from
            book_title: Title of the book
            section_title: Title of the current section

        Returns:
            List of extracted concepts
        """
        if not self._client or not self._model:
            raise RuntimeError("LLM not configured")

        prompt = CONCEPT_EXTRACTION_PROMPT.format(
            chunk_text=text,
            book_title=book_title,
            section_title=section_title,
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a knowledge extraction assistant. Extract concepts and return valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Lower temperature for more consistent extraction
            )

            # Guard against empty choices
            if not response.choices:
                logger.warning("LLM returned empty choices for concept extraction")
                return []

            content = response.choices[0].message.content
            if not content:
                logger.warning("LLM returned empty content for concept extraction")
                return []

            concepts = self._parse_concepts_json(content.strip())
            logger.info(f"Extracted {len(concepts)} concepts from text")
            return concepts

        except Exception as e:
            logger.error(f"Error extracting concepts: {e}")
            return []

    async def extract_relationships(
        self,
        text: str,
        concepts: list[ExtractedConcept],
    ) -> list[ExtractedRelationship]:
        """
        Extract relationships between concepts using LLM.

        Args:
            text: Original text
            concepts: List of concepts extracted from the text

        Returns:
            List of extracted relationships
        """
        if not self._client or not self._model:
            raise RuntimeError("LLM not configured")

        if len(concepts) < 2:
            return []  # Need at least 2 concepts for relationships

        # Format concept list for prompt
        concept_list = "\n".join(f"- {c.name}: {c.definition}" for c in concepts)

        prompt = RELATIONSHIP_EXTRACTION_PROMPT.format(
            concept_list=concept_list,
            chunk_text=text,
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a knowledge extraction assistant. Extract relationships and return valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )

            # Guard against empty choices
            if not response.choices:
                logger.warning("LLM returned empty choices for relationship extraction")
                return []

            content = response.choices[0].message.content
            if not content:
                logger.warning("LLM returned empty content for relationship extraction")
                return []

            relationships = self._parse_relationships_json(content.strip(), concepts)
            logger.info(f"Extracted {len(relationships)} relationships")
            return relationships

        except Exception as e:
            logger.error(f"Error extracting relationships: {e}")
            return []

    async def extract_concepts_incrementally(
        self,
        text: str,
        book_title: str,
        section_title: str,
        skip_chunks: set[int] | None = None,
        known_concept_names: set[str] | None = None,
        pre_chunked: list[str] | None = None,
    ):
        """
        Extract concepts from text chunk by chunk, yielding after each chunk.

        This is an async generator that allows the caller to store concepts
        incrementally as they are extracted, preventing data loss on failure.

        Args:
            text: Text to extract from (ignored if pre_chunked is provided)
            book_title: Title of the book
            section_title: Title of the section
            skip_chunks: Set of chunk indices to skip (for resuming)
            known_concept_names: Set of concept names already extracted (for dedup across resumes)
            pre_chunked: Optional pre-chunked content list to avoid redundant chunking

        Yields:
            Tuple of (chunk_index, total_chunks, concepts, was_skipped) after each chunk
        """
        # Use pre-chunked content if provided, otherwise chunk the text
        chunks = pre_chunked if pre_chunked is not None else self.chunk_content(text)
        total_chunks = len(chunks)
        skip_chunks = skip_chunks or set()

        skipping_count = len(skip_chunks & set(range(total_chunks)))
        logger.info(
            f"Starting incremental extraction: {total_chunks} chunks, "
            f"skipping {skipping_count} already-extracted chunks"
        )

        # Initialize with known concept names to avoid re-extracting duplicates
        concept_names_seen: set[str] = set(known_concept_names or set())

        # Extract concepts from each chunk and yield immediately
        for i, chunk in enumerate(chunks):
            if i in skip_chunks:
                logger.info(
                    f"Chunk {i + 1}/{total_chunks}: SKIPPED (already extracted)"
                )
                yield (i, total_chunks, [], True)
                continue

            logger.info(f"Extracting concepts from chunk {i + 1}/{total_chunks}")
            try:
                concepts = await self.extract_concepts(chunk, book_title, section_title)

                # Deduplicate by name within this extraction
                unique_concepts: list[ExtractedConcept] = []
                for concept in concepts:
                    name_lower = concept.name.lower()
                    if name_lower not in concept_names_seen:
                        concept_names_seen.add(name_lower)
                        unique_concepts.append(concept)

                logger.info(
                    f"Chunk {i + 1}/{total_chunks}: extracted {len(concepts)} concepts, "
                    f"{len(unique_concepts)} unique (after dedup)"
                )
                yield (i, total_chunks, unique_concepts, False)

            except Exception as e:
                logger.error(f"Error extracting from chunk {i + 1}/{total_chunks}: {e}")
                # Yield empty list for this chunk but continue with others
                yield (i, total_chunks, [], False)

    async def extract_relationships_for_concepts(
        self,
        text: str,
        all_concepts: list[ExtractedConcept],
    ) -> list[ExtractedRelationship]:
        """
        Extract relationships between concepts from text.

        This should be called after all concepts have been extracted and stored.

        Args:
            text: Original text to extract relationships from
            all_concepts: All concepts that have been extracted

        Returns:
            List of extracted relationships
        """
        if len(all_concepts) < 2:
            logger.info("Fewer than 2 concepts, skipping relationship extraction")
            return []

        chunks = self.chunk_content(text)
        total_chunks = len(chunks)
        logger.info(f"Extracting relationships from {total_chunks} chunks")

        all_relationships: list[ExtractedRelationship] = []
        relationship_keys_seen: set[str] = set()

        for i, chunk in enumerate(chunks):
            logger.info(f"Extracting relationships from chunk {i + 1}/{total_chunks}")
            try:
                relationships = await self.extract_relationships(chunk, all_concepts)

                # Deduplicate relationships
                for rel in relationships:
                    key = f"{rel.source}|{rel.target}|{rel.type}"
                    if key not in relationship_keys_seen:
                        relationship_keys_seen.add(key)
                        all_relationships.append(rel)

            except Exception as e:
                logger.error(
                    f"Error extracting relationships from chunk {i + 1}/{total_chunks}: {e}"
                )
                # Continue with other chunks

        logger.info(
            f"Relationship extraction complete: {len(all_relationships)} relationships"
        )
        return all_relationships

    async def extract_relationships_incrementally(
        self,
        text: str,
        all_concepts: list[ExtractedConcept],
        skip_chunks: set[int] | None = None,
        known_relationship_keys: set[str] | None = None,
        pre_chunked: list[str] | None = None,
    ):
        """
        Extract relationships chunk by chunk, yielding after each chunk.

        This is an async generator that allows the caller to store relationships
        incrementally as they are extracted, enabling progress tracking and resumability.

        Args:
            text: Text to extract from (ignored if pre_chunked is provided)
            all_concepts: All concepts to find relationships between
            skip_chunks: Set of chunk indices to skip (for resuming)
            known_relationship_keys: Set of relationship keys already extracted (for dedup)
            pre_chunked: Optional pre-chunked content list to avoid redundant chunking

        Yields:
            Tuple of (chunk_index, total_chunks, relationships, was_skipped) after each chunk
        """
        if len(all_concepts) < 2:
            logger.info("Fewer than 2 concepts, skipping relationship extraction")
            return

        # Use pre-chunked content if provided, otherwise chunk the text
        chunks = pre_chunked if pre_chunked is not None else self.chunk_content(text)
        total_chunks = len(chunks)
        skip_chunks = skip_chunks or set()

        skipping_count = len(skip_chunks & set(range(total_chunks)))
        logger.info(
            f"Starting incremental relationship extraction: {total_chunks} chunks, "
            f"skipping {skipping_count} already-extracted chunks"
        )

        # Initialize with known relationship keys to avoid duplicates
        relationship_keys_seen: set[str] = set(known_relationship_keys or set())

        for i, chunk in enumerate(chunks):
            if i in skip_chunks:
                logger.info(
                    f"Relationship chunk {i + 1}/{total_chunks}: SKIPPED (already extracted)"
                )
                yield (i, total_chunks, [], True)
                continue

            logger.info(f"Extracting relationships from chunk {i + 1}/{total_chunks}")
            try:
                relationships = await self.extract_relationships(chunk, all_concepts)

                # Deduplicate relationships
                unique_relationships: list[ExtractedRelationship] = []
                for rel in relationships:
                    key = f"{rel.source}|{rel.target}|{rel.type}"
                    if key not in relationship_keys_seen:
                        relationship_keys_seen.add(key)
                        unique_relationships.append(rel)

                logger.info(
                    f"Relationship chunk {i + 1}/{total_chunks}: extracted {len(relationships)} relationships, "
                    f"{len(unique_relationships)} unique (after dedup)"
                )
                yield (i, total_chunks, unique_relationships, False)

            except Exception as e:
                logger.error(
                    f"Error extracting relationships from chunk {i + 1}/{total_chunks}: {e}"
                )
                # Yield empty list for this chunk but continue with others
                yield (i, total_chunks, [], False)

    async def extract_triples(
        self,
        text: str,
        book_title: str,
        section_title: str,
    ) -> list[ExtractedTriple]:
        """
        Extract knowledge triples from text using LLM (single-pass extraction).

        This is more efficient than separate concept + relationship extraction
        because it makes ONE LLM call instead of TWO.

        Args:
            text: Text to extract triples from
            book_title: Title of the book
            section_title: Title of the current section

        Returns:
            List of extracted triples (subject, predicate, object)
        """
        if not self._client or not self._model:
            raise RuntimeError("LLM not configured")

        prompt = TRIPLE_EXTRACTION_PROMPT.format(
            chunk_text=text,
            book_title=book_title,
            section_title=section_title,
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a knowledge extraction assistant. Extract knowledge triples and return valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )

            if not response.choices:
                logger.warning("LLM returned empty choices for triple extraction")
                return []

            content = response.choices[0].message.content
            if not content:
                logger.warning("LLM returned empty content for triple extraction")
                return []

            triples = self._parse_triples_json(content.strip())
            logger.info(f"Extracted {len(triples)} triples from text")
            return triples

        except Exception as e:
            logger.error(f"Error extracting triples: {e}")
            return []

    def triples_to_concepts(
        self,
        triples: list[ExtractedTriple],
    ) -> list[ExtractedConcept]:
        """
        Convert triples to a deduplicated list of concepts.

        Extracts all unique entities (subjects and objects) from triples.
        Deduplication is case-insensitive.

        Args:
            triples: List of extracted triples

        Returns:
            List of unique ExtractedConcept objects
        """
        seen_names: set[str] = set()
        concepts: list[ExtractedConcept] = []

        for triple in triples:
            # Process subject
            subj_key = triple.subject.name.lower()
            if subj_key not in seen_names:
                seen_names.add(subj_key)
                concepts.append(
                    ExtractedConcept(
                        name=triple.subject.name,
                        definition=triple.subject.definition or "",
                        importance=triple.subject.importance,
                        source_quote=triple.subject.source_quote or "",
                    )
                )

            # Process object
            obj_key = triple.object.name.lower()
            if obj_key not in seen_names:
                seen_names.add(obj_key)
                concepts.append(
                    ExtractedConcept(
                        name=triple.object.name,
                        definition=triple.object.definition or "",
                        importance=triple.object.importance,
                        source_quote=triple.object.source_quote or "",
                    )
                )

        return concepts

    def triples_to_relationships(
        self,
        triples: list[ExtractedTriple],
    ) -> list[ExtractedRelationship]:
        """
        Convert triples to a list of relationships.

        Args:
            triples: List of extracted triples

        Returns:
            List of ExtractedRelationship objects
        """
        relationships: list[ExtractedRelationship] = []

        for triple in triples:
            relationships.append(
                ExtractedRelationship(
                    source=triple.subject.name,
                    target=triple.object.name,
                    type=triple.predicate,
                    description=triple.description or "",
                )
            )

        return relationships

    def _parse_triples_json(self, content: str) -> list[ExtractedTriple]:
        """Parse LLM response into ExtractedTriple objects."""
        try:
            json_str = self._extract_json_array(content)
            data = json.loads(json_str)

            if not isinstance(data, list):
                logger.warning("Expected JSON array for triples, got something else")
                return []

            triples = []
            valid_types = [
                "explains",
                "contrasts",
                "requires",
                "builds-on",
                "examples",
                "causes",
            ]

            for item in data:
                try:
                    # Parse subject
                    subj_data = item.get("subject", {})
                    subject = TripleEntity(
                        name=subj_data.get("name", "").strip(),
                        definition=subj_data.get("definition", ""),
                        importance=min(5, max(1, int(subj_data.get("importance", 3)))),
                        source_quote=subj_data.get("source_quote", ""),
                    )

                    # Parse object
                    obj_data = item.get("object", {})
                    obj = TripleEntity(
                        name=obj_data.get("name", "").strip(),
                        definition=obj_data.get("definition", ""),
                        importance=min(5, max(1, int(obj_data.get("importance", 3)))),
                        source_quote=obj_data.get("source_quote", ""),
                    )

                    # Skip if either entity has empty name
                    if not subject.name or not obj.name:
                        logger.debug("Skipping triple with empty entity name")
                        continue

                    # Normalize predicate
                    predicate = (
                        item.get("predicate", "").strip().lower().replace("_", "-")
                    )
                    if predicate not in valid_types:
                        logger.debug(
                            f"Unknown predicate '{predicate}', using 'related-to'"
                        )
                        predicate = "related-to"

                    triple = ExtractedTriple(
                        subject=subject,
                        predicate=predicate,
                        object=obj,
                        description=item.get("description", "")[:500],
                    )
                    triples.append(triple)

                except Exception as e:
                    logger.warning(f"Failed to parse triple: {e}")
                    continue

            return triples

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse triples JSON: {e}")
            logger.debug(f"Raw content: {content[:500]}")
            return []

    async def extract_from_text(
        self,
        text: str,
        book_title: str,
        section_title: str,
    ) -> tuple[list[ExtractedConcept], list[ExtractedRelationship]]:
        """
        Full extraction pipeline for a piece of text.

        Note: This method extracts all concepts and relationships in one go.
        For incremental extraction with progress saving, use
        extract_concepts_incrementally() followed by extract_relationships_for_concepts().

        Args:
            text: Text to extract from
            book_title: Title of the book
            section_title: Title of the section

        Returns:
            Tuple of (concepts, relationships)
        """
        # Chunk the content if needed
        chunks = self.chunk_content(text)
        logger.info(f"Processing {len(chunks)} chunks for extraction")

        all_concepts: list[ExtractedConcept] = []
        concept_names_seen: set[str] = set()

        # Pass 1: Extract concepts from each chunk
        for i, chunk in enumerate(chunks):
            logger.debug(f"Extracting concepts from chunk {i + 1}/{len(chunks)}")
            concepts = await self.extract_concepts(chunk, book_title, section_title)

            # Deduplicate by name within this extraction
            for concept in concepts:
                name_lower = concept.name.lower()
                if name_lower not in concept_names_seen:
                    concept_names_seen.add(name_lower)
                    all_concepts.append(concept)

        # Pass 2: Extract relationships (using all concepts for context)
        all_relationships = await self.extract_relationships_for_concepts(
            text, all_concepts
        )

        logger.info(
            f"Extraction complete: {len(all_concepts)} concepts, {len(all_relationships)} relationships"
        )
        return all_concepts, all_relationships

    def _parse_concepts_json(self, content: str) -> list[ExtractedConcept]:
        """Parse LLM response into concept objects."""
        try:
            # Try to extract JSON from the response
            json_str = self._extract_json_array(content)
            data = json.loads(json_str)

            if not isinstance(data, list):
                logger.warning("Expected JSON array, got something else")
                return []

            concepts = []
            for item in data:
                try:
                    concept = ExtractedConcept(
                        name=item.get("name", "").strip(),
                        definition=item.get("definition", "").strip(),
                        importance=min(5, max(1, int(item.get("importance", 3)))),
                        source_quote=item.get("source_quote", "")[:200],
                    )
                    if concept.name:  # Skip empty names
                        concepts.append(concept)
                except Exception as e:
                    logger.warning(f"Failed to parse concept: {e}")
                    continue

            return concepts
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse concepts JSON: {e}")
            logger.debug(f"Raw content: {content[:500]}")
            return []

    def _parse_relationships_json(
        self,
        content: str,
        concepts: list[ExtractedConcept],
    ) -> list[ExtractedRelationship]:
        """Parse LLM response into relationship objects."""
        try:
            json_str = self._extract_json_array(content)
            data = json.loads(json_str)

            if not isinstance(data, list):
                return []

            # Build set of valid concept names for validation
            valid_names = {c.name.lower() for c in concepts}

            relationships = []
            for item in data:
                try:
                    source = item.get("source", "").strip()
                    target = item.get("target", "").strip()
                    rel_type = item.get("type", "").strip()

                    # Validate concept names exist
                    if source.lower() not in valid_names:
                        logger.debug(
                            f"Skipping relationship: unknown source '{source}'"
                        )
                        continue
                    if target.lower() not in valid_names:
                        logger.debug(
                            f"Skipping relationship: unknown target '{target}'"
                        )
                        continue

                    # Normalize and validate relationship type
                    # Handle common LLM variations: "Explains" -> "explains",
                    # "builds_on" -> "builds-on"
                    rel_type = rel_type.lower().replace("_", "-")
                    valid_types = [
                        "explains",
                        "contrasts",
                        "requires",
                        "builds-on",
                        "examples",
                        "causes",
                    ]
                    if rel_type not in valid_types:
                        logger.debug(
                            f"Unknown relationship type '{rel_type}', "
                            "falling back to 'related-to'"
                        )
                        rel_type = "related-to"

                    relationship = ExtractedRelationship(
                        source=source,
                        target=target,
                        type=rel_type,
                        description=item.get("description", "")[:500],
                    )
                    relationships.append(relationship)
                except Exception as e:
                    logger.warning(f"Failed to parse relationship: {e}")
                    continue

            return relationships
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse relationships JSON: {e}")
            return []

    def _extract_json_array(self, content: str) -> str:
        """Extract JSON array from LLM response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        content = re.sub(r"```json\s*", "", content)
        content = re.sub(r"```\s*", "", content)
        content = content.strip()

        # Try to find JSON array in the content
        start = content.find("[")
        end = content.rfind("]")

        if start != -1 and end != -1 and end > start:
            return content[start : end + 1]

        return content


# Factory function with thread-safe singleton
_concept_extractor: ConceptExtractor | None = None
_singleton_lock = threading.Lock()


def get_concept_extractor() -> ConceptExtractor:
    """Get the global concept extractor instance (thread-safe)."""
    global _concept_extractor
    if _concept_extractor is None:
        with _singleton_lock:
            # Double-check after acquiring lock
            if _concept_extractor is None:
                _concept_extractor = ConceptExtractor()
    return _concept_extractor

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

from app.models.knowledge_models import ExtractedConcept, ExtractedRelationship
from app.services.llm_config_service import LLMConfigService

logger = logging.getLogger(__name__)

# Prompt templates for extraction
CONCEPT_EXTRACTION_PROMPT = """Extract key concepts from this text. For each concept provide:
- name: canonical form of the concept (capitalize properly)
- definition: 1-2 sentence explanation based on the text
- importance: 1-5 scale (5 = core concept central to understanding, 1 = minor mention)
- source_quote: exact phrase from the text where concept appears (keep brief, max 100 chars)

Focus on concepts that would be valuable for learning and retention. Skip trivial or overly generic terms.

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

    async def extract_from_text(
        self,
        text: str,
        book_title: str,
        section_title: str,
    ) -> tuple[list[ExtractedConcept], list[ExtractedRelationship]]:
        """
        Full extraction pipeline for a piece of text.

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
        all_relationships: list[ExtractedRelationship] = []
        relationship_keys_seen: set[str] = set()

        for i, chunk in enumerate(chunks):
            logger.debug(f"Extracting relationships from chunk {i + 1}/{len(chunks)}")
            relationships = await self.extract_relationships(chunk, all_concepts)

            # Deduplicate relationships
            for rel in relationships:
                key = f"{rel.source}|{rel.target}|{rel.type}"
                if key not in relationship_keys_seen:
                    relationship_keys_seen.add(key)
                    all_relationships.append(rel)

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

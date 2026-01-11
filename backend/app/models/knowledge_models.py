"""
Knowledge Graph Type Models

Pydantic models for concepts, relationships, flashcards, and extraction operations.
"""

from typing import Literal

from pydantic import BaseModel, Field

# ========================================
# CONCEPT MODELS
# ========================================


class ConceptBase(BaseModel):
    """Base fields for a concept"""

    name: str = Field(..., min_length=1, max_length=500)
    definition: str | None = None
    source_quote: str | None = None
    importance: int = Field(default=3, ge=1, le=5)


class ConceptCreate(ConceptBase):
    """Request model for creating a concept"""

    book_id: int
    book_type: Literal["epub", "pdf"]
    nav_id: str | None = None
    page_num: int | None = None


class Concept(ConceptBase):
    """Full concept model with all fields"""

    id: int
    book_id: int
    book_type: Literal["epub", "pdf"]
    nav_id: str | None = None
    page_num: int | None = None
    created_at: str | None = None


class ConceptUpdate(BaseModel):
    """Request model for updating a concept"""

    definition: str | None = None
    source_quote: str | None = None
    importance: int | None = Field(default=None, ge=1, le=5)


# ========================================
# RELATIONSHIP MODELS
# ========================================


RELATIONSHIP_TYPES = Literal[
    "explains",
    "contrasts",
    "requires",
    "builds-on",
    "examples",
    "causes",
    "related-to",
]


class RelationshipBase(BaseModel):
    """Base fields for a relationship"""

    relationship_type: RELATIONSHIP_TYPES
    description: str | None = None
    weight: float = Field(default=1.0, ge=0.0, le=10.0)


class RelationshipCreate(RelationshipBase):
    """Request model for creating a relationship"""

    source_concept_id: int
    target_concept_id: int


class Relationship(RelationshipBase):
    """Full relationship model with all fields"""

    id: int
    source_concept_id: int
    target_concept_id: int
    created_at: str | None = None

    # Joined fields (optional, populated when fetching with concept info)
    source_name: str | None = None
    source_definition: str | None = None
    target_name: str | None = None
    target_definition: str | None = None


class RelationshipUpdate(BaseModel):
    """Request model for updating a relationship"""

    relationship_type: RELATIONSHIP_TYPES | None = None
    description: str | None = None
    weight: float | None = Field(default=None, ge=0.0, le=10.0)


# ========================================
# FLASHCARD MODELS
# ========================================


CARD_TYPES = Literal["qa", "cloze", "connection"]


class FlashcardBase(BaseModel):
    """Base fields for a flashcard"""

    card_type: CARD_TYPES
    front: str
    back: str
    source_text: str | None = None


class FlashcardCreate(FlashcardBase):
    """Request model for creating a flashcard"""

    concept_id: int | None = None
    relationship_id: int | None = None


class Flashcard(FlashcardBase):
    """Full flashcard model with spaced repetition fields"""

    id: int
    concept_id: int | None = None
    relationship_id: int | None = None
    next_review: str | None = None
    interval_days: int = 1
    ease_factor: float = 2.5
    review_count: int = 0
    created_at: str | None = None

    # Joined fields (optional)
    book_id: int | None = None
    concept_name: str | None = None


class FlashcardReview(BaseModel):
    """Request model for submitting a flashcard review"""

    quality: int = Field(..., ge=0, le=5)


class FlashcardReviewResult(BaseModel):
    """Response model after reviewing a flashcard"""

    next_review: str
    interval_days: int
    ease_factor: float
    review_count: int


# ========================================
# EXTRACTION MODELS
# ========================================


class ExtractionRequest(BaseModel):
    """Request model for triggering concept extraction"""

    book_id: int
    book_type: Literal["epub", "pdf"]
    nav_id: str | None = None
    page_num: int | None = None


class ExtractionResponse(BaseModel):
    """Response model after extraction completes"""

    concepts_extracted: int
    relationships_found: int
    section_id: str
    already_extracted: bool = False


class BookExtractionRequest(BaseModel):
    """Request model for batch extraction of an entire book"""

    book_id: int
    book_type: Literal["epub", "pdf"]
    force: bool = False
    # Optional: specify subset of sections
    nav_ids: list[str] | None = None  # For EPUBs
    page_start: int | None = None  # For PDFs
    page_end: int | None = None  # For PDFs


class BookExtractionResponse(BaseModel):
    """Response model after batch extraction completes"""

    total_sections: int
    sections_extracted: int
    sections_skipped: int  # Already extracted
    concepts_extracted: int
    relationships_found: int
    errors: list[str] = Field(default_factory=list)


class ExtractionProgress(BaseModel):
    """Model for extraction progress tracking"""

    id: int
    book_id: int
    book_type: Literal["epub", "pdf"]
    nav_id: str | None = None
    page_num: int | None = None
    extracted_at: str


# ========================================
# GRAPH MODELS
# ========================================


class GraphNode(BaseModel):
    """Node in the knowledge graph for visualization"""

    id: int
    name: str
    definition: str | None = None
    importance: int
    nav_id: str | None = None
    page_num: int | None = None


class GraphEdge(BaseModel):
    """Edge in the knowledge graph for visualization"""

    id: int
    source: int  # source_concept_id
    target: int  # target_concept_id
    type: str  # relationship_type
    description: str | None = None
    weight: float


class GraphData(BaseModel):
    """Full graph data for visualization"""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ========================================
# STATS MODELS
# ========================================


class KnowledgeStats(BaseModel):
    """Statistics about the knowledge database"""

    total_concepts: int = 0
    total_relationships: int = 0
    total_flashcards: int = 0
    sections_extracted: int = 0


# ========================================
# LLM EXTRACTION RESPONSE MODELS
# ========================================


class ExtractedConcept(BaseModel):
    """Concept extracted from text by LLM"""

    name: str
    definition: str
    importance: int = Field(default=3, ge=1, le=5)
    source_quote: str


class ExtractedRelationship(BaseModel):
    """Relationship extracted from text by LLM"""

    source: str  # source concept name
    target: str  # target concept name
    type: RELATIONSHIP_TYPES
    description: str

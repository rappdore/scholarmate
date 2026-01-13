"""
Knowledge Graph API Router

Endpoints for concept extraction, knowledge graph queries, and graph management.
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.models.knowledge_models import (
    BookExtractionRequest,
    BookExtractionResponse,
    Concept,
    ConceptCreate,
    ConceptsResponse,
    ConceptUpdate,
    ExtractionRequest,
    ExtractionResponse,
    GraphData,
    KnowledgeStats,
    Relationship,
    RelationshipCreate,
    RelationshipExtractionRequest,
    RelationshipExtractionResponse,
    RelationshipUpdate,
)
from app.services.epub_documents_service import EPUBDocumentsService
from app.services.epub_service import EPUBService
from app.services.knowledge.extraction_state import get_extraction_registry
from app.services.knowledge.graph_builder import get_graph_builder
from app.services.knowledge.knowledge_database import knowledge_db
from app.services.pdf_documents_service import PDFDocumentsService
from app.services.pdf_service import PDFService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

# Initialize services
epub_documents_service = EPUBDocumentsService()
pdf_documents_service = PDFDocumentsService()
epub_service = EPUBService()
pdf_service = PDFService()


def _get_book_info(book_id: int, book_type: str) -> tuple[str, str]:
    """
    Get book title and verify book exists.

    Returns:
        Tuple of (filename, title)

    Raises:
        HTTPException if book not found
    """
    if book_type == "epub":
        epub_doc = epub_documents_service.get_by_id(book_id)
        if not epub_doc:
            raise HTTPException(
                status_code=404, detail=f"EPUB with id {book_id} not found"
            )
        return epub_doc.get("filename", ""), epub_doc.get(
            "title", epub_doc.get("filename", "")
        )
    else:
        pdf_doc = pdf_documents_service.get_by_id(book_id)
        if not pdf_doc:
            raise HTTPException(
                status_code=404, detail=f"PDF with id {book_id} not found"
            )
        return pdf_doc.filename, pdf_doc.title or pdf_doc.filename


def _get_section_content(
    book_id: int,
    book_type: str,
    nav_id: str | None,
    page_num: int | None,
) -> tuple[str, str]:
    """
    Get content and title for a book section.

    Returns:
        Tuple of (content, section_title)
    """
    if book_type == "epub":
        if not nav_id:
            raise HTTPException(
                status_code=400,
                detail="nav_id is required for EPUB extraction",
            )

        doc = epub_documents_service.get_by_id(book_id)
        if not doc:
            raise HTTPException(status_code=404, detail="EPUB not found")

        filename = doc.get("filename", "")
        content = epub_service.extract_section_text(filename, nav_id)
        if not content:
            raise HTTPException(
                status_code=404,
                detail=f"Section {nav_id} not found or has no content",
            )

        # Get section title from navigation tree
        nav_info = epub_service.get_navigation_tree(filename)
        section_title = nav_id
        for item in nav_info.get("flat_navigation", []):
            if item.get("id") == nav_id:
                section_title = item.get("title", nav_id)
                break

        return content, section_title
    else:
        if page_num is None:
            raise HTTPException(
                status_code=400,
                detail="page_num is required for PDF extraction",
            )

        pdf_doc = pdf_documents_service.get_by_id(book_id)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        content = pdf_service.extract_page_text(pdf_doc.filename, page_num)
        if not content:
            raise HTTPException(
                status_code=404,
                detail=f"Page {page_num} not found or has no content",
            )

        return content, f"Page {page_num}"


@router.post("/extract", response_model=ExtractionResponse)
async def extract_concepts(request: ExtractionRequest) -> ExtractionResponse:
    """
    Trigger concept extraction for a book section.

    For EPUBs, provide book_id, book_type='epub', and nav_id.
    For PDFs, provide book_id, book_type='pdf', and page_num.

    Returns:
        ExtractionResponse with counts of extracted concepts and relationships.
    """
    try:
        # Get book info
        filename, book_title = _get_book_info(request.book_id, request.book_type)

        # Get section content
        content, section_title = _get_section_content(
            book_id=request.book_id,
            book_type=request.book_type,
            nav_id=request.nav_id,
            page_num=request.page_num,
        )

        # Run extraction (using auto method which selects efficient triple-based extraction)
        graph_builder = get_graph_builder()
        result = await graph_builder.extract_and_store_auto(
            content=content,
            book_id=request.book_id,
            book_type=request.book_type,
            book_title=book_title,
            section_title=section_title,
            nav_id=request.nav_id,
            page_num=request.page_num,
        )

        section_id = request.nav_id or f"page_{request.page_num}"
        return ExtractionResponse(
            concepts_extracted=result["concepts_extracted"],
            relationships_found=result["relationships_found"],
            section_id=section_id,
            already_extracted=result.get("already_extracted", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/extract-relationships", response_model=RelationshipExtractionResponse)
async def extract_relationships_only(
    request: RelationshipExtractionRequest,
) -> RelationshipExtractionResponse:
    """
    Extract relationships for a section that already has concepts.

    Use this to:
    - Resume failed relationship extraction
    - Re-extract relationships after manual concept edits
    - Force refresh relationships

    The section must already have concepts extracted. If there are fewer than
    2 concepts, an error will be returned.
    """
    try:
        # Get book info
        filename, book_title = _get_book_info(request.book_id, request.book_type)

        # Get section content
        content, section_title = _get_section_content(
            book_id=request.book_id,
            book_type=request.book_type,
            nav_id=request.nav_id,
            page_num=request.page_num,
        )

        # Run relationship extraction
        graph_builder = get_graph_builder()
        result = await graph_builder.extract_relationships_only(
            content=content,
            book_id=request.book_id,
            book_type=request.book_type,
            nav_id=request.nav_id,
            page_num=request.page_num,
            force=request.force,
        )

        return RelationshipExtractionResponse(
            relationships_found=result["relationships_found"],
            chunks_processed=result["chunks_processed"],
            total_chunks=result["total_chunks"],
            resumed=result["resumed"],
            cancelled=result.get("cancelled", False),
            error=result.get("error"),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Relationship extraction failed: {str(e)}"
        )


@router.post("/cancel-extraction")
async def cancel_extraction(
    book_id: int = Query(..., description="Book ID"),
    book_type: Literal["epub", "pdf"] = Query(..., description="Type of book"),
    section_id: str | None = Query(
        None,
        description="Section ID (nav_id for EPUB, page_X for PDF). If not provided, cancels all for book.",
    ),
) -> dict:
    """
    Cancel a running extraction.

    If section_id is provided, cancels just that section's extraction.
    If section_id is not provided, cancels all running extractions for the book.

    Note: Cancellation is cooperative - the extraction will stop between chunks.
    """
    registry = get_extraction_registry()

    if section_id:
        # Cancel specific section
        success = registry.request_cancellation(book_id, book_type, section_id)
        if success:
            logger.info(
                f"Cancellation requested for {book_type}:{book_id}:{section_id}"
            )
            return {
                "success": True,
                "message": f"Cancellation requested for section {section_id}",
                "book_id": book_id,
                "section_id": section_id,
            }
        else:
            # Check if there's a completed or no extraction
            state = registry.get_extraction_state(book_id, book_type, section_id)
            if state:
                return {
                    "success": False,
                    "message": f"Extraction is not running (status: {state.status.name})",
                    "book_id": book_id,
                    "section_id": section_id,
                }
            else:
                return {
                    "success": False,
                    "message": "No extraction found for this section",
                    "book_id": book_id,
                    "section_id": section_id,
                }
    else:
        # Cancel all for book
        count = registry.cancel_all_for_book(book_id, book_type)
        if count > 0:
            logger.info(
                f"Cancellation requested for {count} extractions for {book_type}:{book_id}"
            )
            return {
                "success": True,
                "message": f"Cancellation requested for {count} running extractions",
                "book_id": book_id,
                "extractions_cancelled": count,
            }
        else:
            return {
                "success": False,
                "message": "No running extractions found for this book",
                "book_id": book_id,
            }


@router.get("/extraction-status")
async def get_extraction_status(
    book_id: int | None = Query(None, description="Filter by book ID"),
    book_type: Literal["epub", "pdf"] | None = Query(
        None, description="Filter by book type"
    ),
    section_id: str | None = Query(None, description="Get status of specific section"),
) -> dict:
    """
    Get the status of running extractions.

    If section_id is provided along with book_id and book_type, returns status of that specific extraction.
    Otherwise, returns all running extractions (optionally filtered by book_id and/or book_type).
    """
    registry = get_extraction_registry()

    if section_id and book_id is not None and book_type is not None:
        # Get specific extraction status
        state = registry.get_extraction_state(book_id, book_type, section_id)
        if state:
            return {
                "found": True,
                "extraction": state.to_dict(),
            }
        else:
            return {
                "found": False,
                "message": "No extraction found for this section",
            }
    else:
        # Get all running extractions
        extractions = registry.get_running_extractions(book_id, book_type)
        return {
            "count": len(extractions),
            "extractions": [e.to_dict() for e in extractions],
        }


@router.get("/concepts/{book_id}", response_model=ConceptsResponse)
async def get_concepts(
    book_id: int,
    book_type: Literal["epub", "pdf"] = Query(..., description="Type of book"),
    nav_id: str | None = Query(None, description="Filter by navigation section (EPUB)"),
    page_num: int | None = Query(None, description="Filter by page number (PDF)"),
    importance_min: int | None = Query(
        None, ge=1, le=5, description="Minimum importance"
    ),
) -> ConceptsResponse:
    """
    Get concepts for a book, optionally filtered by section and importance.

    Returns concepts along with the count of relationships between them.
    """
    try:
        # Verify book exists
        _get_book_info(book_id, book_type)

        graph_builder = get_graph_builder()
        concepts = graph_builder.get_concepts(
            book_id=book_id,
            book_type=book_type,
            nav_id=nav_id,
            page_num=page_num,
            importance_min=importance_min,
        )

        # Get relationship count for the section
        relationship_count = knowledge_db.count_relationships_for_section(
            book_id=book_id,
            book_type=book_type,
            nav_id=nav_id,
            page_num=page_num,
        )

        return ConceptsResponse(
            concepts=concepts,
            relationship_count=relationship_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get concepts: {str(e)}")


@router.get("/graph/{book_id}", response_model=GraphData)
async def get_graph(
    book_id: int,
    book_type: Literal["epub", "pdf"] = Query(..., description="Type of book"),
) -> GraphData:
    """
    Get full graph data for a book (nodes and edges for visualization).
    """
    try:
        _get_book_info(book_id, book_type)

        graph_builder = get_graph_builder()
        graph_data = graph_builder.get_graph(book_id, book_type)

        return GraphData(
            nodes=[
                {
                    "id": n["id"],
                    "name": n["name"],
                    "definition": n.get("definition"),
                    "importance": n.get("importance", 3),
                    "nav_id": n.get("nav_id"),
                    "page_num": n.get("page_num"),
                }
                for n in graph_data["nodes"]
            ],
            edges=[
                {
                    "id": e["id"],
                    "source": e["source"],
                    "target": e["target"],
                    "type": e["type"],
                    "description": e.get("description"),
                    "weight": e.get("weight", 1.0),
                }
                for e in graph_data["edges"]
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get graph: {str(e)}")


@router.get("/concept/{concept_id}", response_model=Concept)
async def get_concept(concept_id: int) -> Concept:
    """Get a specific concept by ID."""
    concept = knowledge_db.get_concept_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    return Concept(**concept)


@router.post("/concept", response_model=Concept)
async def create_concept(concept_data: ConceptCreate) -> Concept:
    """
    Create a concept manually (not via extraction).
    """
    try:
        _get_book_info(concept_data.book_id, concept_data.book_type)

        graph_builder = get_graph_builder()
        concept_id = graph_builder.add_concept_manually(
            book_id=concept_data.book_id,
            book_type=concept_data.book_type,
            name=concept_data.name,
            definition=concept_data.definition,
            importance=concept_data.importance,
            nav_id=concept_data.nav_id,
            page_num=concept_data.page_num,
        )

        if not concept_id:
            raise HTTPException(
                status_code=400,
                detail="Concept may already exist with this name",
            )

        concept = knowledge_db.get_concept_by_id(concept_id)
        return Concept(**concept)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create concept: {str(e)}"
        )


@router.patch("/concept/{concept_id}", response_model=Concept)
async def update_concept(concept_id: int, update_data: ConceptUpdate) -> Concept:
    """Update a concept's definition, source_quote, or importance."""
    concept = knowledge_db.get_concept_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    success = knowledge_db.update_concept(
        concept_id=concept_id,
        definition=update_data.definition,
        source_quote=update_data.source_quote,
        importance=update_data.importance,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update concept")

    updated = knowledge_db.get_concept_by_id(concept_id)
    return Concept(**updated)


@router.delete("/concept/{concept_id}")
async def delete_concept(concept_id: int) -> dict:
    """Delete a concept and its relationships."""
    concept = knowledge_db.get_concept_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    # Also delete embedding
    from app.services.knowledge.embedding_service import get_embedding_service

    get_embedding_service().delete_concept_embedding(concept_id)

    success = knowledge_db.delete_concept(concept_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete concept")

    return {"success": True, "deleted_id": concept_id}


@router.post("/concept/{source_id}/merge/{target_id}")
async def merge_concepts(source_id: int, target_id: int) -> dict:
    """
    Merge source concept into target concept.

    All relationships from source will be moved to target,
    then source will be deleted.
    """
    source = knowledge_db.get_concept_by_id(source_id)
    target = knowledge_db.get_concept_by_id(target_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source concept not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target concept not found")

    graph_builder = get_graph_builder()
    success = graph_builder.merge_concepts(source_id, target_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to merge concepts")

    return {"success": True, "merged_into": target_id}


@router.get("/similar/{concept_id}")
async def find_similar_concepts(
    concept_id: int,
    n_results: int = Query(5, ge=1, le=20),
    cross_book: bool = Query(False, description="Search across all books"),
) -> list[dict]:
    """Find concepts similar to a given concept."""
    concept = knowledge_db.get_concept_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    graph_builder = get_graph_builder()
    similar = graph_builder.find_similar_concepts(
        concept_id=concept_id,
        n_results=n_results,
        cross_book=cross_book,
    )

    return similar


@router.get("/stats", response_model=KnowledgeStats)
async def get_stats() -> KnowledgeStats:
    """Get statistics about the knowledge database."""
    stats = knowledge_db.get_stats()
    return KnowledgeStats(**stats)


@router.get("/extraction-progress/{book_id}")
async def get_extraction_progress(
    book_id: int,
    book_type: Literal["epub", "pdf"] = Query(...),
) -> list[dict]:
    """Get extraction progress for a book (which sections have been extracted)."""
    _get_book_info(book_id, book_type)
    return knowledge_db.get_extraction_progress(book_id, book_type)


@router.delete("/book/{book_id}")
async def delete_book_knowledge(
    book_id: int,
    book_type: Literal["epub", "pdf"] = Query(...),
) -> dict:
    """Delete all knowledge data for a book."""
    _get_book_info(book_id, book_type)

    # Delete embeddings first
    from app.services.knowledge.embedding_service import get_embedding_service

    deleted_embeddings = get_embedding_service().delete_book_embeddings(
        book_id, book_type
    )

    # Delete from database
    success = knowledge_db.delete_book_knowledge(book_id, book_type)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete book knowledge")

    return {
        "success": True,
        "book_id": book_id,
        "embeddings_deleted": deleted_embeddings,
    }


# ========================================
# BATCH EXTRACTION
# ========================================


@router.post("/extract-book", response_model=BookExtractionResponse)
async def extract_book_concepts(
    request: BookExtractionRequest,
) -> BookExtractionResponse:
    """
    Trigger concept extraction for all sections of a book.

    For EPUBs, extracts from all chapters in the navigation tree.
    For PDFs, extracts from all pages (or specified page range).

    This is a long-running operation. Use the extraction-progress endpoint
    to check which sections have been extracted.
    """
    try:
        # Get book info
        filename, book_title = _get_book_info(request.book_id, request.book_type)
        graph_builder = get_graph_builder()

        total_sections = 0
        sections_extracted = 0
        sections_skipped = 0
        concepts_extracted = 0
        relationships_found = 0
        errors: list[str] = []

        if request.book_type == "epub":
            # Get all sections from navigation tree
            nav_info = epub_service.get_navigation_tree(filename)
            flat_nav = nav_info.get("flat_navigation", [])

            # Filter by nav_ids if specified
            if request.nav_ids:
                flat_nav = [n for n in flat_nav if n.get("id") in request.nav_ids]

            total_sections = len(flat_nav)

            for nav_item in flat_nav:
                nav_id = nav_item.get("id")
                section_title = nav_item.get("title", nav_id)

                try:
                    # Get section content
                    content = epub_service.extract_section_text(filename, nav_id)
                    if not content or not content.strip():
                        logger.debug(f"Skipping empty section: {nav_id}")
                        sections_skipped += 1
                        continue

                    # Run extraction (using auto method which selects efficient triple-based extraction)
                    result = await graph_builder.extract_and_store_auto(
                        content=content,
                        book_id=request.book_id,
                        book_type=request.book_type,
                        book_title=book_title,
                        section_title=section_title,
                        nav_id=nav_id,
                        force=request.force,
                    )

                    if result.get("already_extracted"):
                        sections_skipped += 1
                    else:
                        sections_extracted += 1
                        concepts_extracted += result.get("concepts_extracted", 0)
                        relationships_found += result.get("relationships_found", 0)

                except Exception as e:
                    error_msg = f"Section {nav_id}: {str(e)}"
                    logger.error(f"Error extracting section: {error_msg}")
                    errors.append(error_msg)

        else:  # PDF
            doc = pdf_documents_service.get_by_id(request.book_id)
            if not doc:
                raise HTTPException(status_code=404, detail="PDF not found")

            # Get page count
            page_count = pdf_service.get_page_count(doc.filename)

            # Determine page range
            start_page = request.page_start or 1
            end_page = request.page_end or page_count
            end_page = min(end_page, page_count)

            total_sections = end_page - start_page + 1

            for page_num in range(start_page, end_page + 1):
                try:
                    content = pdf_service.extract_page_text(doc.filename, page_num)
                    if not content or not content.strip():
                        logger.debug(f"Skipping empty page: {page_num}")
                        sections_skipped += 1
                        continue

                    result = await graph_builder.extract_and_store_auto(
                        content=content,
                        book_id=request.book_id,
                        book_type=request.book_type,
                        book_title=book_title,
                        section_title=f"Page {page_num}",
                        page_num=page_num,
                        force=request.force,
                    )

                    if result.get("already_extracted"):
                        sections_skipped += 1
                    else:
                        sections_extracted += 1
                        concepts_extracted += result.get("concepts_extracted", 0)
                        relationships_found += result.get("relationships_found", 0)

                except Exception as e:
                    error_msg = f"Page {page_num}: {str(e)}"
                    logger.error(f"Error extracting page: {error_msg}")
                    errors.append(error_msg)

        return BookExtractionResponse(
            total_sections=total_sections,
            sections_extracted=sections_extracted,
            sections_skipped=sections_skipped,
            concepts_extracted=concepts_extracted,
            relationships_found=relationships_found,
            errors=errors,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Batch extraction failed: {str(e)}"
        )


# ========================================
# TEXT SEARCH
# ========================================


@router.get("/search")
async def search_concepts(
    q: str = Query(..., min_length=1, description="Search query"),
    book_id: int | None = Query(None, description="Filter by book ID"),
    book_type: Literal["epub", "pdf"] | None = Query(
        None, description="Filter by book type"
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
) -> list[Concept]:
    """
    Search concepts by keyword.

    Searches both concept names and definitions.
    Results are ordered by relevance (exact name match > partial name > definition).
    """
    try:
        results = knowledge_db.search_concepts(
            query=q,
            book_id=book_id,
            book_type=book_type,
            limit=limit,
        )
        return [Concept(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ========================================
# RELATIONSHIP CRUD
# ========================================


@router.post("/relationship", response_model=Relationship)
async def create_relationship(request: RelationshipCreate) -> Relationship:
    """Create a new relationship between concepts."""
    # Verify both concepts exist
    source = knowledge_db.get_concept_by_id(request.source_concept_id)
    target = knowledge_db.get_concept_by_id(request.target_concept_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source concept not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target concept not found")

    if request.source_concept_id == request.target_concept_id:
        raise HTTPException(
            status_code=400, detail="Cannot create relationship to self"
        )

    relationship_id = knowledge_db.create_relationship(
        source_concept_id=request.source_concept_id,
        target_concept_id=request.target_concept_id,
        relationship_type=request.relationship_type,
        description=request.description,
        weight=request.weight,
    )

    if not relationship_id:
        raise HTTPException(status_code=500, detail="Failed to create relationship")

    relationship = knowledge_db.get_relationship_by_id(relationship_id)
    if not relationship:
        raise HTTPException(
            status_code=500, detail="Relationship created but could not be retrieved"
        )
    return Relationship(**relationship)


@router.get("/relationship/{relationship_id}", response_model=Relationship)
async def get_relationship(relationship_id: int) -> Relationship:
    """Get a specific relationship by ID."""
    relationship = knowledge_db.get_relationship_by_id(relationship_id)
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return Relationship(**relationship)


@router.patch("/relationship/{relationship_id}", response_model=Relationship)
async def update_relationship(
    relationship_id: int, request: RelationshipUpdate
) -> Relationship:
    """Update a relationship's type, description, or weight."""
    relationship = knowledge_db.get_relationship_by_id(relationship_id)
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    success = knowledge_db.update_relationship(
        relationship_id=relationship_id,
        relationship_type=request.relationship_type,
        description=request.description,
        weight=request.weight,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update relationship")

    updated = knowledge_db.get_relationship_by_id(relationship_id)
    if not updated:
        raise HTTPException(
            status_code=500, detail="Relationship updated but could not be retrieved"
        )
    return Relationship(**updated)


@router.delete("/relationship/{relationship_id}")
async def delete_relationship(relationship_id: int) -> dict:
    """Delete a relationship."""
    relationship = knowledge_db.get_relationship_by_id(relationship_id)
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    success = knowledge_db.delete_relationship(relationship_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete relationship")

    return {"success": True, "deleted_id": relationship_id}


@router.get("/relationships/{concept_id}", response_model=list[Relationship])
async def get_concept_relationships(concept_id: int) -> list[Relationship]:
    """Get all relationships for a concept (as source or target)."""
    concept = knowledge_db.get_concept_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    relationships = knowledge_db.get_relationships_for_concept(concept_id)
    return [Relationship(**r) for r in relationships]


# ========================================
# IMPORTANCE MANAGEMENT
# ========================================


@router.post("/recalculate-importance/{book_id}")
async def recalculate_importance(
    book_id: int,
    book_type: Literal["epub", "pdf"] = Query(..., description="Type of book"),
) -> dict:
    """
    Recalculate importance for all concepts in a book based on graph structure.

    Importance is calculated based on:
    - Number of relationships (more connections = higher importance)
    - Types of relationships (being a source of 'explains' = higher importance)
    - Connection to other high-importance concepts
    """
    _get_book_info(book_id, book_type)

    graph_builder = get_graph_builder()
    updated = graph_builder.recalculate_book_importance(book_id, book_type)

    return {
        "success": True,
        "book_id": book_id,
        "concepts_updated": len(updated),
        "new_importance_values": updated,
    }

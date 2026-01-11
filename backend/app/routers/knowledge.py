"""
Knowledge Graph API Router

Endpoints for concept extraction, knowledge graph queries, and graph management.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.models.knowledge_models import (
    Concept,
    ConceptCreate,
    ConceptUpdate,
    ExtractionRequest,
    ExtractionResponse,
    GraphData,
    KnowledgeStats,
)
from app.services.epub_documents_service import EPUBDocumentsService
from app.services.knowledge.graph_builder import get_graph_builder
from app.services.knowledge.knowledge_database import knowledge_db
from app.services.pdf_documents_service import PDFDocumentsService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

# Initialize services
epub_documents_service = EPUBDocumentsService()
pdf_documents_service = PDFDocumentsService()


def _get_book_info(book_id: int, book_type: str) -> tuple[str, str]:
    """
    Get book title and verify book exists.

    Returns:
        Tuple of (filename, title)

    Raises:
        HTTPException if book not found
    """
    if book_type == "epub":
        doc = epub_documents_service.get_by_id(book_id)
        if not doc:
            raise HTTPException(
                status_code=404, detail=f"EPUB with id {book_id} not found"
            )
        return doc.get("filename", ""), doc.get("title", doc.get("filename", ""))
    else:
        doc = pdf_documents_service.get_by_id(book_id)
        if not doc:
            raise HTTPException(
                status_code=404, detail=f"PDF with id {book_id} not found"
            )
        return doc.filename, doc.title or doc.filename


async def _get_section_content(
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
        # Import here to avoid circular imports
        from app.services.epub_service import epub_service

        doc = epub_documents_service.get_by_id(book_id)
        if not doc:
            raise HTTPException(status_code=404, detail="EPUB not found")

        filename = doc.get("filename", "")
        content = epub_service.get_section_text(filename, nav_id)
        if not content:
            raise HTTPException(
                status_code=404,
                detail=f"Section {nav_id} not found or has no content",
            )

        # Get section title
        nav_info = epub_service.get_navigation(filename)
        section_title = nav_id
        for item in nav_info.get("items", []):
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
        from app.services.pdf_service import pdf_service

        doc = pdf_documents_service.get_by_id(book_id)
        if not doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        filename = doc.filename
        content = pdf_service.extract_page_text(filename, page_num)
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
        content, section_title = await _get_section_content(
            book_id=request.book_id,
            book_type=request.book_type,
            nav_id=request.nav_id,
            page_num=request.page_num,
        )

        # Run extraction
        graph_builder = get_graph_builder()
        result = await graph_builder.extract_and_store(
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


@router.get("/concepts/{book_id}", response_model=list[Concept])
async def get_concepts(
    book_id: int,
    book_type: Literal["epub", "pdf"] = Query(..., description="Type of book"),
    nav_id: str | None = Query(None, description="Filter by navigation section (EPUB)"),
    page_num: int | None = Query(None, description="Filter by page number (PDF)"),
    importance_min: int | None = Query(
        None, ge=1, le=5, description="Minimum importance"
    ),
) -> list[Concept]:
    """
    Get concepts for a book, optionally filtered by section and importance.
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
        return concepts

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

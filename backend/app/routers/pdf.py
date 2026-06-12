import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..models.documents import (
    BookStatus,
    DocumentProgress,
    DocumentType,
    PdfPosition,
)
from ..models.pdf_responses import (
    AllReadingProgressResponse,
    BookDeletionResponse,
    CacheRefreshResponse,
    DeletionResults,
    HighlightsInfo,
    NotesInfo,
    PageTextResponse,
    PDFDetailResponse,
    PDFListItemEnriched,
    ProgressSaveResponse,
    ReadingProgress,
    ReadingProgressWithId,
    StatusCountsResponse,
    StatusUpdateResponse,
)
from ..services.database_service import DatabaseService
from ..services.documents_repository import DocumentsRepository
from ..services.highlights_service import HighlightsService
from ..services.notes_service import NotesService
from ..services.pdf_service import PDFService
from ..services.progress_service import ProgressService
from ..services.registry import (
    get_db_service,
    get_documents_repository,
    get_highlights_service,
    get_notes_service,
    get_pdf_service,
    get_progress_service,
    get_sessions_service,
)
from ..services.sessions_service import SessionsService

router = APIRouter(prefix="/pdf", tags=["pdf"])

logger = logging.getLogger(__name__)


class ReadingProgressRequest(BaseModel):
    last_page: int
    total_pages: int


class BookStatusRequest(BaseModel):
    status: str
    manually_set: bool = True


def _to_reading_progress(progress: DocumentProgress) -> ReadingProgress:
    """Map a unified DocumentProgress to the PDF wire model."""
    assert isinstance(progress.position, PdfPosition)
    return ReadingProgress(
        pdf_filename=progress.filename,
        last_page=progress.position.last_page,
        total_pages=progress.position.total_pages,
        last_updated=progress.last_updated or "",
        status=progress.status,
        status_updated_at=progress.status_updated_at,
        manually_set=progress.manually_set,
    )


@router.get("/{pdf_id:int}/info", response_model=PDFDetailResponse)
def get_pdf_info_by_id(
    pdf_id: int,
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
    pdf_service: PDFService = Depends(get_pdf_service),
) -> PDFDetailResponse:
    """
    Get detailed information about a specific PDF by ID
    """
    try:
        # Lookup filename from ID
        pdf_doc = documents_repository.get_by_id(pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        # Get PDF info using filename (returns PDFExtendedMetadata)
        info = pdf_service.get_pdf_info(pdf_doc.filename)
        # Create response model with ID fields
        return PDFDetailResponse(**info.model_dump(), id=pdf_id, pdf_id=pdf_id)
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting PDF info: {str(e)}")


@router.get("/{pdf_id:int}/text/{page_num}", response_model=PageTextResponse)
def get_page_text_by_id(
    pdf_id: int,
    page_num: int,
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
    pdf_service: PDFService = Depends(get_pdf_service),
) -> PageTextResponse:
    """
    Extract text from a specific page of the PDF by ID
    """
    try:
        # Lookup filename from ID
        pdf_doc = documents_repository.get_by_id(pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        text = pdf_service.extract_page_text(pdf_doc.filename, page_num)
        return PageTextResponse(
            pdf_id=pdf_id,
            filename=pdf_doc.filename,
            page_number=page_num,
            text=text,
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting text: {str(e)}")


@router.put("/{pdf_id:int}/progress", response_model=ProgressSaveResponse)
def save_reading_progress_by_id(
    pdf_id: int,
    progress: ReadingProgressRequest,
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
    progress_service: ProgressService = Depends(get_progress_service),
) -> ProgressSaveResponse:
    """
    Save reading progress for a PDF by ID
    """
    try:
        pdf_doc = documents_repository.get_by_id(pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        success = progress_service.save_pdf_progress(
            document_id=pdf_id,
            last_page=progress.last_page,
            total_pages=progress.total_pages,
        )

        if success:
            return ProgressSaveResponse(
                success=True,
                message=f"Reading progress saved for PDF ID {pdf_id}",
                pdf_id=pdf_id,
                last_page=progress.last_page,
            )
        else:
            raise HTTPException(
                status_code=500, detail="Failed to save reading progress"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error saving reading progress: {str(e)}"
        )


@router.get("/{pdf_id:int}/progress", response_model=ReadingProgressWithId)
def get_reading_progress_by_id(
    pdf_id: int,
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
    progress_service: ProgressService = Depends(get_progress_service),
) -> ReadingProgressWithId:
    """
    Get reading progress for a PDF by ID
    """
    try:
        # Lookup filename from ID
        pdf_doc = documents_repository.get_by_id(pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        progress = progress_service.get_progress(pdf_id)

        if progress:
            # Add ID to response
            return ReadingProgressWithId(
                **_to_reading_progress(progress).model_dump(), pdf_id=pdf_id
            )
        else:
            # Return default progress if none found
            return ReadingProgressWithId(
                pdf_filename=pdf_doc.filename,
                last_page=1,
                total_pages=None,
                last_updated=datetime.now().isoformat(),
                status=BookStatus.NEW,
                status_updated_at=None,
                manually_set=False,
                pdf_id=pdf_id,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting reading progress: {str(e)}"
        )


@router.get("/{pdf_id:int}/thumbnail")
def get_pdf_thumbnail_by_id(
    pdf_id: int,
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
    pdf_service: PDFService = Depends(get_pdf_service),
):
    """
    Get a thumbnail image of the first page of the PDF by ID
    """
    try:
        # Lookup filename from ID
        pdf_doc = documents_repository.get_by_id(pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        thumbnail_path = pdf_service.get_thumbnail_path(pdf_doc.filename)

        if not thumbnail_path.exists():
            raise HTTPException(status_code=404, detail="Thumbnail not found")

        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/png",
            filename=f"{pdf_doc.filename}_thumb.png",
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating thumbnail: {str(e)}"
        )


@router.put("/{pdf_id:int}/status", response_model=StatusUpdateResponse)
def update_book_status_by_id(
    pdf_id: int,
    status_request: BookStatusRequest,
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
    progress_service: ProgressService = Depends(get_progress_service),
) -> StatusUpdateResponse:
    """
    Update the reading status of a book by ID
    """
    try:
        # Lookup filename from ID
        pdf_doc = documents_repository.get_by_id(pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        # Validate status (mirrors the EPUB status endpoint)
        valid_statuses = [status.value for status in BookStatus]
        if status_request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}",
            )

        success = progress_service.update_status(
            document_id=pdf_id,
            status=BookStatus(status_request.status),
            manual=status_request.manually_set,
        )

        if success:
            return StatusUpdateResponse(
                success=True,
                message=f"Status updated for PDF ID {pdf_id}",
                pdf_id=pdf_id,
                filename=pdf_doc.filename,
                status=BookStatus(status_request.status),
                manually_set=status_request.manually_set,
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to update book status")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating book status: {str(e)}"
        )


@router.delete("/{pdf_id:int}", response_model=BookDeletionResponse)
def delete_book_by_id(
    pdf_id: int,
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
    pdf_service: PDFService = Depends(get_pdf_service),
    db_service: DatabaseService = Depends(get_db_service),
    sessions_service: SessionsService = Depends(get_sessions_service),
) -> BookDeletionResponse:
    """
    Delete a book by ID and all its associated data (file, thumbnails, progress, notes, highlights)
    """
    try:
        # Lookup filename from ID
        pdf_doc = documents_repository.get_by_id(pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        filename = pdf_doc.filename

        # Delete the PDF file
        pdf_file_deleted = False
        try:
            pdf_file_path = pdf_service.get_pdf_path(filename)
            if pdf_file_path.exists():
                pdf_file_path.unlink()
                pdf_file_deleted = True
        except Exception:
            logger.warning("Could not delete PDF file %s", filename, exc_info=True)

        # Delete thumbnail
        thumbnail_deleted = False
        try:
            thumbnail_path = pdf_service.get_thumbnail_path(filename)
            if thumbnail_path.exists():
                thumbnail_path.unlink()
                thumbnail_deleted = True
        except Exception:
            logger.warning("Could not delete thumbnail for %s", filename, exc_info=True)

        # Delete all database data
        db_results = db_service.delete_all_book_data(filename, pdf_id)

        # Delete reading sessions tied to this PDF
        try:
            sessions_service.delete_sessions_for_document(pdf_id)
        except Exception:
            logger.warning(
                "Could not delete reading sessions for PDF ID %s", pdf_id, exc_info=True
            )

        # Remove the registry row so the ID can no longer resolve
        try:
            documents_repository.delete_by_filename(filename)
        except Exception:
            logger.warning(
                "Could not delete registry row for %s", filename, exc_info=True
            )

        # Evict from the shared in-memory cache so listings update immediately
        pdf_service.cache.remove(filename)

        # Create deletion results
        deletion_details = DeletionResults(
            pdf_file=pdf_file_deleted,
            thumbnail=thumbnail_deleted,
            **db_results.model_dump(),
        )

        # Check if any critical operations failed
        critical_failures = []
        if not deletion_details.pdf_file:
            critical_failures.append("PDF file")

        message = f"Book with PDF ID {pdf_id} deleted successfully"
        if critical_failures:
            message += f" (warnings: {', '.join(critical_failures)} not found)"

        return BookDeletionResponse(
            success=True,
            message=message,
            pdf_id=pdf_id,
            filename=filename,
            deletion_details=deletion_details,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting book: {str(e)}")


# ========================================
# SHARED/UTILITY ENDPOINTS
# ========================================


@router.get("/list", response_model=list[PDFListItemEnriched])
def list_pdfs(
    status: Optional[str] = Query(
        None, description="Filter by book status (new, reading, finished)"
    ),
    pdf_service: PDFService = Depends(get_pdf_service),
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
    progress_service: ProgressService = Depends(get_progress_service),
    notes_service: NotesService = Depends(get_notes_service),
    highlights_service: HighlightsService = Depends(get_highlights_service),
) -> list[PDFListItemEnriched]:
    """
    List all PDFs in the pdfs directory with metadata, reading progress, and notes info.
    Optionally filter by book status.
    """
    try:
        pdfs = pdf_service.list_pdfs()

        # Get reading progress with status information
        if status:
            # Filter by status (an unknown status matches nothing)
            if status in BookStatus:
                books_by_status = progress_service.get_books_by_status(
                    BookStatus(status), DocumentType.PDF
                )
                status_filenames = {book.filename for book in books_by_status}
            else:
                status_filenames = set()
            # Filter PDFs to only include those with the matching status
            pdfs = [pdf for pdf in pdfs if pdf.filename in status_filenames]

        all_progress = {
            p.filename: _to_reading_progress(p)
            for p in progress_service.get_all_progress(DocumentType.PDF)
        }
        all_notes = notes_service.get_notes_summary(DocumentType.PDF)
        all_highlights = highlights_service.get_pdf_highlights_summary()

        # Build enriched list
        enriched_pdfs: list[PDFListItemEnriched] = []

        for pdf in pdfs:
            # Get PDF ID from database
            pdf_doc = documents_repository.get_by_filename(pdf.filename)
            if not pdf_doc:
                continue  # Skip PDFs not in database

            # Get reading progress
            progress = all_progress.get(pdf.filename)

            # Get notes info and convert to NotesInfo if exists
            notes_data = all_notes.get(pdf.filename)
            notes_info = NotesInfo(**notes_data.model_dump()) if notes_data else None

            # Get highlights info and convert to HighlightsInfo if exists
            highlights_data = all_highlights.get(pdf.filename)
            highlights_info = (
                HighlightsInfo(**highlights_data.model_dump())
                if highlights_data
                else None
            )

            # Create enriched item
            enriched_item = PDFListItemEnriched(
                # Copy basic metadata
                filename=pdf.filename,
                type=pdf.type,
                title=pdf.title,
                author=pdf.author,
                num_pages=pdf.num_pages,
                file_size=pdf.file_size,
                modified_date=pdf.modified_date,
                created_date=pdf.created_date,
                thumbnail_path=pdf.thumbnail_path,
                error=pdf.error,
                # Add IDs
                id=pdf_doc.id,
                pdf_id=pdf_doc.id,
                # Add enrichments
                reading_progress=progress,
                notes_info=notes_info,
                highlights_info=highlights_info,
            )

            enriched_pdfs.append(enriched_item)

        return enriched_pdfs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing PDFs: {str(e)}")


@router.get("/{pdf_id:int}/file")
def get_pdf_file(
    pdf_id: int,
    documents_repository: DocumentsRepository = Depends(get_documents_repository),
    pdf_service: PDFService = Depends(get_pdf_service),
):
    """
    Serve the actual PDF file for viewing.

    ID-based so the filename used for file access always comes from the
    documents registry, never from request input.
    """
    try:
        pdf_doc = documents_repository.get_by_id(pdf_id, DocumentType.PDF)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        file_path = pdf_service.get_pdf_path(pdf_doc.filename)

        return FileResponse(
            path=str(file_path),
            media_type="application/pdf",
            filename=pdf_doc.filename,
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving PDF: {str(e)}")


@router.get("/progress/all", response_model=AllReadingProgressResponse)
def get_all_reading_progress(
    progress_service: ProgressService = Depends(get_progress_service),
) -> AllReadingProgressResponse:
    """
    Get reading progress for all PDFs
    """
    try:
        progress = {
            p.filename: _to_reading_progress(p)
            for p in progress_service.get_all_progress(DocumentType.PDF)
        }
        return AllReadingProgressResponse(progress=progress)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting reading progress: {str(e)}"
        )


@router.get("/status/counts", response_model=StatusCountsResponse)
def get_status_counts(
    progress_service: ProgressService = Depends(get_progress_service),
) -> StatusCountsResponse:
    """
    Get count of books for each status
    """
    try:
        counts = progress_service.get_status_counts(DocumentType.PDF)
        return StatusCountsResponse(**counts)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting status counts: {str(e)}"
        )


@router.post("/refresh-cache", response_model=CacheRefreshResponse)
def refresh_pdf_cache(
    pdf_service: PDFService = Depends(get_pdf_service),
) -> CacheRefreshResponse:
    """
    Refresh the PDF cache by rebuilding from filesystem.
    This will rescan all PDFs and regenerate thumbnails.
    """
    try:
        cache_info = pdf_service.refresh_cache()

        try:
            return CacheRefreshResponse(
                success=True,
                **cache_info,
                message=f"Cache refreshed successfully. {cache_info['pdf_count']} PDFs cached.",
            )
        except Exception as validation_error:
            logger.error(
                f"Failed to validate cache refresh response: {validation_error}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Invalid cache info format: {str(validation_error)}",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing cache: {str(e)}")

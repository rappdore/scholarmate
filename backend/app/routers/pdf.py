from datetime import datetime
from typing import Optional, cast

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..models.pdf_responses import (
    AllReadingProgressResponse,
    BookDeletionResponse,
    BookStatus,
    CacheRefreshResponse,
    DeletionResults,
    HighlightsInfo,
    NotesInfo,
    PageTextResponse,
    PDFDetailResponse,
    PDFListItemEnriched,
    ProgressSaveResponse,
    ReadingProgressWithId,
    StatusCountsResponse,
    StatusUpdateResponse,
)
from ..services.database_service import db_service
from ..services.pdf_documents_service import PDFDocumentsService
from ..services.pdf_service import PDFService

router = APIRouter(prefix="/pdf", tags=["pdf"])

# Initialize services
pdf_service = PDFService()
pdf_documents_service = PDFDocumentsService()


class ReadingProgressRequest(BaseModel):
    last_page: int
    total_pages: int


class BookStatusRequest(BaseModel):
    status: str
    manually_set: bool = True


@router.get("/{pdf_id:int}/info", response_model=PDFDetailResponse)
async def get_pdf_info_by_id(pdf_id: int) -> PDFDetailResponse:
    """
    Get detailed information about a specific PDF by ID
    """
    try:
        # Lookup filename from ID
        pdf_doc = pdf_documents_service.get_by_id(pdf_id)
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
async def get_page_text_by_id(pdf_id: int, page_num: int) -> PageTextResponse:
    """
    Extract text from a specific page of the PDF by ID
    """
    try:
        # Lookup filename from ID
        pdf_doc = pdf_documents_service.get_by_id(pdf_id)
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
async def save_reading_progress_by_id(
    pdf_id: int, progress: ReadingProgressRequest
) -> ProgressSaveResponse:
    """
    Save reading progress for a PDF by ID
    """
    try:
        # Lookup filename from ID
        pdf_doc = pdf_documents_service.get_by_id(pdf_id)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        success = db_service.save_reading_progress(
            pdf_filename=pdf_doc.filename,
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
async def get_reading_progress_by_id(pdf_id: int) -> ReadingProgressWithId:
    """
    Get reading progress for a PDF by ID
    """
    try:
        # Lookup filename from ID
        pdf_doc = pdf_documents_service.get_by_id(pdf_id)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        progress = db_service.get_reading_progress(pdf_doc.filename)

        if progress:
            # Add ID to response
            return ReadingProgressWithId(**progress.model_dump(), pdf_id=pdf_id)
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
async def get_pdf_thumbnail_by_id(pdf_id: int):
    """
    Get a thumbnail image of the first page of the PDF by ID
    """
    try:
        # Lookup filename from ID
        pdf_doc = pdf_documents_service.get_by_id(pdf_id)
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
async def update_book_status_by_id(
    pdf_id: int, status_request: BookStatusRequest
) -> StatusUpdateResponse:
    """
    Update the reading status of a book by ID
    """
    try:
        # Lookup filename from ID
        pdf_doc = pdf_documents_service.get_by_id(pdf_id)
        if not pdf_doc:
            raise HTTPException(status_code=404, detail="PDF not found")

        success = db_service.update_book_status(
            pdf_filename=pdf_doc.filename,
            status=status_request.status,
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
async def delete_book_by_id(pdf_id: int) -> BookDeletionResponse:
    """
    Delete a book by ID and all its associated data (file, thumbnails, progress, notes, highlights)
    """
    try:
        # Lookup filename from ID
        pdf_doc = pdf_documents_service.get_by_id(pdf_id)
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
        except Exception as e:
            print(f"Warning: Could not delete PDF file {filename}: {e}")

        # Delete thumbnail
        thumbnail_deleted = False
        try:
            thumbnail_path = pdf_service.get_thumbnail_path(filename)
            if thumbnail_path.exists():
                thumbnail_path.unlink()
                thumbnail_deleted = True
        except Exception as e:
            print(f"Warning: Could not delete thumbnail for {filename}: {e}")

        # Delete all database data
        db_results = db_service.delete_all_book_data(filename)

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
async def list_pdfs(
    status: Optional[str] = Query(
        None, description="Filter by book status (new, reading, finished)"
    ),
) -> list[PDFListItemEnriched]:
    """
    List all PDFs in the pdfs directory with metadata, reading progress, and notes info.
    Optionally filter by book status.
    """
    try:
        pdfs = pdf_service.list_pdfs()

        # Get reading progress with status information
        if status:
            # Filter by status using the database service
            books_by_status = db_service.get_books_by_status(status)
            # Create a set of filenames that match the status
            status_filenames = {book.pdf_filename for book in books_by_status}
            # Filter PDFs to only include those with the matching status
            pdfs = [pdf for pdf in pdfs if pdf.filename in status_filenames]

        all_progress = db_service.get_all_reading_progress()
        all_notes = db_service.get_notes_count_by_pdf()
        all_highlights = db_service.get_highlights_count_by_pdf()

        # Build enriched list
        enriched_pdfs: list[PDFListItemEnriched] = []

        for pdf in pdfs:
            # Get PDF ID from database
            pdf_doc = pdf_documents_service.get_by_filename(pdf.filename)
            if not pdf_doc:
                continue  # Skip PDFs not in database

            # Get reading progress
            progress = all_progress.get(pdf.filename)

            # Get notes info and convert to NotesInfo if exists
            notes_data = all_notes.get(pdf.filename)
            notes_info = NotesInfo(**notes_data) if notes_data else None

            # Get highlights info and convert to HighlightsInfo if exists
            highlights_data = all_highlights.get(pdf.filename)
            highlights_info = (
                HighlightsInfo(**highlights_data) if highlights_data else None
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


@router.get("/{filename}/file")
async def get_pdf_file(filename: str):
    """
    Serve the actual PDF file for viewing
    """
    try:
        file_path = pdf_service.get_pdf_path(filename)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found")

        return FileResponse(
            path=str(file_path), media_type="application/pdf", filename=filename
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving PDF: {str(e)}")


@router.get("/progress/all", response_model=AllReadingProgressResponse)
async def get_all_reading_progress() -> AllReadingProgressResponse:
    """
    Get reading progress for all PDFs
    """
    try:
        progress = db_service.get_all_reading_progress()
        return AllReadingProgressResponse(progress=progress)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting reading progress: {str(e)}"
        )


@router.get("/status/counts", response_model=StatusCountsResponse)
async def get_status_counts() -> StatusCountsResponse:
    """
    Get count of books for each status
    """
    try:
        counts = db_service.get_status_counts()
        return StatusCountsResponse(**counts)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting status counts: {str(e)}"
        )


@router.post("/refresh-cache", response_model=CacheRefreshResponse)
async def refresh_pdf_cache() -> CacheRefreshResponse:
    """
    Refresh the PDF cache by rebuilding from filesystem.
    This will rescan all PDFs and regenerate thumbnails.
    """
    try:
        cache_info = pdf_service.refresh_cache()

        return CacheRefreshResponse(
            success=True,
            cache_built_at=cast(str, cache_info["cache_built_at"]),
            pdf_count=cast(int, cache_info["pdf_count"]),
            message=f"Cache refreshed successfully. {cache_info['pdf_count']} PDFs cached.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing cache: {str(e)}")

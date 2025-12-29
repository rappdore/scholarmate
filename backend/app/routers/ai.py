import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.dual_chat_service import dual_chat_service
from ..services.epub_documents_service import EPUBDocumentsService
from ..services.epub_service import EPUBService
from ..services.ollama_service import ollama_service
from ..services.pdf_documents_service import PDFDocumentsService
from ..services.pdf_service import PDFService
from ..services.request_tracking_service import request_tracking_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])

# Initialize services
pdf_service = PDFService()
epub_service = EPUBService()
pdf_documents_service = PDFDocumentsService()
epub_documents_service = EPUBDocumentsService()


class AnalyzePageRequest(BaseModel):
    pdf_id: int | None = None  # NEW: ID-based reference
    filename: str | None = None  # Legacy: filename-based reference
    page_num: int
    context: str | None = ""


class AnalyzeEpubSectionRequest(BaseModel):
    epub_id: int | None = None  # NEW: ID-based reference
    filename: str | None = None  # Legacy: filename-based reference
    nav_id: str
    context: str | None = ""


class ChatRequest(BaseModel):
    message: str
    pdf_id: int | None = None  # NEW: ID-based reference
    filename: str | None = None  # Legacy: filename-based reference
    page_num: int
    chat_history: list[dict[str, str]] | None = None
    request_id: str | None = None
    is_new_chat: bool | None = False


class EpubChatRequest(BaseModel):
    message: str
    epub_id: int | None = None  # NEW: ID-based reference
    filename: str | None = None  # Legacy: filename-based reference
    nav_id: str
    chat_history: list[dict[str, str]] | None = None
    request_id: str | None = None
    is_new_chat: bool | None = False


class DualChatRequest(BaseModel):
    message: str
    pdf_id: int | None = None  # NEW: ID-based reference
    filename: str | None = None  # Legacy: filename-based reference
    page_num: int
    llm1_history: list[dict[str, str]] | None = []
    llm2_history: list[dict[str, str]] | None = []
    primary_llm_id: int
    secondary_llm_id: int
    is_new_chat: bool | None = False


@router.get("/health")
async def health_check() -> dict[str, object]:
    """
    Check if AI service is working
    """
    try:
        result = await ollama_service.test_connection()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")


@router.post("/analyze")
async def analyze_page(request: AnalyzePageRequest) -> dict[str, object]:
    """
    Analyze a specific page of a PDF using AI.
    Can use either pdf_id (preferred) or filename (legacy).
    """
    try:
        # Resolve filename from pdf_id if provided, otherwise use filename
        if request.pdf_id is not None:
            pdf_doc = pdf_documents_service.get_by_id(request.pdf_id)
            if not pdf_doc:
                raise HTTPException(status_code=404, detail="PDF not found")
            filename = pdf_doc["filename"]
        elif request.filename is not None:
            filename = request.filename
        else:
            raise HTTPException(
                status_code=400, detail="Either pdf_id or filename must be provided"
            )

        # Extract text from the PDF page
        page_text = pdf_service.extract_page_text(filename, request.page_num)

        if not page_text.strip():
            return {
                "filename": filename,
                "page_number": request.page_num,
                "analysis": "This page appears to be empty or contains no extractable text. It might contain only images, diagrams, or formatted elements that couldn't be processed.",
                "text_extracted": False,
            }

        # Get AI analysis
        analysis = await ollama_service.analyze_page(
            text=page_text,
            filename=filename,
            page_num=request.page_num,
            context=request.context,
        )

        return {
            "filename": filename,
            "page_number": request.page_num,
            "analysis": analysis,
            "text_extracted": True,
            "text_length": len(page_text),
        }

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze-epub-section")
async def analyze_epub_section(request: AnalyzeEpubSectionRequest) -> dict[str, object]:
    """
    Analyze a specific section of an EPUB using AI.
    Can use either epub_id (preferred) or filename (legacy).
    """
    try:
        # Resolve filename from epub_id if provided, otherwise use filename
        if request.epub_id is not None:
            epub_doc = epub_documents_service.get_by_id(request.epub_id)
            if not epub_doc:
                raise HTTPException(status_code=404, detail="EPUB not found")
            filename = epub_doc["filename"]
        elif request.filename is not None:
            filename = request.filename
        else:
            raise HTTPException(
                status_code=400, detail="Either epub_id or filename must be provided"
            )

        section_text = epub_service.extract_section_text(filename, request.nav_id)

        if not section_text.strip():
            return {
                "filename": filename,
                "nav_id": request.nav_id,
                "analysis": "This section appears to be empty or contains no extractable text.",
                "text_extracted": False,
            }

        analysis = await ollama_service.analyze_epub_section(
            text=section_text,
            filename=filename,
            nav_id=request.nav_id,
            context=request.context,
        )

        return {
            "filename": filename,
            "nav_id": request.nav_id,
            "analysis": analysis,
            "text_extracted": True,
            "text_length": len(section_text),
        }

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze-epub-section/stream")
async def analyze_epub_section_stream(
    request: AnalyzeEpubSectionRequest,
) -> StreamingResponse:
    """
    Analyze a specific section of an EPUB using AI with a streaming response.
    Can use either epub_id (preferred) or filename (legacy).
    Returns structured data with separated thinking/response content.

    Stream format:
        data: {"type": "metadata", "content": null, "metadata": {"thinking_started": true}}
        data: {"type": "thinking", "content": "chunk", "metadata": {...}, "text_extracted": true}
        data: {"type": "response", "content": "chunk", "metadata": {...}, "text_extracted": true}
        data: {"done": true}
    """
    try:
        # Resolve filename from epub_id if provided, otherwise use filename
        if request.epub_id is not None:
            epub_doc = epub_documents_service.get_by_id(request.epub_id)
            if not epub_doc:
                raise HTTPException(status_code=404, detail="EPUB not found")
            filename = epub_doc["filename"]
        elif request.filename is not None:
            filename = request.filename
        else:
            raise HTTPException(
                status_code=400, detail="Either epub_id or filename must be provided"
            )

        section_text = epub_service.extract_section_text(filename, request.nav_id)

        if not section_text.strip():

            async def generate_empty_response():
                yield f"data: {json.dumps({'type': 'response', 'content': 'This section appears to be empty or contains no extractable text.', 'metadata': {{}}, 'text_extracted': False})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"

            return StreamingResponse(
                generate_empty_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )

        async def generate_analysis():
            try:
                async for structured_data in ollama_service.analyze_epub_section_stream(
                    text=section_text,
                    filename=filename,
                    nav_id=request.nav_id,
                    context=request.context,
                ):
                    # Merge structured data with text_extracted flag
                    output = {**structured_data, "text_extracted": True}
                    yield f"data: {json.dumps(output)}\n\n"

                yield f"data: {json.dumps({'done': True})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate_analysis(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze/stream")
async def analyze_page_stream(request: AnalyzePageRequest) -> StreamingResponse:
    """
    Analyze a specific page of a PDF using AI with streaming response.
    Can use either pdf_id (preferred) or filename (legacy).
    Returns structured data with separated thinking/response content.

    Stream format:
        data: {"type": "metadata", "content": null, "metadata": {"thinking_started": true}}
        data: {"type": "thinking", "content": "chunk", "metadata": {...}, "text_extracted": true}
        data: {"type": "response", "content": "chunk", "metadata": {...}, "text_extracted": true}
        data: {"done": true}
    """
    try:
        # Resolve filename from pdf_id if provided, otherwise use filename
        if request.pdf_id is not None:
            pdf_doc = pdf_documents_service.get_by_id(request.pdf_id)
            if not pdf_doc:
                raise HTTPException(status_code=404, detail="PDF not found")
            filename = pdf_doc["filename"]
        elif request.filename is not None:
            filename = request.filename
        else:
            raise HTTPException(
                status_code=400, detail="Either pdf_id or filename must be provided"
            )

        # Extract text from the PDF page
        page_text = pdf_service.extract_page_text(filename, request.page_num)

        if not page_text.strip():

            async def generate_empty_response():
                yield f"data: {json.dumps({'type': 'response', 'content': 'This page appears to be empty or contains no extractable text. It might contain only images, diagrams, or formatted elements that could not be processed.', 'metadata': {{}}, 'text_extracted': False})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"

            return StreamingResponse(
                generate_empty_response(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/event-stream",
                },
            )

        async def generate_analysis():
            try:
                async for structured_data in ollama_service.analyze_page_stream(
                    text=page_text,
                    filename=filename,
                    page_num=request.page_num,
                    context=request.context,
                ):
                    # Merge structured data with text_extracted flag
                    output = {**structured_data, "text_extracted": True}
                    yield f"data: {json.dumps(output)}\n\n"

                # Send end-of-stream marker
                yield f"data: {json.dumps({'done': True})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate_analysis(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/chat")
async def chat_with_ai(request: ChatRequest) -> StreamingResponse:
    """
    Chat with AI about the PDF content with streaming response.
    Can use either pdf_id (preferred) or filename (legacy).
    Returns structured data with separated thinking/response content.

    Stream format:
        data: {"request_id": "..."}
        data: {"type": "metadata", "content": null, "metadata": {"thinking_started": true}}
        data: {"type": "thinking", "content": "chunk", "metadata": {...}}
        data: {"type": "response", "content": "chunk", "metadata": {...}}
        data: {"done": true}
    """
    try:
        # Resolve filename from pdf_id if provided, otherwise use filename
        if request.pdf_id is not None:
            pdf_doc = pdf_documents_service.get_by_id(request.pdf_id)
            if not pdf_doc:
                raise HTTPException(status_code=404, detail="PDF not found")
            filename = pdf_doc["filename"]
        elif request.filename is not None:
            filename = request.filename
        else:
            raise HTTPException(
                status_code=400, detail="Either pdf_id or filename must be provided"
            )

        # Register the request for tracking
        request_id = request_tracking_service.register_request(
            filename=filename,
            document_type="pdf",
            page_num=request.page_num,
            request_id=request.request_id,
        )
        logger.info(f"[AI Router] Registered chat request {request_id} for {filename}")

        # Extract text from current page for context
        page_text = pdf_service.extract_page_text(filename, request.page_num)

        async def generate_response():
            try:
                # Send the request ID first
                yield f"data: {json.dumps({'request_id': request_id})}\n\n"

                # CHANGED: ollama_service now yields structured StreamChunk dictionaries
                async for structured_data in ollama_service.chat_stream(
                    message=request.message,
                    filename=filename,
                    page_num=request.page_num,
                    pdf_text=page_text,
                    chat_history=request.chat_history,
                    request_id=request_id,
                    is_new_chat=request.is_new_chat,
                ):
                    # Check if request was cancelled
                    if request_tracking_service.is_cancelled(request_id):
                        logger.info(f"[AI Router] Request {request_id} cancelled")
                        yield f"data: {json.dumps({'cancelled': True})}\n\n"
                        break

                    # CHANGED: Send structured data directly
                    # structured_data is a StreamChunk TypedDict:
                    # {
                    #   "type": "thinking" | "response" | "metadata",
                    #   "content": "...",
                    #   "metadata": {...}
                    # }
                    yield f"data: {json.dumps(structured_data)}\n\n"

                # Send end-of-stream marker
                yield f"data: {json.dumps({'done': True})}\n\n"
                logger.info(f"[AI Router] Completed chat request {request_id}")

            except asyncio.CancelledError:
                logger.warning(f"[AI Router] Request {request_id} asyncio cancelled")
                yield f"data: {json.dumps({'cancelled': True})}\n\n"
            except Exception as e:
                logger.error(
                    f"[AI Router] Error in chat stream: {str(e)}", exc_info=True
                )
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                # Clean up the request
                request_tracking_service.complete_request(request_id)

        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[AI Router] Chat endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/chat/epub")
async def chat_with_ai_epub(request: EpubChatRequest) -> StreamingResponse:
    """
    Chat with AI about the EPUB content with streaming response.
    Can use either epub_id (preferred) or filename (legacy).
    Returns structured data with separated thinking/response content.

    Stream format: Same as /chat endpoint (see above)
    """
    try:
        # Resolve filename from epub_id if provided, otherwise use filename
        if request.epub_id is not None:
            epub_doc = epub_documents_service.get_by_id(request.epub_id)
            if not epub_doc:
                raise HTTPException(status_code=404, detail="EPUB not found")
            filename = epub_doc["filename"]
        elif request.filename is not None:
            filename = request.filename
        else:
            raise HTTPException(
                status_code=400, detail="Either epub_id or filename must be provided"
            )

        # Register the request for tracking
        request_id = request_tracking_service.register_request(
            filename=filename,
            document_type="epub",
            nav_id=request.nav_id,
            request_id=request.request_id,
        )
        logger.info(
            f"[AI Router] Registered EPUB chat request {request_id} for {filename}"
        )

        # Extract text from current section for context
        section_text = epub_service.extract_section_text(filename, request.nav_id)

        async def generate_response():
            try:
                # Send the request ID first
                yield f"data: {json.dumps({'request_id': request_id})}\n\n"

                # CHANGED: ollama_service now yields structured StreamChunk dictionaries
                async for structured_data in ollama_service.chat_epub_stream(
                    message=request.message,
                    filename=filename,
                    nav_id=request.nav_id,
                    epub_text=section_text,
                    chat_history=request.chat_history,
                    request_id=request_id,
                    is_new_chat=request.is_new_chat,
                ):
                    # Check if request was cancelled
                    if request_tracking_service.is_cancelled(request_id):
                        logger.info(f"[AI Router] EPUB request {request_id} cancelled")
                        yield f"data: {json.dumps({'cancelled': True})}\n\n"
                        break

                    # CHANGED: Send structured data directly
                    yield f"data: {json.dumps(structured_data)}\n\n"

                # Send end-of-stream marker
                yield f"data: {json.dumps({'done': True})}\n\n"
                logger.info(f"[AI Router] Completed EPUB chat request {request_id}")

            except asyncio.CancelledError:
                logger.warning(
                    f"[AI Router] EPUB request {request_id} asyncio cancelled"
                )
                yield f"data: {json.dumps({'cancelled': True})}\n\n"
            except Exception as e:
                logger.error(
                    f"[AI Router] Error in EPUB chat stream: {str(e)}", exc_info=True
                )
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                # Clean up the request
                request_tracking_service.complete_request(request_id)

        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="EPUB not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[AI Router] EPUB chat endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"EPUB chat failed: {str(e)}")


@router.get("/{filename}/context/{page_num}")
async def get_page_context(
    filename: str, page_num: int, context_pages: int = 1
) -> dict[str, object]:
    """
    Get text context around a specific page (current page ± context_pages)
    This can be useful for providing broader context to AI analysis
    """
    try:
        # Get PDF info to know total pages
        pdf_info = pdf_service.get_pdf_info(filename)
        total_pages = pdf_info["num_pages"]

        # Calculate page range
        start_page = max(1, page_num - context_pages)
        end_page = min(total_pages, page_num + context_pages)

        context_text = {}
        for page in range(start_page, end_page + 1):
            try:
                text = pdf_service.extract_page_text(filename, page)
                context_text[str(page)] = text
            except Exception as e:
                context_text[str(page)] = f"Error extracting page {page}: {str(e)}"

        return {
            "filename": filename,
            "current_page": page_num,
            "context_range": {"start": start_page, "end": end_page},
            "total_pages": total_pages,
            "context_text": context_text,
        }

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting context: {str(e)}")


@router.post("/chat/stop/{request_id}")
async def stop_chat(request_id: str) -> dict[str, str]:
    """
    Stop an active PDF chat streaming request
    """
    try:
        success = request_tracking_service.cancel_request(request_id)
        if success:
            return {"message": f"Request {request_id} cancelled successfully"}
        else:
            raise HTTPException(
                status_code=404, detail="Request not found or already completed"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping chat: {str(e)}")


@router.post("/chat/epub/stop/{request_id}")
async def stop_epub_chat(request_id: str) -> dict[str, str]:
    """
    Stop an active EPUB chat streaming request
    """
    try:
        success = request_tracking_service.cancel_request(request_id)
        if success:
            return {"message": f"Request {request_id} cancelled successfully"}
        else:
            raise HTTPException(
                status_code=404, detail="Request not found or already completed"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error stopping EPUB chat: {str(e)}"
        )


@router.post("/dual-chat")
async def dual_chat(request: DualChatRequest) -> StreamingResponse:
    """
    Chat with two LLMs simultaneously about PDF content with streaming response.
    Can use either pdf_id (preferred) or filename (legacy).
    Both LLMs receive the same prompt but maintain independent conversation histories.
    """
    try:
        # Resolve filename from pdf_id if provided, otherwise use filename
        if request.pdf_id is not None:
            pdf_doc = pdf_documents_service.get_by_id(request.pdf_id)
            if not pdf_doc:
                raise HTTPException(status_code=404, detail="PDF not found")
            filename = pdf_doc["filename"]
        elif request.filename is not None:
            filename = request.filename
        else:
            raise HTTPException(
                status_code=400, detail="Either pdf_id or filename must be provided"
            )

        return StreamingResponse(
            dual_chat_service.stream_dual_chat_response(
                message=request.message,
                filename=filename,
                page_num=request.page_num,
                llm1_history=request.llm1_history or [],
                llm2_history=request.llm2_history or [],
                primary_llm_id=request.primary_llm_id,
                secondary_llm_id=request.secondary_llm_id,
                is_new_chat=request.is_new_chat or False,
            ),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dual chat failed: {str(e)}")


@router.post("/dual-chat/stop/{request_id}")
async def stop_dual_chat(request_id: str) -> dict[str, str]:
    """
    Stop an active dual chat streaming request
    """
    try:
        await dual_chat_service.stop_session(request_id)
        return {"message": f"Dual chat request {request_id} stopped successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error stopping dual chat: {str(e)}"
        )

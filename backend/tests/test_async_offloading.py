"""
Regression tests for C-4: no blocking parse/DB work on the event loop.

Two protections:
1. Endpoints that only do synchronous work (SQLite, file parsing) must be
   plain ``def`` so FastAPI runs them on its threadpool. An allowlist pins
   the endpoints that legitimately stay ``async def`` (they await LLM calls
   or return SSE streams).
2. The ``async def`` endpoints/services that *do* keep blocking work
   (pdfplumber page extraction, full EPUB parse, LLM-config SQLite reads)
   must run it via ``asyncio.to_thread`` — asserted by recording the thread
   the blocking call executes on.
"""

import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.routing import APIRoute

import main
from app.routers import ai
from app.services.dual_chat_service import DualChatService

# Endpoints that legitimately remain async: they await the LLM client or
# orchestrate SSE streams. Everything else must be sync (threadpool-offloaded).
ASYNC_ALLOWLIST = {
    ("POST", "/ai/analyze"),
    ("POST", "/ai/analyze-epub-section"),
    ("POST", "/ai/analyze-epub-section/stream"),
    ("POST", "/ai/analyze/stream"),
    ("POST", "/ai/chat"),
    ("POST", "/ai/chat/epub"),
    ("POST", "/ai/dual-chat"),
    ("POST", "/ai/dual-chat/stop/{request_id}"),
    ("GET", "/ai/health"),
    ("POST", "/llm-config/{config_id}/test"),
}


def _http_routes():
    for route in main.app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                yield (method, route.path), route


class TestEndpointSyncness:
    def test_only_allowlisted_endpoints_are_async(self):
        import inspect

        offenders = [
            key
            for key, route in _http_routes()
            if inspect.iscoroutinefunction(route.endpoint)
            and key not in ASYNC_ALLOWLIST
        ]
        assert offenders == [], (
            f"async def endpoints doing only sync work block the event loop: {offenders}. "
            "Make them plain def (FastAPI offloads those to its threadpool) or, "
            "if they genuinely await, add them to ASYNC_ALLOWLIST."
        )

    def test_allowlisted_endpoints_exist(self):
        registered = {key for key, _ in _http_routes()}
        missing = ASYNC_ALLOWLIST - registered
        assert missing == set(), f"stale allowlist entries: {missing}"


def _fake_pdf_documents(filename="book.pdf"):
    return SimpleNamespace(get_by_id=lambda pdf_id: SimpleNamespace(filename=filename))


def _fake_epub_documents(filename="book.epub"):
    return SimpleNamespace(get_by_id=lambda epub_id: {"filename": filename})


class ThreadRecorder:
    """Records the thread each named call runs on."""

    def __init__(self):
        self.threads: dict[str, int] = {}

    def record(self, name: str):
        self.threads[name] = threading.get_ident()

    def calls_on_loop(self):
        """Names of recorded calls that ran on the event-loop thread (i.e. were not offloaded)."""
        loop_thread = threading.get_ident()
        return {
            name: ident for name, ident in self.threads.items() if ident == loop_thread
        }


@pytest.mark.asyncio
async def test_analyze_page_offloads_resolve_and_pdf_parse():
    recorder = ThreadRecorder()

    def get_by_id(pdf_id):
        recorder.record("resolve")
        return SimpleNamespace(filename="book.pdf")

    def extract_page_text(filename, page_num):
        recorder.record("extract")
        return "page text"

    result = await ai.analyze_page(
        ai.AnalyzePageRequest(pdf_id=1, page_num=2),
        pdf_documents_service=SimpleNamespace(get_by_id=get_by_id),
        pdf_service=SimpleNamespace(extract_page_text=extract_page_text),
        ollama_service=SimpleNamespace(analyze_page=AsyncMock(return_value="analysis")),
    )

    assert result["analysis"] == "analysis"
    assert recorder.calls_on_loop() == {}, (
        f"blocking calls ran on the event loop thread: {recorder.calls_on_loop()}"
    )


@pytest.mark.asyncio
async def test_analyze_epub_section_offloads_epub_parse():
    recorder = ThreadRecorder()

    def get_epub_book(filename):
        recorder.record("read_epub")
        return object()

    def get_chat_context(**kwargs):
        recorder.record("context")
        return SimpleNamespace(current_section_text="section text")

    result = await ai.analyze_epub_section(
        ai.AnalyzeEpubSectionRequest(epub_id=1, nav_id="ch1"),
        epub_documents_service=_fake_epub_documents(),
        epub_service=SimpleNamespace(get_epub_book=get_epub_book),
        epub_chat_context_service=SimpleNamespace(get_chat_context=get_chat_context),
        ollama_service=SimpleNamespace(
            analyze_epub_section=AsyncMock(return_value="analysis")
        ),
    )

    assert result["analysis"] == "analysis"
    assert recorder.calls_on_loop() == {}, (
        f"blocking calls ran on the event loop thread: {recorder.calls_on_loop()}"
    )


@pytest.mark.asyncio
async def test_chat_with_ai_offloads_pdf_parse():
    recorder = ThreadRecorder()

    def extract_page_text(filename, page_num):
        recorder.record("extract")
        return "page text"

    tracking = SimpleNamespace(
        register_request=lambda **kwargs: "req-1",
        is_cancelled=lambda request_id: False,
        complete_request=lambda request_id: None,
    )

    response = await ai.chat_with_ai(
        ai.ChatRequest(message="hi", pdf_id=1, page_num=2),
        pdf_documents_service=_fake_pdf_documents(),
        pdf_service=SimpleNamespace(extract_page_text=extract_page_text),
        ollama_service=SimpleNamespace(),  # stream generator never consumed
        request_tracking_service=tracking,
    )

    assert response.media_type == "text/plain"
    assert recorder.calls_on_loop() == {}, (
        f"blocking calls ran on the event loop thread: {recorder.calls_on_loop()}"
    )


@pytest.mark.asyncio
async def test_chat_with_ai_epub_offloads_epub_parse():
    recorder = ThreadRecorder()

    def get_epub_book(filename):
        recorder.record("read_epub")
        return object()

    def get_chat_context(**kwargs):
        recorder.record("context")
        return SimpleNamespace(current_section_text="section text")

    tracking = SimpleNamespace(
        register_request=lambda **kwargs: "req-1",
        is_cancelled=lambda request_id: False,
        complete_request=lambda request_id: None,
    )

    response = await ai.chat_with_ai_epub(
        ai.EpubChatRequest(message="hi", epub_id=1, nav_id="ch1"),
        epub_documents_service=_fake_epub_documents(),
        epub_service=SimpleNamespace(get_epub_book=get_epub_book),
        epub_chat_context_service=SimpleNamespace(get_chat_context=get_chat_context),
        ollama_service=SimpleNamespace(),
        request_tracking_service=tracking,
    )

    assert response.media_type == "text/plain"
    assert recorder.calls_on_loop() == {}, (
        f"blocking calls ran on the event loop thread: {recorder.calls_on_loop()}"
    )


class TestDualChatServiceOffloading:
    @pytest.fixture
    def service(self, tmp_path):
        recorder = ThreadRecorder()

        def extract_page_text(filename, page_num):
            recorder.record(f"extract:{page_num}")
            return f"text of page {page_num}"

        pdf_service = SimpleNamespace(
            extract_page_text=extract_page_text,
            get_pdf_info=lambda filename: SimpleNamespace(num_pages=10),
        )
        svc = DualChatService(
            db_path=str(tmp_path / "test.db"), pdf_service=pdf_service
        )
        return svc, recorder

    @pytest.mark.asyncio
    async def test_document_context_runs_off_loop(self, service):
        svc, recorder = service
        context = await svc._get_document_context("book.pdf", 5, is_new_chat=True)

        assert "text of page 5" in context
        assert "text of page 4" in context
        assert "text of page 6" in context
        assert recorder.calls_on_loop() == {}, (
            f"pdfplumber parses ran on the event loop thread: {recorder.calls_on_loop()}"
        )

    @pytest.mark.asyncio
    async def test_llm_config_lookup_runs_off_loop(self, service):
        svc, recorder = service

        original = svc._fetch_llm_config

        def recording_fetch(config_id):
            recorder.record("llm_config")
            return original(config_id)

        svc._fetch_llm_config = recording_fetch
        result = await svc._get_llm_config(99999)

        assert result is None  # no such config in a fresh DB
        assert recorder.calls_on_loop() == {}, (
            f"SQLite lookup ran on the event loop thread: {recorder.calls_on_loop()}"
        )
